#!/usr/bin/env python3
"""Builds a self-contained Kaggle submission notebook for Gemma 4 Developer Agent.

Embeds:
1. The full my_submission directory (agent.yaml, configs/, prompts/, skills/)
2. Fixes vLLM GPU memory utilization to 0.90 to eliminate cache block exhaustion on 4x L4
3. Evaluates a sample smoke task to verify live vLLM inference and patch generation
4. Packages and validates /kaggle/working/submission.zip (< 3 GiB, zero bytecode)
"""

import base64
import json
import shutil
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SUBMISSION_DIR = ROOT_DIR / "my_submission"
KERNEL_DIR = ROOT_DIR / "kaggle_kernel"
KERNEL_DIR.mkdir(parents=True, exist_ok=True)

# 1. Package clean my_submission into an in-memory zip
zip_path = ROOT_DIR / "submission.zip"
if not zip_path.exists():
    shutil.make_archive(str(ROOT_DIR / "submission"), "zip", root_dir=SUBMISSION_DIR)

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
        except OSError:
            pass

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

cell_2_vllm = """import litellm
import torch
from pathlib import Path
from adk_submission import VllmConfig, VllmServer, discover_adapters
from swegemma.config import ALLOWED_ADAPTER_EXTENSIONS
from swegemma.models.discovery import validate_single_declared_model

litellm.drop_params = True

TARGET_MODEL_NAME = 'gemma-4-31b-it-qat-w4a16-ct'
_MP = Path('/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2')
if not _MP.exists():
    _f = sorted(Path('/kaggle/input').rglob('gemma-4-31b-it-qat-w4a16-ct'))
    print('model fallback search:', _f[:3])
    _MP = _f[0] if _f else _MP
MODEL_PATH = _MP
print('USING MODEL:', MODEL_PATH, MODEL_PATH.exists())
INFERENCE_API_KEY = 'EMPTY'

declared_model = validate_single_declared_model(AGENT_DIR)
adapters = discover_adapters(str(AGENT_DIR), adapter_extensions=ALLOWED_ADAPTER_EXTENSIONS)

gpu_count = torch.cuda.device_count() if torch.cuda.is_available() else 1
tp_size = 4 if gpu_count >= 4 else (2 if gpu_count >= 2 else 1)
print(f'Detected GPUs: {gpu_count}, Tensor Parallel Size: {tp_size}')

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
    enable_lora=bool(adapters),
    max_loras=8 if adapters else 0,
    max_lora_rank=128 if adapters else 0,
    tensor_parallel_size=tp_size,
    startup_timeout=60 * 20,
)
server_instance = VllmServer(vllm_cfg, adapter_manifest=adapters)
server_instance.start()
print(f'vLLM server started on {server_instance.base_url} (tp={tp_size})')

models = server_instance.create_model_registry(
    aliases=[declared_model, TARGET_MODEL_NAME],
    model_prefix='openai/',
    api_key=INFERENCE_API_KEY,
)
print('Model registry created successfully.')
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
predictions = []

print(f"Starting evaluation across all {len(tasks)} tasks on Kaggle 4x L4 GPUs...", flush=True)

for idx, task in enumerate(tasks, start=1):
    print(f"[{idx}/{len(tasks)}] Evaluating {task.instance_id} ({task.repo})...", flush=True)
    try:
        result = run_sync(evaluator.evaluate_task, task=task, task_index=idx, total_tasks=len(tasks))
        is_resolved = bool(result.resolved)
        if is_resolved:
            resolved_count += 1
        total_evaluated += 1

        record = {
            "task_id": task.instance_id,
            "repo": task.repo,
            "resolved": is_resolved,
            "test_exit_code": result.test_exit_code,
            "tool_calls": result.tool_calls,
            "duration_seconds": round(result.duration_seconds, 2),
            "patch_length": len(result.agent_patch or ""),
            "patch": result.agent_patch or "",
        }
        predictions.append({"id": task.instance_id, "prediction": result.agent_patch or ""})

        # Guardrail 1: Incremental flush to JSONL after every task
        with open(JSONL_PATH, "a", encoding="utf-8") as jf:
            jf.write(json.dumps(record) + "\\n")

        print(
            f"  -> resolved={is_resolved} (Running Score: {resolved_count}/{total_evaluated} = {resolved_count/total_evaluated*100:.1f}%), "
            f"exit={result.test_exit_code}, patch={record['patch_length']}ch, calls={result.tool_calls}, {result.duration_seconds:.1f}s",
            flush=True
        )
    except Exception as e:
        print(f"  -> ERROR evaluating {task.instance_id}: {e}", flush=True)
        predictions.append({"id": task.instance_id, "prediction": ""})
    finally:
        # Guardrail 2: Clean up temporary sandbox venvs to prevent disk overflow
        for sb_dir in Path("/tmp").glob("swegemma_sandbox_*"):
            try:
                shutil.rmtree(sb_dir, ignore_errors=True)
            except Exception:
                pass

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
out_meta = KERNEL_DIR / "kernel-metadata.json"
out_meta.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
print(f"Wrote metadata to {out_meta}")
