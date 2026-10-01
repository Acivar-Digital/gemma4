#!/usr/bin/env python3
"""Builds a standalone Kaggle training kernel for Unsloth Gemma 31B LoRA fine-tuning.

Embeds:
1. The curated SFT training dataset (data/unsloth_sft_train.jsonl) containing 56 verified winning trajectories.
2. Unsloth FastLanguageModel 4-bit QLoRA configuration (Rank 16, alpha 16, target attention + MLP modules).
3. SFTTrainer loop with cosine learning rate schedule, fp16/bf16 auto-detection, and gradient checkpointing.
4. Export pipeline saving clean adapter_model.safetensors (~200MB) to /kaggle/working/adapters/.
"""

import base64
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT_DIR / "data" / "unsloth_sft_train.jsonl"
KERNEL_DIR = ROOT_DIR / "kaggle_unsloth"
KERNEL_DIR.mkdir(parents=True, exist_ok=True)

assert DATA_PATH.exists(), f"SFT dataset not found at {DATA_PATH}"
b64_data = base64.b64encode(DATA_PATH.read_bytes()).decode("ascii")
print(f"Embedded SFT dataset base64 payload: {len(b64_data)} chars ({DATA_PATH.stat().st_size / 1024:.1f} KB)")

# Cell 0: Environment setup and Unsloth installation
cell_0_env = """import subprocess
import sys
import os

print("Installing Unsloth, TRL, PEFT, and bitsandbytes with internet enabled...")
subprocess.run([
    sys.executable, "-m", "pip", "install", "-q", "--upgrade",
    "torch", "torchvision", "torchaudio",
    "bitsandbytes", "transformers", "accelerate", "trl", "peft"
], check=True)

try:
    import unsloth
except ImportError:
    subprocess.run([
        sys.executable, "-m", "pip", "install", "-q",
        "git+https://github.com/unslothai/unsloth.git"
    ], check=True)

print("Environment setup and Unsloth installation complete.")
"""

# Cell 1: Unpack SFT dataset
cell_1_unpack = f"""import base64
import json
from pathlib import Path

WORKING_DIR = Path("/kaggle/working")
DATA_DIR = WORKING_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

B64_DATA = "{b64_data}"
train_path = DATA_DIR / "train.jsonl"
train_path.write_bytes(base64.b64decode(B64_DATA))

with open(train_path, "r", encoding="utf-8") as f:
    examples = [json.loads(line) for line in f if line.strip()]

print(f"Loaded {{len(examples)}} training examples into {{train_path}}.")
print(f"First example task ID: {{examples[0].get('task_id')}}, repo: {{examples[0].get('repo')}}")
"""

# Cell 2: Model and LoRA configuration
cell_2_model = """import torch
from unsloth import FastLanguageModel

max_seq_length = 4096
dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
load_in_4bit = True

print(f"Loading Gemma 31B in 4-bit QLoRA (max_seq_length={max_seq_length}, dtype={dtype})...")

# Check for local Kaggle model path first, otherwise load from HuggingFace
LOCAL_MODEL_PATH = Path("/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2")
model_name = str(LOCAL_MODEL_PATH) if LOCAL_MODEL_PATH.exists() else "google/gemma-4-31b-it"

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=model_name,
    max_seq_length=max_seq_length,
    dtype=dtype,
    load_in_4bit=load_in_4bit,
)

print("Adding Rank-16 LoRA adapter to attention and MLP projections...")
model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=[
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ],
    lora_alpha=16,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=42,
)

model.print_trainable_parameters()
print("Model initialized and PEFT LoRA configured successfully.")
"""

# Cell 3: Training loop
cell_3_train = """from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments

dataset = load_dataset("json", data_files=str(train_path), split="train")
print(f"HuggingFace dataset loaded: {len(dataset)} rows.")

OUTPUT_DIR = WORKING_DIR / "training_outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

training_args = TrainingArguments(
    output_dir=str(OUTPUT_DIR),
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    warmup_steps=5,
    max_steps=60,
    learning_rate=1.5e-4,
    fp16=not torch.cuda.is_bf16_supported(),
    bf16=torch.cuda.is_bf16_supported(),
    logging_steps=5,
    optim="adamw_8bit",
    weight_decay=0.01,
    lr_scheduler_type="cosine",
    seed=42,
    report_to="none",
)

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=max_seq_length,
    dataset_num_proc=2,
    packing=False,
    args=training_args,
)

print("Starting Unsloth LoRA fine-tuning...")
train_stats = trainer.train()
print("Training complete! Train stats:")
print(train_stats)
"""

# Cell 4: Export and verify adapter
cell_4_export = """from pathlib import Path

ADAPTER_DIR = WORKING_DIR / "adapters"
ADAPTER_DIR.mkdir(parents=True, exist_ok=True)

print(f"Exporting LoRA adapter weights to {ADAPTER_DIR}...")
model.save_pretrained(str(ADAPTER_DIR))
tokenizer.save_pretrained(str(ADAPTER_DIR))

print("\\n================ EXPORTED ADAPTER FILES ================")
total_size = 0
for p in sorted(ADAPTER_DIR.iterdir()):
    if p.is_file():
        sz = p.stat().st_size
        total_size += sz
        print(f"  - {p.name} ({sz / (1024 * 1024):.2f} MiB)")

print(f"Total Adapter Size: {total_size / (1024 * 1024):.2f} MiB")
print(f"SUCCESS: Ready to mount in my_submission/adapters/ for competition submission!")
"""

notebook = {
    "cells": [
        {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": cell_0_env.splitlines(keepends=True)},
        {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": cell_1_unpack.splitlines(keepends=True)},
        {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": cell_2_model.splitlines(keepends=True)},
        {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": cell_3_train.splitlines(keepends=True)},
        {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": cell_4_export.splitlines(keepends=True)},
    ],
    "metadata": {
        "kaggle": {
            "accelerator": "nvidiaTeslaL4",
            "dataSources": [
                {"sourceId": 149921, "sourceType": "competition"},
                {"datasetId": 6426555, "sourceId": 10834371, "sourceType": "datasetVersion"},
                {"modelInstanceId": 182745, "sourceId": 185124, "sourceType": "modelInstanceVersion"},
            ],
            "dockerImageVersionId": 30880,
            "isGpuEnabled": True,
            "isInternetEnabled": True,
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

out_nb = KERNEL_DIR / "train_gemma4_lora.ipynb"
out_nb.write_text(json.dumps(notebook, indent=1), encoding="utf-8")
print(f"Wrote Unsloth training notebook to {out_nb} ({out_nb.stat().st_size / 1024:.1f} KB)")

metadata = {
    "id": "francisclyap/gemma4-unsloth-lora-training",
    "title": "gemma4-unsloth-lora-training",
    "code_file": "train_gemma4_lora.ipynb",
    "language": "python",
    "kernel_type": "notebook",
    "is_private": True,
    "enable_gpu": True,
    "enable_tpu": False,
    "enable_internet": True,
    "keywords": ["gpu", "unsloth", "lora"],
    "dataset_sources": ["metric/gemma-4-developer-agent-wheelhouse"],
    "kernel_sources": [],
    "competition_sources": ["gemma-4-developer-agent"],
    "model_sources": ["google/gemma-4/Other/gemma-4-31b-it-qat-w4a16-ct/2"],
    "machine_shape": "NvidiaL4",
}
out_meta = KERNEL_DIR / "kernel-metadata.json"
out_meta.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
print(f"Wrote metadata to {out_meta}")
