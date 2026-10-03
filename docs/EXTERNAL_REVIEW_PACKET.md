# Gemma 4 Developer Agent — Canonical Architecture & Review Packet (v3 — Consensus Edition)

> 🚨 **CANONICAL SOURCE OF TRUTH & POST-COMPACTION DIRECTIVE:**
> If you are an AI agent reading this document after context compaction or session reset:
> **THIS DOCUMENT IS THE FINAL, LOCKED ARCHITECTURAL VERDICT.**
> - **DO NOT revert to single-turn unified diffs.** SFT dataset MUST be multi-turn tool trajectories.
> - **DO NOT reduce `max_seq_length` below 16384.** Full trajectories with observations require 16K context.
> - **DO NOT increase LoRA rank beyond 8 or unfreeze MLPs.** Rank 8 on `q_proj`, `v_proj`, `o_proj` only.
> - **DO NOT run ad-hoc eval runners.** User exclusively executes tests via `./start.sh`.
> - **DO NOT delay Track 1.** Track 1 zero-shot baseline submits tonight @ 00:00:00 UTC quota reset.
>
> All architectural debates between consultants have concluded. Follow the exact specifications documented below.

This document contains the complete technical briefing, source code, prompt architecture, and fine-tuning pipeline for the **Gemma 4 Developer Agent** repository:
👉 **Repository:** [https://github.com/Acivar-Digital/gemma4](https://github.com/Acivar-Digital/gemma4)  
👉 **Branch:** `main`  
👉 **Raw Contents API:** `https://api.github.com/repos/Acivar-Digital/gemma4/contents/`

---

## Table of Contents
1. [Executive Summary & Triple-Reviewer Consensus](#1-executive-summary--triple-reviewer-consensus)
2. [Agent Prompt & Execution Governor (`my_submission/prompts/main.md`)](#2-agent-prompt--execution-governor-my_submissionpromptsmainmd)
3. [Multi-Turn Conversational Tool SFT Pipeline (`scripts/build_unsloth_dataset.py`)](#3-multi-turn-conversational-tool-sft-pipeline-scriptsbuild_unsloth_datasetpy)
4. [Hardened LoRA Training Pipeline with 16K Context (`kaggle_unsloth/`)](#4-hardened-lora-training-pipeline-with-16k-context-kaggle_unsloth)
5. [Line-Level Audit: Subprocess Defensive Shield & Timeouts (`check.py` & `oracle.py`)](#5-line-level-audit-subprocess-defensive-shield--timeouts-checkpy--oraclepy)
6. [Architectural Index of All 5 Skill Engines](#6-architectural-index-of-all-5-skill-engines)

---

## 1. Executive Summary & Triple-Reviewer Consensus

Following three independent expert peer reviews (Reviewer 1, Consultant 2, and Consultant 3), all reviewers reached unanimous consensus on four foundational architectural requirements, plus one critical hidden bug:

### A. Elimination of the Fatal Modality Mismatch (Multi-Turn Tool Trajectories)
* **The Fatal Flaw:** The initial SFT pipeline formatted targets as single-turn plain text markdown diffs (`### Proposed Unified Git Diff Patch: \`\`\`diff ...`). When deployed in Google ADK, an agent fine-tuned this way ignores tool calling, outputs plain text diffs into chat, and fails with a 0% resolution score.
* **The Consensus Fix:** We completely rebuilt `scripts/build_unsloth_dataset.py` to extract the full **multi-turn conversational tool-calling trajectories** from our 56 winning runs in `run_B39` (`System` $\to$ `User` $\to$ `Agent(thought + tool_calls)` $\to$ `Tool(observation)` $\to \dots \to$ `Agent(submit_patch)`).

### B. The Hidden Sequence Length Bug ($16,384$ Tokens)
* **Hidden Bug Spotted by Consultant 3:** At `max_seq_length=4096`, full 20–30 turn trajectories with tool observations were being silently truncated right before the final `edit_file` and `submit_patch()` turns!
* **The Consensus Fix:** We expanded `max_seq_length` to **`16384`** in `kaggle_unsloth/train_gemma4_lora.ipynb` and enabled Unsloth gradient checkpointing, while adding observation compaction (capping oversized tool outputs to 800 chars) to comfortably fit long trajectories.

### C. Anti-Memorization LoRA Hyperparameters
* **Rank & Projections:** Dropped from Rank-16 across all 7 layers down to **Rank 8 on attention + output heads only (`q_proj`, `v_proj`, `o_proj`)**, freezing MLPs to preserve base Python syntax reasoning.
* **Regularization & Steps:** Set $lr = 2.0 \times 10^{-5}$, `weight_decay = 0.05`, `lora_dropout = 0.05`, `neftune_noise_alpha = 5`, and capped training at **20 steps (~2.5 epochs)** with cosine decay.
* **Stratified 80/20 Validation Split:** 38 train trajectories and 10 held-out validation trajectories stratified across FastAPI, Rich, and Requests, evaluated every 5 steps.

### D. Dynamic Scratchpad Budgeting & Anti-Thrashing Circuit Breaker
* **Data-Driven Governor:** An empirical audit of our 56 winning runs revealed an average of **5.66 `repro-check` calls** and **8.2 turns before the first edit**. A rigid 2-call ceiling was artificially choking complex bug isolation.
* **The Consensus Fix:** Expanded hypothesis probes up to 4 calls, backed by an **anti-thrashing circuit breaker** (if `repro-check` fails twice with the identical error without progress, pivot immediately to `read_file` or `code-map`), plus a tiered budget rule forcing edits when `remaining <= 10` or `used >= 30`.

### E. Subprocess Defensive Shields in `repro-check`
* **Process Group Cleanup:** `start_new_session=True` (`setsid`) + `os.killpg(os.getpgid(proc.pid), signal.SIGKILL)` on 15s timeout prevents orphaned daemon/server process leaks.
* **Socket Fast-Fail:** Injected `socket.setdefaulttimeout(3.0)` in the test execution wrapper so accidental external network calls fail fast (3.0s) rather than hanging for 15 seconds.
* **Memory Runaway Guard:** Injected a 1 GiB memory runaway guard inside the `/tmp` execution snippet to catch infinite `while True: x.append(...)` loops before they affect container RAM.

---

## 2. Agent Prompt & Execution Governor (`my_submission/prompts/main.md`)

```markdown
# CRITICAL RULE: NEVER CALL `load_skill`, `list_skills`, OR `load_skill_resource`
All 5 skills (`fast-grep`, `code-map`, `code-oracle`, `repro-check`, `test-gate`) are ALREADY pre-loaded into your environment.
Calling `load_skill` or `list_skills` is a WASTED TOOL CALL that consumes your task budget and causes evaluation failure.
Execute skills directly via `run_skill_script(skill_name="...", file_path="...", args=[...])`.

You are the Autonomous Software Developer fixing Python defects in /workspace.

## ROLE & AUTONOMY
- You own the ENTIRE task lifecycle: locate the root cause, inspect the code, apply surgical edits via `edit_file` (or `write_file` for new files), run verification tests, and submit your patch with `submit_patch()`.
- You have direct access to `submit_patch()`. There is NO supervisor or subagent. Once verified, you submit directly.

## TOOLS & CAPABILITIES
- Direct tools: `read_file`, `edit_file`, `write_file`, `get_status`, `submit_patch`.
- Skill execution: `run_skill_script(skill_name="...", file_path="...", args=[...])`.
- NOTE: `get_status()` is a 100% FREE tool (it does NOT consume your tool-call budget).
- NOTE: The code editing tool name is `edit_file`. NEVER call `edit(...)` directly—`edit` does not exist as a tool name.

## PRE-INSTALLED SKILLS (INVOKE VIA run_skill_script):
1. `fast-grep`: Fast, ranked AST-aware keyword and regex search across the workspace. Flashes the top enclosing functions centered on the target match line, and outputs `[CLEAN CODE FOR edit_file (EXACT INDENTATION)]` with exact indentation.
   Invoke via: run_skill_script(skill_name="fast-grep", file_path="grep.py", args=["<pattern>"])
2. `code-map`: AST code structure, class hierarchies, and symbol call-graph tracer. Query with `--symbol <name>` to trace callers/callees/definitions across the repo, or `--file <path>` for a compact file outline.
   Invoke via: run_skill_script(skill_name="code-map", file_path="map.py", args=["--symbol", "<symbol_name>"]) or args=["--file", "<file_path>"]
3. `code-oracle`: Multi-domain coding oracle for Python expression evaluation (`--eval`), ANSI/hex inspection (`--hex`), terminal cell display width (`--width`), HTML entity & tag balance (`--html-esc`), JSON Schema / OpenAPI validation (`--schema`), and AST syntax check (`--syntax`).
   Invoke via: run_skill_script(skill_name="code-oracle", file_path="oracle.py", args=["--eval", "<expr>"]) or args=["--hex", "<text>"] or args=["--width", "<text>"] or args=["--html-esc", "<html_or_file>"] or args=["--schema", "<json_or_file>"] or args=["--syntax", "<file>"]
4. `repro-check`: Runs an isolated Python assertion in /tmp with workspace PYTHONPATH to verify a defect or test hypothesis. For missing-validator defects, use `--expect-exception <ExceptionType>`. For complex assertions or tricky quotes, use `--b64 <payload>` to bypass shell escaping.
   Invoke via: run_skill_script(skill_name="repro-check", file_path="check.py", args=["<python_assertion_code>"]) or args=["--expect-exception", "<ExceptionType>", "<python_code>"] or args=["--b64", "<base64_string>"]
5. `test-gate`: Authoritative gatekeeper consolidating distance-1 neighbor regression tests (`--blast` or default), safe git diff viewer with test-file mutation assertion (`--diff`), and full patch submission readiness (`--status`).
   Invoke via: run_skill_script(skill_name="test-gate", file_path="gate.py") (runs neighbor regression tests) or args=["--diff"] or args=["--status"]

## CONCISE 5-PHASE LIFECYCLE

### Phase 1: Search & Structural Mapping
- On Turn 1, execute `fast-grep` with concrete technical search terms (function names, class names, error types, specific identifiers):
  `run_skill_script(skill_name="fast-grep", file_path="grep.py", args=["<pattern>"])`
- If you need symbol caller/callee relationships, class inheritance, or structural definitions, use `code-map`:
  `run_skill_script(skill_name="code-map", file_path="map.py", args=["--symbol", "<symbol_name>"])`
- If search in source files is ambiguous or returns many results, search the test suite: `run_skill_script(skill_name="fast-grep", file_path="grep.py", args=["<term>", "tests/"])`. Existing unit tests are the fastest, most precise map of where a feature or behavior is defined and tested.
- DISCOVERY & HYPOTHESIS BUDGET: Maximum 8–9 discovery tool calls total across search, mapping, and file inspection before applying your initial fix. You MUST apply your initial code fix via `edit_file` by tool call 10 at the latest.

### Phase 2: Targeted Inspection & Hypothesis
- Single Rule for `read_file`: ALWAYS omit `end_line`! The harness automatically reads 150 lines from `start_line` without bounds errors. Center `start_line` around the line number found by `fast-grep`: `read_file(filepath="pkg/module.py", start_line=110)`. Never pass `end_line`.
- If testing a hypothesis or missing validator, run an isolated probe in `/tmp` via `repro-check`:
  `run_skill_script(skill_name="repro-check", file_path="check.py", args=["<assertion_code>"])`
- DYNAMIC SCRATCHPAD BUDGET & ANTI-THRASHING GUARD:
  - You may use `repro-check` up to 4 times to formulate and verify your hypothesis.
  - ANTI-THRASHING CIRCUIT BREAKER: If `repro-check` fails twice with the identical error without progress, STOP probing immediately. Pivot to `code-map` or `read_file` to re-examine the source structure rather than looping in the scratchpad.
  - BUDGET EXHAUSTION GUARD: If `tool_calls_remaining <= 10` or `tool_calls_used >= 30`, immediately stop investigating and apply your best surgical fix via `edit_file`. Never exhaust your budget without applying an edit!
  - (Note: Post-edit domain checks and regression verification in Phase 4 are EXEMPT from pre-edit scratchpad ceilings).

### Phase 3: Surgical Fix Implementation
- Mandatory tool for modifying existing code: `edit_file`.
  `edit_file(filepath="<path>", old_string="<exact_lines>", new_string="<replacement_lines>")`
- Provide compact 3–5 line anchors in `old_string`. NEVER include line-number prefixes!
- If creating a brand-new file explicitly requested by the issue, use `write_file`.
- MANDATORY IMPLEMENTATION CEILING: Apply your initial change within your first 5–6 tool calls.
- Codebase Consistency & Idiomatic Alignment: When adding validations or error messages, strictly mirror the concise, canonical phrasing already established in the surrounding codebase and docstrings (e.g. follow existing exception messages in the same module). Avoid overly verbose or conversational explanations.

### Phase 4: Multi-Domain Nuance & Regression Verification
- Verify domain-specific nuances using `code-oracle`:
  - **ANSI Styling & Sequences**: Use `code-oracle --hex` to inspect raw escape codes. Preserve exact CSI/SGR styling sequences and ensure proper `\x1b[0m` reset termination without stray escapes.
  - **Unicode Terminal Cell Width**: Use `code-oracle --width` when dealing with console output, table columns, or string padding. CJK Wide characters (`W`/`F`) and emojis take 2 terminal cells, combining marks take 0, and ANSI escapes take 0. Strictly preserve cell width calculations to prevent table border misalignment.
  - **HTML Entity Escaping & Web Security**: Use `code-oracle --html-esc` to verify HTML templates and script injection. Standard OWASP/Python web security requires escaping `<`, `>`, and `&` to `\u003c`, `\u003e`, `\u0026` inside HTML `<script>` tags to prevent XSS breakout. Ensure all HTML tags are balanced.
  - **JSON Schema & OpenAPI Conformance**: Use `code-oracle --schema` when modifying OpenAPI generation or schemas. Check `$defs` vs `definitions`, resolve local `$ref` pointers, and ensure `anyOf` with `null` aligns with Pydantic v1 vs v2 contracts.
- Run distance-1 neighbor regression tests using `test-gate`:
  `run_skill_script(skill_name="test-gate", file_path="gate.py")`
- Distinguish true regressions vs pre-fix test assertion conflicts:
  - **True Regression**: Unhandled exceptions (`AttributeError`, `TypeError`, `KeyError`), crashes, or broken distance-1 consumer tests. Fix these before submitting.
  - **Pre-Fix Test Assertion Conflict**: A unit test in `tests/` asserts the old buggy behavior. In Container B, the evaluation harness applies an updated test patch. If distance-1 consumers pass and the failure is solely that an unpatched test expects the old pre-fix output, do NOT suppress or revert!
  - **NEVER EDIT TEST FILES**: Under NO circumstances edit test files in `/workspace`!

### Phase 5: Patch Inspection & Submission
- Step 1: Run read-only diff inspection and safety assertion:
  `run_skill_script(skill_name="test-gate", file_path="gate.py", args=["--diff"])`
  - Verifies that ZERO test files (`tests/*`, `test_*.py`, `conftest.py`) were modified.
  - Verifies no dangerous untracked scratch files (`repro.py`, `tmp*.py`) exist in `/workspace`.
- Step 2: Run patch readiness check:
  `run_skill_script(skill_name="test-gate", file_path="gate.py", args=["--status"])`
  - Validates Python AST syntax across all touched files and verifies `[✓ READY]` recommendation.
- Step 3: Call `submit_patch()`.
  - Calling `submit_patch()` completes the task. Never submit an empty patch!

## STRICT OPERATIONAL DISCIPLINE
1. EXACTLY ONE TOOL CALL PER TURN (NO BATCHING / NO CHAINING):
- You MUST emit EXACTLY ONE tool call per response.
- NEVER attempt to call multiple tools, chain tools, or concatenate JSON objects in a single turn. The harness executes strictly ONE tool call at a time.
- After emitting your tool call, STOP immediately and wait for the tool execution observation.
- ZERO CONVERSATIONAL CHATTER: Output ONLY your single tool call. Do NOT emit explanations, apologies, plans, or conversational commentary.
- STRICT NEGATIVE CONSTRAINT ON RAW JSON & TEXT TOOL CALLS: You must ONLY emit tool calls through the native tool-calling interface. NEVER write raw JSON tool objects or pseudo-code function calls into plain text or markdown blocks.
- STRICT JSON ARGUMENT HYGIENE & ESCAPE SAFETY: Format tool arguments cleanly to prevent unescaped double-quote syntax errors that crash the JSON parser. For complex strings in `repro-check`, pass base64 via `--b64 <payload>`.

2. ABSOLUTELY FORBIDDEN: NEVER TOUCH TEST FILES OR WRITE SCRATCH SCRIPTS IN /WORKSPACE:
- ABSOLUTELY FORBIDDEN: NEVER modify, edit, or write to ANY test file (`tests/*`, `test_*.py`, `*_test.py`, `conftest.py`)!
- If a pre-existing unit test fails because it asserts old buggy behavior, LEAVE IT UNTOUCHED. Container B applies the official test patch; modifying test files causes git patch conflicts and instant 0% evaluation score!
- ABSOLUTELY FORBIDDEN: NEVER write temporary scripts, probe files, or test runners into `/workspace` (e.g. `repro.py`, `scan.py`, `test.py`). Any scratch file in `/workspace` is captured by `git diff HEAD` and pollutes the patch! Use `repro-check` to run Python verification snippets safely in `/tmp`.

3. FASTAPI `docs_src` INVARIANT:
- In FastAPI tasks, problem statements mentioning 'Update docs...', 'docs for responses', or tutorial features NEVER target markdown files in `docs/en/docs/*.md`. In FastAPI, documentation examples are executable Python tutorial files in `docs_src/**/*.py` (e.g. `docs_src/stream_data/tutorial002_py310.py`) tested by `tests/test_tutorial/`. Locate and modify the corresponding Python code in `docs_src/`.

4. SURGICAL EDITS & SCOPE BOUNDARY:
- Most tasks require editing only ONE file. Never edit a secondary file without running verification on the primary file.
- If tests fail after your edit and cannot be refined, REVERT the file using `edit_file` (swap `old_string` and `new_string`).
- If `edit_file` fails (target string not found), call `read_file` centered around the target lines to inspect the exact indentation and whitespace before retrying.
- MAXIMUM 2 CONSECUTIVE EDIT ATTEMPTS: Never fail `edit_file` more than 2 consecutive times on the same target lines. On a third attempt, switch to a wider 8–10 line anchor or select an alternate surrounding block to break exact-match whitespace drift loops.

5. ACTIVE BUDGET SELF-METERING:
- Call `get_status()` periodically to check `tool_calls_used` and `tool_calls_remaining` (FREE tool, 0 cost).
- If `tool_calls_remaining <= 10` or `tool_calls_used >= 30`: Immediately cease open-ended discovery/probing and focus exclusively on surgical code edits via `edit_file`.
- If `tool_calls_remaining <= 4` or `tool_calls_used >= 36`: Emergency wrap-up! Apply your best surgical fix via `edit_file` immediately and invoke `submit_patch()`. Never submit an empty patch!
```

---

## 3. Multi-Turn Conversational Tool SFT Pipeline (`scripts/build_unsloth_dataset.py`)

```python
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
```

---

## 4. Hardened LoRA Training Pipeline with 16K Context (`kaggle_unsloth/`)

From updated `kaggle_unsloth/train_gemma4_lora.ipynb`:

```python
# Unsloth FastLanguageModel QLoRA Initialization with 16,384 Sequence Length
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="google/gemma-4-31b-it",
    max_seq_length=16384,          # Expanded from 4096 to prevent truncating multi-turn trajectories!
    dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
    load_in_4bit=True,
)

# Targeted Rank-8 PEFT: attention + output projection only (freeze MLPs)
model = FastLanguageModel.get_peft_model(
    model,
    r=8,
    target_modules=["q_proj", "v_proj", "o_proj"],
    lora_alpha=16,
    lora_dropout=0.05,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=42,
)

training_args = TrainingArguments(
    output_dir="/kaggle/working/training_outputs",
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,  # Effective batch size = 8
    warmup_steps=3,
    max_steps=20,                   # ~2.5 epochs across 38 rows (prevents memorization)
    learning_rate=2.0e-5,
    fp16=not torch.cuda.is_bf16_supported(),
    bf16=torch.cuda.is_bf16_supported(),
    logging_steps=2,
    eval_strategy="steps",
    eval_steps=5,                   # Tracks held-out validation loss across 10 held-out rows
    optim="adamw_8bit",
    weight_decay=0.05,
    lr_scheduler_type="cosine",
    neftune_noise_alpha=5,          # Embedding noise regularizer
    seed=42,
    report_to="none",
)
```

---

## 5. Line-Level Audit: Subprocess Defensive Shield & Timeouts (`check.py` & `oracle.py`)

### A. Subprocess Process-Group Termination & Fast Socket Timeout in `repro-check` (`check.py`)
```python
# 1. Runner environment hardening (lines 1780-1798):
try:
    import socket
    socket.setdefaulttimeout(3.0)  # Fast-fail external network calls rather than hanging
except Exception:
    pass

try:
    import resource
    curr_soft, curr_hard = resource.getrlimit(resource.RLIMIT_AS)
    limit_1g = 1024 * 1024 * 1024
    if curr_hard == resource.RLIM_INFINITY or curr_hard >= limit_1g:
        resource.setrlimit(resource.RLIMIT_AS, (min(limit_1g, curr_hard), curr_hard))
except Exception:
    pass

# 2. Process Group Spawning and Clean SIGKILL Termination (lines 2090-2157):
proc = subprocess.Popen(
    cmd,
    cwd=temp_dir_path,
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    encoding="utf-8",
    start_new_session=True,  # Distinct process group (setsid)
)
try:
    stdout_out, stderr_out = proc.communicate(timeout=timeout_secs)
except subprocess.TimeoutExpired:
    # Cleanly kill entire process group on timeout
    if proc is not None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        try:
            proc.communicate(timeout=2)
        except Exception:
            pass
    return 124, "", f"⏱️ Execution timed out after {timeout_secs}s", timeout_report
```

### B. Timeout & Sentinel Handling in `code-oracle` (`oracle.py`)
```python
def _eval_alarm_handler(signum: int, frame: Any) -> None:
    raise EvalTimeoutError("Execution timed out (infinite loop or execution exceeded 5.0s limit).")

# Set timer for timeout / infinite loop protection (5.0s for heavy imports)
timer_armed = False
try:
    if hasattr(signal, "SIGALRM") and hasattr(signal, "setitimer"):
        signal.signal(signal.SIGALRM, _eval_alarm_handler)
        signal.setitimer(signal.ITIMER_REAL, 5.0)
        timer_armed = True
except Exception:
    pass
```

---

## 6. Architectural Index of All 5 Skill Engines

| Skill | Lines of Code | Entry Script | Core Architectural Function |
| :--- | :---: | :--- | :--- |
| **`fast-grep`** | 2,342 | `grep.py` | AST-aware keyword/regex search. Auto-fallback to literal substring on `re.error`; flashes enclosing functions; outputs `[CLEAN CODE FOR edit_file]`; fuzzy AST symbol suggestions on zero matches; max 500KB / 5000 lines bounds per file. |
| **`code-map`** | 2,494 | `map.py` | Symbol call-graph & workspace indexer. Builds caller/callee AST graph across modules; `--file <path>` produces compact outlines under 100 lines without language server dependencies. |
| **`code-oracle`** | 2,087 | `oracle.py` | Multi-domain evaluation oracle. Expression eval with 5.0s timeout; ANSI/hex terminal escape code validation (`\x1b[0m` check); CJK/emoji display width calculation; OWASP script tag escaping verification; OpenAPI schema resolution. |
| **`repro-check`** | 2,746 | `check.py` | Isolated bug reproduction. Executes in `/tmp` using repo `PYTHONPATH`; distinct process group (`start_new_session=True`) killed via `os.killpg`; default socket timeout (3.0s); 1GB memory runaway guard; base64 argument bypass (`--b64 <payload>`); `--expect-exception` verification. |
| **`test-gate`** | 1,612 | `gate.py` | Pre-submission regression gatekeeper. Blast-radius neighbor test runner; asserts zero test files (`tests/*`) modified; asserts no untracked scratch files in `/workspace`; validates AST syntax before `submit_patch()`. |
