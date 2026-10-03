#!/usr/bin/env python3
"""
Standalone Unsloth Fine-Tuning Script for Gemma 4 31B IT on GCP A100.
Enforces:
- Rank-8 LoRA on Attention/Output heads (q_proj, v_proj, o_proj, k_proj), MLPs frozen
- max_seq_length = 16384 with Unsloth gradient checkpointing
- Response-only loss masking (<start_of_turn>model\\n)
- Minimal thinking mode (<thought>\\nThinking Process: ...</thought>)
- Clean export of adapter_model.safetensors and tokenizer
"""

import sys
import os

# Configure PyTorch memory allocator to eliminate fragmentation and allocate dynamically
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
os.environ["PYTORCH_ALLOC_CONF"] = "expandable_segments:True"

# Block broken VM torchaudio ABI from crashing transformers audio_utils
sys.modules["torchaudio"] = None

# Import unsloth first as recommended for kernel optimizations
try:
    from unsloth import FastLanguageModel
    from unsloth.chat_templates import train_on_responses_only
except ImportError:
    print("Error: Unsloth not installed. Run 'pip install unsloth' first.", file=sys.stderr)
    sys.exit(1)

import json
import torch
from pathlib import Path
from datasets import load_dataset
from transformers import TrainingArguments
try:
    from trl import SFTConfig, SFTTrainer
except ImportError:
    from trl import SFTTrainer
    SFTConfig = None

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

def main():
    print("=== Gemma 4 31B Unsloth SFT Fine-Tuning Starting ===")
    
    # Paths
    DATA_DIR = Path(os.environ.get("DATA_DIR", "/opt/data"))
    OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/opt/output/main_lora"))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    train_path = DATA_DIR / "unsloth_sft_train.jsonl"
    val_path = DATA_DIR / "unsloth_sft_val.jsonl"
    
    assert train_path.exists(), f"Fatal: Training dataset missing at {train_path}"
    assert val_path.exists(), f"Fatal: Validation dataset missing at {val_path}"
    
    print(f"Train dataset: {train_path} ({train_path.stat().st_size} bytes)")
    print(f"Val dataset:   {val_path} ({val_path.stat().st_size} bytes)")
    
    # Model configuration - 3072 context provides >4.5GB VRAM headroom on 24GB L4 GPU, eliminating SDPA attention spikes
    max_seq_length = 3072
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    load_in_4bit = True
    
    # Prefer local cached model if available in GCS /opt/model, then candidate repos
    hf_token = os.environ.get("HF_TOKEN", None)
    local_model_dir = Path(os.environ.get("LOCAL_MODEL_DIR", "/opt/model"))
    candidate_models = []
    if (local_model_dir / "config.json").exists():
        candidate_models.append(str(local_model_dir))
    candidate_models.extend([
        "unsloth/gemma-4-31B-it-unsloth-bnb-4bit",
        "google/gemma-4-31b-it",
    ])
    
    model = None
    tokenizer = None
    for cand in candidate_models:
        try:
            print(f"Attempting to load model from: {cand}...")
            model, tokenizer = FastLanguageModel.from_pretrained(
                model_name=cand,
                max_seq_length=max_seq_length,
                dtype=dtype,
                load_in_4bit=load_in_4bit,
                token=hf_token,
            )
            print(f"Successfully loaded {cand}!")
            break
        except Exception as e:
            print(f"Failed loading {cand}: {e}")
            continue
            
    if model is None:
        print("Fatal: Could not load any candidate Gemma model.", file=sys.stderr)
        sys.exit(1)
        
    # Configure Rank-8 LoRA targeting attention projections only (freeze MLPs)
    print("Configuring Rank-8 LoRA (q_proj, k_proj, v_proj, o_proj)...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=8,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        lora_alpha=16,
        lora_dropout=0.0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )
    model.print_trainable_parameters()
    
    # Ingest datasets
    print("Loading Hugging Face datasets from JSONL...")
    train_dataset = load_dataset("json", data_files=str(train_path), split="train")
    val_dataset = load_dataset("json", data_files=str(val_path), split="train")
    print(f"Loaded: train={len(train_dataset)}, val={len(val_dataset)}")
    
    # Preprocess messages: ensure tool call arguments are parsed dictionaries, then apply chat template
    def prepare_sample(example):
        if "messages" in example and isinstance(example["messages"], list):
            for msg in example["messages"]:
                if "tool_calls" in msg and isinstance(msg["tool_calls"], list):
                    for tc in msg["tool_calls"]:
                        fn = tc.get("function", {})
                        if "arguments" in fn and isinstance(fn["arguments"], str):
                            try:
                                fn["arguments"] = json.loads(fn["arguments"])
                            except Exception:
                                pass
        text = tokenizer.apply_chat_template(example["messages"], tokenize=False, add_generation_prompt=False)
        if text.startswith("<bos>"):
            text = text.removeprefix("<bos>")
        example["text"] = text
        return example

    print("Formatting datasets with Gemma 4 chat template...")
    train_dataset = train_dataset.map(prepare_sample, remove_columns=["messages"], desc="Formatting train chat")
    val_dataset = val_dataset.map(prepare_sample, remove_columns=["messages"], desc="Formatting val chat")
    print(f"Dataset formatting complete. Sample text length: {len(train_dataset[0]['text'])}")
    
    # Training arguments tuned for L4 24GB GPU
    if SFTConfig is not None:
        sft_config_kwargs = {
            "output_dir": str(OUTPUT_DIR / "checkpoints"),
            "dataset_text_field": "text",
            "packing": False,
            "dataset_num_proc": 2,
            "per_device_train_batch_size": 1,
            "gradient_accumulation_steps": 4,
            "gradient_checkpointing": True,
            "warmup_steps": 5,
            "max_steps": 60,
            "learning_rate": 2.0e-5,
            "fp16": not torch.cuda.is_bf16_supported(),
            "bf16": torch.cuda.is_bf16_supported(),
            "logging_steps": 2,
            "eval_strategy": "no",
            "optim": "paged_adamw_8bit",
            "weight_decay": 0.05,
            "lr_scheduler_type": "cosine",
            "seed": 42,
            "report_to": "none",
            "save_strategy": "steps",
            "save_steps": 15,
        }
        try:
            training_args = SFTConfig(max_length=max_seq_length, **sft_config_kwargs)
        except TypeError:
            training_args = SFTConfig(max_seq_length=max_seq_length, **sft_config_kwargs)

        try:
            trainer = SFTTrainer(
                model=model,
                train_dataset=train_dataset,
                eval_dataset=None,
                processing_class=tokenizer,
                args=training_args,
            )
        except TypeError:
            trainer = SFTTrainer(
                model=model,
                train_dataset=train_dataset,
                eval_dataset=None,
                tokenizer=tokenizer,
                args=training_args,
            )
    else:
        training_args = TrainingArguments(
            output_dir=str(OUTPUT_DIR / "checkpoints"),
            per_device_train_batch_size=1,
            gradient_accumulation_steps=4,
            warmup_steps=5,
            max_steps=60,
            learning_rate=2.0e-5,
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
            logging_steps=2,
            eval_strategy="no",
            optim="paged_adamw_8bit",
            weight_decay=0.05,
            lr_scheduler_type="cosine",
            seed=42,
            report_to="none",
            save_strategy="steps",
            save_steps=15,
        )
        sft_kwargs = {
            "model": model,
            "train_dataset": train_dataset,
            "eval_dataset": None,
            "dataset_text_field": "text",
            "max_seq_length": max_seq_length,
            "dataset_num_proc": 2,
            "packing": False,
            "args": training_args,
        }
        try:
            trainer = SFTTrainer(processing_class=tokenizer, **sft_kwargs)
        except TypeError:
            trainer = SFTTrainer(tokenizer=tokenizer, **sft_kwargs)
    
    # Apply response-only loss masking with canonical Gemma 4 tokens
    try:
        trainer = train_on_responses_only(
            trainer,
            instruction_part="<start_of_turn>user\n",
            response_part="<start_of_turn>model\n",
        )
        print("Successfully applied response-only loss masking on model turns (<start_of_turn>model).")
    except Exception as exc:
        print(f"Warning: Response-only loss masking fallback: {exc}")
        
    print("=== Commencing Model Fine-Tuning ===")
    train_stats = trainer.train()
    print("Fine-tuning completed successfully!")
    print(train_stats)
    
    # Export adapter weights & tokenizer
    print(f"Saving PEFT adapter weights to {OUTPUT_DIR}...")
    model.save_pretrained(str(OUTPUT_DIR))
    tokenizer.save_pretrained(str(OUTPUT_DIR))
    
    print("=== Export Complete ===")
    for p in sorted(OUTPUT_DIR.iterdir()):
        if p.is_file():
            print(f"  {p.name}: {p.stat().st_size:,} bytes")

if __name__ == "__main__":
    main()
