#!/usr/bin/env python3
"""Builds high-quality SFT training datasets for Unsloth Gemma 31B fine-tuning.

Sources:
1. All 56 verified resolved tasks from SWE-Gemma run_B39 (ground truth winning trajectories).
2. Clean, surgical git diff patches from results/run_B39/patches/.
3. Formats into Gemma-4 chat template turns:
   <start_of_turn>user\n{problem_statement}<end_of_turn>\n<start_of_turn>model\n{reasoning_and_patch}<end_of_turn>
"""

import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
B39_DIR = ROOT_DIR / "results" / "run_B39"
TRACES_DIR = B39_DIR / "traces"
PATCHES_DIR = B39_DIR / "patches"
RESULTS_JSONL = B39_DIR / "task_results.jsonl"
OUT_DIR = ROOT_DIR / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PATH = OUT_DIR / "unsloth_sft_train.jsonl"


def extract_problem_statement(trace_path: Path) -> str:
    """Extracts the user problem statement from the trace JSON."""
    if not trace_path.exists():
        return ""
    try:
        with open(trace_path, encoding="utf-8") as f:
            trace = json.load(f)
        for step in trace.get("steps", []):
            if step.get("source") == "user":
                return step.get("message", "").strip()
    except Exception:
        pass
    return ""


def extract_agent_reasoning(trace_path: Path) -> list:
    """Extracts key thoughts and scratchpad reflections from agent turns."""
    if not trace_path.exists():
        return []
    thoughts = []
    try:
        with open(trace_path, encoding="utf-8") as f:
            trace = json.load(f)
        for step in trace.get("steps", []):
            if step.get("source") == "agent":
                msg = step.get("message")
                if msg and isinstance(msg, str) and len(msg.strip()) > 10:
                    thoughts.append(msg.strip())
    except Exception:
        pass
    return thoughts


def build_dataset():
    if not RESULTS_JSONL.exists():
        print(f"Error: {RESULTS_JSONL} not found.")
        return

    resolved_records = []
    with open(RESULTS_JSONL, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("resolved") is True:
                resolved_records.append(rec)

    print(f"Found {len(resolved_records)} verified resolved tasks in run_B39.")

    sft_examples = []
    skipped_no_patch = 0
    skipped_no_prompt = 0

    for rec in resolved_records:
        inst_id = rec.get("instance_id")
        repo = rec.get("repo")
        trace_file = TRACES_DIR / f"trace_{inst_id}.json"
        patch_file = PATCHES_DIR / f"{inst_id}.patch"

        if not patch_file.exists():
            skipped_no_patch += 1
            continue
        patch_text = patch_file.read_text(encoding="utf-8").strip()
        if not patch_text:
            skipped_no_patch += 1
            continue

        problem_text = extract_problem_statement(trace_file)
        if not problem_text:
            skipped_no_prompt += 1
            continue

        thoughts = extract_agent_reasoning(trace_file)
        # Construct focused reasoning summary
        reasoning_summary = ""
        if thoughts:
            reasoning_summary = thoughts[0]  # Initial hypothesis / root-cause diagnosis

        # Format turn structure
        # User turn: Repo + Issue Statement
        # Assistant turn: Root Cause Analysis + Precise Git Diff Patch
        user_content = (
            f"You are an expert software engineer fixing an issue in `{repo}`.\n\n"
            f"Problem Statement:\n{problem_text}\n\n"
            "Please analyze the defect and provide the minimal, correct unified git diff patch to resolve the issue."
        )

        model_content = (
            f"### Root Cause Analysis:\n{reasoning_summary}\n\n"
            f"### Proposed Unified Git Diff Patch:\n```diff\n{patch_text}\n```"
            if reasoning_summary
            else f"### Proposed Unified Git Diff Patch:\n```diff\n{patch_text}\n```"
        )

        # Standard Hugging Face / Unsloth messages schema
        messages = [
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": model_content},
        ]

        # Gemma-4 raw chat template formatting
        raw_text = (
            f"<start_of_turn>user\n{user_content}<end_of_turn>\n"
            f"<start_of_turn>model\n{model_content}<end_of_turn>"
        )

        sft_examples.append(
            {
                "task_id": inst_id,
                "repo": repo,
                "patch_lines": len(patch_text.splitlines()),
                "tool_calls": rec.get("tool_calls", 0),
                "messages": messages,
                "text": raw_text,
            }
        )

    with open(OUT_PATH, "w", encoding="utf-8") as out_f:
        for ex in sft_examples:
            out_f.write(json.dumps(ex) + "\n")

    print(f"\n================ DATASET CURATION SUMMARY ================")
    print(f"Total verified SFT examples written: {len(sft_examples)}")
    print(f"Output saved to: {OUT_PATH} ({OUT_PATH.stat().st_size / 1024:.1f} KB)")
    print(f"Skipped missing patch: {skipped_no_patch}")
    print(f"Skipped missing prompt: {skipped_no_prompt}")

    # Sweet-spot metrics
    line_counts = [ex["patch_lines"] for ex in sft_examples]
    short_diffs = sum(1 for lc in line_counts if lc <= 25)
    print(
        f"Diffs <= 25 lines (Sweet Spot): {short_diffs}/{len(sft_examples)} ({short_diffs/len(sft_examples)*100:.1f}%)"
    )
    print(f"Median diff lines: {sorted(line_counts)[len(line_counts)//2]}")
    print("==========================================================")


if __name__ == "__main__":
    build_dataset()
