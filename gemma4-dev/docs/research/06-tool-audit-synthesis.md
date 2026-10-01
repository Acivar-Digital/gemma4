# 06 — The 8-Task Gauntlet Tool Audit Synthesis

> Root Cause Analysis of Autonomous SWE-bench Failure & Required Tool Architecture  
> Persisted in Beads via `bd recall gauntlet-8-tool-audit-synthesis` and `bd recall decision-8-task-tool-audit`.

---

## 1. Executive Summary

Autonomous SWE-bench agents do not fail primarily because LLM reasoning is deficient; they fail because **the tools and evaluation feedback loops provide deceptive signals that mislead the model**.

Across the 8 archetypal defect categories in the Gauntlet, our concurrent subagents identified 6 recurring systemic traps and derived 5 targeted tool/prompt upgrades required to achieve true zero-human-in-the-loop autonomy.

---

## 2. The 6 Systemic Failure Traps

| # | Trap Name | Root Cause & Failure Mechanism | Tasks Affected |
|---|---|---|---|
| **1** | **The False-Confidence Gate** | Container B oracle tests are withheld in Container A. Pre-existing tests pass 100% on buggy code. `blast-radius` reports `✅ ALL PASSED`, falsely confirming broken or no-op patches. | `requests_7328`<br>`requests_6589`<br>`rich_4077`<br>`fastapi_15588` |
| **2** | **The 0-Test Silent Pass** | When creating brand-new modules or scripts, `blast-radius` finds 0 tests and 0 consumers, prints a warning, but returns `passed=True` (`exit code 0`). Broken code is submitted unchecked. | `fastapi_15661` |
| **3** | **The Negative-Constraint Exit 0** | Missing validation defects silently accept invalid inputs and exit 0. `repro-check` marks `defect_confirmed=False` and trips the circuit breaker: *"STOP probing immediately"*. | `fastapi_15588` |
| **4** | **The Anti-Multi-File Panic** | `blast-radius` emits alarmist warnings (`⚠️ MULTI-FILE DIFF DETECTED: revert secondary files!`), and prompts mandate single-file edits only. In real 2-file PRs, agents panic and revert valid fixes. | `fastapi_14986` |
| **5** | **The Pre-Fix Unit Test Dilemma** | Correct fixes break existing unit tests that asserted the *old buggy behavior*. `blast-radius` shouts `⚠️ FIX OR REVERT`, causing the model to undo working fixes. | `rich_4076` |
| **6** | **The Executable Docs Blindspot** | `fast-grep` penalized any path containing `"doc"` by `-40 points`, demoting executable FastAPI tutorial code in `docs_src/` below unrelated modules. | `fastapi_15023` |

---

## 3. The 5 Required Tool Capabilities & Upgrades

### 1. `smart-blast` (Semantic Test Resolver & Smart Verdict)
- **Symbol-Reference Matching**: Scans test files for imports and call-sites of modified AST symbols, replacing naive file stem matching (`tutorial002_py310.py` $\to$ `test_tutorial002.py`).
- **Framework-Aware Directory Mapping**: Maps `docs_src/<category>/tutorial<N>[_variant].py` directly to `tests/test_tutorial/test_<category>/test_tutorial<N>.py`.
- **Smart Verdict**:
  - If direct unit tests fail because they assert pre-fix behavior, but **100% of distance-1 consumers pass**, emit `PRE-FIX TEST CONFLICT ADVISORY` instead of shouting `FIX OR REVERT`.
  - If **0 tests are found**, **FAIL** the gate (no silent green pass allowed).
- **Multi-File Diff Support**: Eliminate the panic-inducing *"revert secondary files first"* warning when modified files are part of the target module.

### 2. `repro-check` V2 (Negative Assertions & Raw Script Execution)
- **`--expect-exception <ExceptionType>`**: For missing validation bugs, if baseline code does *not* raise the exception, mark `defect_confirmed=True`. When the fix causes the exception to be raised, mark `status=PASSED`.
- **Raw Multi-Line Execution**: Support executing raw multi-line scripts in `/tmp` without JSON argument quote-escaping corruption.
- **Path Routing Guard**: Prevent accidental writing to `/workspace/tmp/...` via `write_file`, keeping the git working tree 100% clean.

### 3. `syntax-guard` (Immediate Post-Edit AST Check)
- Run `ast.parse()` immediately after `edit_file` or `write_file`.
- Instantly flag syntax errors (e.g. unescaped regex lookbehinds `r"(?<=\n)"` or unterminated string literals) before wasting tool calls on failed test runners.

### 4. `fast-grep` Optimizations
- **Multi-Word Query Tokenization**: Automatically split whitespace-separated queries so copying issue titles verbatim (e.g. `"preserve newlines"`) does not return 0 matches.
- **Remove Anti-Docs Penalty**: Treat `docs_src/*.py` as first-class executable application code rather than doc spam.

### 5. Prompt De-Dogmatization (`prompts/main.md`)
- Relax the single-file prohibition to permit legitimate multi-file architectural changes explicitly required by the issue.
- Permit `write_file` when creating brand-new files or scripts (relaxing the `edit_file`-only mandate).
- Clarify that passing `blast-radius` is a regression guard (0 regressions), not proof of new feature correctness.
