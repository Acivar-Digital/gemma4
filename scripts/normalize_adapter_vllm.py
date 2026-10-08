#!/usr/bin/env python3
"""Normalize and verify Unsloth / PEFT Gemma 4 LoRA adapters for vLLM serving.

Ground Truth Architecture Invariants (from Research Report Gemma4_Unsloth_LoRA_Adapter_Settings_Eng):
1. vLLM Gemma4ForConditionalGeneration expects keys under:
     base_model.model.language_model.model.layers.{i}.self_attn.{q,v,o}_proj.lora_{A,B}.weight
   whereas standard PEFT / Unsloth (text_only) saves keys under:
     base_model.model.model.layers.{i}.self_attn.{q,v,o}_proj.lora_{A,B}.weight
   If mismatched, vLLM's LoRAModel silently skips the adapter and serves base model weights!
2. Module count: exactly 170 modules (60 q_proj + 50 v_proj + 60 o_proj; 10 global layers
   have attention_k_eq_v=True and omit v_proj). Total tensors: 170 * 2 = 340 tensors.
3. Precision: all LoRA weights MUST be torch.bfloat16. Any FP32 tensors are recast.
"""

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Tuple

import torch
from safetensors.torch import load_file, save_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("normalize_adapter_vllm")

EXPECTED_MODULES = {"q_proj", "v_proj", "o_proj"}
TOTAL_EXPECTED_MODULES = 170
TOTAL_EXPECTED_TENSORS = 340
TARGET_PREFIX = "base_model.model.language_model.model.layers."


def normalize_adapter_for_vllm(adapter_dir: Path, output_dir: Path = None) -> Tuple[bool, str]:
    """Reads adapter_model.safetensors and adapter_config.json, normalizes keys to vLLM format."""
    adapter_dir = Path(adapter_dir)
    if output_dir is None:
        output_dir = adapter_dir
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    weights_path = adapter_dir / "adapter_model.safetensors"
    config_path = adapter_dir / "adapter_config.json"

    if not weights_path.exists():
        return False, f"Missing safetensors weights at {weights_path}"
    if not config_path.exists():
        return False, f"Missing adapter config at {config_path}"

    logger.info(f"Loading adapter tensors from {weights_path}")
    tensors = load_file(str(weights_path))
    logger.info(f"Found {len(tensors)} tensors in {weights_path.name}")

    normalized_tensors: Dict[str, torch.Tensor] = {}
    renamed_count = 0
    fp32_recast_count = 0

    for key, val in tensors.items():
        new_key = key
        # Case A: Standard PEFT text model saved without multimodal prefix
        if "base_model.model.model.layers." in key and "language_model." not in key:
            new_key = key.replace("base_model.model.model.layers.", TARGET_PREFIX)
            renamed_count += 1
        # Case B: Model saved with base_model.model.layers.
        elif "base_model.model.layers." in key and "language_model." not in key:
            new_key = key.replace("base_model.model.layers.", TARGET_PREFIX)
            renamed_count += 1

        # Force torch.bfloat16 precision
        if val.dtype != torch.bfloat16:
            val = val.to(torch.bfloat16)
            fp32_recast_count += 1

        normalized_tensors[new_key] = val

    logger.info(f"Renamed {renamed_count} keys to vLLM multimodal namespace.")
    if fp32_recast_count > 0:
        logger.info(f"Recast {fp32_recast_count} tensors to torch.bfloat16.")

    # Update adapter_config.json
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    config["target_modules"] = sorted(list(EXPECTED_MODULES))
    config["r"] = 8
    config["lora_alpha"] = 16

    # Save outputs
    out_weights = output_dir / "adapter_model.safetensors"
    out_config = output_dir / "adapter_config.json"

    save_file(normalized_tensors, str(out_weights), metadata={"format": "pt"})
    with open(out_config, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    logger.info(f"Serialized normalized adapter to {output_dir}")
    return verify_adapter(output_dir)


def verify_adapter(adapter_dir: Path) -> Tuple[bool, str]:
    """Strict verification gate for normalized adapter assets."""
    adapter_dir = Path(adapter_dir)
    weights_path = adapter_dir / "adapter_model.safetensors"
    config_path = adapter_dir / "adapter_config.json"

    if not weights_path.exists():
        return False, f"Missing {weights_path}"
    if not config_path.exists():
        return False, f"Missing {config_path}"

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    if config.get("r") != 8 or config.get("lora_alpha") != 16:
        return False, f"LoRA rank/alpha mismatch: r={config.get('r')}, alpha={config.get('lora_alpha')}"

    state_dict = load_file(str(weights_path))
    if len(state_dict) != TOTAL_EXPECTED_TENSORS:
        return False, f"Tensor count mismatch: expected {TOTAL_EXPECTED_TENSORS}, got {len(state_dict)}"

    for name, tensor in state_dict.items():
        if not name.startswith(TARGET_PREFIX):
            return False, f"Key {name} missing required vLLM prefix {TARGET_PREFIX}"
        if tensor.dtype != torch.bfloat16:
            return False, f"Key {name} has invalid dtype {tensor.dtype}, must be torch.bfloat16"

    size_mb = os.path.getsize(weights_path) / (1024 * 1024)
    if size_mb > 35.0:
        return False, f"Adapter file size {size_mb:.2f} MB exceeds 35.0 MB limit"

    logger.info(f"VERIFICATION PASS: All 340 tensors match vLLM spec ({size_mb:.2f} MB, BF16).")
    return True, "Adapter verified successfully."


def main():
    parser = argparse.ArgumentParser(description="Normalize and verify Gemma 4 LoRA adapter for vLLM.")
    parser.add_argument("adapter_dir", type=Path, help="Directory containing adapter assets")
    parser.add_argument("--output_dir", type=Path, default=None, help="Optional output directory")
    parser.add_argument("--verify-only", action="store_true", help="Only verify existing adapter")
    args = parser.parse_args()

    if args.verify_only:
        ok, msg = verify_adapter(args.adapter_dir)
    else:
        ok, msg = normalize_adapter_for_vllm(args.adapter_dir, args.output_dir)

    if not ok:
        logger.error(f"FAILURE: {msg}")
        exit(1)
    logger.info(f"SUCCESS: {msg}")


if __name__ == "__main__":
    main()
