#!/usr/bin/env python3
"""Builds high-quality, stratified SFT training & validation datasets for Unsloth Gemma 31B.

Sources & Hardening:
1. Verified resolved tasks from SWE-Gemma run_B39 (ground truth winning trajectories).
2. Supervision quality: Extracts agent thought immediately adjacent to the successful final edit.
3. Outlier filtering: Rejects non-surgical diffs (>150 lines) and flailing runs (tool_calls > 35).
4. Near-duplicate deduplication: Collapses patches with >90% similarity via difflib SequenceMatcher.
5. Stratified 80/20 split: Balances train/validation sets across repository domains.
6. Zero template duplication: Outputs pure Gemma-4 chat template turns directly to avoid tokenizer bugs.
7. Strict error budget: Logs failures and hard-fails if corrupted traces exceed 5%.
"""

from collections import defaultdict
import difflib
import json
import logging
from pathlib import Path
import random
from typing import Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_unsloth_dataset")

ROOT_DIR = Path(__file__).resolve().parent.parent
B39_DIR = ROOT_DIR / "results" / "run_B39"
TRACES_DIR = B39_DIR / "traces"
PATCHES_DIR = B39_DIR / "patches"
RESULTS_JSONL = B39_DIR / "task_results.jsonl"
OUT_DIR = ROOT_DIR / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)
TRAIN_OUT_PATH = OUT_DIR / "unsloth_sft_train.jsonl"
VAL_OUT_PATH = OUT_DIR / "unsloth_sft_val.jsonl"

MAX_DIFF_LINES = 150
MAX_TOOL_CALLS = 35
DEDUP_SIMILARITY_THRESHOLD = 0.90
MAX_SKIP_RATE = 0.05
VAL_RATIO = 0.20
SEED = 42


def extract_problem_statement(trace_path: Path) -> str:
    """Extracts the user problem statement from the trace JSON with explicit error logging."""
    if not trace_path.exists():
        logger.warning(f"Trace file missing: {trace_path}")
        return ""
    try:
        with open(trace_path, encoding="utf-8") as f:
            trace = json.load(f)
        for step in trace.get("steps", []):
            if step.get("source") == "user":
                msg = step.get("message", "").strip()
                if msg:
                    return msg
    except Exception as exc:
        logger.error(f"Failed to read user prompt from {trace_path}: {exc}")
    return ""


def extract_agent_reasoning_pre_edit(trace_path: Path) -> str:
    """Extracts the agent thought immediately preceding the successful final edit."""
    if not trace_path.exists():
        return ""
    try:
        with open(trace_path, encoding="utf-8") as f:
            trace = json.load(f)
        steps = trace.get("steps", [])

        # Find the last successful or final edit_file / write_file step
        last_edit_idx = -1
        for idx, step in enumerate(steps):
            for tc in step.get("tool_calls", []):
                if tc.get("function_name") in ("edit_file", "write_file"):
                    last_edit_idx = idx

        # Extract closest preceding agent message
        if last_edit_idx > 0:
            for p in range(last_edit_idx - 1, -1, -1):
                msg = steps[p].get("message")
                if steps[p].get("source") == "agent" and msg and isinstance(msg, str):
                    clean_msg = msg.strip()
                    if len(clean_msg) > 10:
                        return clean_msg

        # Fallback to the first substantive agent thought if no pre-edit thought exists
        for step in steps:
            if step.get("source") == "agent":
                msg = step.get("message")
                if msg and isinstance(msg, str) and len(msg.strip()) > 10:
                    return msg.strip()
    except Exception as exc:
        logger.error(f"Failed to extract reasoning from {trace_path}: {exc}")
    return ""


def build_dataset():
    if not RESULTS_JSONL.exists():
        raise FileNotFoundError(f"Missing results log: {RESULTS_JSONL}")

    resolved_records = []
    with open(RESULTS_JSONL, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("resolved") is True:
                resolved_records.append(rec)

    total_resolved = len(resolved_records)
    logger.info(f"Loaded {total_resolved} verified resolved tasks from run_B39.")
    assert total_resolved > 0, "No resolved tasks found!"

    skipped_no_patch = 0
    skipped_no_prompt = 0
    filtered_outliers = 0
    candidate_examples: List[Dict] = []

    for rec in resolved_records:
        inst_id = rec.get("instance_id")
        repo = rec.get("repo")
        trace_file = TRACES_DIR / f"trace_{inst_id}.json"
        patch_file = PATCHES_DIR / f"{inst_id}.patch"

        if not patch_file.exists():
            skipped_no_patch += 1
            logger.warning(f"Task {inst_id} missing patch file.")
            continue
        patch_text = patch_file.read_text(encoding="utf-8").strip()
        if not patch_text:
            skipped_no_patch += 1
            logger.warning(f"Task {inst_id} has empty patch file.")
            continue

        patch_lines = len(patch_text.splitlines())
        tool_calls = rec.get("tool_calls", 0)

        # Outlier filtering
        if patch_lines > MAX_DIFF_LINES:
            filtered_outliers += 1
            logger.info(f"Skipping {inst_id}: patch lines ({patch_lines}) > {MAX_DIFF_LINES}")
            continue
        if tool_calls > MAX_TOOL_CALLS:
            filtered_outliers += 1
            logger.info(f"Skipping {inst_id}: tool calls ({tool_calls}) > {MAX_TOOL_CALLS} (flailing run)")
            continue

        problem_text = extract_problem_statement(trace_file)
        if not problem_text:
            skipped_no_prompt += 1
            logger.warning(f"Task {inst_id} missing problem statement.")
            continue

        pre_edit_thought = extract_agent_reasoning_pre_edit(trace_file)
        if not pre_edit_thought:
            skipped_no_prompt += 1
            logger.warning(f"Task {inst_id} missing pre-edit thought.")
            continue

        candidate_examples.append({
            "task_id": inst_id,
            "repo": repo,
            "patch_lines": patch_lines,
            "tool_calls": tool_calls,
            "problem_text": problem_text,
            "reasoning": pre_edit_thought,
            "patch_text": patch_text,
        })

    # Hard-fail guard against corrupted traces
    total_skipped = skipped_no_patch + skipped_no_prompt
    skip_rate = total_skipped / total_resolved
    if skip_rate > MAX_SKIP_RATE:
        raise RuntimeError(
            f"Dataset build failed: skip rate {skip_rate:.2%} ({total_skipped}/{total_resolved}) "
            f"exceeds allowed maximum {MAX_SKIP_RATE:.0%}!"
        )

    logger.info(f"Passed quality filters: {len(candidate_examples)} candidates (dropped {filtered_outliers} outliers).")

    # Near-duplicate patch deduplication within same repository
    deduped_examples: List[Dict] = []
    collapsed_duplicates = 0

    for cand in candidate_examples:
        is_duplicate = False
        for accepted in deduped_examples:
            if cand["repo"] == accepted["repo"]:
                sim = difflib.SequenceMatcher(None, cand["patch_text"], accepted["patch_text"]).ratio()
                if sim >= DEDUP_SIMILARITY_THRESHOLD:
                    is_duplicate = True
                    collapsed_duplicates += 1
                    logger.info(
                        f"Collapsed near-duplicate patch {cand['task_id']} "
                        f"(similarity {sim:.2f} with {accepted['task_id']})"
                    )
                    break
        if not is_duplicate:
            deduped_examples.append(cand)

    logger.info(
        f"Deduplication complete: {len(deduped_examples)} unique examples "
        f"({collapsed_duplicates} collapsed)."
    )

    # Format into pure Gemma-4 chat turns (avoiding dual-template bugs in Unsloth)
    formatted_dataset = []
    for ex in deduped_examples:
        user_content = (
            f"You are an expert software engineer fixing an issue in `{ex['repo']}`.\n\n"
            f"Problem Statement:\n{ex['problem_text']}\n\n"
            "Please analyze the defect and provide the minimal, correct unified git diff patch to resolve the issue."
        )
        model_content = (
            f"### Root Cause Analysis:\n{ex['reasoning']}\n\n"
            f"### Proposed Unified Git Diff Patch:\n```diff\n{ex['patch_text']}\n```"
        )
        raw_text = (
            f"<start_of_turn>user\n{user_content}<end_of_turn>\n"
            f"<start_of_turn>model\n{model_content}<end_of_turn>"
        )
        formatted_dataset.append({
            "task_id": ex["task_id"],
            "repo": ex["repo"],
            "patch_lines": ex["patch_lines"],
            "tool_calls": ex["tool_calls"],
            "text": raw_text,
        })

    # Stratified 80/20 Train/Validation Split
    repo_groups = defaultdict(list)
    for row in formatted_dataset:
        repo_groups[row["repo"]].append(row)

    random.seed(SEED)
    train_rows: List[Dict] = []
    val_rows: List[Dict] = []

    for repo, rows in sorted(repo_groups.items()):
        random.shuffle(rows)
        val_count = max(1, int(round(len(rows) * VAL_RATIO))) if len(rows) > 3 else (1 if len(rows) > 1 else 0)
        repo_val = rows[:val_count]
        repo_train = rows[val_count:]
        val_rows.extend(repo_val)
        train_rows.extend(repo_train)
        logger.info(f"Repo {repo}: total={len(rows)}, train={len(repo_train)}, val={len(repo_val)}")

    # Write train and validation datasets
    with open(TRAIN_OUT_PATH, "w", encoding="utf-8") as f_train:
        for row in train_rows:
            f_train.write(json.dumps(row) + "\n")

    with open(VAL_OUT_PATH, "w", encoding="utf-8") as f_val:
        for row in val_rows:
            f_val.write(json.dumps(row) + "\n")

    print("\n" + "=" * 60)
    print("           STRATIFIED DATASET CURATION SUMMARY")
    print("=" * 60)
    print(f"Total verified input traces:        {total_resolved}")
    print(f"Passed filters & deduplication:     {len(formatted_dataset)}")
    print(f"Training set (80%):                 {len(train_rows)} rows -> {TRAIN_OUT_PATH}")
    print(f"Validation set (20% held-out):      {len(val_rows)} rows -> {VAL_OUT_PATH}")
    print(f"Skipped missing patch/prompt:       {total_skipped}")
    print(f"Filtered outliers (>150 lines/>35): {filtered_outliers}")
    print(f"Collapsed near-duplicate patches:   {collapsed_duplicates}")
    print("=" * 60)


if __name__ == "__main__":
    build_dataset()
