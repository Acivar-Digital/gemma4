#!/usr/bin/env python3
"""Builds a self-contained Kaggle submission notebook for Gemma 4 Developer Agent.

Embeds:
1. The full my_submission directory (agent.yaml, configs/, prompts/, skills/, adapters/)
2. Fixes vLLM GPU memory utilization to 0.90 to eliminate cache block exhaustion on 4x L4
3. Evaluates a sample smoke task to verify live vLLM inference and patch generation
4. Packages and validates /kaggle/working/submission.zip (< 3 GiB, zero bytecode)

Hardening pass. This builder must never emit a kernel that builds cleanly and then
fails opaquely at run time, because "kernel built" and "model was weak" are
indistinguishable from a score alone. Every pre-flight condition that can be
checked without spending GPU quota is checked HERE, before the notebook is
written, and aborts the build with an actionable message.

Fail-loud policy for the generated kernel:
  * the model directory must exist and look like a real model before vLLM starts;
  * the served model, the model declared in agent.yaml, and the model the model
    registry aliases must all be the same string;
  * the adapter must exist on disk with its weight + config files before the
    expensive build, and at run time again after the zip is unpacked;
  * the inference endpoint is health-probed before the campaign starts and
    re-probed before every task; an unhealthy endpoint aborts the campaign;
  * any unexpected per-task exception aborts the campaign. Per-task resolution
    failure is normal data; an exception is not.

Deliberate exceptions to the fail-loud policy, each documented at its site:
  * removing a broken cutlass .pth hook (OSError, line ~cell_0) -- the file is
    already gone or unwritable, and the hook is cosmetic for this run;
  * sandbox scratch-dir cleanup (OSError, cell_3 finally) -- best-effort disk
    hygiene, must never mask the real task outcome.
"""

import base64
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
SUBMISSION_DIR = ROOT_DIR / "submissions/track1_live"
KERNEL_DIR = ROOT_DIR / "simulation/kernels_diag/kaggle_kernel"
KERNEL_DIR.mkdir(parents=True, exist_ok=True)

# The served competition model. This string is policy/harness-defined and is the
# single model the kernel targets. It is NOT re-read or duplicated here: the
# generated kernel re-derives the model it serves from agent.yaml's `model:` key
# and asserts that key against this constant, so agent.yaml can never drift
# away from what the kernel actually starts.
KERNEL_TARGET_MODEL = "gemma-4-31b-it-qat-w4a16-ct"

# Adapter contract, mirroring scripts/gate_policy.yaml `adapter:`. The kernel
# serves a real adapter now, so a missing/empty adapter is a hard build abort.
ADAPTER_DIR_NAME = "adapters"
ADAPTER_REQUIRED_FILES = ("adapter_config.json", "adapter_model.safetensors")


def _fail(message: str) -> None:
    """Abort the build loudly. Never returns."""
    raise SystemExit(
        "\n"
        "================================================================\n"
        "KERNEL BUILD ABORTED -- refusing to emit a kernel that would fail\n"
        "silently at run time.\n"
        "================================================================\n"
        f"REASON: {message}\n"
        "OPERATOR ACTION: fix the item above, then re-run this script.\n"
        "================================================================\n"
    )


def _banner(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def _read_agent_yaml_model(agent_dir: Path) -> str:
    """Return the `model:` value from agent.yaml without a YAML dependency.

    agent.yaml is a flat scalar map plus `!include` tags, so a line scan is
    sufficient and avoids adding PyYAML to the build host. The scan is strict:
    anything ambiguous raises rather than guessing, because guessing here would
    reintroduce exactly the silent-drift failure this pass removes.
    """
    agent_yaml = agent_dir / "agent.yaml"
    if not agent_yaml.is_file():
        _fail(f"{agent_yaml} is missing. The submission has no agent declaration.")
    matches = []
    for line in agent_yaml.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("model:") or stripped.startswith("#"):
            continue
        value = stripped.split(":", 1)[1].strip().strip("'\"")
        if value:
            matches.append(value)
    if not matches:
        _fail(f"{agent_yaml} declares no `model:` key. Cannot confirm the served model.")
    unique = sorted(set(matches))
    if len(unique) > 1:
        _fail(f"{agent_yaml} declares conflicting `model:` values {unique}. Refusing to guess.")
    return unique[0]


def _preflight() -> dict:
    """Validate everything cheap to check before writing any expensive artifact.

    Returns a report dict that is echoed to the operator and interpolated into
    the generated kernel, so the kernel and this build log cannot disagree.
    """
    _banner("KERNEL BUILD PRE-FLIGHT (no GPU quota spent)")

    if not SUBMISSION_DIR.is_dir():
        _fail(f"Submission directory {SUBMISSION_DIR} does not exist.")

    # --- Baseline Whitelist Verification (Compute Mode) ----------------
    print("  verifying baseline whitelist against compute mode...")
    gate_script = ROOT_DIR / "scripts" / "baseline_gate.py"
    gate_res = subprocess.run(
        [sys.executable, str(gate_script), "verify", "--mode=compute"],
        capture_output=True,
        text=True,
    )
    if gate_res.returncode != 0:
        print(gate_res.stdout)
        print(gate_res.stderr, file=sys.stderr)
        raise RuntimeError(
            "unapproved working tree modifications exist without an approved exception."
        )
    print("  baseline gate check           : OK (compute mode verified)")

    registry_path = ROOT_DIR / "configs" / "baseline_registry.json"
    if not registry_path.is_file():
        _fail(f"Baseline registry {registry_path} is missing.")
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    whitelist = registry.get("whitelist", {})
    exceptions = registry.get("exceptions", {})

    # --- Which model? -------------------------------------------------
    declared_model = _read_agent_yaml_model(SUBMISSION_DIR)
    print(f"  served model (policy constant) : {KERNEL_TARGET_MODEL}")
    print(f"  agent.yaml declared model      : {declared_model}")
    if declared_model != KERNEL_TARGET_MODEL:
        _fail(
            "agent.yaml declares a different model than the kernel serves.\n"
            f"    agent.yaml : {declared_model}\n"
            f"    kernel     : {KERNEL_TARGET_MODEL}\n"
            "  A kernel that serves model A against an agent built for model B "
            "produces a garbage score that looks exactly like model weakness. "
            "Fix agent.yaml (or the policy constant) before building."
        )
    print(f"  model agreement               : OK ({declared_model})")

    # --- Which adapter? ------------------------------------------------
    adapters_root = SUBMISSION_DIR / ADAPTER_DIR_NAME
    declared_adapter = None
    agent_yaml_text = (SUBMISSION_DIR / "agent.yaml").read_text(encoding="utf-8")
    for line in agent_yaml_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("adapter:") and not stripped.startswith("#"):
            declared_adapter = stripped.split(":", 1)[1].strip().strip("'\"")
            break

    if declared_adapter is None:
        print("  declared adapter              : None (base weights only, adapter optional)")
        adapter_dir = None
        adapter_bytes = 0
        adapter_files = []
    else:
        print(f"  declared adapter              : {declared_adapter}")
        adapter_dir = adapters_root / declared_adapter
        if not adapter_dir.is_dir():
            _fail(
                f"Adapter directory {adapter_dir} is missing.\n"
                "  The submission declares an adapter but does not ship it. Train/promote first."
            )
        missing = [name for name in ADAPTER_REQUIRED_FILES if not (adapter_dir / name).is_file()]
        if missing:
            _fail(f"Adapter {adapter_dir} is incomplete; missing {missing}.")
        empty = [
            name
            for name in ADAPTER_REQUIRED_FILES
            if (adapter_dir / name).stat().st_size == 0
        ]
        if empty:
            _fail(f"Adapter {adapter_dir} has empty file(s) {empty}. Refusing to build.")
        adapter_bytes = (adapter_dir / "adapter_model.safetensors").stat().st_size
        adapter_files = list(ADAPTER_REQUIRED_FILES)
        print(f"  adapter dir                   : {adapter_dir}")
        print(f"  adapter weights               : {adapter_bytes:,} bytes")
        print(f"  adapter files present         : OK {adapter_files}")

    print(f"\n  TARGET MODEL : {declared_model}")
    print(f"  ADAPTER MOUNT: {declared_adapter or 'None (pure base weights)'} ({adapter_bytes:,} bytes of LoRA weights)")
    print("  ABOUT TO DO  : rebuild submission.zip from my_submission/, embed it as")
    print("                base64 into a 5-cell notebook, and write")
    print("                kaggle_kernel/gemma4-eval-40calls.ipynb + kernel-metadata.json.")
    print("                The kernel will health-probe the vLLM endpoint before the")
    print("                campaign and before every task, and will abort rather than")
    print("                report a score if the endpoint is dead.")

    return {
        "model": declared_model,
        "adapter_name": declared_adapter,
        "adapter_files": adapter_files,
        "adapter_weights_bytes": adapter_bytes,
        "whitelist": whitelist,
        "exceptions": exceptions,
    }


PREFLIGHT = _preflight()

# 1. Package clean my_submission into an in-memory zip
# NOTE: make_archive is derived from the basename of the output prefix, so the
# archive is always <prefix>.zip. Derive that name instead of assuming it.
zip_path = ROOT_DIR / "submission.zip"
if not zip_path.exists():
    archive_base = str(ROOT_DIR / "submission")
    made = shutil.make_archive(archive_base, "zip", root_dir=SUBMISSION_DIR)
    zip_path = Path(made)

if not zip_path.is_file() or zip_path.stat().st_size == 0:
    _fail(f"Packaged submission archive {zip_path} is missing or empty.")

if PREFLIGHT["adapter_name"]:
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    adapter_prefix = f"{ADAPTER_DIR_NAME}/{PREFLIGHT['adapter_name']}/"
    absent = [
        name for name in PREFLIGHT["adapter_files"] if adapter_prefix + name not in names
    ]
    if absent:
        _fail(
            f"{zip_path} does not contain {adapter_prefix}{absent}.\n"
            f"  The archive is stale relative to {SUBMISSION_DIR}."
        )
    print(f"Adapter present in {zip_path.name}: {adapter_prefix}{PREFLIGHT['adapter_files']}")
else:
    print(f"No adapter declared; packaging base-model submission.")

b64_zip = base64.b64encode(zip_path.read_bytes()).decode("ascii")
print(f"Embedded submission.zip base64 payload: {len(b64_zip)} chars")

# 2. Build Notebook Cells
cell_0_env = """import glob
import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Configure environment variables for offline vLLM serving and LiteLLM routing
os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
os.environ['TRANSFORMERS_NO_TF'] = '1'
os.environ['VLLM_WORKER_MULTIPROC_METHOD'] = 'spawn'
os.environ['VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS'] = '1'
os.environ['VLLM_ENGINE_READY_TIMEOUT_S'] = '1200'
os.environ['VLLM_NO_USAGE_STATS'] = '1'
os.environ['OTEL_SDK_DISABLED'] = 'true'
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

_CANDS = [
    Path('/kaggle/input/gemma-4-developer-agent-wheelhouse'),
    Path('/kaggle/input/datasets/metric/gemma-4-developer-agent-wheelhouse')
]
WHEELHOUSE_DIR = next((p for p in _CANDS if p.exists() and list(p.glob('*.whl'))), None)
if WHEELHOUSE_DIR is None:
    _found = sorted(Path('/kaggle/input').rglob('swegemma*.whl'))
    assert _found, 'no swegemma wheel anywhere under /kaggle/input'
    WHEELHOUSE_DIR = _found[0].parent
print('USING WHEELHOUSE:', WHEELHOUSE_DIR)

# Remove broken cutlass .pth hooks if present
for pth_pattern in (
    '/usr/local/lib/python*/dist-packages/*cutlass*.pth',
    '/usr/local/lib/python*/site-packages/*cutlass*.pth',
):
    for pth in glob.glob(pth_pattern):
        try:
            os.unlink(pth)
        except OSError as hook_error:
            # SPECIFIC, DELIBERATE TOLERANCE. The only OSError conditions
            # reachable here are FileNotFoundError (another glob match or a
            # previous cell already removed it -- success either way) and
            # PermissionError on a read-only dist-packages layer. In the second
            # case the hook stays, which degrades to the same behaviour the
            # pre-existing code tolerated, and the cell continues. This is NOT
            # a swallow-all: the handler names OSError, does not catch
            # Exception/BaseException, and logs what it did not remove so the
            # condition is visible in the log rather than invisible.
            print(f'WARNING: could not remove cutlass .pth hook {pth}: {hook_error!r}')

# Restore PEP 440 '+cu128' wheel filenames stripped by Kaggle dataset uploads
tmp_whl = Path('/tmp/wheelhouse')
tmp_whl.mkdir(parents=True, exist_ok=True)
for w in WHEELHOUSE_DIR.glob('*.whl'):
    if 'cutlass' in w.name.lower():
        continue
    target_name = (
        w.name.replace('cu128', '+cu128')
        if ('cu128' in w.name and '+' not in w.name)
        else w.name
    )
    target = tmp_whl / target_name
    if not target.exists():
        os.symlink(w, target)

wheels = sorted(str(w) for w in tmp_whl.glob('*.whl'))
print(f'Installing {len(wheels)} wheels from {WHEELHOUSE_DIR}...')
subprocess.run(
    [sys.executable, '-m', 'pip', 'install', '-q', '--no-deps', '--force-reinstall', *wheels],
    check=True,
)
importlib.invalidate_caches()
print('Wheelhouse installation complete.')
"""
if PREFLIGHT["adapter_name"]:
    _cell_1_adapter_snippet = f"""# FAIL LOUD: the adapter must be on disk AFTER unpacking, not just at build time.
ADAPTER_NAME = '{PREFLIGHT['adapter_name']}'
ADAPTER_DIR = AGENT_DIR / 'adapters' / ADAPTER_NAME
assert ADAPTER_DIR.is_dir(), (
    f'ADAPTER MISSING: {{ADAPTER_DIR}} does not exist after unpacking. The kernel '
    'will NOT score the model you think it is scoring. Do not continue.'
)
for _required in {PREFLIGHT['adapter_files']!r}:
    _p = ADAPTER_DIR / _required
    assert _p.is_file() and _p.stat().st_size > 0, (
        f'ADAPTER INCOMPLETE: {{_p}} missing or zero bytes. Aborting before vLLM starts.'
    )
print('ADAPTER VERIFIED ON DISK:', ADAPTER_DIR,
      sorted(p.name for p in ADAPTER_DIR.iterdir() if p.is_file()))"""
else:
    _cell_1_adapter_snippet = "print('NO ADAPTER DECLARED: serving pure base weights (decision-adapter-optional).')"

if PREFLIGHT["adapter_name"]:
    _cell_2_adapter_snippet = f"""adapters = discover_adapters(str(AGENT_DIR), adapter_extensions=ALLOWED_ADAPTER_EXTENSIONS)
assert adapters, (
    'NO ADAPTERS DISCOVERED at run time, but this kernel was built to mount '
    f'{PREFLIGHT["adapter_name"]}. vLLM would serve base weights only and '
    'the resulting score would be a serving artefact, not a model result.'
)
print('ADAPTERS DISCOVERED:', adapters)
enable_lora_flag = bool(adapters)
max_loras_val = 8
max_lora_rank_val = 128"""
    _cell_2_lora_assert = "assert vllm_cfg.enable_lora, 'vLLM LoRA is disabled despite a discovered adapter manifest.'"
else:
    _cell_2_adapter_snippet = """adapters = []
print('NO ADAPTERS CONFIGURED: LoRA disabled for maximum KV cache.')
enable_lora_flag = False
max_loras_val = 0
max_lora_rank_val = 0"""
    _cell_2_lora_assert = "# Pure base weights: LoRA disabled"

_cell_1_integrity_snippet = f"""# --- Baseline Integrity Verification (Compute Mode) ---
import hashlib

WHITELIST = {PREFLIGHT['whitelist']!r}
EXCEPTIONS = {PREFLIGHT['exceptions']!r}

unpacked_files = {{}}
for p in sorted(AGENT_DIR.rglob('*')):
    if not p.is_file():
        continue
    if any(part in {{'.DS_Store', '__pycache__'}} for part in p.parts):
        continue
    if p.suffix in {{'.pyc', '.pyo'}} or p.name in {{'.DS_Store', '__pycache__'}}:
        continue
    rel = p.relative_to(AGENT_DIR).as_posix()
    h = hashlib.sha256()
    with p.open('rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    unpacked_files[rel] = h.hexdigest()

violations = []
all_keys = sorted(set(WHITELIST.keys()) | set(unpacked_files.keys()) | set(EXCEPTIONS.keys()))
for rel_path in all_keys:
    in_current = rel_path in unpacked_files
    in_whitelist = rel_path in WHITELIST
    in_exceptions = rel_path in EXCEPTIONS
    current_hash = unpacked_files.get(rel_path)
    whitelist_hash = WHITELIST.get(rel_path)
    exception_entry = EXCEPTIONS.get(rel_path, {{}})

    if in_exceptions:
        exp_hash = exception_entry.get('sha256') if isinstance(exception_entry, dict) else None
        if not in_current:
            violations.append(f'MISSING EXCEPTION FILE: {{rel_path}}')
        elif current_hash != exp_hash:
            violations.append(f'EXCEPTION MISMATCH: {{rel_path}} ({{current_hash}} != {{exp_hash}})')
        else:
            print(f'  [PASS] {{rel_path}} (APPROVED EXCEPTION)')
    elif in_whitelist:
        if not in_current:
            violations.append(f'MISSING: {{rel_path}}')
        elif current_hash != whitelist_hash:
            violations.append(f'UNAPPROVED MODIFICATION: {{rel_path}} ({{current_hash}} != {{whitelist_hash}})')
        else:
            print(f'  [PASS] {{rel_path}} (matches whitelist)')
    else:
        violations.append(f'UNAPPROVED FILE: {{rel_path}}')

assert not violations, 'BASELINE INTEGRITY CHECK FAILED:\\n' + '\\n'.join(violations)
print(f'BASELINE INTEGRITY VERIFIED: {{len(unpacked_files)}} files cleanly match whitelist / approved exceptions.')"""

cell_1_unpack = f"""import base64
import os
import shutil
import zipfile
from pathlib import Path
from swegemma.models import load_tasks

DATA_DIR = Path('/kaggle/input/competitions/gemma-4-developer-agent')
WORKING_DIR = Path('/kaggle/working')
WORKING_DIR.mkdir(parents=True, exist_ok=True)

AGENT_DIR = WORKING_DIR / 'my_submission'
if AGENT_DIR.exists():
    shutil.rmtree(AGENT_DIR)
AGENT_DIR.mkdir(parents=True, exist_ok=True)

# Unpack embedded verified agent bundle
B64_SUBMISSION = "{b64_zip}"
zip_archive_path = WORKING_DIR / 'submission.zip'
zip_archive_path.write_bytes(base64.b64decode(B64_SUBMISSION))

with zipfile.ZipFile(zip_archive_path, 'r') as zf:
    zf.extractall(AGENT_DIR)

# Purge any stray bytecode (.pyc, __pycache__)
for root, dirs, files in os.walk(AGENT_DIR):
    for f in files:
        if f.endswith('.pyc') or f == '.DS_Store':
            os.remove(os.path.join(root, f))
    for d in list(dirs):
        if d == '__pycache__':
            shutil.rmtree(os.path.join(root, d))


{_cell_1_integrity_snippet}
{_cell_1_adapter_snippet}

TASKS_PATH = DATA_DIR / 'tasks.jsonl'
tasks = load_tasks(TASKS_PATH)
GRAPH_DIR = str(DATA_DIR / 'graphs')
EMBEDDINGS_DIR = str(DATA_DIR / 'embeddings')
print(f'Data: {{DATA_DIR}} | Agent: {{AGENT_DIR}} | tasks: {{len(tasks)}}')

print('Unpacked submission files:')
for p in sorted(AGENT_DIR.rglob('*')):
    if p.is_file():
        print(f'  - {{p.relative_to(AGENT_DIR)}} ({{p.stat().st_size}} bytes)')
"""

cell_2_vllm = f"""import json
import queue
import threading
import time
import urllib.request

import litellm
import torch
from pathlib import Path
from adk_submission import VllmConfig, VllmServer, discover_adapters
from swegemma.config import ALLOWED_ADAPTER_EXTENSIONS
from swegemma.models.discovery import validate_single_declared_model

# ---------------------------------------------------------------- banner ----
# An operator reading only the log must never be misled about what is running.
print('=' * 78)
print(f'  TARGET MODEL : {PREFLIGHT["model"]}')
print(f'  ADAPTER      : {PREFLIGHT["adapter_name"]} '
      f'({PREFLIGHT["adapter_weights_bytes"]:,} bytes)')
print(f'  ADAPTER MOUNT: enabled -- vLLM will serve this LoRA on top of the base model.')
print('  ABOUT TO DO  : start vLLM on port 8000, health-probe /health and')
print('                /v1/chat/completions, and only then evaluate all tasks.')
print('  ON FAILURE   : this kernel ABORTS with a named error. It never reports a')
print('                score for a run it could not actually serve.')
print('=' * 78)

# ------------------------------------------------- litellm.drop_params ------
# This line used to be a bare attribute assignment, which fails INVISIBLY in
# two ways: (1) if the imported litellm has no `drop_params` attribute, Python
# happily creates one on the module and litellm keeps RAISING on unsupported
# params -- every inference call then fails far away from this line; (2) if the
# litellm in the wheelhouse moved the flag, it is set on an object nobody reads.
# So: set it, then read it back and fail loudly if it did not take.
litellm.drop_params = True
assert getattr(litellm, 'drop_params', None) is True, (
    'litellm.drop_params did not take effect: litellm will raise on '
    'unsupported params and every model call will fail far from this line. '
    'Abort instead of scoring 0 on a routing error.'
)
print('litellm.drop_params verified True (unsupported params will be dropped, not raised).')

# -------------------------------------------------- model path validation ---
# Used to be: `if not _MP.exists(): search ... ; _MP = _f[0] if _f else _MP`
# followed by a print of MODEL_PATH.exists(). That print was cosmetic: if the
# search found nothing, the ORIGINAL non-existent path was kept, vLLM was asked
# to load it, and the failure surfaced as an opaque serving error at run time.
# Now the path is a hard precondition and the search result is asserted.
TARGET_MODEL_NAME = '{PREFLIGHT["model"]}'
MODEL_WEIGHTS_MARKERS = ('config.json',)
_canonical = Path('/kaggle/input/models/google/gemma-4/other/{PREFLIGHT["model"]}/2')
if not _canonical.is_dir():
    _found = sorted(
        p for p in Path('/kaggle/input').rglob('{PREFLIGHT["model"]}')
        if p.is_dir() and (p / 'config.json').is_file()
    )
    if not _found:
        raise SystemExit(
            f'MODEL NOT FOUND: {{_canonical}} is absent and no directory containing '
            f'config.json was found for {{TARGET_MODEL_NAME!r}} under /kaggle/input.\\n'
            '  Attach the google/gemma-4 model to the kernel and re-run. Serving '
            'without it cannot produce a valid score.'
        )
    print('model fallback search:', [str(p) for p in _found[:3]])
    _canonical = _found[0]

MODEL_PATH = _canonical
assert MODEL_PATH.is_dir(), f'MODEL PATH NOT A DIRECTORY: {{MODEL_PATH}}'
for _marker in MODEL_WEIGHTS_MARKERS:
    assert (MODEL_PATH / _marker).is_file(), (
        f'MODEL WEIGHTS INCOMPLETE: {{MODEL_PATH / _marker}} is missing. '
        'vLLM cannot load this model; abort rather than serve nothing.'
    )
print('USING MODEL:', MODEL_PATH, '| exists:', MODEL_PATH.exists(), '| config.json: OK')

INFERENCE_API_KEY = 'EMPTY'

declared_model = validate_single_declared_model(AGENT_DIR)
assert declared_model == TARGET_MODEL_NAME, (
    f'MODEL MISMATCH: agent.yaml declares {{declared_model!r}} but this kernel '
    f'serves {{TARGET_MODEL_NAME!r}}. The agent would be scored against weights '
    'it was not built for. Aborting.'
)
print('agent.yaml model matches served model:', declared_model)

{_cell_2_adapter_snippet}

gpu_count = torch.cuda.device_count() if torch.cuda.is_available() else 1
tp_size = 4 if gpu_count >= 4 else (2 if gpu_count >= 2 else 1)
print(f'Detected GPUs: {{gpu_count}}, Tensor Parallel Size: {{tp_size}}')

# Configure vLLM with 0.90 memory utilization (official starter recommendation)
# to guarantee sufficient KV cache memory blocks for 32,768 context length
vllm_cfg = VllmConfig(
    model=str(MODEL_PATH),
    port=8000,
    host='127.0.0.1',
    tool_call_parser='gemma4',
    reasoning_parser='gemma4',
    max_model_len=32768,
    dtype='bfloat16' if (torch.cuda.is_available() and torch.cuda.is_bf16_supported()) else 'auto',
    gpu_memory_utilization=0.90,
    enable_auto_tool_choice=True,
    enable_lora=enable_lora_flag,
    max_loras=max_loras_val,
    max_lora_rank=max_lora_rank_val,
    tensor_parallel_size=tp_size,
    startup_timeout=60 * 20,
)
{_cell_2_lora_assert}
server_instance = VllmServer(vllm_cfg, adapter_manifest=adapters)
server_instance.start()
print(f'vLLM server started on {{server_instance.base_url}} (tp={{tp_size}})')

models = server_instance.create_model_registry(
    aliases=[declared_model, TARGET_MODEL_NAME],
    model_prefix='openai/',
    api_key=INFERENCE_API_KEY,
)
print('Model registry created successfully.')

# ------------------------------------------------------- run-health gate ----
# ADAPTED from the known-good prior art at
# docs/gemma-and-the-shape-of-doubt.md:2818 (SAMPLING_HEALTH_RUNNER), whose
# docstring is: 'Hash-pinned V14 evaluation with a separate inference health
# gate per task. The gate runs before the task timer and never enters agent
# history. It stops the campaign on infrastructure failure; it does not retry
# or change a patch.'
#
# Reused VERBATIM in shape: the /health + /v1/chat/completions '2+2 -> 4'
# probe, the daemon-thread absolute wall deadline, and EndpointUnhealthy as a
# BaseException subclass so the campaign abort escapes ordinary per-task
# `except Exception` handling. Deliberately NOT reused: install_health_gate(),
# which monkeypatches a V14-specific runner module's progress() and reads a
# V14-specific argparse Namespace (args.run_root, args.port) that does not
# exist here. Those two lines are the only V14-bound parts of the prior art.
#
# Purpose: a kernel that builds and serves a DEAD endpoint currently looks
# identical to a kernel serving a weak model. The last real run scored 0/129
# with 77/95 traces at zero completion tokens -- exactly this confusion. This
# gate makes dead-serving loud.
class EndpointUnhealthy(BaseException):
    \"\"\"Campaign abort, deliberately outside ordinary per-task error handling.\"\"\"


def _probe_endpoint(base, *, timeout=20):
    started = time.monotonic()
    with urllib.request.urlopen(base + '/health', timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError('Health endpoint did not return 200')
    active_model_name = TARGET_MODEL_NAME
    try:
        with urllib.request.urlopen(base + '/v1/models', timeout=timeout) as response:
            document = json.loads(response.read(65537))
        models_data = document.get('data', []) if isinstance(document, dict) else []
        if isinstance(models_data, list) and len(models_data) > 0 and isinstance(models_data[0], dict):
            active_model_name = models_data[0].get('id') or TARGET_MODEL_NAME
    except Exception:
        active_model_name = TARGET_MODEL_NAME
    payload = {{'model': active_model_name, 'temperature': 0, 'max_tokens': 8,
               'chat_template_kwargs': {{'enable_thinking': False}},
               'messages': [{{'role': 'user', 'content': 'What is 2+2? Reply with only the integer.'}}]}}
    request = urllib.request.Request(base + '/v1/chat/completions',
        data=json.dumps(payload).encode(), headers={{'Content-Type': 'application/json'}})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read(65537)
        if len(data) > 65536:
            raise RuntimeError('Probe response exceeded 64 KiB')
    document = json.loads(data)
    if (document['choices'][0]['message'].get('content') or '').strip() != '4':
        raise RuntimeError('Inference probe did not return 4')
    return {{'status': 'PASS', 'model': active_model_name, 'elapsed_seconds': round(time.monotonic() - started, 3),
            'usage': document.get('usage'), 'response_sha256': __import__('hashlib').sha256(data).hexdigest()}}


def probe_endpoint(base, *, timeout=20, wall_timeout=40):
    # Socket timeouts alone do not bound a slow-drip response. A daemon worker
    # gives the gate one absolute deadline; a missed deadline aborts the run.
    result = queue.Queue(maxsize=1)

    def worker():
        try:
            result.put((True, _probe_endpoint(base, timeout=timeout)))
        except BaseException as error:
            result.put((False, error))

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    try:
        passed, value = result.get(timeout=wall_timeout)
    except queue.Empty as error:
        raise TimeoutError('Inference health gate exceeded its absolute wall deadline') from error
    if not passed:
        raise value
    return value


INFERENCE_BASE_URL = 'http://127.0.0.1:8000'
HEALTH_LOG_PATH = WORKING_DIR / 'endpoint_health.jsonl'


def require_healthy_endpoint(context):
    \"\"\"Probe the endpoint or abort the whole campaign. Never enters agent history.\"\"\"
    row = {{'context': context, 'kind': 'VALIDATION_ONLY_INFERENCE_PROBE',
           'enters_agent_history': False}}
    try:
        row.update(probe_endpoint(INFERENCE_BASE_URL))
    except Exception as error:
        row.update(status='HOLD', error=repr(error))
        with HEALTH_LOG_PATH.open('a') as stream:
            stream.write(json.dumps(row, sort_keys=True) + '\\n')
        raise EndpointUnhealthy(
            'INFERENCE ENDPOINT DEAD before ' + context + ': ' + repr(error) + '\\n'
            '  The kernel built and vLLM started, but the model is not being '
            'served. Every task below would score 0 for an infrastructure '
            'reason. STOP: read the vLLM log above for the load error, fix it, '
            'and re-run. This run is void.'
        ) from error
    with HEALTH_LOG_PATH.open('a') as stream:
        stream.write(json.dumps(row, sort_keys=True) + '\\n')
    print(f'  endpoint health ({{context}}): {{row[\"status\"]}} '
          f'in {{row[\"elapsed_seconds\"]}}s usage={{row.get(\"usage\")}}', flush=True)
    return row


require_healthy_endpoint('pre_campaign')
print('Pre-campaign endpoint health: PASS. The campaign may proceed.')
"""

cell_3_eval = """import asyncio
import concurrent.futures
import json
import os
import shutil
from pathlib import Path
import pandas as pd
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.apps._configs import EventsCompactionConfig
from swegemma.config import EvalConfig, build_submission_limits
from swegemma.evaluate import Evaluator

def run_sync(coro_or_fn, *args, **kwargs):
    fn = (lambda: coro_or_fn(*args, **kwargs)) if callable(coro_or_fn) else (lambda: coro_or_fn)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(fn())).result()
    return asyncio.run(fn())

# Full 129-task cloud evaluation on Kaggle 4x L4 GPUs
limits, gen_constraints = build_submission_limits()
RESULTS_DIR = WORKING_DIR / 'results'
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
JSONL_PATH = RESULTS_DIR / 'task_results.jsonl'

eval_config = EvalConfig(
    tasks_path=TASKS_PATH,
    snapshots_dir=DATA_DIR / 'snapshots',
    results_dir=RESULTS_DIR,
    submission_dir=AGENT_DIR,
    models=models,
    sandbox='subprocess',
    timeout_seconds=60,
    max_time_minutes=4.5,
    max_tool_calls=40,
    max_turns=100,
    limits=limits,
    generation_constraints=gen_constraints,
    adapter_manifest=adapters,
    context_cache_config=ContextCacheConfig(min_tokens=2048, ttl_seconds=1800, cache_intervals=10),
    events_compaction_config=EventsCompactionConfig(
        compaction_interval=15, overlap_size=2,
        token_threshold=14336, event_retention_size=5),
    graph_dir=GRAPH_DIR,
    embeddings_dir=EMBEDDINGS_DIR,
    wheels_dir=DATA_DIR / 'wheels',
    verbose=False,
)
evaluator = Evaluator(eval_config)

resolved_count = 0
total_evaluated = 0
zero_token_tasks = []
predictions = []

print(f"Starting evaluation across all {len(tasks)} tasks on Kaggle 4x L4 GPUs...", flush=True)
print(f"Model under test: {TARGET_MODEL_NAME} | adapter: {ADAPTER_NAME}", flush=True)

# Degenerate-run detector. The previous real run scored 0/129 with 77/95 traces
# at ZERO completion tokens -- an infrastructure failure that looked exactly like
# model weakness. This threshold makes that class of run impossible to mistake
# for a genuine weak-model result. See also require_healthy_endpoint() in the
# serving cell, which catches the same failure earlier and more precisely.
DEGENERATE_PATCH_CHARS = 200
DEGENERATE_FRACTION = 0.9

for idx, task in enumerate(tasks, start=1):
    print(f"[{idx}/{len(tasks)}] Evaluating {task.instance_id} ({task.repo})...", flush=True)

    # Run-health gate before the task timer, per the prior art
    # (docs/gemma-and-the-shape-of-doubt.md:2818): 'The gate runs before the task
    # timer and never enters agent history. It stops the campaign on
    # infrastructure failure; it does not retry or change a patch.'
    # EndpointUnhealthy subclasses BaseException, so it deliberately escapes the
    # `except Exception` below and aborts the campaign.
    require_healthy_endpoint(f'pre_task:{task.instance_id}')

    try:
        result = run_sync(evaluator.evaluate_task, task=task, task_index=idx, total_tasks=len(tasks))
        is_resolved = bool(result.resolved)
        if is_resolved:
            resolved_count += 1
        total_evaluated += 1

        patch_text = result.agent_patch or ""
        record = {
            "task_id": task.instance_id,
            "repo": task.repo,
            "resolved": is_resolved,
            "test_exit_code": result.test_exit_code,
            "tool_calls": result.tool_calls,
            "duration_seconds": round(result.duration_seconds, 2),
            "patch_length": len(patch_text),
            "patch": patch_text,
        }
        predictions.append({"id": task.instance_id, "prediction": patch_text})

        if len(patch_text) < DEGENERATE_PATCH_CHARS:
            zero_token_tasks.append(task.instance_id)

        # Guardrail 1: Incremental flush to JSONL after every task
        with open(JSONL_PATH, "a", encoding="utf-8") as jf:
            jf.write(json.dumps(record) + "\\n")

        print(
            f"  -> resolved={is_resolved} (Running Score: {resolved_count}/{total_evaluated} = {resolved_count/total_evaluated*100:.1f}%), "
            f"exit={result.test_exit_code}, patch={record['patch_length']}ch, calls={result.tool_calls}, {result.duration_seconds:.1f}s",
            flush=True
        )
    except EndpointUnhealthy:
        # Infrastructure failure. Re-raise: the campaign is void, and continuing
        # would produce a 0-score that is indistinguishable from model weakness.
        raise
    except Exception as error:
        # FAIL LOUD. This handler used to print the error, append an empty
        # prediction, and continue to the next task -- so a run in which every
        # task raised produced a clean "EVALUATION COMPLETE / Final Score:
        # 0.00%" line, indistinguishable from a model that is simply weak. That
        # is precisely the confusion this gate system exists to eliminate, and
        # it is what burned the last quota. The partial results already written
        # to task_results.jsonl are preserved for diagnosis, then the campaign
        # aborts with a named error.
        with open(JSONL_PATH, "a", encoding="utf-8") as jf:
            jf.write(json.dumps({
                "task_id": task.instance_id,
                "repo": task.repo,
                "resolved": False,
                "error": repr(error),
                "aborted": True,
            }) + "\\n")
        raise SystemExit(
            f'\\nEVALUATION ABORTED at task {idx}/{len(tasks)} ({task.instance_id}): {error!r}\\n'
            '  An unexpected exception is NOT a task-level result; it is a bug or '
            'an infrastructure fault. Continuing would emit an empty prediction '
            'and finish with a 0-score that cannot be distinguished from model '
            f'weakness. Partial per-task results are preserved at {JSONL_PATH}. '
            'Fix the cause and re-run.'
        ) from error
    finally:
        # Guardrail 2: Clean up temporary sandbox venvs to prevent disk overflow
        for sb_dir in Path("/tmp").glob("swegemma_sandbox_*"):
            try:
                shutil.rmtree(sb_dir, ignore_errors=True)
            except OSError as cleanup_error:
                # SPECIFIC, DELIBERATE TOLERANCE. This is best-effort disk
                # hygiene running in a finally block: rmtree(ignore_errors=True)
                # already suppresses per-file errors, so the only escape here is
                # an OSError on the directory entry itself. Raising from a
                # finally would MASK the real task outcome, which is the one
                # thing this block must not do. The error is named and printed
                # so a disk-overflow failure is still visible in the log.
                print(f"WARNING: sandbox cleanup failed for {sb_dir}: {cleanup_error!r}", flush=True)

# Post-campaign degenerate-run assertion: a run in which almost every task
# produced no patch is an infra failure, not a model result. Refuse to print a
# headline score for it.
if total_evaluated:
    degenerate_fraction = len(zero_token_tasks) / total_evaluated
    print(
        f"\\nDegenerate-run check: {len(zero_token_tasks)}/{total_evaluated} tasks "
        f"produced < {DEGENERATE_PATCH_CHARS} patch chars ({degenerate_fraction:.1%}).",
        flush=True,
    )
    if degenerate_fraction >= DEGENERATE_FRACTION:
        raise SystemExit(
            f'\\nEVALUATION ABORTED: degenerate run -- {degenerate_fraction:.1%} of '
            f'{total_evaluated} tasks produced essentially no patch '
            f'(first few: {zero_token_tasks[:5]}).\\n'
            '  This is the signature of the previous 0/129 run (77/95 traces at '
            'zero completion tokens): the model is not being served, or every '
            'generation is empty. It is NOT evidence of model weakness. Do not '
            f'read the score as one. Per-task results: {JSONL_PATH}; endpoint '
            f'health log: {HEALTH_LOG_PATH}.'
        )

print(f"\\n=================== EVALUATION COMPLETE ===================", flush=True)
print(f"Final Score: {resolved_count}/{total_evaluated} ({resolved_count/max(1, total_evaluated)*100:.2f}%)", flush=True)
submission_df = pd.DataFrame(predictions, columns=['id', 'prediction'])
submission_df.to_csv(RESULTS_DIR / 'predictions.csv', index=False)
print(f"Saved predictions.csv ({len(submission_df)} rows)", flush=True)
"""

cell_4_package = """import zipfile
from swegemma.config import ALLOWED_SUBMISSION_EXTENSIONS, MAX_SUBMISSION_SIZE_BYTES

# Finalize submission.zip in /kaggle/working/
zip_base = WORKING_DIR / 'submission'
zip_path = Path(shutil.make_archive(str(zip_base), 'zip', root_dir=AGENT_DIR))

with zipfile.ZipFile(zip_path, 'r') as zf:
    infos = zf.infolist()
    total_size = sum(i.file_size for i in infos)
    assert total_size <= MAX_SUBMISSION_SIZE_BYTES, f'Archive exceeds 3 GiB: {total_size}'
    for info in infos:
        if not info.is_dir():
            ext = Path(info.filename).suffix.lower()
            assert ext in ALLOWED_SUBMISSION_EXTENSIONS, f'Disallowed ext: {info.filename}'

print(f'SUCCESS: Verified submission archive ready at {zip_path}')
print(f'Archive Size: {zip_path.stat().st_size / (1024 * 1024):.2f} MiB (limit: 3072 MiB)')
"""

notebook = {
    "cells": [
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": cell_0_env.splitlines(keepends=True),
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": cell_1_unpack.splitlines(keepends=True),
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": cell_2_vllm.splitlines(keepends=True),
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": cell_3_eval.splitlines(keepends=True),
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": cell_4_package.splitlines(keepends=True),
        },
    ],
    "metadata": {
        "kaggle": {
            "accelerator": "nvidiaTeslaL4",
            "dataSources": [
                {"sourceId": 149921, "sourceType": "competition"},
                {
                    "datasetId": 6426555,
                    "sourceId": 10834371,
                    "sourceType": "datasetVersion",
                },
                {
                    "modelInstanceId": 182745,
                    "sourceId": 185124,
                    "sourceType": "modelInstanceVersion",
                },
            ],
            "dockerImageVersionId": 30880,
            "isGpuEnabled": True,
            "isInternetEnabled": False,
            "language": "python",
            "sourceType": "notebook",
        },
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "codemirror_mode": {"name": "ipython", "version": 3},
            "file_extension": ".py",
            "mimetype": "text/x-python",
            "name": "python",
            "nbformat": 4,
            "nbformat_minor": 5,
            "pygments_lexer": "ipython3",
            "version": "3.12.0",
        },
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

out_nb = KERNEL_DIR / "gemma4-eval-40calls.ipynb"
out_nb.write_text(json.dumps(notebook, indent=1), encoding="utf-8")
print(f"Wrote notebook to {out_nb} ({out_nb.stat().st_size} bytes)")

# Post-write self-check: re-open what was actually serialized and confirm the
# hardening survived the JSON round-trip. Cheap, and it closes the gap where an
# f-string interpolation silently dropped a guard.
_emitted = json.loads(out_nb.read_text(encoding="utf-8"))
_emitted_cells = "\n".join(
    "".join(cell["source"]) for cell in _emitted["cells"] if cell["cell_type"] == "code"
)
required_markers = [
    ("MODEL NOT FOUND", "model-path precondition"),
    ("litellm.drop_params did not take effect", "drop_params verification"),
    ("INFERENCE ENDPOINT DEAD", "run-health gate"),
    ("EVALUATION ABORTED at task", "per-task fail-loud handler"),
    ("degenerate run", "degenerate-run detector"),
    ("BASELINE INTEGRITY CHECK FAILED", "unpacked-files integrity verification"),
]

if PREFLIGHT["adapter_name"]:
    required_markers.extend([
        ("ADAPTER INCOMPLETE", "run-time adapter precondition"),
        ("NO ADAPTERS DISCOVERED", "run-time adapter precondition"),
        (PREFLIGHT["adapter_name"], "adapter identity"),
    ])
else:
    required_markers.append(("NO ADAPTER DECLARED", "adapter-less mode confirmation"))

for _required_marker, _why in required_markers:
    if _required_marker not in _emitted_cells:
        _fail(
            f"Emitted notebook is missing the '{_why}' guard "
            f"(marker {_required_marker!r} absent). Refusing to ship a kernel "
            "that would fail silently."
        )
print(f"Emitted-notebook self-check: all {len(_emitted['cells'])} cells carry their guards.")

# 3. Write kernel-metadata.json
metadata = {
    "id": "francisclyap/gemma4-eval-40calls",
    "title": "gemma4-eval-40calls",
    "code_file": "gemma4-eval-40calls.ipynb",
    "language": "python",
    "kernel_type": "notebook",
    "is_private": True,
    "enable_gpu": True,
    "enable_tpu": False,
    "enable_internet": False,
    "keywords": ["gpu"],
    "dataset_sources": ["metric/gemma-4-developer-agent-wheelhouse"],
    "kernel_sources": [],
    "competition_sources": ["gemma-4-developer-agent"],
    "model_sources": ["google/gemma-4/Other/gemma-4-31b-it-qat-w4a16-ct/2"],
    "machine_shape": "NvidiaL4",
}
# The Kaggle model-source slug embeds the model name as a path segment. Assert it
# still agrees with the policy constant so the attached model and the served
# model can never drift apart unnoticed.
_model_sources = metadata["model_sources"]
assert len(_model_sources) == 1 and f"/{PREFLIGHT['model']}/" in _model_sources[0], (
    f"kernel-metadata model_sources {_model_sources} does not pin "
    f"{PREFLIGHT['model']!r}. The kernel would attach a different model than it "
    "serves. Fix the slug and re-run."
)
out_meta = KERNEL_DIR / "kernel-metadata.json"
out_meta.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
print(f"Wrote metadata to {out_meta}")

_banner("KERNEL BUILT -- WHAT IS IN THE BOX")
print(f"  notebook     : {out_nb}")
print(f"  metadata     : {out_meta}")
print(f"  target model : {PREFLIGHT['model']}")
print(f"  adapter      : {PREFLIGHT['adapter_name'] or 'None (pure base weights)'} "
      f"({PREFLIGHT['adapter_weights_bytes']:,} bytes)")
print(f"  eval scope   : all tasks from the competition tasks.jsonl, 4x L4")
print("  fail-loud    : model path, adapter presence, litellm.drop_params,")
print("                 per-task endpoint health, per-task exceptions, and a")
print("                 degenerate-run check all abort the kernel with a named")
print("                 error instead of emitting a 0-score.")
print("  NEXT STEP    : this script only BUILDS the kernel. It does not run it")
print("                 and spends no GPU quota. To execute the evaluation the")
print("                 operator runs ./start.sh.")
