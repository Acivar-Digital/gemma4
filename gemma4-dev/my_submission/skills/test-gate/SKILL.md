---
name: test-gate
description: Authoritative gatekeeper consolidating blast-radius regression test runner and diff-inspect safe git diff viewer with SWE-bench test file safety assertions.
---

# test-gate Skill

Consolidates regression testing (`blast-radius`) and git diff inspection (`diff-inspect`) into a single authoritative gatekeeper for SWE-bench agent workflows.

## Key Capabilities

1. **Distance-1 Regression Tests (`--blast` or default)**:
   - Auto-detects modified Python files in the git working tree or accepts explicit targets.
   - Maps source files to neighbor test files (e.g. `fastapi/routing.py` -> `tests/test_routing.py`, `rich/ansi.py` -> `tests/test_ansi.py`).
   - Runs pytest with 60s/file timeout and formats concise failure summaries with traceback snippets.
   - Guard against 0-test false passes: flags `UNVERIFIED_NO_TESTS` if no tests were found.

2. **Safe Git Diff & Safety Assertion (`--diff`)**:
   - Runs safe read-only git diff against `HEAD`.
   - **CRITICAL SWE-BENCH SAFETY ASSERTION**: Detects any test file modifications in `/workspace` (`tests/*`, `test_*.py`, `conftest.py`). Emits a loud `🚨 FORBIDDEN TEST FILE MODIFIED IN /WORKSPACE` warning with exact `git checkout -- <file>` revert commands because Container B discards test edits.
   - Detects untracked scratch files (`repro*.py`, `tmp*.py`) that `git add -N .` would pollute the patch with.
   - Summarizes lines added, lines deleted, and files touched with a context-capped diff preview.

3. **Full Patch Readiness Gate (`--status`)**:
   - Synthesizes diff stats, test file safety, scratch file checks, and AST syntax validation across all touched `.py` files.
   - Outputs definitive `[✓ READY]` or `[✗ BLOCKED]` advice for calling `submit_patch()`.

4. **Structured JSON Output (`--json`)**:
   - Returns 100% Pydantic v2 structured schemas (`TestGateResult`) for programmatic tool use.

## How to Run

### Auto-run regression tests on modified files
```bash
python3 gate.py
```

### Run regression tests for an explicit file
```bash
python3 gate.py fastapi/routing.py
# or explicitly
python3 gate.py --blast rich/ansi.py
```

### Inspect diff and verify no test files were touched
```bash
python3 gate.py --diff
```

### Check full patch readiness before calling submit_patch
```bash
python3 gate.py --status
```

### Machine-readable JSON output
```bash
python3 gate.py --status --json
```

## Guarantees
- **Always Safe**: Read-only, never mutates files, and always exits with code 0.
- **Context-Safe**: Tracebacks and diffs are capped to avoid LLM context blowout.
- **Actionable Diagnostics**: When tests fail, outputs exact test names; when no files are modified, lists available repo files; when invalid flags are passed, prints helpful examples.
