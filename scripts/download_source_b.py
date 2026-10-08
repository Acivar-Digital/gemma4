#!/usr/bin/env python3
"""Downloads all three Source B trajectory datasets cited in the Deep Research report:

1. SWE-bench/SWE-smith-trajectories ('tool' split, 8 shards, ~1.00 GB) -> data/source_b/swe_smith/
2. nebius/SWE-rebench-openhands-trajectories (trajectories.parquet + metadata, ~1.94 GB) -> data/source_b/swe_rebench/
3. nvidia/SWE-Zero-openhands-trajectories ('train' split, 64 shards, ~11.37 GB) -> data/source_b/swe_zero/

All downloads use atomic .tmp writes and exact Content-Length byte verification.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
import time
import urllib.request
from pathlib import Path

SOURCES = [
    {
        "name": "SWE-bench/SWE-smith-trajectories",
        "base_url": "https://huggingface.co/datasets/SWE-bench/SWE-smith-trajectories/resolve/main/",
        "target_dir": Path("data/source_b/swe_smith"),
        "files": ["README.md"] + [f"data/tool-{i:05d}-of-00008.parquet" for i in range(8)],
    },
    {
        "name": "nebius/SWE-rebench-openhands-trajectories",
        "base_url": "https://huggingface.co/datasets/nebius/SWE-rebench-openhands-trajectories/resolve/main/",
        "target_dir": Path("data/source_b/swe_rebench"),
        "files": [
            "LICENSE",
            "README.md",
            "config.toml",
            "tools.json",
            "trajectories.parquet",
        ],
    },
    {
        "name": "nvidia/SWE-Zero-openhands-trajectories",
        "base_url": "https://huggingface.co/datasets/nvidia/SWE-Zero-openhands-trajectories/resolve/main/",
        "target_dir": Path("data/source_b/swe_zero"),
        "files": ["README.md"] + [f"data/train-{i:05d}-of-00064.parquet" for i in range(64)],
    },
]


def download_file(base_url: str, rel_path: str, target_dir: Path, max_retries: int = 3) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(rel_path).name
    dest_path = target_dir / filename
    temp_path = target_dir / f"{filename}.tmp"
    url = base_url + rel_path

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "gemma4-dev-agent/1.0 (Python urllib)"},
            )

            with urllib.request.urlopen(req, timeout=60) as resp:
                expected_size = int(resp.headers.get("Content-Length", 0))

                if expected_size > 0 and dest_path.exists() and dest_path.stat().st_size == expected_size:
                    print(
                        f"[SKIP] {target_dir.name}/{filename} already exists ({expected_size / (1024*1024):.2f} MB)",
                        flush=True,
                    )
                    return dest_path

                print(
                    f"[START] {target_dir.name}/{filename} ({expected_size / (1024*1024):.2f} MB)...",
                    flush=True,
                )
                start_time = time.time()
                downloaded = 0
                with open(temp_path, "wb") as f_out:
                    chunk_size = 4 * 1024 * 1024  # 4 MB
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f_out.write(chunk)
                        downloaded += len(chunk)

            if expected_size > 0 and temp_path.stat().st_size != expected_size:
                raise IOError(
                    f"Size mismatch for {filename}: expected {expected_size} bytes, got {temp_path.stat().st_size}"
                )

            temp_path.replace(dest_path)
            elapsed = time.time() - start_time
            mb = dest_path.stat().st_size / (1024 * 1024)
            rate = mb / max(elapsed, 0.001)
            print(
                f"[DONE]  {target_dir.name}/{filename} ({mb:.2f} MB in {elapsed:.1f}s @ {rate:.1f} MB/s)",
                flush=True,
            )
            return dest_path
        except Exception as exc:
            if attempt == max_retries:
                raise RuntimeError(f"Failed downloading {url} after {max_retries} attempts: {exc}") from exc
            time.sleep(2 * attempt)
    return dest_path


def main():
    print("=" * 72)
    print("   DOWNLOADING ALL 3 CITED SOURCE B TRAJECTORY DATASETS")
    print("=" * 72)
    total_start = time.time()

    tasks = []
    for src in SOURCES:
        for rel_path in src["files"]:
            tasks.append((src["name"], src["base_url"], rel_path, src["target_dir"]))

    completed_paths = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        future_to_task = {
            pool.submit(download_file, base_url, rel_path, target_dir): (name, rel_path)
            for name, base_url, rel_path, target_dir in tasks
        }
        for future in as_completed(future_to_task):
            dest = future.result()
            completed_paths.append(dest)

    total_elapsed = time.time() - total_start
    total_bytes = sum(p.stat().st_size for p in completed_paths)
    total_gb = total_bytes / (1024 ** 3)

    print("\n" + "=" * 72)
    for src in SOURCES:
        tdir = src["target_dir"]
        files = sorted(p for p in tdir.iterdir() if p.is_file() and not p.name.endswith(".tmp"))
        gb = sum(p.stat().st_size for p in files) / (1024 ** 3)
        print(f"  - {src['name']:42s} -> {tdir} ({len(files)} files, {gb:.2f} GB)")
    print("-" * 72)
    print(f"Total Files:   {len(completed_paths)}")
    print(f"Total Size:    {total_gb:.2f} GB ({total_bytes / (1024**2):.2f} MB)")
    print(f"Total Time:    {total_elapsed:.1f}s")
    print("=" * 72)


if __name__ == "__main__":
    main()
