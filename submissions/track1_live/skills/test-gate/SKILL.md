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
   - Diff truncation safety: truncates diffs exceeding 80 lines or 6KB to protect LLM context windows, providing file-by-file stats and net changes.
   - Detects untracked scratch files (`repro*.py`, `tmp*.py`) that `git add -N .` would pollute the official patch with.

3. **Full Patch Readiness Gate (`--status`, `status`, `-s`)**:
   - Synthesizes diff stats, test file safety, scratch file checks, and AST syntax validation across all touched `.py` files.
   - Outputs definitive `[✓ READY TO SUBMIT]` or `[✗ BLOCKED]` advice for calling `submit_patch()`.

4. **Structured JSON Output (`--json`, `-j`)**:
   - Returns 100% Pydantic v2 structured schemas (`TestGateResult`) for programmatic tool use.

## Tool Invocation Contract

Pass the following parameters to `run_skill_script`:
* skill_name: "test-gate"
* file_path: "gate.py"
* args: List of string arguments

## How to Run

### Via ADK `run_skill_script`

#### 1. Smart Default (tests modified files or shows status)
```python
skill_name: "test-gate", file_path: "gate.py", args: []
```
Or via `args: [...]` schema:
```yaml
args: []
```

#### 2. Positional Argument Routing
```python
skill_name: "test-gate", file_path: "gate.py", args: ["diff"]                 # View diff & check test file safety
skill_name: "test-gate", file_path: "gate.py", args: ["blast"]                # Run neighbor tests on touched files
skill_name: "test-gate", file_path: "gate.py", args: ["status"]               # Check patch readiness before submitting
skill_name: "test-gate", file_path: "gate.py", args: ["fastapi/routing.py"]   # Run neighbor tests for target file
```
Or via `args: [...]` schema:
```yaml
args: ["diff"]                 # View diff & check test file safety
args: ["blast"]                # Run neighbor tests on touched files
args: ["status"]               # Check patch readiness before submitting
args: ["fastapi/routing.py"]   # Run neighbor tests for target file
```

#### 3. Forgiving Flags & Timeout Tuning
```python
skill_name: "test-gate", file_path: "gate.py", args: ["-d"]                   # Short flag for diff
skill_name: "test-gate", file_path: "gate.py", args: ["-s"]                   # Short flag for status
skill_name: "test-gate", file_path: "gate.py", args: ["-b", "-t", "30"]       # Blast with 30s timeout per test file
skill_name: "test-gate", file_path: "gate.py", args: ["status", "--json"]     # Machine-readable JSON output
```
Or via `args: [...]` schema:
```yaml
args: ["-d"]                   # Short flag for diff
args: ["-s"]                   # Short flag for status
args: ["-b", "-t", "30"]       # Blast with 30s timeout per test file
args: ["status", "--json"]     # Machine-readable JSON output
```

## Guarantees
- **Always Safe**: Read-only, never mutates files, and always exits with code 0.
- **Context-Safe**: Tracebacks and diffs are capped (<80 lines / <6KB) to prevent LLM context blowout.
- **Actionable Diagnostics**: Emits exact failing test names, line numbers, statements, and revert commands.
