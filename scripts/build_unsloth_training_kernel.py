#!/usr/bin/env python3
"""Builds a standalone Kaggle training kernel for Unsloth Gemma 4 31B LoRA fine-tuning.

Aligned with the Locked Track 2 Specification:
1. Embeds the 1,500-sample zero-thought 262K Gemma 4 SFT dataset (1,194 train + 306 val).
2. Dual-path base model loader: primary `google/gemma-4-31b-it-qat-w4a16-ct` (`load_in_4bit=False, use_exact_model_name=True`), fallback `google/gemma-4-31B-it-qat-q4_0-unquantized` (`load_in_4bit=True, bnb_4bit_quant_type="fp4", bnb_4bit_use_double_quant=False`) and strict `torch.bfloat16` (`bf16=True, fp16=False`).
3. Configures Rank-8 LoRA on `['q_proj', 'v_proj', 'o_proj']` (`r=8, lora_alpha=16, lora_dropout=0.0, neftune_noise_alpha=None`).
4. Uses pre-tokenized prefix-delta masking (`labels[:len(prefix_ids)] = -100` with `add_special_tokens=False`), `max_seq_length=3072`, `eval_strategy="no"`.
5. Normalizes exported PEFT adapter in-place for vLLM (`base_model.model.language_model.model.layers.*`, 340 BF16 tensors <= 35.0 MB) and retains strictly `adapter_config.json` and `adapter_model.safetensors`.
"""

import base64
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_TRAIN_PATH = ROOT_DIR / "data" / "unsloth_sft_train.jsonl"
DATA_VAL_PATH = ROOT_DIR / "data" / "unsloth_sft_val.jsonl"
KERNEL_DIR = ROOT_DIR / "kaggle_unsloth"
KERNEL_DIR.mkdir(parents=True, exist_ok=True)

assert DATA_TRAIN_PATH.exists(), f"Train dataset not found at {DATA_TRAIN_PATH}"
assert DATA_VAL_PATH.exists(), f"Val dataset not found at {DATA_VAL_PATH}"

b64_train = base64.b64encode(DATA_TRAIN_PATH.read_bytes()).decode("ascii")
b64_val = base64.b64encode(DATA_VAL_PATH.read_bytes()).decode("ascii")
print(f"Embedded Train payload: {len(b64_train)} chars ({DATA_TRAIN_PATH.stat().st_size / 1024:.1f} KB)")
print(f"Embedded Val payload:   {len(b64_val)} chars ({DATA_VAL_PATH.stat().st_size / 1024:.1f} KB)")

cell_0_env = """import subprocess
import sys
import torch

if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
    raise RuntimeError("CUDA GPU with native bfloat16 support is required (zero fp16 fallback).")

print("Installing Unsloth, TRL, PEFT, compressed-tensors, llm-compressor, and bitsandbytes...")
subprocess.run([
    sys.executable, "-m", "pip", "install", "-q", "--upgrade",
    "torch", "torchvision", "torchaudio",
    "bitsandbytes", "transformers", "accelerate", "trl", "peft",
    "compressed-tensors", "llm-compressor"
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

cell_1_unpack = f"""import base64
import json
from pathlib import Path

WORKING_DIR = Path("/kaggle/working")
DATA_DIR = WORKING_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

B64_TRAIN = "{b64_train}"
B64_VAL = "{b64_val}"

train_path = DATA_DIR / "train.jsonl"
train_path.write_bytes(base64.b64decode(B64_TRAIN))

val_path = DATA_DIR / "val.jsonl"
val_path.write_bytes(base64.b64decode(B64_VAL))

with open(train_path, "r", encoding="utf-8") as f:
    train_examples = [json.loads(line) for line in f if line.strip()]

with open(val_path, "r", encoding="utf-8") as f:
    val_examples = [json.loads(line) for line in f if line.strip()]

print(f"Loaded {{len(train_examples)}} training rows and {{len(val_examples)}} held-out validation rows.")
"""

cell_2_model = """import json
from pathlib import Path
import torch
from transformers import AutoTokenizer, BitsAndBytesConfig
from unsloth import FastLanguageModel

max_seq_length = 3072
dtype = torch.bfloat16

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="fp4",
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_use_double_quant=False,
)

def is_pack_quantized_candidate(cand: str) -> bool:
    if "w4a16-ct" in cand.lower():
        return True
    cfg_file = Path(cand) / "config.json"
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            q_cfg = cfg.get("quantization_config", {})
            if q_cfg.get("format") == "pack-quantized" or q_cfg.get("quant_method") == "compressed-tensors":
                return True
        except Exception:
            pass
    return False

candidate_models = []
for local_cand in (
    "/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2",
    "/kaggle/input/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2",
    "/opt/model",
):
    if (Path(local_cand) / "config.json").exists():
        candidate_models.append(local_cand)

candidate_models.extend([
    "google/gemma-4-31b-it-qat-w4a16-ct",
    "google/gemma-4-31B-it-qat-q4_0-unquantized",
])
candidate_models = list(dict.fromkeys(candidate_models))

model = None
tokenizer = None
for cand in candidate_models:
    if "bnb-4bit" in cand.lower():
        continue
    is_pack_quant = is_pack_quantized_candidate(cand)
    print(f"Attempting to load model from: {cand} (pack_quantized={is_pack_quant})...")
    try:
        if is_pack_quant:
            model, tokenizer = FastLanguageModel.from_pretrained(
                model_name=cand,
                max_seq_length=max_seq_length,
                dtype=dtype,
                load_in_4bit=False,
                use_exact_model_name=True,
            )
        else:
            model, tokenizer = FastLanguageModel.from_pretrained(
                model_name=cand,
                max_seq_length=max_seq_length,
                dtype=dtype,
                load_in_4bit=True,
                quantization_config=bnb_config,
                use_exact_model_name=True,
            )
        if tokenizer is None:
            tokenizer = AutoTokenizer.from_pretrained(cand)
        print(f"Successfully loaded {cand}!")
        break
    except Exception as e:
        print(f"Failed loading {cand}: {e}")
        continue

if model is None or tokenizer is None:
    raise RuntimeError("Fatal: Could not load any candidate Gemma 4 model.")

assert len(tokenizer) == 262144, f"Expected 262144 vocab size, got {len(tokenizer)}"

model = FastLanguageModel.get_peft_model(
    model,
    r=8,
    target_modules=["q_proj", "v_proj", "o_proj"],
    lora_alpha=16,
    lora_dropout=0.0,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=3407,
    use_rslora=False,
)

model.print_trainable_parameters()
print("Model initialized and PEFT LoRA configured successfully.")
"""

cell_3_train = """import torch
from datasets import load_dataset
from transformers import Trainer, TrainingArguments

raw_train = load_dataset("json", data_files=str(train_path), split="train")

def tokenize_with_prefix_mask(example):
    p_ids = tokenizer(example["prefix_text"], add_special_tokens=False)["input_ids"]
    f_ids = tokenizer(example["text"], truncation=True, max_length=max_seq_length, add_special_tokens=False)["input_ids"]
    mask_len = min(len(p_ids), len(f_ids))
    labels = [-100] * mask_len + list(f_ids[mask_len:])
    return {"input_ids": f_ids, "attention_mask": [1] * len(f_ids), "labels": labels}

train_dataset = raw_train.map(tokenize_with_prefix_mask, remove_columns=raw_train.column_names)

class PrefixDeltaCollator:
    def __init__(self, pad_token_id: int):
        self.pad_token_id = pad_token_id
    def __call__(self, features):
        max_len = max(len(f["input_ids"]) for f in features)
        input_ids, attention_mask, labels = [], [], []
        for f in features:
            pad_len = max_len - len(f["input_ids"])
            input_ids.append(f["input_ids"] + [self.pad_token_id] * pad_len)
            attention_mask.append(f["attention_mask"] + [0] * pad_len)
            labels.append(f["labels"] + [-100] * pad_len)
        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "attention_mask": torch.tensor(attention_mask, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
        }

OUTPUT_DIR = WORKING_DIR / "training_outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

training_args = TrainingArguments(
    output_dir=str(OUTPUT_DIR),
    per_device_train_batch_size=1,
    gradient_accumulation_steps=8,
    warmup_steps=15,
    num_train_epochs=1,
    learning_rate=1.5e-4,
    fp16=False,
    bf16=True,
    logging_steps=5,
    eval_strategy="no",
    optim="paged_adamw_8bit",
    weight_decay=0.01,
    max_grad_norm=1.0,
    lr_scheduler_type="cosine",
    neftune_noise_alpha=None,
    seed=3407,
    report_to="none",
)

trainer = Trainer(
    model=model,
    train_dataset=train_dataset,
    data_collator=PrefixDeltaCollator(tokenizer.pad_token_id or 0),
    args=training_args,
)

print("Starting Unsloth Rank-8 LoRA fine-tuning with zero-thought prefix-delta masking...")
train_stats = trainer.train()
print("Training complete! Train stats:")
print(train_stats)
"""

cell_4_export = """import json
import os
from pathlib import Path
import torch
from safetensors.torch import load_file, save_file

def normalize_adapter_for_vllm(adapter_dir: Path) -> tuple[bool, str]:
    adapter_dir = Path(adapter_dir)
    weights_path = adapter_dir / "adapter_model.safetensors"
    config_path = adapter_dir / "adapter_config.json"

    if not weights_path.exists():
        return False, f"Missing safetensors weights at {weights_path}"
    if not config_path.exists():
        return False, f"Missing adapter config at {config_path}"

    target_prefix = "base_model.model.language_model.model.layers."
    tensors = load_file(str(weights_path))

    normalized_tensors = {}
    renamed_count = 0
    fp32_recast_count = 0

    for key, val in tensors.items():
        new_key = key
        if ".layers." in key:
            suffix = key.split(".layers.", 1)[1]
            new_key = f"{target_prefix}{suffix}"
            if new_key != key:
                renamed_count += 1
        if val.dtype != torch.bfloat16:
            val = val.to(torch.bfloat16)
            fp32_recast_count += 1

        normalized_tensors[new_key] = val

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    config["target_modules"] = ["o_proj", "q_proj", "v_proj"]
    config["r"] = 8
    config["lora_alpha"] = 16

    save_file(normalized_tensors, str(weights_path), metadata={"format": "pt"})
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    for p in list(adapter_dir.iterdir()):
        if p.is_file() and p.name not in ("adapter_config.json", "adapter_model.safetensors"):
            p.unlink()

    if len(normalized_tensors) != 340:
        return False, f"Tensor count mismatch: expected 340, got {len(normalized_tensors)}"

    for name, tensor in normalized_tensors.items():
        if not name.startswith(target_prefix):
            return False, f"Key {name} missing required vLLM prefix {target_prefix}"
        if tensor.dtype != torch.bfloat16:
            return False, f"Key {name} has invalid dtype {tensor.dtype}, must be torch.bfloat16"

    size_mb = os.path.getsize(weights_path) / (1024 * 1024)
    if size_mb > 35.0:
        return False, f"Adapter file size {size_mb:.2f} MB exceeds 35.0 MB limit"

    return (
        True,
        f"Normalized {renamed_count} keys ({fp32_recast_count} recast to BF16); verified 340 tensors ({size_mb:.2f} MB).",
    )

ADAPTER_DIR = WORKING_DIR / "adapters"
ADAPTER_DIR.mkdir(parents=True, exist_ok=True)

print(f"Exporting LoRA adapter weights to {ADAPTER_DIR}...")
model.save_pretrained(str(ADAPTER_DIR))

norm_ok, norm_msg = normalize_adapter_for_vllm(ADAPTER_DIR)
assert norm_ok, f"FATAL: Adapter normalization failed: {norm_msg}"
print(f"Adapter normalization succeeded: {norm_msg}")

print("\\n================ EXPORTED ADAPTER FILES ================")
total_size = 0
for p in sorted(ADAPTER_DIR.iterdir()):
    if p.is_file():
        sz = p.stat().st_size
        total_size += sz
        print(f"  - {p.name} ({sz / (1024 * 1024):.2f} MiB)")

print(f"Total Adapter Size: {total_size / (1024 * 1024):.2f} MiB")
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
