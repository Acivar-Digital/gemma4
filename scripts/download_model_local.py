#!/usr/bin/env python3
"""
download_model_local.py
Downloads and verifies Gemma 4 31B base model locally on user hard drive.
Eliminates repeated searching on Hugging Face and avoids any cloud storage fees on GCP.

Target Default: unsloth/gemma-4-31B-it-unsloth-bnb-4bit (~17.5 GB)
Target Directory: ./models/gemma-4-31B-it-unsloth-bnb-4bit/
"""

import os
import sys
import shutil
import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_ID = "unsloth/gemma-4-31B-it-unsloth-bnb-4bit"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "models" / "gemma-4-31B-it-unsloth-bnb-4bit"

def load_hf_token() -> str | None:
    """Load HF_TOKEN from environment or .env.gcp."""
    token = os.environ.get("HF_TOKEN")
    if token:
        return token
    
    env_file = REPO_ROOT / ".env.gcp"
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("export HF_TOKEN="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    return val
                elif line.startswith("HF_TOKEN="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    return val
    return None

def check_disk_space(target_dir: Path, min_gb_required: float = 22.0) -> float:
    """Check free space in gigabytes on the target directory drive."""
    parent = target_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    total, used, free = shutil.disk_usage(parent)
    free_gb = free / (1024 ** 3)
    if free_gb < min_gb_required:
        print(f"Error: Insufficient disk space! Required: {min_gb_required:.1f} GB, Available: {free_gb:.1f} GB", file=sys.stderr)
        sys.exit(1)
    return free_gb

def main():
    parser = argparse.ArgumentParser(description="Download Gemma 4 base model to local hard drive.")
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID, help=f"Hugging Face model ID (default: {DEFAULT_MODEL_ID})")
    parser.add_argument("--dest", type=Path, default=DEFAULT_OUTPUT_DIR, help="Destination directory on hard drive")
    parser.add_argument("--token", default=None, help="Hugging Face read token (defaults to .env.gcp)")
    args = parser.parse_args()

    token = args.token or load_hf_token()
    if not token:
        print("Warning: No HF_TOKEN found in environment or .env.gcp. Gated repos may fail.", file=sys.stderr)

    dest_dir: Path = args.dest.resolve()
    print("=" * 80)
    print("Local Model Downloader for Gemma 4 (Zero GCP Storage Cost)")
    print("=" * 80)
    print(f"  Model ID        : {args.model_id}")
    print(f"  Destination Dir : {dest_dir}")
    
    free_gb = check_disk_space(dest_dir, min_gb_required=20.0)
    print(f"  Free Hard Drive : {free_gb:.2f} GB available")
    print("=" * 80)

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("Error: huggingface_hub is not installed in the active environment.", file=sys.stderr)
        sys.exit(1)

    print(f"\nInitiating snapshot download for '{args.model_id}'...")
    print("Files will be cached and assembled directly into the local models folder.\n")

    local_path = snapshot_download(
        repo_id=args.model_id,
        local_dir=str(dest_dir),
        token=token,
        local_dir_use_symlinks=False,
        resume_download=True,
    )

    # Verification of downloaded artifacts
    print("\n" + "=" * 80)
    print("Verifying Downloaded Artifacts:")
    print("=" * 80)

    required_configs = ["config.json", "tokenizer.json"]
    missing = [c for c in required_configs if not (dest_dir / c).exists()]
    if missing:
        print(f"Error: Missing essential model configurations: {missing}", file=sys.stderr)
        sys.exit(1)

    total_size_bytes = 0
    file_manifest = []
    for p in sorted(dest_dir.rglob("*")):
        if p.is_file():
            size = p.stat().st_size
            total_size_bytes += size
            rel_path = p.relative_to(dest_dir)
            file_manifest.append({"path": str(rel_path), "size_bytes": size})
            if p.suffix in (".safetensors", ".json", ".model"):
                print(f"  ✓ {str(rel_path):<40} ({size / (1024*1024):8.2f} MB)")

    total_gb = total_size_bytes / (1024 ** 3)
    print("-" * 80)
    print(f"Total Local Footprint: {total_gb:.2f} GB ({len(file_manifest)} files)")
    
    # Save receipt
    receipt = {
        "model_id": args.model_id,
        "local_dir": str(dest_dir),
        "total_size_gb": round(total_gb, 3),
        "files_count": len(file_manifest),
    }
    with open(dest_dir / "download_manifest.json", "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2)

    print(f"Download receipt written to: {dest_dir / 'download_manifest.json'}")
    print("✅ Model successfully saved permanently to your local hard drive.")
    print("Zero GCP storage fees incurred!")

if __name__ == "__main__":
    main()
