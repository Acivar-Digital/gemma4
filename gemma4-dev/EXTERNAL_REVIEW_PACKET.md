# Gemma 4 Developer Agent — External Technical Review Packet

This document contains the complete technical briefing, source code, prompt architecture, and fine-tuning pipeline for external review of the **Gemma 4 Developer Agent** repository:
👉 **Repository:** [https://github.com/Acivar-Digital/gemma4](https://github.com/Acivar-Digital/gemma4)  
👉 **Branch:** `main`  
👉 **Raw Contents API:** `https://api.github.com/repos/Acivar-Digital/gemma4/contents/`

---

## Table of Contents
1. [Response to Reviewer Critique: The 56-Trajectory LoRA](#1-response-to-reviewer-critique-the-56-trajectory-lora)
2. [Agent Prompt & Execution Governor (`my_submission/prompts/main.md`)](#2-agent-prompt--execution-governor-my_submissionpromptsmainmd)
3. [SFT Dataset Curation Pipeline (`scripts/build_unsloth_dataset.py`)](#3-sft-dataset-curation-pipeline-scriptsbuild_unsloth_datasetpy)
4. [LoRA Fine-Tuning Setup & Hyperparameters (`kaggle_unsloth/`)](#4-lora-fine-tuning-setup--hyperparameters-kaggle_unsloth)
5. [The 5 Deterministic Skill Engines (`my_submission/skills/`)](#5-the-5-deterministic-skill-engines-my_submissionskills)
6. [Key Questions for Reviewers](#6-key-questions-for-reviewers)

---

## 1. Response to Reviewer Critique: The 56-Trajectory LoRA

> **Reviewer's Note:** *"56 examples is dangerously thin for SFT unless you've augmented, deduplicated near-identical repair patterns, and held out an untouched eval split. That's exactly the scrutiny I'll apply once I can read the dataset builder."*

### Detailed Technical Analysis & Proposed Hardening:

1. **Origin of the 56 Trajectories:**
   - The 56 examples originate directly from our verified resolved tasks in baseline evaluation run `run_B39` (56/129 benchmark tasks = **43.4% resolution rate** on FastAPI, Rich, Requests, HTTPX).
   - Each trajectory is guaranteed valid: it passed full end-to-end regression evaluation in an isolated SWE-bench evaluation container.

2. **The 3 Legitimate Risks in the Current Implementation:**
   - **Distributional Skew:** The SWE-Gemma development set contains 67 FastAPI, 48 Rich, 13 Requests, and 1 HTTPX tasks. Consequently, the 56 winning trajectories are heavily dominated by FastAPI and Rich. Training without weighting or cross-repo generalization guards risks learning framework-specific idioms instead of generic defect resolution.
   - **Over-Parameterization on Small Data:** In `scripts/build_unsloth_training_kernel.py`, the initial draft targets **all 7 linear projections** (`q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj`) with Rank 16 ($r=16, \alpha=16$) at $lr = 1.5 \times 10^{-4}$ for 60 steps (~8.5 epochs). For only 56 examples, adapting both the attention heads and MLP layers at high learning rate introduces significant risk of memorization and catastrophic forgetting of broad Python reasoning.
   - **Modality Mismatch (Agent Tool Calls vs. Direct Unified Patch):** In the Google ADK harness, the agent does NOT output unified git diffs as chat responses; it interacts with the environment via structured tool calls (`edit_file`, `submit_patch()`, `read_file`, `run_skill_script`). The current `build_unsloth_dataset.py` formats the output as `### Proposed Unified Git Diff Patch: \`\`\`diff ... \`\`\``. This trains the model as an offline patch generator rather than a tool-calling autonomous agent.

3. **Proposed Architectural Hardening for Review:**
   - **Constrain PEFT Target Modules:** Restrict LoRA to attention-only (`q_proj`, `v_proj`), drop rank to $r = 8$ or $r = 4$, and reduce learning rate to $2.0 \times 10^{-5}$ with weight decay $0.1$.
   - **Data Augmentation & Regularization:**
     - Counterfactual / DPO pairs using the 73 failed benchmark runs as negative trajectories.
     - Synthetic code perturbations (renaming local identifiers, reordering docstrings/imports) to triple effective trajectory diversity without altering semantic logic.
   - **Held-Out Stratified Validation Split:** Enforce an 80/20 train/validation split (45 train / 11 held-out val) stratified across repository types, evaluating checkpoints strictly by AST syntax validity and patch edit distance.

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

### Phase 2: Targeted Inspection & Hypothesis
- Dual truncation cap: `read_file` is strictly capped by the harness at 150 lines and 10,000 characters.
- RULE: Omit `end_line`! The tool automatically reads 150 lines from `start_line` without bounds errors. If specified, `end_line` MUST be `start_line + 40`. NEVER pass a small integer like 15 or 30 as `end_line`!
- Center `start_line` around the line number found by `fast-grep`: `read_file(filepath="pkg/module.py", start_line=110)`.
- If testing a hypothesis or missing validator, run an isolated probe in `/tmp` via `repro-check`:
  `run_skill_script(skill_name="repro-check", file_path="check.py", args=["<assertion_code>"])`
- HARD SCRATCHPAD GOVERNOR: Maximum 2 investigation/eval calls total across `repro-check` or `code-oracle`. NEVER enter an interactive evaluation loop! If a probe or eval completes, do NOT keep iterating in the scratchpad—pivot directly to applying your surgical edit via `edit_file`.

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

5. ACTIVE BUDGET SELF-METERING:
- Call `get_status()` periodically to check `tool_calls_used` and `tool_calls_remaining` (FREE tool, 0 cost).
- If `tool_calls_remaining <= 5` or `tool_calls_used >= 45`: Apply your best surgical fix via `edit_file` BEFORE calling `submit_patch()`. Never submit an empty patch!
```

---

## 3. SFT Dataset Curation Pipeline (`scripts/build_unsloth_dataset.py`)

```python
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
        reasoning_summary = ""
        if thoughts:
            reasoning_summary = thoughts[0]  # Initial hypothesis / root-cause diagnosis

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

        messages = [
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": model_content},
        ]

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

    line_counts = [ex["patch_lines"] for ex in sft_examples]
    short_diffs = sum(1 for lc in line_counts if lc <= 25)
    print(
        f"Diffs <= 25 lines (Sweet Spot): {short_diffs}/{len(sft_examples)} ({short_diffs/len(sft_examples)*100:.1f}%)"
    )
    print(f"Median diff lines: {sorted(line_counts)[len(line_counts)//2]}")
    print("==========================================================")


if __name__ == "__main__":
    build_dataset()
```

---

## 4. LoRA Fine-Tuning Setup & Hyperparameters (`kaggle_unsloth/`)

From `kaggle_unsloth/train_gemma4_lora.ipynb`:

```python
# Unsloth FastLanguageModel QLoRA Initialization
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="google/gemma-4-31b-it",
    max_seq_length=4096,
    dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
    load_in_4bit=True,
)

model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=[
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ],
    lora_alpha=16,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=42,
)

training_args = TrainingArguments(
    output_dir="/kaggle/working/training_outputs",
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,  # Effective batch size = 8
    warmup_steps=5,
    max_steps=60,                   # ~8.5 epochs over 56 items
    learning_rate=1.5e-4,
    fp16=not torch.cuda.is_bf16_supported(),
    bf16=torch.cuda.is_bf16_supported(),
    logging_steps=5,
    optim="adamw_8bit",
    weight_decay=0.01,
    lr_scheduler_type="cosine",
    seed=42,
    report_to="none",
)
```

---

## 5. The 5 Deterministic Skill Engines (`my_submission/skills/`)

The 5 custom skills total **11,264 lines of production-grade Python** located under `my_submission/skills/`. They run with zero subagent overhead and conform to strict sandbox limits:

| Skill | Lines of Code | Core Architectural Purpose | Critical Guarantees |
| :--- | :---: | :--- | :--- |
| **`fast-grep`** | 2,342 | AST-aware keyword & regex search engine | Auto-falls back to literal search on `re.error`; prioritizes definitions over call sites; emits `[CLEAN CODE FOR edit_file]` with exact indentation; fuzzy AST symbol suggestions on zero matches; max 500KB / 5000 lines bound per file; always exits 0. |
| **`code-map`** | 2,494 | Symbol call-graph & workspace indexer | `--symbol <name>` builds caller/callee AST graph across modules; `--file <path>` returns compact AST outline under 100 lines without running an external language server. |
| **`code-oracle`** | 2,087 | Multi-domain evaluation oracle | `--eval` runs in subprocess with 2.0s hard timeout; `--hex` validates ANSI/SGR escape sequences & `\x1b[0m` reset; `--width` validates CJK Wide (2) vs ASCII (1) vs emoji (2) terminal display widths; `--html-esc` verifies OWASP `<script>` tag escaping; `--schema` verifies OpenAPI `$defs` and nullability. |
| **`repro-check`** | 2,729 | Isolated hypothesis & defect verification | Runs test code in `/tmp` using repo `PYTHONPATH`; never pollutes `/workspace`; 15s subprocess timeout; `--b64 <payload>` eliminates shell escaping issues; handles `--expect-exception`. |
| **`test-gate`** | 1,612 | Pre-submission regression gatekeeper | Auto-detects distance-1 neighbor unit tests; verifies **zero modifications** to test files (`tests/*`); asserts no scratch scripts exist in `/workspace`; validates AST syntax before calling `submit_patch()`. |

---

## 6. Key Questions for Reviewers

1. **LoRA Fine-Tuning Strategy:** Given 56 ground-truth examples, should we keep Rank-16 across all 7 modules, or scale down to $r = 8$ strictly targeting attention projections (`q_proj`, `v_proj`) with $lr = 2\times 10^{-5}$?
2. **Trajectory Format:** Is it better to fine-tune the model to output the direct unified diff (offline patch oracle), or fine-tune multi-turn tool-calling trajectories (`read_file` $\to$ `edit_file` $\to$ `submit_patch`)?
3. **Execution Governor (`prompts/main.md`):** Does the 2-call scratchpad ceiling for `repro-check` adequately prevent hallucination thrashing without choking on complex multi-layered bugs?
4. **Skill Engine Robustness:** In `code-oracle` and `repro-check`, are there any blind spots in our subprocess isolation or timeout guards that could hang on pathological code?