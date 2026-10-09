#!/usr/bin/env python3
"""
Standalone Unsloth Fine-Tuning Script for Gemma 4 31B IT on GCP L4/A100.
Enforces:
- Dual-path base model loader:
  * Primary: google/gemma-4-31b-it-qat-w4a16-ct (INT4 pack-quantized, load_in_4bit=False, use_exact_model_name=True)
  * Fallback: google/gemma-4-31B-it-qat-q4_0-unquantized (BitsAndBytes FP4, bnb_4bit_use_double_quant=False)
- Rank-8 LoRA on Attention/Output heads (q_proj, v_proj, o_proj, k_proj omitted per attention_k_eq_v=True), MLPs frozen
- max_seq_length = 3072 with Unsloth gradient checkpointing
- Zero-thought pre-tokenized prefix-delta loss masking (labels[:mask_len] = -100)
- Inline vLLM adapter normalization (base_model.model.language_model.model.layers.*, 340 BF16 tensors <35MB)
"""

import argparse
import json
import os
from pathlib import Path
import sys
# Block broken VM torchaudio ABI from crashing transformers audio_utils
sys.modules["torchaudio"] = None
import torch
from datasets import load_dataset
from safetensors.torch import load_file, save_file
from transformers import BitsAndBytesConfig, TrainingArguments
try:
    from trl import SFTConfig, SFTTrainer
except ImportError:
    try:
        from trl import SFTTrainer
        SFTConfig = None
    except ImportError:
        SFTTrainer = None
        SFTConfig = None

# Configure PyTorch memory allocator to eliminate fragmentation and allocate dynamically
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
os.environ["PYTORCH_ALLOC_CONF"] = "expandable_segments:True"


# Import unsloth first as recommended for kernel optimizations
try:
    from unsloth import FastLanguageModel
except ImportError:
    print("Error: Unsloth not installed. Run 'pip install unsloth' first.", file=sys.stderr)
    sys.exit(1)

# Monkey patch _Gemma4KVSharedSafeProxy to allow attribute assignment forwarding to the real config
try:
    from unsloth_zoo.temporary_patches import gemma4 as gemma4_patches
    if hasattr(gemma4_patches, "_Gemma4KVSharedSafeProxy"):
        def _proxy_setattr(self, name, value):
            if name == "_real":
                super(gemma4_patches._Gemma4KVSharedSafeProxy, self).__setattr__(name, value)
            else:
                setattr(self._real, name, value)
        gemma4_patches._Gemma4KVSharedSafeProxy.__setattr__ = _proxy_setattr
        print("Patched _Gemma4KVSharedSafeProxy.__setattr__ for TRL compatibility.")
except Exception as e:
    print(f"Notice: _Gemma4KVSharedSafeProxy patch bypassed: {e}")


class PrefixDeltaDataCollator:
    """Collator for pre-tokenized examples with -100 padded labels ensuring equal-length labels."""

    def __init__(self, pad_token_id: int):
        self.pad_token_id = pad_token_id

    def __call__(self, features: list[dict]) -> dict[str, torch.Tensor]:
        max_len = max(len(f["input_ids"]) for f in features)
        batch_input_ids = []
        batch_attention_mask = []
        batch_labels = []

        for f in features:
            input_ids = f["input_ids"]
            attention_mask = f["attention_mask"]
            labels = f["labels"]
            pad_len = max_len - len(input_ids)

            # Right padding
            batch_input_ids.append(input_ids + [self.pad_token_id] * pad_len)
            batch_attention_mask.append(attention_mask + [0] * pad_len)
            batch_labels.append(labels + [-100] * pad_len)

        input_ids_tensor = torch.tensor(batch_input_ids, dtype=torch.long)
        labels_tensor = torch.tensor(batch_labels, dtype=torch.long)
        assert input_ids_tensor.shape == labels_tensor.shape, (
            f"Shape mismatch: input_ids {input_ids_tensor.shape} != labels {labels_tensor.shape}"
        )

        return {
            "input_ids": input_ids_tensor,
            "attention_mask": torch.tensor(batch_attention_mask, dtype=torch.long),
            "labels": labels_tensor,
        }



def is_pack_quantized_candidate(cand: str) -> bool:
    """Detect if candidate model is INT4 pack-quantized (compressed-tensors / w4a16-ct)."""
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


def normalize_adapter_for_vllm(adapter_dir: Path) -> tuple[bool, str]:
    """Normalize and verify exported PEFT Gemma 4 LoRA adapter for vLLM serving."""
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

def parse_args():
    parser = argparse.ArgumentParser(description="Gemma 4 31B Unsloth SFT Fine-Tuning")
    parser.add_argument(
        "--preflight-probe",
        action="store_true",
        help="Run 10-step probe on 5 samples and test model.generate() prefix completion",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=os.environ.get("DATA_DIR", "/opt/data"),
        help="Directory containing unsloth_sft_train.jsonl and unsloth_sft_val.jsonl",
    )
    parser.add_argument(
        "--train-file",
        type=str,
        default=None,
        help="Path to JSONL training dataset (overrides --data-dir)",
    )
    parser.add_argument(
        "--val-file",
        type=str,
        default=None,
        help="Path to JSONL validation dataset (overrides --data-dir)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=os.environ.get("OUTPUT_DIR", "/opt/output/main_lora"),
        help="Directory to save final LoRA adapter weights",
    )
    parser.add_argument(
        "--local-model-dir",
        type=str,
        default=os.environ.get("LOCAL_MODEL_DIR", "/opt/model"),
        help="Local directory with cached base model",
    )
    parser.add_argument(
        "--hf-token",
        type=str,
        default=os.environ.get("HF_TOKEN", None),
        help="Hugging Face authentication token",
    )
    parser.add_argument(
        "--max-seq-length",
        type=int,
        default=3072,
        help="Maximum sequence length (default: 3072)",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="Maximum training optimizer steps (default: None)",
    )
    parser.add_argument(
        "--num-train-epochs",
        type=int,
        default=1,
        help="Number of training epochs (default: 1)",
    )
    parser.add_argument(
        "--gradient-accumulation-steps",
        type=int,
        default=8,
        help="Gradient accumulation steps (default: 8)",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=1.5e-4,
        help="Learning rate (default: 1.5e-4)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=== Gemma 4 31B Unsloth SFT Fine-Tuning Starting ===")
    if args.preflight_probe:
        print("[MODE] Preflight probe active: training 10 steps on 5 samples then verifying model.generate()")

    # Paths
    DATA_DIR = Path(args.data_dir)
    OUTPUT_DIR = Path(args.output_dir)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.train_file:
        train_path = Path(args.train_file)
    elif (DATA_DIR / "train.jsonl").exists():
        train_path = DATA_DIR / "train.jsonl"
    else:
        train_path = DATA_DIR / "unsloth_sft_train.jsonl"

    if args.val_file:
        val_path = Path(args.val_file)
    elif (DATA_DIR / "val.jsonl").exists():
        val_path = DATA_DIR / "val.jsonl"
    else:
        val_path = DATA_DIR / "unsloth_sft_val.jsonl"

    assert train_path.exists(), f"Fatal: Training dataset missing at {train_path}"
    assert val_path.exists(), f"Fatal: Validation dataset missing at {val_path}"

    print(f"Train dataset: {train_path} ({train_path.stat().st_size} bytes)")
    print(f"Val dataset:   {val_path} ({val_path.stat().st_size} bytes)")

    # Model configuration - 3072 default context (configurable via --max-seq-length)
    max_seq_length = args.max_seq_length
    bf16 = True
    fp16 = False
    dtype = torch.bfloat16

    # Configure BitsAndBytes 4-bit quantization (linear FP4 without double quant distortion)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="fp4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=False,
    )

    # Base model candidates: prioritizing w4a16-ct primary, followed by q4_0-unquantized fallback
    local_model_path = Path(args.local_model_dir)
    candidate_models = []
    if (local_model_path / "config.json").exists():
        candidate_models.append(str(local_model_path))
    else:
        candidate_models.append("/opt/model")
    candidate_models.extend([
        "google/gemma-4-31b-it-qat-w4a16-ct",
        "google/gemma-4-31B-it-qat-q4_0-unquantized",
        "google/gemma-4-31b-it",
    ])
    # Deduplicate while preserving order
    candidate_models = list(dict.fromkeys(candidate_models))

    model = None
    tokenizer = None
    for cand in candidate_models:
        if "bnb-4bit" in cand.lower():
            print(f"Skipping forbidden NF4 model candidate: {cand}")
            continue

        is_pack_quant = is_pack_quantized_candidate(cand)
        print(f"Attempting to load model from: {cand} (pack_quantized={is_pack_quant})...")
        try:
            if is_pack_quant:
                # Primary loader path for compressed-tensors INT4 w4a16-ct
                try:
                    model, tokenizer = FastLanguageModel.from_pretrained(
                        model_name=cand,
                        max_seq_length=max_seq_length,
                        dtype=dtype,
                        load_in_4bit=False,
                        use_exact_model_name=True,
                        token=args.hf_token,
                    )
                except TypeError:
                    model, tokenizer = FastLanguageModel.from_pretrained(
                        model_name=cand,
                        max_seq_length=max_seq_length,
                        dtype=dtype,
                        load_in_4bit=False,
                        token=args.hf_token,
                    )
            else:
                # Fallback loader path for q4_0-unquantized with Linear FP4 BitsAndBytes
                try:
                    model, tokenizer = FastLanguageModel.from_pretrained(
                        model_name=cand,
                        max_seq_length=max_seq_length,
                        dtype=dtype,
                        load_in_4bit=True,
                        quantization_config=bnb_config,
                        token=args.hf_token,
                    )
                except TypeError:
                    model, tokenizer = FastLanguageModel.from_pretrained(
                        model_name=cand,
                        max_seq_length=max_seq_length,
                        dtype=dtype,
                        load_in_4bit=True,
                        token=args.hf_token,
                    )
            print(f"Successfully loaded {cand}!")
            break
        except Exception as e:
            err_str = str(e)
            if is_pack_quant and ("load_in_4bit" in err_str or "BitsAndBytes" in err_str):
                print(f"Retrying {cand} with BitsAndBytes FP4 fallback...")
                try:
                    model, tokenizer = FastLanguageModel.from_pretrained(
                        model_name=cand,
                        max_seq_length=max_seq_length,
                        dtype=dtype,
                        load_in_4bit=True,
                        quantization_config=bnb_config,
                        token=args.hf_token,
                    )
                    print(f"Successfully loaded {cand} via FP4 fallback!")
                    break
                except Exception as retry_err:
                    print(f"Retry failed for {cand}: {retry_err}")
            elif not is_pack_quant and ("CompressedTensors" in err_str or "pack-quantized" in err_str):
                print(f"Retrying {cand} with pack-quantized load_in_4bit=False...")
                try:
                    model, tokenizer = FastLanguageModel.from_pretrained(
                        model_name=cand,
                        max_seq_length=max_seq_length,
                        dtype=dtype,
                        load_in_4bit=False,
                        use_exact_model_name=True,
                        token=args.hf_token,
                    )
                    print(f"Successfully loaded {cand} via pack-quantized retry!")
                    break
                except Exception as retry_err:
                    print(f"Retry failed for {cand}: {retry_err}")

            print(f"Failed loading {cand}: {e}")
            continue
    if model is None:
        print("Fatal: Could not load any candidate Gemma model.", file=sys.stderr)
        sys.exit(1)
    if hasattr(tokenizer, "tokenizer"):
        tokenizer = tokenizer.tokenizer

    # Configure Rank-8 LoRA targeting attention projections only (freeze MLPs)
    print("Configuring Rank-8 LoRA (q_proj, v_proj, o_proj)...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=8,
        target_modules=["q_proj", "v_proj", "o_proj"],
        lora_alpha=16,
        lora_dropout=0.0,
        bias="none",
        use_rslora=False,
        use_gradient_checkpointing="unsloth",
        random_state=3407,
    )
    model.print_trainable_parameters()

    # Ingest datasets
    print("Loading Hugging Face datasets from JSONL...")
    train_dataset = load_dataset("json", data_files=str(train_path), split="train")
    val_dataset = load_dataset("json", data_files=str(val_path), split="train")
    print(f"Loaded: train={len(train_dataset)}, val={len(val_dataset)}")

    # Preflight probe sample selection
    if args.preflight_probe:
        print("Preflight probe mode: selecting 5 training samples and 5 validation probe prompts...")
        probe_count = min(5, len(val_dataset))
        probe_prompts = [val_dataset[i]["prefix_text"] for i in range(probe_count)]
        train_dataset = train_dataset.select(range(min(5, len(train_dataset))))
        val_dataset = val_dataset.select(range(probe_count))
    else:
        probe_prompts = []

    print("Pre-tokenizing datasets with prefix-delta loss masking...")
    train_columns = list(train_dataset.column_names)
    val_columns = list(val_dataset.column_names)

    def tokenize_with_prefix_mask(example):
        full_text = example.get("full_text") or example.get("text", "")
        prefix_text = example["prefix_text"]
        full_ids = tokenizer(text=full_text, add_special_tokens=False)["input_ids"]
        prefix_ids = tokenizer(text=prefix_text, add_special_tokens=False)["input_ids"]
        completion_len = max(1, len(full_ids) - len(prefix_ids))
        if len(full_ids) > max_seq_length:
            full_ids = full_ids[-max_seq_length:]
        num_completion = min(completion_len, len(full_ids))
        num_prefix = len(full_ids) - num_completion
        labels = [-100] * num_prefix + full_ids[num_prefix:]
        return {"input_ids": full_ids, "attention_mask": [1] * len(full_ids), "labels": labels}

    train_dataset = train_dataset.map(
        tokenize_with_prefix_mask,
        remove_columns=train_columns,
        desc="Tokenizing train dataset with prefix-delta masking",
    )
    val_dataset = val_dataset.map(
        tokenize_with_prefix_mask,
        remove_columns=val_columns,
        desc="Tokenizing val dataset with prefix-delta masking",
    )
    print(f"Tokenization complete. Sample input_ids length: {len(train_dataset[0]['input_ids'])}")

    pad_token_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id
    if pad_token_id is None:
        pad_token_id = 0
    data_collator = PrefixDeltaDataCollator(pad_token_id=pad_token_id)

    # Training arguments tuned for L4 24GB GPU
    max_steps = args.max_steps if args.max_steps is not None else (10 if args.preflight_probe else 170)
    warmup_steps = 2 if args.preflight_probe else 15
    logging_steps = 1 if args.preflight_probe else 5

    training_args_kwargs = {
        "output_dir": str(OUTPUT_DIR / "checkpoints"),
        "per_device_train_batch_size": 1,
        "gradient_accumulation_steps": args.gradient_accumulation_steps,
        "gradient_checkpointing": True,
        "warmup_steps": warmup_steps,
        "num_train_epochs": args.num_train_epochs,
        "max_steps": max_steps,
        "learning_rate": args.learning_rate,
        "fp16": fp16,
        "bf16": bf16,
        "logging_steps": logging_steps,
        "eval_strategy": "no",
        "optim": "paged_adamw_8bit",
        "weight_decay": 0.01,
        "max_grad_norm": 1.0,
        "lr_scheduler_type": "cosine",
        "seed": 3407,
        "report_to": "none",
        "save_strategy": "no",
        "remove_unused_columns": False,
    }

    try:
        training_args = TrainingArguments(
            neftune_noise_alpha=None,
            **training_args_kwargs,
        )
    except TypeError:
        training_args = TrainingArguments(
            **training_args_kwargs,
        )

    # Initialize Trainer with pre-tokenized collator
    from transformers import Trainer
    trainer = Trainer(
        model=model,
        train_dataset=train_dataset,
        eval_dataset=None,
        data_collator=data_collator,
        args=training_args,
    )

    print("=== Commencing Model Fine-Tuning ===")
    train_stats = trainer.train()
    print("Fine-tuning completed successfully!")
    print(train_stats)

    # If preflight probe is enabled, run generation on the 5 probe prompts
    if args.preflight_probe:
        print("\n=== Running Preflight Generation Probe on 5 Validation Prompts ===")
        if hasattr(FastLanguageModel, "for_inference"):
            FastLanguageModel.for_inference(model)
        else:
            model.eval()

        device = next(model.parameters()).device
        for idx, prompt in enumerate(probe_prompts):
            inputs = tokenizer(text=[prompt], return_tensors="pt", add_special_tokens=False).to(device)
            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=256,
                    use_cache=True,
                    pad_token_id=pad_token_id,
                )
            gen_tokens = outputs[0][inputs["input_ids"].shape[1]:]
            completion = tokenizer.decode(gen_tokens, skip_special_tokens=False)
            print(f"[Probe Sample {idx+1}] Output preview: {repr(completion[:120])}")
            assert completion.startswith("<|tool_call>call:"), (
                f"Probe sample {idx+1} failed: completion does not start with '<|tool_call>call:'. Got: {repr(completion[:80])}"
            )
            assert "<|channel>thought" not in completion, (
                f"Probe sample {idx+1} failed: '<|channel>thought' found in completion: {repr(completion[:80])}"
            )
            assert "<|think|>" not in completion, (
                f"Probe sample {idx+1} failed: '<|think|>' found in completion: {repr(completion[:80])}"
            )
        print("Preflight probe PASSED: all probe completions generated valid tool calls with zero thought tokens.")

    # Export adapter weights and normalize for vLLM serving
    print(f"Saving PEFT adapter weights to {OUTPUT_DIR}...")
    model.save_pretrained(str(OUTPUT_DIR))

    print("Normalizing adapter weights for vLLM serving...")
    norm_ok, norm_msg = normalize_adapter_for_vllm(OUTPUT_DIR)
    if not norm_ok:
        print(f"FATAL: Adapter normalization failed: {norm_msg}", file=sys.stderr)
        sys.exit(1)
    print(f"Adapter normalization succeeded: {norm_msg}")

    print("=== Export Complete ===")
    for p in sorted(OUTPUT_DIR.iterdir()):
        if p.is_file():
            print(f"  {p.name}: {p.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
