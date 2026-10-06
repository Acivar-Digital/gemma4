---
name: test-gate
description: Authoritative gatekeeper consolidating blast-radius regression test runner and diff-inspect safe git diff viewer with SWE-bench test file safety assertions.
---

# test-gate Skill

Consolidates regression testing (`blast-radius`) and git diff inspection (`diff-inspect`) into a single authoritative gatekeeper for SWE-bench agent workflows.

## Key Capabilities

1. **Distance-1 Regression Tests (`--blast`, `blast`, or default)**:
   - Auto-detects modified Python files in the git working tree or accepts explicit targets.
   - Maps source files to neighbor test files (e.g. `fastapi/routing.py` -> `tests/test_routing.py`, `rich/ansi.py` -> `tests/test_ansi.py`).
   - Runs pytest with 60s/file timeout (configurable via `-t` or `--timeout`) and formats concise failure summaries with traceback snippets.
   - Guard against 0-test false passes: flags `UNVERIFIED_NO_TESTS` if no tests were found.

2. **Safe Git Diff & Safety Assertion (`--diff`, `diff`, `-d`)**:
   - Runs safe read-only git diff against `HEAD`.
   - **CRITICAL SWE-BENCH SAFETY ASSERTION**: Detects any test file modifications in `/workspace` (`tests/*`, `test_*.py`, `conftest.py`). Emits a loud `🚨 FORBIDDEN TEST FILE MODIFIED IN /WORKSPACE` warning with exact `git checkout -- <file>` revert commands because Container B automatically reverts (discards) test-file modifications during evaluation.
   - Diff truncation safety: truncates diffs exceeding 500 lines or 50KB to protect LLM context windows, providing file-by-file stats and net changes.
   - Detects untracked scratch files (`repro*.py`, `tmp*.py`) that `git add -N .` would pollute the official patch with.

3. **Full Patch Readiness Gate (`--status`, `status`, `-s`)**:
   - Synthesizes diff stats, test file safety, scratch file checks, and AST syntax validation across all touched `.py` files.
   - Outputs definitive `[✓ READY TO SUBMIT]` or `[✗ BLOCKED]` advice for calling `submit_patch()`.

4. **Structured JSON Output (`--json`, `-j`)**:
   - Returns 100% Pydantic v2 structured schemas (`TestGateResult`) for programmatic tool use.

## How to Run

### Smart Default (tests modified files or shows status)
```bash
python3 gate.py
```

### Positional Argument Routing
```bash
python3 gate.py diff                 # View diff & check test file safety
python3 gate.py blast                # Run neighbor tests on touched files
python3 gate.py status               # Check patch readiness before submitting
python3 gate.py fastapi/routing.py   # Run neighbor tests for target file
```

### Forgiving Flags & Timeout Tuning
```bash
python3 gate.py -d                   # Short flag for diff
python3 gate.py -s                   # Short flag for status
python3 gate.py -b -t 30             # Blast with 30s timeout per test file
python3 gate.py status --json        # Machine-readable JSON output
```

## Guarantees
- **Always Safe**: Read-only, never mutates files, and always exits with code 0.
- **Context-Safe**: Tracebacks and diffs are capped (<500 lines / <50KB) to prevent LLM context blowout.
- **Actionable Diagnostics**: Emits exact failing test names, line numbers, statements, and revert commands.
