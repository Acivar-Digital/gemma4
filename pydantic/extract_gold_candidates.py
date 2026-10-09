#!/usr/bin/env python3
"""Extract exactly 1,500 qualified single-file .py candidate tasks for SFT DAG translation.

Qualification Rules Enforced:
1. Zero benchmark leakage (exclude all 129 instance IDs in tasks.jsonl).
2. 100% single-file .py patches (is_single_file_py_patch).
3. Patch line count <= 300 (MAX_DIFF_LINES).
4. Trajectory length & call budget:
   - Total clean calls < 20
   - Total negative calls < 20
   - Total tool calls < 40
5. Negative call taxonomy:
   - 0 Type-B dumb calls (no syntax errors, edit string mismatches, FileNotFoundError loops)
   - Type-A pivoting negatives kept (Red-to-Green pytest / assertion failures)
6. Raw steps must actually touch the single target .py file.
7. Outputs raw untranslated tasks into pydantic/gold/raw_candidates_1500.jsonl.
"""

from __future__ import annotations

import argparse
import glob
import json
import logging
import re
from pathlib import Path
import sys
from typing import Any

import pyarrow.parquet as pq

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.sft_data_filters import (
    MAX_DIFF_LINES,
    is_single_file_py_patch,
    load_benchmark_exclusion_set,
    sanitize_text,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("extract_gold_candidates")

BENCHMARK_FILE = REPO_ROOT / "tasks.jsonl"
GOLD_DIR = REPO_ROOT / "pydantic" / "gold"
OUTPUT_FILE = GOLD_DIR / "raw_candidates_1500.jsonl"


def extract_single_target_py_filepath(patch: str) -> str | None:
    """Extracts target filepath if patch touches exactly 1 .py file."""
    if not is_single_file_py_patch(patch):
        return None
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                b_path = parts[3].removeprefix("b/")
                if b_path.endswith(".py"):
                    return b_path
    return None


def classify_raw_steps_budget(
    steps: list[dict[str, Any]], target_file: str
) -> tuple[bool, dict[str, int], list[dict[str, Any]]]:
    """Evaluates raw trajectory against tool call budget and Type-A/Type-B negative rules.

    Returns:
        (is_valid, stats_dict, structured_raw_steps)
    """
    clean_calls = 0
    negative_calls = 0
    type_a_pivoting = 0
    type_b_dumb = 0

    structured_raw_steps: list[dict[str, Any]] = []
    files_touched: set[str] = set()

    for idx, s in enumerate(steps):
        tool_name = s.get("tool_name", "")
        tool_input = s.get("tool_input", {})
        obs = str(s.get("observation", ""))

        # Track file touches
        inp_str = json.dumps(tool_input)
        for m in re.findall(r"[\w\-./]+\.py", inp_str):
            files_touched.add(m.strip().lstrip("/"))

        # Classify negative vs clean
        # Type B dumb negatives: syntax errors, failed edit string mismatches, FileNotFoundError
        is_type_b = False
        edit_errors = [
            "could not find",
            "not found in file",
            "did not match",
            "Failed to edit",
            "SyntaxError",
            "old_str did not match",
        ]
        if any(err.lower() in obs.lower() for err in edit_errors):
            is_type_b = True

        read_errors = ["FileNotFoundError", "No such file", "does not exist", "IsADirectoryError"]
        if not is_type_b and any(err.lower() in obs.lower() for err in read_errors):
            is_type_b = True

        if is_type_b:
            type_b_dumb += 1
            negative_calls += 1
        elif any(fail in obs.lower() for fail in ["failed", "error", "traceback", "assertionerror"]):
            # Type A pivoting negative (e.g. pytest failure, assert True/False repro)
            type_a_pivoting += 1
            negative_calls += 1
        else:
            clean_calls += 1

        structured_raw_steps.append({
            "step_index": idx,
            "tool_name": tool_name,
            "tool_input": tool_input,
            "observation": obs,
        })

    # Strict Gates:
    # 1. 0 Type-B dumb calls
    if type_b_dumb > 0:
        return False, {}, []

    # 2. Dual < 20 budget
    if clean_calls >= 20 or negative_calls >= 20 or (clean_calls + negative_calls) >= 40:
        return False, {}, []

    # 3. Minimum steps (must have at least exploration, edit, and completion)
    if len(structured_raw_steps) < 2:
        return False, {}, []

    # 4. Target file touched
    norm_target = target_file.strip().lstrip("/")
    if not any(norm_target in f or f in norm_target for f in files_touched):
        return False, {}, []

    stats = {
        "clean_calls": clean_calls,
        "negative_calls": negative_calls,
        "type_a_pivoting": type_a_pivoting,
        "type_b_dumb": type_b_dumb,
        "total_calls": len(structured_raw_steps),
    }
    return True, stats, structured_raw_steps


def parse_swe_zero_record(
    row: dict[str, Any], benchmark_exclusions: set[str]
) -> dict[str, Any] | None:
    task_id = str(row.get("instance_id") or "")
    if not task_id or task_id in benchmark_exclusions:
        return None

    patch = str(row.get("model_patch") or "")
    target_file = extract_single_target_py_filepath(patch)
    if not target_file or len(patch.splitlines()) > MAX_DIFF_LINES:
        return None

    traj = row.get("trajectory") or []
    if not isinstance(traj, list) or len(traj) < 3:
        return None

    problem_statement = ""
    raw_steps: list[dict[str, Any]] = []

    for item in traj:
        role = item.get("role")
        content = item.get("content") or ""
        if role == "user" and not problem_statement:
            problem_statement = sanitize_text(content)
        elif role == "assistant":
            tcs = item.get("tool_calls") or []
            for tc in tcs:
                fn = tc.get("function") or {}
                fn_name = fn.get("name") or tc.get("name") or "unknown"
                fn_args = fn.get("arguments") or tc.get("arguments") or {}
                if isinstance(fn_args, str):
                    try:
                        fn_args = json.loads(fn_args)
                    except Exception:
                        fn_args = {"raw": fn_args}
                if fn_name == "think":
                    continue
                raw_steps.append({
                    "tool_name": fn_name,
                    "tool_input": fn_args,
                    "observation": "",
                })
        elif role == "tool" and raw_steps:
            raw_steps[-1]["observation"] = str(content)

    if not problem_statement or not raw_steps:
        return None

    is_valid, stats, structured_steps = classify_raw_steps_budget(raw_steps, target_file)
    if not is_valid:
        return None

    return {
        "task_id": task_id,
        "repo": str(row.get("repo") or task_id.split("__")[0] if "__" in task_id else "python"),
        "problem_statement": problem_statement,
        "gold_patch": patch,
        "target_filepath": target_file,
        "source": "swe_zero",
        "raw_steps": structured_steps,
        "stats": stats,
    }


def parse_swe_smith_record(
    row: dict[str, Any], benchmark_exclusions: set[str]
) -> dict[str, Any] | None:
    task_id = str(row.get("instance_id") or "")
    if not task_id or task_id in benchmark_exclusions or not row.get("resolved"):
        return None

    patch = str(row.get("patch") or "")
    target_file = extract_single_target_py_filepath(patch)
    if not target_file or len(patch.splitlines()) > MAX_DIFF_LINES:
        return None

    messages = row.get("messages") or []
    if isinstance(messages, str):
        try:
            messages = json.loads(messages)
        except Exception:
            return None
    if not isinstance(messages, list) or len(messages) < 3:
        return None

    problem_statement = ""
    raw_steps: list[dict[str, Any]] = []

    for item in messages:
        role = item.get("role")
        content = item.get("content") or ""
        if role == "user" and not problem_statement:
            problem_statement = sanitize_text(content)
        elif role == "assistant":
            tcs = item.get("tool_calls") or []
            if isinstance(tcs, str):
                try:
                    tcs = json.loads(tcs)
                except Exception:
                    tcs = []
            for tc in tcs:
                fn = tc.get("function") or {}
                fn_name = fn.get("name") or tc.get("name") or "unknown"
                fn_args = fn.get("arguments") or tc.get("arguments") or {}
                if isinstance(fn_args, str):
                    try:
                        fn_args = json.loads(fn_args)
                    except Exception:
                        fn_args = {"raw": fn_args}
                if fn_name == "think":
                    continue
                raw_steps.append({
                    "tool_name": fn_name,
                    "tool_input": fn_args,
                    "observation": "",
                })
        elif role == "tool" and raw_steps:
            raw_steps[-1]["observation"] = str(content)

    if not problem_statement or not raw_steps:
        return None

    is_valid, stats, structured_steps = classify_raw_steps_budget(raw_steps, target_file)
    if not is_valid:
        return None

    return {
        "task_id": task_id,
        "repo": str(row.get("repo") or task_id.split("__")[0] if "__" in task_id else "python"),
        "problem_statement": problem_statement,
        "gold_patch": patch,
        "target_filepath": target_file,
        "source": "swe_smith",
        "raw_steps": structured_steps,
        "stats": stats,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract 1,500 qualified raw SFT tasks.")
    parser.add_argument("--limit", type=int, default=1500, help="Target total qualified tasks.")
    parser.add_argument("--out", type=Path, default=OUTPUT_FILE, help="Output JSONL path.")
    args = parser.parse_args()

    benchmark_exclusions = load_benchmark_exclusion_set(BENCHMARK_FILE)
    logger.info("Loaded %d benchmark exclusion tasks from %s", len(benchmark_exclusions), BENCHMARK_FILE)

    target_limit = args.limit
    per_source_target = target_limit // 2

    # Shard paths
    swe_zero_shards = sorted(glob.glob(str(REPO_ROOT / "data/source_b/swe_zero/*.parquet")))
    swe_smith_shards = sorted(glob.glob(str(REPO_ROOT / "data/source_b/swe_smith/*.parquet")))

    logger.info("Found %d swe_zero shards, %d swe_smith shards", len(swe_zero_shards), len(swe_smith_shards))

    extracted_tasks: list[dict[str, Any]] = []
    seen_task_ids: set[str] = set()

    # 1. Extract from swe_zero (target: 750)
    zero_count = 0
    for shard_path in swe_zero_shards:
        if zero_count >= per_source_target:
            break
        table = pq.read_table(shard_path)
        for r_idx in range(table.num_rows):
            if zero_count >= per_source_target:
                break
            row = {col: table[col][r_idx].as_py() for col in table.column_names}
            parsed = parse_swe_zero_record(row, benchmark_exclusions)
            if parsed and parsed["task_id"] not in seen_task_ids:
                seen_task_ids.add(parsed["task_id"])
                extracted_tasks.append(parsed)
                zero_count += 1

    logger.info("Extracted %d qualified tasks from swe_zero", zero_count)

    # 2. Extract from swe_smith (target: 750, or remainder to reach limit)
    smith_target = target_limit - len(extracted_tasks)
    smith_count = 0
    for shard_path in swe_smith_shards:
        if smith_count >= smith_target:
            break
        table = pq.read_table(shard_path)
        for r_idx in range(table.num_rows):
            if smith_count >= smith_target:
                break
            row = {col: table[col][r_idx].as_py() for col in table.column_names}
            parsed = parse_swe_smith_record(row, benchmark_exclusions)
            if parsed and parsed["task_id"] not in seen_task_ids:
                seen_task_ids.add(parsed["task_id"])
                extracted_tasks.append(parsed)
                smith_count += 1

    logger.info("Extracted %d qualified tasks from swe_smith", smith_count)

    # If swe_smith didn't reach smith_target, backfill with remaining swe_zero shards
    if len(extracted_tasks) < target_limit:
        remaining = target_limit - len(extracted_tasks)
        logger.info("Backfilling %d remaining tasks from swe_zero shards...", remaining)
        for shard_path in swe_zero_shards:
            if len(extracted_tasks) >= target_limit:
                break
            table = pq.read_table(shard_path)
            for r_idx in range(table.num_rows):
                if len(extracted_tasks) >= target_limit:
                    break
                row = {col: table[col][r_idx].as_py() for col in table.column_names}
                parsed = parse_swe_zero_record(row, benchmark_exclusions)
                if parsed and parsed["task_id"] not in seen_task_ids:
                    seen_task_ids.add(parsed["task_id"])
                    extracted_tasks.append(parsed)

    logger.info("Total qualified tasks extracted: %d / %d", len(extracted_tasks), target_limit)

    # Save to gold output file
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for t in extracted_tasks:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")

    logger.info("Wrote %d raw qualified tasks -> %s", len(extracted_tasks), args.out)


if __name__ == "__main__":
    main()
