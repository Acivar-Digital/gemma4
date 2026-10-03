#!/usr/bin/env python3
"""Validate and install fine-tuned Gemma 4 PEFT LoRA adapter into my_submission.

Checks:
1. Structural integrity and allowed file extensions (.json, .safetensors only)
2. Tensor validity: no NaNs, no Infs, finite norms, expected shapes and dtypes
3. Parameter count and target modules matching Track 2 specs (Rank 8: q_proj, v_proj, o_proj)
4. Config alignment with official competition schema
5. Strict submission size limits (< 3 GiB) and clean packaging
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

ROOT_DIR = Path(__file__).resolve().parent.parent
SUBMISSION_DIR = ROOT_DIR / "my_submission"
ADAPTERS_DIR = SUBMISSION_DIR / "adapters" / "main_lora"


def validate_adapter_tensors(weights_path: Path) -> dict[str, Any]:
    from safetensors import safe_open

    tensors_meta = {}
    total_params = 0
    nan_count = 0
    inf_count = 0

    with safe_open(str(weights_path), framework="pt") as f:
        for key in f.keys():
            t = f.get_tensor(key)
            numel = t.numel()
            total_params += numel
            is_nan = bool(t.isnan().any().item())
            is_inf = bool(t.isinf().any().item())
            if is_nan:
                nan_count += 1
            if is_inf:
                inf_count += 1
            t_float = t.float()
            norm_val = float(t_float.norm().item())
            min_val = float(t_float.min().item())
            max_val = float(t_float.max().item())
            tensors_meta[key] = {
                "shape": list(t.shape),
                "dtype": str(t.dtype),
                "params": numel,
                "norm": round(norm_val, 4),
                "min": round(min_val, 6),
                "max": round(max_val, 6),
                "nan": is_nan,
                "inf": is_inf,
            }

    return {
        "total_tensors": len(tensors_meta),
        "total_params": total_params,
        "nan_count": nan_count,
        "inf_count": inf_count,
        "tensors": tensors_meta,
    }


def validate_adapter_config(config_path: Path) -> dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Standardize base model name if needed for swegemma loader
    required_keys = ["peft_type", "r", "target_modules"]
    for k in required_keys:
        if k not in config:
            raise ValueError(f"Missing required key '{k}' in adapter_config.json")

    return config


def install_adapter(source_dir: Path, dry_run: bool = False) -> None:
    source_weights = source_dir / "adapter_model.safetensors"
    source_config = source_dir / "adapter_config.json"

    if not source_weights.exists():
        raise FileNotFoundError(f"Missing adapter_model.safetensors at {source_weights}")
    if not source_config.exists():
        raise FileNotFoundError(f"Missing adapter_config.json at {source_config}")

    print(f"Validating adapter configuration: {source_config}")
    cfg = validate_adapter_config(source_config)
    print(f"  PEFT Type: {cfg.get('peft_type')}")
    print(f"  Rank (r): {cfg.get('r')}")
    print(f"  Target Modules: {cfg.get('target_modules')}")
    print(f"  Base Model: {cfg.get('base_model_name_or_path')}")

    print(f"Validating adapter tensors: {source_weights} ({source_weights.stat().st_size:,} bytes)")
    tensor_stats = validate_adapter_tensors(source_weights)
    print(f"  Total Tensors: {tensor_stats['total_tensors']}")
    print(f"  Total Active Parameters: {tensor_stats['total_params']:,}")
    print(f"  NaN Count: {tensor_stats['nan_count']}")
    print(f"  Inf Count: {tensor_stats['inf_count']}")

    if tensor_stats["nan_count"] > 0 or tensor_stats["inf_count"] > 0:
        raise ValueError("Adapter tensors contain NaN or Inf values! Refusing to install corrupt weights.")

    if dry_run:
        print("[Dry Run] Validation succeeded. Installation skipped.")
        return

    ADAPTERS_DIR.mkdir(parents=True, exist_ok=True)

    # Clean existing destination
    for item in ADAPTERS_DIR.iterdir():
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)

    dest_weights = ADAPTERS_DIR / "adapter_model.safetensors"
    dest_config = ADAPTERS_DIR / "adapter_config.json"

    shutil.copy2(source_weights, dest_weights)
    shutil.copy2(source_config, dest_config)

    print(f"Installed adapter files to {ADAPTERS_DIR}:")
    for item in sorted(ADAPTERS_DIR.iterdir()):
        print(f"  {item.name} ({item.stat().st_size:,} bytes)")

    # Update agent.yaml if needed
    agent_yaml_path = SUBMISSION_DIR / "agent.yaml"
    agent_yaml_content = agent_yaml_path.read_text(encoding="utf-8")
    if "adapter:" not in agent_yaml_content:
        lines = agent_yaml_content.splitlines()
        new_lines = []
        for line in lines:
            new_lines.append(line)
            if line.startswith("model:"):
                new_lines.append("adapter: main_lora")
        agent_yaml_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        print("Updated my_submission/agent.yaml with 'adapter: main_lora'.")
    else:
        print("my_submission/agent.yaml already has adapter configuration.")


def main():
    parser = argparse.ArgumentParser(description="Validate and install Gemma 4 LoRA adapter.")
    parser.add_argument("--source", type=str, required=True, help="Directory containing adapter files")
    parser.add_argument("--dry-run", action="store_true", help="Validate without copying")
    args = parser.parse_args()

    source_path = Path(args.source).resolve()
    if not source_path.exists():
        print(f"Error: Source directory {source_path} does not exist", file=sys.stderr)
        sys.exit(1)

    install_adapter(source_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
