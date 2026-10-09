#!/usr/bin/env python3
"""Parallel Parquet shard extractor for external Source B datasets (swe_smith and swe_zero).

Enforces:
1. 0% tasks.jsonl benchmark overlap.
2. 0% swe_rebench inclusion (only swe_smith and swe_zero).
3. 100% single-file .py patches only (is_single_file_py_patch).
4. Dual < 20 tool-call budget (< 20 clean calls AND < 20 Type-A negative calls, < 40 total).
5. 0 Type-B dumb negative calls (no failed edits, no FileNotFoundError, no blind thrashing).
6. Thinking turned OFF: assistant turns keep role='assistant' and omit 'reasoning'.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Set

import pyarrow.parquet as pq

# Ensure repo root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.sft_data_filters import (
    MAX_DIFF_LINES,
    classify_trajectory_steps,
    compact_observation,
    is_single_file_py_patch,
    load_benchmark_exclusion_set,
    sanitize_text,
    translate_tool_call,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("extract_source_b")

SOURCE_B_DIR = ROOT_DIR / "data" / "source_b"
TASKS_BENCHMARK_PATH = ROOT_DIR / "tasks.jsonl"


def _parse_swe_smith_row(row: Dict[str, Any], benchmark_exclusions: Set[str]) -> Dict[str, Any] | None:
    inst_id = row.get("instance_id", "")
    if not inst_id or inst_id in benchmark_exclusions or not row.get("resolved"):
        return None

    patch = row.get("patch") or ""
    if not is_single_file_py_patch(patch) or len(patch.splitlines()) > MAX_DIFF_LINES:
        return None

    raw_msgs = row.get("messages")
    if isinstance(raw_msgs, str):
        try:
            raw_msgs = json.loads(raw_msgs)
        except Exception:
            return None
    if not isinstance(raw_msgs, list) or len(raw_msgs) < 4:
        return None

    user_prompt = ""
    steps: List[Dict[str, Any]] = []
    context: Dict[str, Any] = {"repro_files": {}}

    for m in raw_msgs:
        r = m.get("role")
        if r == "user" and not user_prompt:
            user_prompt = sanitize_text(m.get("content", ""))
        elif r == "assistant":
            raw_tcs = m.get("tool_calls") or []
            if isinstance(raw_tcs, str):
                try:
                    raw_tcs = json.loads(raw_tcs)
                except Exception:
                    raw_tcs = []
            valid_tcs = []
            for tc in raw_tcs:
                fn = tc.get("function", {}) if isinstance(tc, dict) else {}
                name = fn.get("name", "")
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                if name == "think":
                    continue
                translated = translate_tool_call(name, args, context=context)
                if translated:
                    valid_tcs.append(translated)
            if valid_tcs:
                # If previous step was also assistant without tool response, overwrite or skip
                if steps and steps[-1].get("role") == "assistant":
                    steps.pop()
                steps.append(
                    {
                        "role": "assistant",
                        "tool_calls": [
                            {"id": f"call_{len(steps)}_{idx}", "type": "function", "function": tc}
                            for idx, tc in enumerate(valid_tcs)
                        ],
                    }
                )
                if any(tc.get("name") == "submit_patch" for tc in valid_tcs):
                    steps.append(
                        {
                            "role": "tool",
                            "name": "submit_patch",
                            "tool_call_id": steps[-1]["tool_calls"][0]["id"],
                            "content": "Patch submitted.",
                        }
                    )
                    break
        elif r == "tool" and steps and steps[-1].get("role") == "assistant":
            obs = compact_observation(m.get("content", ""))
            steps.append(
                {
                    "role": "tool",
                    "name": steps[-1]["tool_calls"][0]["function"]["name"],
                    "tool_call_id": steps[-1]["tool_calls"][0]["id"],
                    "content": obs,
                }
            )

    if steps and steps[-1].get("role") == "assistant":
        # Ensure final assistant step has a synthetic or terminal tool observation if needed,
        # or keep if it is submit_patch
        last_fn = steps[-1]["tool_calls"][0]["function"]["name"]
        if last_fn == "submit_patch":
            steps.append(
                {
                    "role": "tool",
                    "name": "submit_patch",
                    "tool_call_id": steps[-1]["tool_calls"][0]["id"],
                    "content": "Patch submitted.",
                }
            )
        else:
            steps.pop()

    if not user_prompt or len(steps) < 4:
        return None

    is_valid, stats = classify_trajectory_steps(steps)
    if not is_valid:
        return None

    return {
        "task_id": inst_id,
        "repo": inst_id.split("__")[0] if "__" in inst_id else "python",
        "source": "swe_smith",
        "user_prompt": user_prompt,
        "messages": steps,
        "stats": stats,
    }


def _parse_swe_zero_row(row: Dict[str, Any], benchmark_exclusions: Set[str]) -> Dict[str, Any] | None:
    inst_id = row.get("instance_id", "")
    patch = row.get("model_patch") or ""
    if not inst_id or inst_id in benchmark_exclusions:
        return None
    if not is_single_file_py_patch(patch) or len(patch.splitlines()) > MAX_DIFF_LINES:
        return None

    traj = row.get("trajectory") or []
    if not isinstance(traj, list) or len(traj) < 4:
        return None

    user_prompt = ""
    steps: List[Dict[str, Any]] = []
    context: Dict[str, Any] = {"repro_files": {}}

    for m in traj:
        r = m.get("role")
        content = m.get("content") or ""
        if r == "user" and not user_prompt:
            user_prompt = sanitize_text(content)
        elif r == "assistant":
            raw_tcs = m.get("tool_calls") or []
            valid_tcs = []
            for tc in raw_tcs:
                fn = tc.get("function", {}) if isinstance(tc, dict) else {}
                name = fn.get("name", "")
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                if name == "think":
                    continue
                translated = translate_tool_call(name, args, context=context)
                if translated:
                    valid_tcs.append(translated)
            if valid_tcs:
                if steps and steps[-1].get("role") == "assistant":
                    steps.pop()
                steps.append(
                    {
                        "role": "assistant",
                        "tool_calls": [
                            {"id": f"call_{len(steps)}_{idx}", "type": "function", "function": tc}
                            for idx, tc in enumerate(valid_tcs)
                        ],
                    }
                )
        elif r == "tool" and steps and steps[-1].get("role") == "assistant":
            obs = compact_observation(content)
            steps.append(
                {
                    "role": "tool",
                    "name": steps[-1]["tool_calls"][0]["function"]["name"],
                    "tool_call_id": steps[-1]["tool_calls"][0]["id"],
                    "content": obs,
                }
            )

    if steps and steps[-1].get("role") == "assistant":
        last_fn = steps[-1]["tool_calls"][0]["function"]["name"]
        if last_fn == "submit_patch":
            steps.append(
                {
                    "role": "tool",
                    "name": "submit_patch",
                    "tool_call_id": steps[-1]["tool_calls"][0]["id"],
                    "content": "Patch submitted.",
                }
            )
        else:
            steps.pop()

    if not user_prompt or len(steps) < 4:
        return None

    is_valid, stats = classify_trajectory_steps(steps)
    if not is_valid:
        return None

    return {
        "task_id": inst_id,
        "repo": row.get("repo") or (inst_id.split("__")[0] if "__" in inst_id else "python"),
        "source": "swe_zero",
        "user_prompt": user_prompt,
        "messages": steps,
        "stats": stats,
    }


def process_shard(shard_path_str: str, source: str, benchmark_exclusions: Set[str], per_shard_limit: int) -> List[Dict[str, Any]]:
    shard_path = Path(shard_path_str)
    results: List[Dict[str, Any]] = []
    seen_tasks: Set[str] = set()
    pf = pq.ParquetFile(shard_path)

    for batch in pf.iter_batches(batch_size=200):
        if len(results) >= per_shard_limit:
            break
        for row in batch.to_pylist():
            if len(results) >= per_shard_limit:
                break
            inst_id = row.get("instance_id", "")
            if inst_id in seen_tasks:
                continue
            parsed = (
                _parse_swe_smith_row(row, benchmark_exclusions)
                if source == "swe_smith"
                else _parse_swe_zero_row(row, benchmark_exclusions)
            )
            if parsed is not None:
                seen_tasks.add(inst_id)
                results.append(parsed)
    return results


def extract_source(source: str, limit: int, out_path: Path, max_workers: int = 4) -> List[Dict[str, Any]]:
    benchmark_exclusions = load_benchmark_exclusion_set(TASKS_BENCHMARK_PATH)
    if source == "swe_smith":
        shard_dir = SOURCE_B_DIR / "swe_smith"
        shards = sorted(shard_dir.glob("tool-*.parquet"))
    elif source == "swe_zero":
        shard_dir = SOURCE_B_DIR / "swe_zero"
        shards = sorted(shard_dir.glob("train-*.parquet"))[:8]
    else:
        raise ValueError(f"Unsupported source: {source} (swe_rebench is strictly dropped)")

    if not shards:
        raise FileNotFoundError(f"No Parquet shards found for {source} in {shard_dir}")

    per_shard_limit = max(25, (limit // len(shards)) + 20)
    logger.info(f"Extracting {source} across {len(shards)} shards with {max_workers} workers (target={limit} tasks)...")

    collected_by_shard: Dict[str, List[Dict[str, Any]]] = {}
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        fut_to_shard = {
            executor.submit(process_shard, str(s), source, benchmark_exclusions, per_shard_limit): str(s)
            for s in shards
        }
        for fut in as_completed(fut_to_shard):
            s_name = fut_to_shard[fut]
            shard_rows = fut.result()
            collected_by_shard[s_name] = shard_rows
            logger.info(f"  Shard {Path(s_name).name}: {len(shard_rows)} qualifying single-file .py tasks")

    # Merge deterministically in sorted shard order, deduplicating by task_id
    extracted: List[Dict[str, Any]] = []
    seen_global: Set[str] = set()
    for s in shards:
        for item in collected_by_shard.get(str(s), []):
            if item["task_id"] not in seen_global:
                seen_global.add(item["task_id"])
                extracted.append(item)
                if len(extracted) >= limit:
                    break
        if len(extracted) >= limit:
            break

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for row in extracted:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    total_steps = sum(sum(1 for m in r["messages"] if m.get("role") == "assistant") for r in extracted)
    logger.info(f"[{source}] Wrote {len(extracted)} tasks ({total_steps} assistant decision steps) -> {out_path}")
    return extracted


def main() -> None:
    parser = argparse.ArgumentParser(description="Parallel Source B trajectory extractor")
    parser.add_argument("--source", choices=["swe_smith", "swe_zero"], required=True)
    parser.add_argument("--limit", type=int, default=160)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 4))
    args = parser.parse_args()
    extract_source(args.source, args.limit, args.out, args.workers)


if __name__ == "__main__":
    main()
