---
name: diff-inspect
description: Inspects git status and unified git diff against baseline or HEAD in /workspace without modifying any files or blowing the context budget.
---

# diff-inspect Skill

Safe, read-only Git status and diff inspector for `/workspace`.

## Why Use This?
- **Verify edits before `submit_patch`**: `submit_patch` is final and terminates the session. `diff-inspect` allows you to inspect your exact changes before submitting.
- **Catch scratch file pollution**: `submit_patch` runs `git add -N . && git diff HEAD`. Any scratch reproduction files created inside `/workspace` will pollute your patch. `diff-inspect` runs `git status --short` to alert you to untracked files (`??`) before submission.
- **Zero modification**: Unlike `submit_patch` or git add commands, `diff-inspect` does not alter `/workspace`, `.git`, or the git index.
- **Context-Safe**: Automatically caps diff output at 100 lines so large diffs never blow the agent's 32K context window.
- **Always exits code 0**: Never crashes your agent loop.

## How to Run

### Basic inspection (status + diff against baseline/HEAD)
```python
run_skill_script(
    skill_name="diff-inspect",
    file_path="diff.py",
    args=[]
)
```

### Inspect specific files
```python
run_skill_script(
    skill_name="diff-inspect",
    file_path="diff.py",
    args=["fastapi/routing.py"]
)
```

### Inspect diff summary (--stat)
```python
run_skill_script(
    skill_name="diff-inspect",
    file_path="diff.py",
    args=["--stat"]
)
```

## Guarantees
- **Strictly read-only**: Executes only read-only `git` commands (`git status --short`, `git diff`).
- **Context-capped**: Capped at 100 lines of diff output with clear omission notices.
- **Deterministic**: Resolves workspace cleanly across Docker containers and test runners without race conditions.
- **Zero external dependencies**: Standard Python library only.
