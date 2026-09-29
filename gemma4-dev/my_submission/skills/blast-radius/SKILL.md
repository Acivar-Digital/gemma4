---
name: blast-radius
description: Runs targeted pytest tests across the Distance-1 Blast Radius (target file + its direct consumers) to verify changes and catch regressions without running the entire test suite.
---

# blast-radius Skill

Targeted regression and test verification tool based on **Distance-1 Code Blast Radius**. 

Instead of guessing or running the entire slow test suite, `blast-radius`:
1. Maps the target file to its direct test file (e.g. `rich/text.py` -> `tests/test_text.py`).
2. Uses AST analysis to identify all direct consumers (files that import the target).
3. Automatically runs `pytest` across the target test and immediate consumer tests (e.g. `tests/test_ansi.py`, `tests/test_console.py`).
4. Produces a clean, concise, 25-line maximum test report highlighting exact failures and broken assertions.

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

### Test multiple files or a specific test file
```python
run_skill_script(
    skill_name="blast-radius",
    file_path="test_blast.py",
    args=["rich/text.py", "tests/test_ansi.py"]
)
```

## Guarantees
- **Ultra-Fast (<3s)**: Only tests the targeted distance-1 dependency cluster, never the whole test suite.
- **Context-Safe**: Output is strictly capped to 30 lines.
- **Always Safe**: Never pollutes `/workspace` and always exits cleanly with code 0.
