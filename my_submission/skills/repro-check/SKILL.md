---
name: repro-check
description: Executes a Python reproduction snippet or test assertion in an isolated process with workspace PYTHONPATH to verify a defect before editing and confirm the fix after editing.
---

# repro-check Skill

Fast, isolated Python verification tool to **reproduce a reported issue** and **confirm your fix**.

## Why Use This?
In SWE-bench and real-world issues, there is **no unit test in the repo for the reported bug yet**.
`blast-radius` only checks if existing tests still pass (regression check).
`repro-check` directly tests if the **defect reported in the issue description is resolved**.

## How to Run

Pass a Python code string containing your reproduction assertion:

```python
run_skill_script(
    skill_name="repro-check",
    file_path="check.py",
    args=["from rich.text import Text; assert Text.from_ansi('\\n').plain == '\\n'"]
)
```

You can also pass multi-line Python snippets:
```python
run_skill_script(
    skill_name="repro-check",
    file_path="check.py",
    args=["""
from rich.text import Text
assert Text.from_ansi("Hello").plain == "Hello"
assert Text.from_ansi("Hello\\n").plain == "Hello\\n"
assert Text.from_ansi("\\n").plain == "\\n"
"""]
)
```

## Guarantees
- **Runs outside `/workspace`**: Uses a temporary file in `/tmp`, leaving `git diff HEAD` 100% clean.
- **Uses workspace code**: Automatically sets `PYTHONPATH` to `/workspace` so changes in your edited files are immediately reflected.
- **Assertion-Aware**: Confirms whether assertions actually ran. Warns if code ran without `assert`.
- **Fast & Safe (<2s)**: 10-second timeout, capped output (max 20 lines), and always exits cleanly with code 0 so the agent never crashes on an `AssertionError`.
