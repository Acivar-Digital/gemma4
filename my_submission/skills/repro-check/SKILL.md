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
- **Omnivorous Execution**: Auto-asserts bare comparisons (`a == b`), auto-invokes uncalled test functions (`def test_...():`), and cleanly strips markdown fences.
- **Runs outside `/workspace`**: Uses a temporary directory in `/tmp` as `cwd`, leaving `git diff HEAD` 100% clean and preventing any scratch file pollution.
- **Uses workspace code**: Automatically sets `PYTHONPATH` to `/workspace/src:/workspace` so changes in your edited files are immediately reflected, supporting both flat and `src/` layouts.
- **Smart Result Classification**: Distinguishes between `DEFECT CONFIRMED (Assertion Failed)`, `DEFECT REPRODUCED (Workspace Runtime Exception)`, `PASSED`, and `PROBE EXECUTION`.
- **Probe Budget Limiter (Circuit Breaker)**: Enforces a strict 2-probe cap on pure exploratory checks before warning the agent to formulate a hypothesis and edit source code immediately.
- **Fast & Safe (<2s)**: 45-second timeout, capped output, and always exits cleanly with code 0.

## Probe Budget & Circuit Breaker (Max 2 Probes)
To prevent burning tool calls on open-ended exploratory `print()` probes:
- Pure probe snippets (exit code 0 with no assertions or test functions) increment a probe counter stored in `/tmp/.swegemma_repro_probe_count`.
- **2-Probe Cap**: When counter reaches 2, `repro-check` emits:
  `[repro-check] ⚠️ PROBE BUDGET REACHED (2/2 probes used): You have executed 2 exploratory probes without reproducing a defect or failing an assertion. Stop probing! Formulate your defect hypothesis, locate candidate source lines, and call edit_file immediately.`
- **Automatic Reset**: Any defect reproduction (`AssertionError` or `Workspace Runtime Exception`) or passing verification (`✅ PASSED`) automatically resets the probe counter to 0.
- **Rule**: Do not continue probing after 2 exploratory probes. Immediately formulate a candidate fix and invoke `edit_file`.
