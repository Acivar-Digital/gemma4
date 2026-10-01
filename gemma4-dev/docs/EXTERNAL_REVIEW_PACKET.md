# Gemma 4 Developer Agent — External Technical Review Packet (v2)

This document contains the complete technical briefing, source code, prompt architecture, and fine-tuning pipeline for external review of the **Gemma 4 Developer Agent** repository:
👉 **Repository:** [https://github.com/Acivar-Digital/gemma4](https://github.com/Acivar-Digital/gemma4)  
👉 **Branch:** `main`  
👉 **Raw Contents API:** `https://api.github.com/repos/Acivar-Digital/gemma4/contents/`

---

## Table of Contents
1. [Executive Summary & Direct Answers to Reviewer Critique](#1-executive-summary--direct-answers-to-reviewer-critique)
2. [Agent Prompt & Execution Governor (`my_submission/prompts/main.md`)](#2-agent-prompt--execution-governor-my_submissionpromptsmainmd)
3. [Upgraded Stratified SFT Dataset Pipeline (`scripts/build_unsloth_dataset.py`)](#3-upgraded-stratified-sft-dataset-pipeline-scriptsbuild_unsloth_datasetpy)
4. [Hardened LoRA Training Pipeline (`kaggle_unsloth/`)](#4-hardened-lora-training-pipeline-kaggle_unsloth)
5. [Line-Level Audit: Subprocess Isolation & Timeouts (`check.py` & `oracle.py`)](#5-line-level-audit-subprocess-isolation--timeouts-checkpy--oraclepy)
6. [Architectural Index of All 5 Skill Engines](#6-architectural-index-of-all-5-skill-engines)

---

## 1. Executive Summary & Direct Answers to Reviewer Critique

Following the expert review, we executed four critical architectural fixes across the codebase:

### A. Prompt Governor: Eliminated Contradictions & Loops
1. **Collapsed `read_file` Single Mandate:** Eliminated the conflicting "omit `end_line`" vs "MUST be `start_line + 40`" rule. The prompt now mandates a single rule: **"ALWAYS omit `end_line`."**
2. **Edit Oscillation Circuit Breaker:** Added an explicit attempt ceiling: **"Maximum 2 consecutive failed `edit_file` attempts on the same location; on the 3rd attempt, expand to a wider 8–10 line anchor or select an alternate surrounding block."**
3. **Explicit Discovery Phase Ceiling:** Enforced that Phase 1 & 2 search/inspection cannot exceed 8 tool calls, mandating the initial `edit_file` by call 9 at the latest.
4. **Phase-Scoped Scratchpad Governor:** Clarified that the 2-call probe ceiling applies strictly to **pre-edit hypothesis probes** (`repro-check`/`code-oracle`). Post-edit verification in Phase 4 via `code-oracle` and `test-gate` is explicitly **exempt**.

### B. Dataset Builder: Supervision Quality & Stratification
1. **Adjacent Pre-Edit Reasoning:** Replaced naive `thoughts[0]` with `extract_agent_reasoning_pre_edit()`, extracting the agent thought immediately preceding the final successful edit turn.
2. **Outlier Filtering:** Dropped non-surgical diffs (`patch_lines > 150`) and flailing trajectories (`tool_calls > 35`).
3. **Dedup Pass:** Added SequenceMatcher deduplication (>90% similarity) to collapse near-duplicate tutorial variants.
4. **Stratified 80/20 Split:** Hardened into 38 train rows and 10 held-out validation rows stratified across repositories (FastAPI 20/5, Rich 12/3, Requests 6/2).
5. **Zero Double-Templating:** Emits pure Gemma-4 chat turns directly (`<start_of_turn>user...<end_of_turn>\n<start_of_turn>model...<end_of_turn>`) without a redundant `messages` object.

### C. LoRA Hyperparameters: Anti-Memorization Hardening
1. **Rank & Projections:** Dropped from Rank-16 on all 7 layers down to **Rank 8 on attention + output heads only (`q_proj`, `v_proj`, `o_proj`)**.
2. **Epoch Reduction:** Cut training from 60 steps (~8.5 epochs) to **20 steps (~2.5 epochs)** with cosine schedule.
3. **Learning Rate & Regularization:** Reduced learning rate to **$2.0 \times 10^{-5}$**, set `weight_decay = 0.05`, `lora_dropout = 0.05`, and injected **NEFTune noise (`neftune_noise_alpha = 5`)**.

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
- PHASE 1 & 2 DISCOVERY CEILING: Maximum 8 discovery tool calls total across search, mapping, and file inspection. You MUST apply your initial code fix via `edit_file` by tool call 9 at the latest.

### Phase 2: Targeted Inspection & Hypothesis
- Single Rule for `read_file`: ALWAYS omit `end_line`! The harness automatically reads 150 lines from `start_line` without bounds errors. Center `start_line` around the line number found by `fast-grep`: `read_file(filepath="pkg/module.py", start_line=110)`. Never pass `end_line`.
- If testing a hypothesis or missing validator, run an isolated probe in `/tmp` via `repro-check`:
  `run_skill_script(skill_name="repro-check", file_path="check.py", args=["<assertion_code>"])`
- HARD SCRATCHPAD GOVERNOR: Maximum 2 *pre-edit* hypothesis probe calls total across `repro-check` or `code-oracle`. NEVER enter an interactive evaluation loop! Once a probe finishes, pivot directly to applying your surgical edit via `edit_file`. (Note: Post-edit domain checks and regression verification in Phase 4 are EXEMPT from this ceiling).

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
- If `tool_calls_remaining <= 5` or `tool_calls_used >= 45`: Apply your best surgical fix via `edit_file` BEFORE calling `submit_patch()`. Never submit an empty patch!
```

---

## 3. Upgraded Stratified SFT Dataset Pipeline (`scripts/build_unsloth_dataset.py`)

```python
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
    """Extracts user problem statement from trace JSON with explicit error logging."""
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
    """Extracts agent thought immediately preceding the successful final edit."""
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
```

---

## 4. Hardened LoRA Training Pipeline (`kaggle_unsloth/`)

From updated `kaggle_unsloth/train_gemma4_lora.ipynb`:

```python
# Unsloth FastLanguageModel QLoRA Initialization
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="google/gemma-4-31b-it",
    max_seq_length=4096,
    dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
    load_in_4bit=True,
)

# Targeted Rank-8 PEFT: attention + output projection only
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
    eval_steps=5,                   # Tracks held-out validation loss
    optim="adamw_8bit",
    weight_decay=0.05,
    lr_scheduler_type="cosine",
    neftune_noise_alpha=5,          # Embedding noise regularizer
    seed=42,
    report_to="none",
)
```

---

## 5. Line-Level Audit: Subprocess Isolation & Timeouts (`check.py` & `oracle.py`)

As requested for the line-level audit, here are the exact subprocess isolation, process group killing, and timeout mechanisms:

### A. Subprocess Process-Group Termination in `repro-check` (`check.py` lines 2090–2157)
```python
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
    # Terminate entire process group cleanly via SIGKILL
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

    timeout_summary = f"⏱️ Execution timed out after {timeout_secs}s (possible infinite loop in repro script)"
    timeout_report = DiagnosticReport(
        status="timeout",
        exit_code=124,
        summary=timeout_summary,
        raw_stderr=f"Timeout expired ({timeout_secs}s)",
    )
    return 124, "", timeout_summary, timeout_report
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
| **`repro-check`** | 2,729 | `check.py` | Isolated bug reproduction. Executes in `/tmp` using repo `PYTHONPATH`; distinct process group (`start_new_session=True`) killed via `os.killpg`; base64 argument bypass (`--b64 <payload>`); `--expect-exception` verification. |
| **`test-gate`** | 1,612 | `gate.py` | Pre-submission regression gatekeeper. Blast-radius neighbor test runner; asserts zero test files (`tests/*`) modified; asserts no untracked scratch files in `/workspace`; validates AST syntax before `submit_patch()`. |