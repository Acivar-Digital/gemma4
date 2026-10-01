---
name: blast-radius
description: Runs targeted pytest tests across the Distance-1 Blast Radius (target file + its direct consumers) with symbol-level test resolution, framework path mapping, 0-test protection, and smart verdicts.
---

# blast-radius Skill

Targeted regression and test verification tool based on **Distance-1 Code Blast Radius** and **Smart AST Test Resolution**.

Instead of guessing or running the entire slow test suite, `blast-radius`:
1. **Framework-Aware Path Mapping**: Directly maps framework tutorials (e.g. FastAPI `docs_src/<category>/tutorial<N>[_<variant>].py` -> `tests/test_tutorial/test_<category>/test_tutorial<N>.py`, automatically stripping python version variants like `_py310`, `_py39`, `_an_py310`).
2. **Symbol-Level Test Resolution**: In addition to file stem matching, parses git diff and AST to extract modified symbols (classes, methods, functions, constants) and scans test files for direct imports or call-sites.
3. **Distance-1 Consumer Blast Radius**: Uses AST analysis to identify all direct consumers (files importing the target module) and discovers their corresponding regression tests.
4. **0-Test Guard (Eliminates False Green)**: When 0 tests are found or executed, never returns `passed=True`. Explicitly outputs `status: UNVERIFIED_NO_TESTS` and flags required verification so agents never falsely assume an unverified patch succeeded.
5. **Strict Guard for Direct Test Failures & Pre-Fix Conflicts**: When direct unit tests fail, `passed` is strictly `False`. Even if distance-1 consumer tests pass and a pre-fix baseline conflict is suspected, verification CANNOT pass while direct unit tests fail. Reports `status: FAILED_DIRECT_TESTS_SUSPECTED_CONFLICT` with an explicit advisory warning to verify whether the edited file is indeed the target file requested by the issue.
6. **Legitimate Multi-File Diff Support**: Non-alarmist handling of multi-file changes across repository files without panic-inducing revert warnings.
7. **Context-Capped Diagnostics**: Produces deterministic failure triage reports with failing statements, expected vs actual values, diff previews, and root-cause explanations.

## How to Run

### Test an explicitly modified file
```python
run_skill_script(
    skill_name="blast-radius",
    file_path="test_blast.py",
    args=["rich/text.py"]
)
```

### Auto-test all currently modified files in git
If no arguments are passed, it automatically runs `git status` to detect your edited files and tests their blast radius:
```python
run_skill_script(
    skill_name="blast-radius",
    file_path="test_blast.py"
)
```

### Test multiple files or doc tutorials
```python
run_skill_script(
    skill_name="blast-radius",
    file_path="test_blast.py",
    args=["docs_src/body/tutorial001_py310.py"]
)
```

### Structured JSON Output
Pass `--json` to get complete machine-readable Pydantic v2 diagnostics:
```python
run_skill_script(
    skill_name="blast-radius",
    file_path="test_blast.py",
    args=["--json", "fastapi/routing.py"]
)
```

## Status Values in JSON Mode
- `PASSED`: All direct and consumer tests passed cleanly (exit code 0, at least 1 test executed).
- `FAILED_DIRECT_TESTS_SUSPECTED_CONFLICT`: Direct unit tests failed while distance-1 consumer tests passed. Pre-fix baseline conflict suspected, but verification CANNOT pass while direct tests fail (`passed = False`).
- `FAILED`: Real regression detected in tests (or runtime error).
- `UNVERIFIED_NO_TESTS`: 0 tests were found or executed for the modified targets. Verification required before submission (`passed = False`).

## Guarantees
- **Ultra-Fast (<3s)**: Only tests the targeted distance-1 dependency cluster, never the whole test suite.
- **Context-Safe**: Failure report is strictly capped to 40 lines.
- **Always Safe**: Never pollutes `/workspace` and always exits cleanly with code 0.
