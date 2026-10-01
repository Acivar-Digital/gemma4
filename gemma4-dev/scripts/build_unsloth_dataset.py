#!/usr/bin/env python3
"""Builds high-quality, stratified Multi-Turn Tool SFT training & validation datasets for Unsloth Gemma 31B.

Consensus Architectural Upgrades (Triple-Reviewer Harmonized):
1. ELIMINATES MODALITY MISMATCH: Formats data as full multi-turn conversational tool-calling
   trajectories (system -> user -> agent tool_calls -> tool observation -> submit_patch),
   NOT plain text markdown diffs, preserving autonomous agent reflexes in Google ADK.
2. OBSERVATION COMPACTION: Compresses voluminous tool outputs (capped at 800 chars) to ensure
   complete 20-30 turn trajectories fit comfortably inside the 16,384 token window.
3. OUTLIER FILTERING: Drops non-surgical diffs (>150 lines) and flailing runs (tool_calls > 35).
4. DEDUPLICATION: Collapses near-duplicate patches (>90% similarity via difflib).
5. STRATIFIED 80/20 SPLIT: Balances train/val sets across repository domains.
6. DUAL SCHEMA: Outputs both standard OpenAI-compatible `messages` and rendered Gemma `text` turns.
7. STRICT INTEGRITY GUARD: Hard-fails if corrupted or skipped traces exceed 5%.
"""

from collections import defaultdict
import difflib
import json
import logging
from pathlib import Path
import random
from typing import Any, Dict, List, Optional, Tuple

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
MAX_OBSERVATION_CHARS = 800
SEED = 42


def compact_observation(raw_obs: Any) -> str:
    """Compacts tool observation output to fit long trajectories into 16K context."""
    if isinstance(raw_obs, dict):
        # Extract stdout or content if available
        if "stdout" in raw_obs and raw_obs["stdout"]:
            text = str(raw_obs["stdout"])
        elif "content" in raw_obs and raw_obs["content"]:
            text = str(raw_obs["content"])
        else:
            text = json.dumps(raw_obs, ensure_ascii=False)
    else:
        text = str(raw_obs or "").strip()

    if len(text) <= MAX_OBSERVATION_CHARS:
        return text

    # Keep head and tail of oversized outputs
    half = MAX_OBSERVATION_CHARS // 2 - 20
    return text[:half] + "\n... [truncated] ...\n" + text[-half:]


def extract_trajectory_messages(trace_path: Path) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """Extracts system instruction, user prompt, and multi-turn tool interaction messages."""
    if not trace_path.exists():
        logger.warning(f"Trace file missing: {trace_path}")
        return None, []

    try:
        with open(trace_path, encoding="utf-8") as f:
            trace = json.load(f)
    except Exception as exc:
        logger.error(f"Failed to parse trace {trace_path}: {exc}")
        return None, []

    steps = trace.get("steps", [])
    user_prompt = ""
    messages: List[Dict[str, Any]] = []

    for step in steps:
        src = step.get("source")
        msg = (step.get("message") or "").strip()
        tcalls = step.get("tool_calls", [])
        obs = step.get("observation")

        if src == "system" and msg:
            if not messages or messages[0].get("role") != "system":
                messages.append({"role": "system", "content": msg})

        elif src == "user" and msg:
            if not user_prompt:
                user_prompt = msg
                messages.append({"role": "user", "content": msg})

        elif src == "agent":
            # Build assistant message
            asst_dict: Dict[str, Any] = {"role": "assistant"}
            if msg:
                asst_dict["content"] = msg
            if tcalls:
                formatted_calls = []
                for idx, tc in enumerate(tcalls):
                    call_id = tc.get("tool_call_id") or f"call_{len(messages)}_{idx}"
                    formatted_calls.append({
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": tc.get("function_name"),
                            "arguments": json.dumps(tc.get("arguments", {}), ensure_ascii=False)
                        }
                    })
                asst_dict["tool_calls"] = formatted_calls

            if "content" in asst_dict or "tool_calls" in asst_dict:
                messages.append(asst_dict)

            # Build tool observation response if present
            if obs:
                compact_text = compact_observation(obs)
                call_id = (tcalls[0].get("tool_call_id") or f"call_{len(messages)-1}_0") if tcalls else "call_0"
                fn_name = tcalls[0].get("function_name") if tcalls else "tool"
                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": fn_name,
                    "content": compact_text
                })

    return user_prompt, messages


def render_gemma_chat_turns(messages: List[Dict[str, Any]]) -> str:
    """Renders structured messages into canonical Gemma turn markers."""
    turns: List[str] = []

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content") or ""
        tool_calls = msg.get("tool_calls", [])

        if role == "system":
            # In Gemma 4, system prompts are typically included in the user turn or system turn
            turns.append(f"<start_of_turn>system\n{content}<end_of_turn>")
        elif role == "user":
            turns.append(f"<start_of_turn>user\n{content}<end_of_turn>")
        elif role == "assistant":
            parts = []
            if content:
                parts.append(content)
            if tool_calls:
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    fn_name = fn.get("name")
                    fn_args = fn.get("arguments")
                    parts.append(f"<|tool_call|>call:{fn_name}{fn_args}<|tool_call|>")
            asst_body = "\n".join(parts)
            turns.append(f"<start_of_turn>model\n{asst_body}<end_of_turn>")
        elif role == "tool":
            tool_name = msg.get("name", "tool")
            turns.append(f"<start_of_turn>tool\n{content}<end_of_turn>")

    return "\n".join(turns)


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
    skipped_no_trace = 0
    filtered_outliers = 0
    candidate_examples: List[Dict[str, Any]] = []

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

        user_prompt, messages = extract_trajectory_messages(trace_file)
        if not user_prompt or not messages or len(messages) < 4:
            skipped_no_trace += 1
            logger.warning(f"Task {inst_id} invalid or missing trajectory steps.")
            continue

        candidate_examples.append({
            "task_id": inst_id,
            "repo": repo,
            "patch_lines": patch_lines,
            "tool_calls": tool_calls,
            "user_prompt": user_prompt,
            "patch_text": patch_text,
            "messages": messages,
            "turns_count": len(messages),
        })

    # Hard-fail guard against corrupted traces
    total_skipped = skipped_no_patch + skipped_no_trace
    skip_rate = total_skipped / total_resolved
    if skip_rate > MAX_SKIP_RATE:
        raise RuntimeError(
            f"Dataset build failed: skip rate {skip_rate:.2%} ({total_skipped}/{total_resolved}) "
            f"exceeds allowed maximum {MAX_SKIP_RATE:.0%}!"
        )

    logger.info(f"Passed quality filters: {len(candidate_examples)} candidates (dropped {filtered_outliers} outliers).")

    # Near-duplicate patch deduplication within same repository
    deduped_examples: List[Dict[str, Any]] = []
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
        f"Deduplication complete: {len(deduped_examples)} unique multi-turn trajectories "
        f"({collapsed_duplicates} collapsed)."
    )

    # Format into Gemma-4 chat turns and include structured messages
    formatted_dataset = []
    for ex in deduped_examples:
        raw_text = render_gemma_chat_turns(ex["messages"])
        formatted_dataset.append({
            "task_id": ex["task_id"],
            "repo": ex["repo"],
            "patch_lines": ex["patch_lines"],
            "tool_calls": ex["tool_calls"],
            "turns_count": ex["turns_count"],
            "messages": ex["messages"],
            "text": raw_text,
        })

    # Stratified 80/20 Train/Validation Split
    repo_groups = defaultdict(list)
    for row in formatted_dataset:
        repo_groups[row["repo"]].append(row)

    random.seed(SEED)
    train_rows: List[Dict[str, Any]] = []
    val_rows: List[Dict[str, Any]] = []

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
            f_train.write(json.dumps(row, ensure_ascii=False) + "\n")

    with open(VAL_OUT_PATH, "w", encoding="utf-8") as f_val:
        for row in val_rows:
            f_val.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("\n" + "=" * 65)
    print("      STRATIFIED MULTI-TURN SFT DATASET CURATION SUMMARY")
    print("=" * 65)
    print(f"Total verified input traces:        {total_resolved}")
    print(f"Passed filters & deduplication:     {len(formatted_dataset)}")
    print(f"Training set (80%):                 {len(train_rows)} trajectories -> {TRAIN_OUT_PATH}")
    print(f"Validation set (20% held-out):      {len(val_rows)} trajectories -> {VAL_OUT_PATH}")
    print(f"Filtered outliers (>150 lines/>35): {filtered_outliers}")
    print(f"Collapsed near-duplicate patches:   {collapsed_duplicates}")
    print("=" * 65)


if __name__ == "__main__":
    build_dataset()
