#!/usr/bin/env python3
"""Builds the zero-leakage, zero-thought Multi-Turn Decision SFT dataset for Gemma 4 31B LoRA.

Enforces all locked Track 2 specifications:
1. 0% tasks.jsonl benchmark overlap & 0% local run_B* traces.
2. 100% external Source B only: swe_smith + swe_zero (swe_rebench dropped completely).
3. 100% single-file .py patches only.
4. Dual < 20 tool-call budget gate (< 20 clean calls AND < 20 Type-A negative calls, < 40 total).
5. Two-Kind Negative Filter: keep Type A endgame-pivoting negatives; reject Type B dumb calls.
6. Official 262,144-token Gemma 4 AutoTokenizer (models/gemma-4-31b-it-qat-w4a16-ct).
7. Thinking turned OFF during SFT (enable_thinking=False): 0 <|channel>thought tokens in completions,
   with Turn-0 boundary reconciliation and add_special_tokens=False single-<bos> prefix-ID alignment.
"""

from collections import Counter, defaultdict
import hashlib
import json
import logging
import os
from pathlib import Path
import random
import sys
from typing import Any, Dict, List

from transformers import AutoTokenizer

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.extract_source_b import extract_source
from scripts.sft_data_filters import (
    SYSTEM_PROMPT,
    TOOLS_SCHEMA,
    load_benchmark_exclusion_set,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_unsloth_dataset")

DATA_DIR = ROOT_DIR / "data"
SFT_DIR = DATA_DIR / "unsloth_sft"
DATA_DIR.mkdir(parents=True, exist_ok=True)
SFT_DIR.mkdir(parents=True, exist_ok=True)

TRAIN_OUT_PATH = DATA_DIR / "unsloth_sft_train.jsonl"
VAL_OUT_PATH = DATA_DIR / "unsloth_sft_val.jsonl"
SFT_TRAIN_OUT_PATH = SFT_DIR / "train.jsonl"
SFT_VAL_OUT_PATH = SFT_DIR / "val.jsonl"
SFT_METADATA_PATH = SFT_DIR / "metadata.json"

STAGING_SMITH_PATH = SFT_DIR / "staging_swe_smith.jsonl"
STAGING_ZERO_PATH = SFT_DIR / "staging_swe_zero.jsonl"

TASKS_BENCHMARK_PATH = ROOT_DIR / "tasks.jsonl"
MODEL_TOKENIZER_DIR = ROOT_DIR / "models" / "gemma-4-31b-it-qat-w4a16-ct"

VAL_RATIO = 0.20
MAX_SEQ_TOKENS = 3072
TARGET_MAX_SAMPLES = 1500
SEED = 42
EMPTY_THOUGHT_CLOSURE = "<|channel>thought\n<channel|>"


def load_or_extract_staging(source: str, staging_path: Path, limit: int = 250) -> List[Dict[str, Any]]:
    """Loads pre-extracted staging trajectories if present, otherwise runs parallel shard extraction."""
    if staging_path.exists() and staging_path.stat().st_size > 0:
        rows = []
        with open(staging_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        if rows:
            logger.info(f"Loaded {len(rows)} staged trajectories from {staging_path}")
            return rows
    return extract_source(source=source, limit=limit, out_path=staging_path)


def _strip_reasoning_from_message(msg: Dict[str, Any]) -> Dict[str, Any]:
    """Preserves role='assistant' while stripping reasoning fields so zero thoughts are rendered."""
    if msg.get("role") != "assistant":
        return dict(msg)
    cleaned = {"role": "assistant"}
    if "tool_calls" in msg:
        cleaned["tool_calls"] = msg["tool_calls"]
    if "content" in msg and not msg.get("tool_calls"):
        cleaned["content"] = msg["content"]
    return cleaned


def slice_trajectory_decisions(
    task_id: str,
    repo: str,
    user_prompt: str,
    messages: List[Dict[str, Any]],
    tokenizer: Any,
) -> List[Dict[str, Any]]:
    """Slices a verified trajectory into zero-thought Gemma 4 prefix-delta decision windows."""
    samples: List[Dict[str, Any]] = []

    for i, m in enumerate(messages):
        if m.get("role") != "assistant":
            continue
        tcalls = m.get("tool_calls") or []
        if not tcalls:
            continue

        window: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # Include up to 2 preceding messages (assistant + tool observation pair)
        start_ctx = max(0, i - 2)
        for ctx_idx in range(start_ctx, i):
            window.append(_strip_reasoning_from_message(messages[ctx_idx]))

        target_msg = _strip_reasoning_from_message(m)
        window.append(target_msg)
        prefix_messages = window[:-1]

        try:
            prefix_text = tokenizer.apply_chat_template(
                prefix_messages,
                tools=TOOLS_SCHEMA,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            full_text = tokenizer.apply_chat_template(
                window,
                tools=TOOLS_SCHEMA,
                tokenize=False,
                add_generation_prompt=False,
                enable_thinking=False,
            )
        except Exception as exc:
            logger.warning(f"Template render error for {task_id} turn {i}: {exc}")
            continue

        # Turn-0 Boundary Reconciliation:
        # On Turn 0 (immediately after user), add_generation_prompt=True with enable_thinking=False
        # appends '<|channel>thought\n<channel|>' after '<|turn>model\n', whereas full_text omits it
        # when reasoning is empty. Reconcile by injecting '<|channel>thought\n<channel|>' after the
        # target '<|turn>model\n' so full_text.startswith(prefix_text) holds 100% natively.
        if not full_text.startswith(prefix_text) and prefix_text.endswith(EMPTY_THOUGHT_CLOSURE):
            base_prefix = prefix_text[: -len(EMPTY_THOUGHT_CLOSURE)]
            if full_text.startswith(base_prefix):
                full_text = prefix_text + full_text[len(base_prefix) :]

        if not full_text.startswith(prefix_text):
            logger.warning(f"Prefix mismatch for {task_id} turn {i}")
            continue

        completion_text = full_text[len(prefix_text) :]
        if not completion_text.startswith("<|tool_call>call:"):
            continue
        if "<|channel>thought" in completion_text or "<|think|>" in completion_text:
            continue

        # Verify 262,144-token ID alignment with add_special_tokens=False (single <bos> invariant)
        prefix_ids = tokenizer(prefix_text, add_special_tokens=False)["input_ids"]
        full_ids = tokenizer(full_text, add_special_tokens=False)["input_ids"]

        if len(full_ids) > MAX_SEQ_TOKENS:
            continue
        if len(full_ids) <= len(prefix_ids) or full_ids[: len(prefix_ids)] != prefix_ids:
            logger.warning(f"Token boundary mismatch for {task_id} turn {i}")
            continue

        target_tools = [tc["function"]["name"] for tc in tcalls]
        samples.append(
            {
                "task_id": task_id,
                "repo": repo,
                "messages": window,
                "prefix_text": prefix_text,
                "completion_text": completion_text,
                "text": full_text,
                "prefix_token_count": len(prefix_ids),
                "total_token_count": len(full_ids),
                "target_turn_index": i,
                "target_tools": target_tools,
            }
        )

    return samples


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_dataset() -> Dict[str, Any]:
    logger.info(f"Loading official 262,144-token Gemma 4 tokenizer from {MODEL_TOKENIZER_DIR}...")
    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_TOKENIZER_DIR))
    assert len(tokenizer) == 262144, f"Expected vocab size 262144, got {len(tokenizer)}"

    benchmark_exclusions = load_benchmark_exclusion_set(TASKS_BENCHMARK_PATH)

    # Load from staged JSONLs (or extract in parallel if not yet staged)
    sources = [
        ("swe_smith", load_or_extract_staging("swe_smith", STAGING_SMITH_PATH, limit=160)),
        ("swe_zero", load_or_extract_staging("swe_zero", STAGING_ZERO_PATH, limit=160)),
    ]

    all_trajectories = [t for _, trajs in sources for t in trajs]
    logger.info(f"Total verified single-file .py Source B trajectories loaded: {len(all_trajectories)}")
    assert len(all_trajectories) > 0, "No external trajectories extracted!"

    all_samples: List[Dict[str, Any]] = []
    tool_counter: Counter = Counter()
    source_counter: Counter = Counter()
    per_source_cap = TARGET_MAX_SAMPLES // 2  # 750 swe_smith + 750 swe_zero = 1500

    for source_name, trajs in sources:
        src_samples = 0
        for traj in trajs:
            raw_tid = traj["task_id"]
            assert raw_tid not in benchmark_exclusions, f"Benchmark leakage detected: {raw_tid}"
            samples = slice_trajectory_decisions(
                task_id=f"{source_name}__{raw_tid}",
                repo=traj["repo"],
                user_prompt=traj["user_prompt"],
                messages=traj["messages"],
                tokenizer=tokenizer,
            )
            for s in samples:
                s["source"] = source_name
                for t in s["target_tools"]:
                    tool_counter[t] += 1
                all_samples.append(s)
                src_samples += 1
                source_counter[source_name] += 1
                if src_samples >= per_source_cap:
                    break
            if src_samples >= per_source_cap:
                break

    logger.info(f"Samples per source: {dict(source_counter)}")
    logger.info(f"Total decision samples: {len(all_samples)}")
    logger.info(f"Target tool distribution: {dict(tool_counter)}")

    # Stratified split by task_id (zero task overlap between train and val)
    repo_to_tasks = defaultdict(set)
    for row in all_samples:
        repo_to_tasks[row["repo"]].add(row["task_id"])

    random.seed(SEED)
    train_task_ids = set()
    val_task_ids = set()

    for repo, task_ids in sorted(repo_to_tasks.items()):
        sorted_tasks = sorted(task_ids)
        random.shuffle(sorted_tasks)
        val_count = (
            max(1, int(round(len(sorted_tasks) * VAL_RATIO)))
            if len(sorted_tasks) > 3
            else (1 if len(sorted_tasks) > 1 else 0)
        )
        val_task_ids.update(sorted_tasks[:val_count])
        train_task_ids.update(sorted_tasks[val_count:])

    # Ensure val_task_ids is non-empty
    if not val_task_ids and len(train_task_ids) > 4:
        all_t = sorted(train_task_ids)
        val_c = max(1, int(round(len(all_t) * VAL_RATIO)))
        val_task_ids = set(all_t[:val_c])
        train_task_ids = set(all_t[val_c:])

    assert train_task_ids.isdisjoint(val_task_ids), "CRITICAL: Train and validation task IDs overlap!"

    train_rows = [r for r in all_samples if r["task_id"] in train_task_ids]
    val_rows = [r for r in all_samples if r["task_id"] in val_task_ids]

    for path, rows in [
        (TRAIN_OUT_PATH, train_rows),
        (VAL_OUT_PATH, val_rows),
        (SFT_TRAIN_OUT_PATH, train_rows),
        (SFT_VAL_OUT_PATH, val_rows),
    ]:
        with open(path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    train_sha = _sha256_file(SFT_TRAIN_OUT_PATH)
    val_sha = _sha256_file(SFT_VAL_OUT_PATH)

    metadata = {
        "total_samples": len(all_samples),
        "train_samples": len(train_rows),
        "val_samples": len(val_rows),
        "train_tasks": len(train_task_ids),
        "val_tasks": len(val_task_ids),
        "source_distribution": dict(source_counter),
        "tool_distribution": dict(tool_counter),
        "benchmark_leakage_prevented": len(benchmark_exclusions),
        "vocab_size": len(tokenizer),
        "max_seq_tokens": max((r["total_token_count"] for r in all_samples), default=0),
        "enable_thinking": False,
        "train_sha256": train_sha,
        "val_sha256": val_sha,
    }
    with open(SFT_METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print("\n" + "=" * 70)
    print("   ZERO-THOUGHT 262K GEMMA 4 SFT DATASET CURATION SUMMARY")
    print("=" * 70)
    print(f"Total verified trajectories:        {len(all_trajectories)}")
    print(f"Total decision samples extracted:   {len(all_samples)} ({dict(source_counter)})")
    print(f"Training set (80% tasks):           {len(train_rows)} samples across {len(train_task_ids)} tasks")
    print(f"Validation set (20% held-out tasks):{len(val_rows)} samples across {len(val_task_ids)} tasks")
    print(f"Max token length (<=3072):          {metadata['max_seq_tokens']} tokens")
    print(f"Target tool distribution:           {dict(tool_counter)}")
    print(f"Train SHA-256:                      {train_sha[:16]}...")
    print(f"Val SHA-256:                        {val_sha[:16]}...")
    print("Zero benchmark leakage:             PASS (0% tasks.jsonl overlap)")
    print("Zero swe_rebench rows:              PASS (100% swe_smith + swe_zero)")
    print("Zero thought tokens in completions: PASS (enable_thinking=False)")
    print("=" * 70)
    return metadata


if __name__ == "__main__":
    build_dataset()
