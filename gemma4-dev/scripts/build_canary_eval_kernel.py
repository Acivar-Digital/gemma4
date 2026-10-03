#!/usr/bin/env python3
"""Builds the dedicated Kaggle canary evaluation notebook to test the fine-tuned Rank-8 LoRA adapter
on two high-signal failed tasks: fastapi_14479 and requests_7205.
"""

import base64
import io
import json
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SUBMISSION_DIR = ROOT_DIR / "my_submission"
OUT_DIR = ROOT_DIR / "kaggle_canary_eval"
OUT_DIR.mkdir(parents=True, exist_ok=True)

NOTEBOOK_PATH = OUT_DIR / "canary_eval.ipynb"
METADATA_PATH = OUT_DIR / "kernel-metadata.json"

# Package declarative submission into base64 (excluding adapters, which come from the Kaggle dataset)
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
    for p in sorted(SUBMISSION_DIR.rglob("*")):
        if p.is_file() and "adapters" not in p.parts and not p.name.endswith(".pyc") and "__pycache__" not in p.parts and p.name != ".DS_Store":
            rel = p.relative_to(SUBMISSION_DIR)
            zf.write(p, rel)

b64_payload = base64.b64encode(buf.getvalue()).decode("ascii")

metadata = {
    "id": "francisclyap/gemma4-canary-eval",
    "title": "gemma4-canary-eval",
    "code_file": "canary_eval.ipynb",
    "language": "python",
    "kernel_type": "notebook",
    "is_private": True,
    "enable_gpu": True,
    "enable_tpu": False,
    "enable_internet": False,
    "keywords": ["gpu"],
    "dataset_sources": [
        "metric/gemma-4-developer-agent-wheelhouse",
        "francisclyap/gemma4-lora-adapter"
    ],
    "kernel_sources": [],
    "competition_sources": [
        "gemma-4-developer-agent"
    ],
    "model_sources": [
        "google/gemma-4/Other/gemma-4-31b-it-qat-w4a16-ct/2"
    ],
    "machine_shape": "NvidiaL4"
}

METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
print(f"Wrote metadata: {METADATA_PATH}")

cells = [
    # Cell 0: Environment Setup & Wheelhouse Installation
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# ==============================================================================\n",
            "# CELL 0: HARDWARE, ENVIRONMENT & WHEELHOUSE INSTALLATION\n",
            "# ==============================================================================\n",
            "import glob\n",
            "import importlib\n",
            "import os\n",
            "import shutil\n",
            "import subprocess\n",
            "import sys\n",
            "from pathlib import Path\n",
            "\n",
            "os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'\n",
            "os.environ['TRANSFORMERS_NO_TF'] = '1'\n",
            "os.environ['VLLM_WORKER_MULTIPROC_METHOD'] = 'spawn'\n",
            "os.environ['VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS'] = '1'\n",
            "os.environ['VLLM_ENGINE_READY_TIMEOUT_S'] = '1200'\n",
            "os.environ['VLLM_NO_USAGE_STATS'] = '1'\n",
            "os.environ['OTEL_SDK_DISABLED'] = 'true'\n",
            "os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'\n",
            "os.environ['PYTHONDONTWRITEBYTECODE'] = '1'\n",
            "\n",
            "_CANDS = [\n",
            "    Path('/kaggle/input/gemma-4-developer-agent-wheelhouse'),\n",
            "    Path('/kaggle/input/datasets/metric/gemma-4-developer-agent-wheelhouse')\n",
            "]\n",
            "WHEELHOUSE_DIR = next((p for p in _CANDS if p.exists() and list(p.glob('*.whl'))), None)\n",
            "if WHEELHOUSE_DIR is None:\n",
            "    _found = sorted(Path('/kaggle/input').rglob('swegemma*.whl'))\n",
            "    assert _found, 'no swegemma wheel anywhere under /kaggle/input'\n",
            "    WHEELHOUSE_DIR = _found[0].parent\n",
            "print('USING WHEELHOUSE:', WHEELHOUSE_DIR)\n",
            "\n",
            "for pth_pattern in (\n",
            "    '/usr/local/lib/python*/dist-packages/*cutlass*.pth',\n",
            "    '/usr/local/lib/python*/site-packages/*cutlass*.pth',\n",
            "):\n",
            "    for pth in glob.glob(pth_pattern):\n",
            "        try:\n",
            "            os.unlink(pth)\n",
            "        except OSError:\n",
            "            pass\n",
            "\n",
            "tmp_whl = Path('/tmp/wheelhouse')\n",
            "tmp_whl.mkdir(parents=True, exist_ok=True)\n",
            "for w in WHEELHOUSE_DIR.glob('*.whl'):\n",
            "    if 'cutlass' in w.name.lower():\n",
            "        continue\n",
            "    target_name = (\n",
            "        w.name.replace('cu128', '+cu128')\n",
            "        if ('cu128' in w.name and '+' not in w.name)\n",
            "        else w.name\n",
            "    )\n",
            "    target = tmp_whl / target_name\n",
            "    if not target.exists():\n",
            "        os.symlink(w, target)\n",
            "\n",
            "wheels = sorted(str(w) for w in tmp_whl.glob('*.whl'))\n",
            "print(f'Installing {len(wheels)} wheels from {WHEELHOUSE_DIR}...')\n",
            "subprocess.run(\n",
            "    [sys.executable, '-m', 'pip', 'install', '-q', '--no-deps', '--force-reinstall', *wheels],\n",
            "    check=True,\n",
            ")\n",
            "importlib.invalidate_caches()\n",
            "print('Wheelhouse installation complete.')\n"
        ]
    },
    # Cell 1: Extract Submission & Mount LoRA Adapter
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# ==============================================================================\n",
            "# CELL 1: EXTRACT SUBMISSION & MOUNT FINE-TUNED LORA ADAPTER\n",
            "# ==============================================================================\n",
            "import base64\n",
            "import io\n",
            "import os\n",
            "import shutil\n",
            "import zipfile\n",
            "from pathlib import Path\n",
            "\n",
            "DATA_DIR = Path('/kaggle/input/competitions/gemma-4-developer-agent')\n",
            "WORKING_DIR = Path('/kaggle/working')\n",
            "AGENT_DIR = WORKING_DIR / 'submission'\n",
            "if AGENT_DIR.exists():\n",
            "    shutil.rmtree(AGENT_DIR)\n",
            "AGENT_DIR.mkdir(parents=True, exist_ok=True)\n",
            "\n",
            "# 1. Unpack declarative agent assets\n",
            f"B64_SUBMISSION = '{b64_payload}'\n",
            "with zipfile.ZipFile(io.BytesIO(base64.b64decode(B64_SUBMISSION))) as zf:\n",
            "    zf.extractall(AGENT_DIR)\n",
            "print(f'Extracted declarative submission assets to {AGENT_DIR}')\n",
            "\n",
            "# 2. Locate and mount LoRA adapter\n",
            "adapter_cands = [\n",
            "    Path('/kaggle/input/gemma4-lora-adapter'),\n",
            "    Path('/kaggle/input/datasets/francisclyap/gemma4-lora-adapter')\n",
            "]\n",
            "ADAPTER_SRC = next((p for p in adapter_cands if p.exists() and (p / 'adapter_model.safetensors').exists()), None)\n",
            "if ADAPTER_SRC is None:\n",
            "    found_tensors = list(Path('/kaggle/input').rglob('adapter_model.safetensors'))\n",
            "    assert found_tensors, 'adapter_model.safetensors not found under /kaggle/input!'\n",
            "    ADAPTER_SRC = found_tensors[0].parent\n",
            "print('USING LORA ADAPTER SOURCE:', ADAPTER_SRC)\n",
            "\n",
            "LORA_DEST = AGENT_DIR / 'adapters' / 'main_lora'\n",
            "LORA_DEST.mkdir(parents=True, exist_ok=True)\n",
            "for item in ADAPTER_SRC.iterdir():\n",
            "    if item.is_file() and not item.name.startswith('.'):\n",
            "        shutil.copy2(item, LORA_DEST / item.name)\n",
            "\n",
            "print('LoRA adapter mounted at:', LORA_DEST)\n",
            "for p in sorted(AGENT_DIR.rglob('*')):\n",
            "    if p.is_file():\n",
            "        print(f'  - {p.relative_to(AGENT_DIR)}: {p.stat().st_size:,} bytes')\n"
        ]
    },
    # Cell 2: Start Offline vLLM Server with LoRA Adapter Enabled
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# ==============================================================================\n",
            "# CELL 2: START OFFLINE VLLM SERVER (WITH LORA ADAPTER ENABLED)\n",
            "# ==============================================================================\n",
            "import litellm\n",
            "import torch\n",
            "from pathlib import Path\n",
            "from adk_submission import VllmConfig, VllmServer, discover_adapters\n",
            "from swegemma.config import ALLOWED_ADAPTER_EXTENSIONS\n",
            "from swegemma.models.discovery import validate_single_declared_model\n",
            "\n",
            "litellm.drop_params = True\n",
            "\n",
            "TARGET_MODEL_NAME = 'gemma-4-31b-it-qat-w4a16-ct'\n",
            "_MP = Path('/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2')\n",
            "if not _MP.exists():\n",
            "    _f = sorted(Path('/kaggle/input').rglob('gemma-4-31b-it-qat-w4a16-ct'))\n",
            "    print('model fallback search:', _f[:3])\n",
            "    _MP = _f[0] if _f else _MP\n",
            "MODEL_PATH = _MP\n",
            "print('USING MODEL:', MODEL_PATH, MODEL_PATH.exists())\n",
            "\n",
            "declared_model = validate_single_declared_model(AGENT_DIR)\n",
            "adapters = discover_adapters(str(AGENT_DIR), adapter_extensions=ALLOWED_ADAPTER_EXTENSIONS)\n",
            "print(f'Discovered Adapters: {adapters}')\n",
            "\n",
            "gpu_count = torch.cuda.device_count() if torch.cuda.is_available() else 1\n",
            "tp_size = 4 if gpu_count >= 4 else (2 if gpu_count >= 2 else 1)\n",
            "print(f'Detected GPUs: {gpu_count}, Tensor Parallel Size: {tp_size}')\n",
            "\n",
            "vllm_cfg = VllmConfig(\n",
            "    model=str(MODEL_PATH),\n",
            "    port=8000,\n",
            "    host='127.0.0.1',\n",
            "    tool_call_parser='gemma4',\n",
            "    reasoning_parser='gemma4',\n",
            "    max_model_len=32768,\n",
            "    dtype='bfloat16' if (torch.cuda.is_available() and torch.cuda.is_bf16_supported()) else 'auto',\n",
            "    gpu_memory_utilization=0.90,\n",
            "    enable_auto_tool_choice=True,\n",
            "    enable_lora=bool(adapters),\n",
            "    max_loras=8 if adapters else 0,\n",
            "    max_lora_rank=128 if adapters else 0,\n",
            "    tensor_parallel_size=tp_size,\n",
            "    startup_timeout=60 * 20,\n",
            ")\n",
            "server_instance = VllmServer(vllm_cfg, adapter_manifest=adapters)\n",
            "server_instance.start()\n",
            "print(f'vLLM server started on {server_instance.base_url} (tp={tp_size})')\n",
            "\n",
            "models = server_instance.create_model_registry(\n",
            "    aliases=[declared_model, TARGET_MODEL_NAME],\n",
            "    model_prefix='openai/',\n",
            "    api_key='EMPTY',\n",
            ")\n",
            "print('Model registry created successfully.')\n"
        ]
    },
    # Cell 3: Canary Evaluation on fastapi_14479 and requests_7205
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# ==============================================================================\n",
            "# CELL 3: RUN CANARY EVALUATION ON TWO TARGET FAILED TASKS\n",
            "# ==============================================================================\n",
            "import asyncio\n",
            "import concurrent.futures\n",
            "import json\n",
            "import os\n",
            "import shutil\n",
            "from pathlib import Path\n",
            "import pandas as pd\n",
            "from google.adk.agents.context_cache_config import ContextCacheConfig\n",
            "from google.adk.apps._configs import EventsCompactionConfig\n",
            "from swegemma.config import EvalConfig, build_submission_limits\n",
            "from swegemma.evaluate import Evaluator\n",
            "from swegemma.models import load_tasks\n",
            "\n",
            "def run_sync(coro_or_fn, *args, **kwargs):\n",
            "    fn = (lambda: coro_or_fn(*args, **kwargs)) if callable(coro_or_fn) else (lambda: coro_or_fn)\n",
            "    try:\n",
            "        loop = asyncio.get_running_loop()\n",
            "    except RuntimeError:\n",
            "        loop = None\n",
            "    if loop is not None and loop.is_running():\n",
            "        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:\n",
            "            return pool.submit(lambda: asyncio.run(fn())).result()\n",
            "    return asyncio.run(fn())\n",
            "\n",
            "TASKS_PATH = DATA_DIR / 'tasks.jsonl'\n",
            "tasks = load_tasks(TASKS_PATH)\n",
            "GRAPH_DIR = str(DATA_DIR / 'graphs')\n",
            "EMBEDDINGS_DIR = str(DATA_DIR / 'embeddings')\n",
            "\n",
            "# Two high-signal near-miss tasks:\n",
            "# 1. fastapi_14479: small assertion error string mismatch\n",
            "# 2. requests_7205: _parse_content_type_header boolean flag handling\n",
            "TARGET_IDS = ['fastapi_14479', 'requests_7205']\n",
            "canary_tasks = [t for t in tasks if t.instance_id in TARGET_IDS]\n",
            "print(f'Target Tasks ({len(canary_tasks)}): {[t.instance_id for t in canary_tasks]}')\n",
            "\n",
            "limits, gen_constraints = build_submission_limits()\n",
            "RESULTS_DIR = WORKING_DIR / 'results'\n",
            "RESULTS_DIR.mkdir(parents=True, exist_ok=True)\n",
            "JSONL_PATH = RESULTS_DIR / 'task_results.jsonl'\n",
            "\n",
            "eval_config = EvalConfig(\n",
            "    tasks_path=TASKS_PATH,\n",
            "    snapshots_dir=DATA_DIR / 'snapshots',\n",
            "    results_dir=RESULTS_DIR,\n",
            "    submission_dir=AGENT_DIR,\n",
            "    models=models,\n",
            "    sandbox='subprocess',\n",
            "    timeout_seconds=60,\n",
            "    max_time_minutes=4.0,\n",
            "    max_tool_calls=30,\n",
            "    max_turns=50,\n",
            "    limits=limits,\n",
            "    generation_constraints=gen_constraints,\n",
            "    adapter_manifest=adapters,\n",
            "    context_cache_config=ContextCacheConfig(min_tokens=2048, ttl_seconds=1800, cache_intervals=10),\n",
            "    events_compaction_config=EventsCompactionConfig(\n",
            "        compaction_interval=15, overlap_size=2,\n",
            "        token_threshold=14336, event_retention_size=5),\n",
            "    graph_dir=GRAPH_DIR,\n",
            "    embeddings_dir=EMBEDDINGS_DIR,\n",
            "    wheels_dir=DATA_DIR / 'wheels',\n",
            "    verbose=True,\n",
            ")\n",
            "evaluator = Evaluator(eval_config)\n",
            "\n",
            "resolved_count = 0\n",
            "total_evaluated = 0\n",
            "\n",
            "print('\\nStarting canary evaluation of fine-tuned Gemma 4 LoRA agent...\\n', flush=True)\n",
            "\n",
            "for idx, task in enumerate(canary_tasks, start=1):\n",
            "    print(f'[{idx}/{len(canary_tasks)}] Evaluating {task.instance_id} ({task.repo})...', flush=True)\n",
            "    try:\n",
            "        result = run_sync(evaluator.evaluate_task, task=task, task_index=idx, total_tasks=len(canary_tasks))\n",
            "        is_resolved = bool(result.resolved)\n",
            "        if is_resolved:\n",
            "            resolved_count += 1\n",
            "        total_evaluated += 1\n",
            "\n",
            "        record = {\n",
            "            'task_id': task.instance_id,\n",
            "            'repo': task.repo,\n",
            "            'resolved': is_resolved,\n",
            "            'test_exit_code': result.test_exit_code,\n",
            "            'tool_calls': result.tool_calls,\n",
            "            'duration_seconds': round(result.duration_seconds, 2),\n",
            "            'patch_length': len(result.agent_patch or ''),\n",
            "            'patch': result.agent_patch or '',\n",
            "        }\n",
            "\n",
            "        with open(JSONL_PATH, 'a', encoding='utf-8') as jf:\n",
            "            jf.write(json.dumps(record) + '\\n')\n",
            "\n",
            "        print(\n",
            "            f'  -> resolved={is_resolved} (Running Score: {resolved_count}/{total_evaluated}), '\n",
            "            f'exit={result.test_exit_code}, patch={record[\"patch_length\"]}ch, calls={result.tool_calls}, {result.duration_seconds:.1f}s',\n",
            "            flush=True\n",
            "        )\n",
            "    except Exception as e:\n",
            "        print(f'  -> ERROR evaluating {task.instance_id}: {e}', flush=True)\n",
            "    finally:\n",
            "        for sb_dir in Path('/tmp').glob('swegemma_sandbox_*'):\n",
            "            try:\n",
            "                shutil.rmtree(sb_dir, ignore_errors=True)\n",
            "            except Exception:\n",
            "                pass\n",
            "\n",
            "print(f'\\n=================== CANARY RUN COMPLETE ===================', flush=True)\n",
            "print(f'Canary Score: {resolved_count}/{total_evaluated} resolved.', flush=True)\n"
        ]
    },
    # Cell 4: Trace and Patch Inspection
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# ==============================================================================\n",
            "# CELL 4: TRACE AND PATCH INSPECTION\n",
            "# ==============================================================================\n",
            "import json\n",
            "from pathlib import Path\n",
            "\n",
            "print('=== GENERATED PATCHES ===\\n')\n",
            "if JSONL_PATH.exists():\n",
            "    with open(JSONL_PATH) as f:\n",
            "        for line in f:\n",
            "            rec = json.loads(line)\n",
            "            print(f\"Task: {rec['task_id']} | Resolved: {rec['resolved']} | Exit Code: {rec['test_exit_code']}\")\n",
            "            print(f\"Patch ({rec['patch_length']} chars):\\n\")\n",
            "            print(rec.get('patch', '')[:1000])\n",
            "            print('-' * 60)\n",
            "\n",
            "print('\\nCanary evaluation complete.')\n"
        ]
    }
]

notebook = {
    "cells": cells,
    "metadata": {
        "kaggle": {
            "accelerator": "nvidiaGpu",
            "dataSources": [
                {
                    "datasetId": 0,
                    "sourceId": 0,
                    "sourceType": "dataset"
                }
            ],
            "isGpuEnabled": True,
            "isInternetEnabled": False,
            "language": "python",
            "type": "notebook"
        },
        "language_info": {
            "name": "python"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 4
}

NOTEBOOK_PATH.write_text(json.dumps(notebook, indent=2), encoding="utf-8")
print(f"Generated Canary Notebook: {NOTEBOOK_PATH} ({NOTEBOOK_PATH.stat().st_size:,} bytes)")
