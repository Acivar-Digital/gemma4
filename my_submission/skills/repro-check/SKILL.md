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

### 1. Direct Python Snippet
Pass a Python code string containing your reproduction assertion:

```python
run_skill_script(
    skill_name="repro-check",
    file_path="check.py",
    args=["from rich.text import Text; assert Text.from_ansi('\\n').plain == '\\n'"]
)
```

Or multiline assertion matrix:

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

### 2. Missing-Validation Defect Verification (`--expect-exception`)
For bugs where invalid input is silently accepted without validation:

```python
run_skill_script(
    skill_name="repro-check",
    file_path="check.py",
    args=["--expect-exception", "ValueError", "from mypkg import validate; validate(-1)"]
)
```
- **Baseline reproduction**: If the baseline code fails to raise `ValueError`, `repro-check` marks `defect_confirmed=True` (`🎯 DEFECT CONFIRMED (Expected Exception Not Raised)`).
- **Post-fix verification**: When the fix causes `ValueError` to be raised, `repro-check` marks `status=PASSED` (`✅ PASSED: Expected exception 'ValueError' was raised as expected`).
- Supports built-in and custom exception types (e.g. `ValueError`, `KeyError`, `AssertionError`, `pydantic.ValidationError`).

### 3. Base64-Encoded Assertion Code (`--b64` / `--base64`)
To completely eliminate JSON delimiter collisions and shell escaping bugs:

```python
run_skill_script(
    skill_name="repro-check",
    file_path="check.py",
    args=["--b64", "YXNzZXJ0IDQgKyA0ID09IDg="]
)
```

CLI:
```bash
python3 check.py --b64 "YXNzZXJ0IDQgKyA0ID09IDg="
# Or with --expect-exception:
python3 check.py --expect-exception ValueError --b64 "cmFpc2UgVmFsdWVFcnJvcignYmFkJyk="
```

### 4. Raw Multiline Script Execution (`--file` / `--stdin`)
To avoid shell quote-escaping issues, newlines, and emoji/unicode truncation:

```bash
# Write script to /tmp using write_file
# Then execute via --file:
python3 check.py --file /tmp/repro.py

# Or with --expect-exception:
python3 check.py --file /tmp/repro.py --expect-exception ValueError

# Or via stdin pipe:
cat /tmp/repro.py | python3 check.py --expect-exception ValueError
```

## CLI Options & Flags
- `--expect-exception, -e <EXC>`: Expect a specific exception type (e.g. `ValueError`, `KeyError`, `AssertionError`).
  - Baseline silently completes -> `defect_confirmed=True` (exit 1).
  - Fix raises exception -> `status=PASSED` (exit 0).
- `--b64, --base64 <B64>`: Execute base64-encoded Python assertion code to completely eliminate shell quote-escaping or JSON crashes.
- `--file, -f <FILE>`: Execute raw Python script from file inside `/tmp`.
- `--stdin, -`: Execute raw Python script read from standard input.
- `--help, -h`: Show usage instructions and exit (exit code 0).

## Deep Assertion Diagnostics & Value Diffs
When standard assertions fail (e.g. `assert a == b`), standard Python output often conceals subtle differences like invisible ANSI escapes, Unicode widths, or dictionary key sets. `repro-check` provides deterministic, high-signal diagnostics:

1. **String Mismatch**:
   - Explicit `Actual:` and `Expected:` values with exact string lengths.
   - Pinpoints the first character divergence: `Diff at index <i>: actual=<val_a> (hex: <hex_a>) vs expected=<val_b> (hex: <hex_b>)`.
   - **ANSI & Control Escape Breakdown**: When `\x1b` or control characters are present, decodes escape sequences (e.g. CSI 31m Red text, CSI 0m Reset) and invisible characters (CR `\r`, zero-width spaces `\u200b`, BOM `\ufeff`) so hidden differences are immediately visible.
2. **Dictionary / JSON Mismatch**:
   - Identifies **Missing keys** (in expected but missing from actual).
   - Identifies **Extra keys** (in actual but not expected).
   - Highlights **Value differences for shared keys** with types and representations.
3. **Sequence / List Mismatch**:
   - Reports exact **Length differences** (`actual` vs `expected`).
   - Pinpoints the **First differing element with its index** and types.
4. **Actionable Root Cause Hints**:
   - Outputs a dedicated section: `💡 ROOT CAUSE HINT FOR LLM:` summarizing what differed and providing actionable instructions for adjusting the codebase.

## Hardened Quote Sanitization & Syntax Pre-Validation
`repro-check` includes native hardening against common LLM formatting artifacts:
1. **Redundant Outer Quotes**: Strips outer `'...'`, `"..."`, `"""..."""`, `'''...'''`, and escaped outer `\"...\"` / `\'...\'`.
2. **Markdown Code Fences**: Automatically strips ```python ... ``` and ``` ... ``` fences.
3. **Escaped Quote Normalization**: Normalizes literal `\"` to `"` and `\'` to `'` when passed due to double-escaping in JSON tool payloads.
4. **AST Pre-Parse Syntax Check**: Before writing any file to `/tmp` or spawning a process, `check.py` validates the code syntax with `ast.parse()`. If syntax is malformed, it outputs a clean, formatted `SYNTAX_ERROR` message with line number, snippet, and caret, exiting with code 1 rather than hanging or crashing.

## Guarantees
- **Native Exception Expectation**: Deterministically catches missing validation bugs with `--expect-exception`.
- **Omnivorous Execution**: Auto-asserts bare comparisons (`a == b`), auto-invokes uncalled test functions (`def test_...():`), and cleanly strips markdown fences.
- **Quote Sanitization & Hardening**: Automatically handles outer quotes, escaped quotes from JSON, and markdown fences.
- **AST Pre-Parse Validation**: Pre-checks Python syntax and cleanly reports `SYNTAX_ERROR` without unhandled crashes.
- **Deterministic Exit Codes**: Exits 0 on verification pass; exits 1 on assertion failure, missing expected exception, runtime exception, or syntax error.
- **Path Containment Guard (Strict `/tmp` Isolation)**:
  - All scratch files are strictly written into `/tmp`.
  - Execution runs with `cwd` inside an isolated temporary directory in `/tmp`.
  - Active containment guard intercepts and cleans up any accidental `/workspace/tmp/...` files, leaving `git diff HEAD` 100% clean.
- **Uses workspace code**: Automatically sets `PYTHONPATH` prioritizing `/workspace` and `/workspace/src` so edits are immediately reflected across flat and `src/` layouts.
- **Smart Result Classification**: Distinguishes between `DEFECT CONFIRMED (Assertion Failed)`, `DEFECT CONFIRMED (Expected Exception Not Raised)`, `DEFECT REPRODUCED (Workspace Runtime Exception)`, `PASSED`, and `PROBE RUN`.
- **Probe Budget Limiter (Circuit Breaker)**: Enforces a strict 2-probe cap on pure exploratory checks. Automatically bypassed when testing assertions or `--expect-exception`.
- **Fast & Safe (<2s)**: 35-second execution timeout, capped output, zero git pollution.

## Probe Budget & Circuit Breaker (Max 2 Probes)
To prevent burning tool calls on open-ended exploratory `print()` probes:
- Pure probe snippets (exit code 0 with no assertions, test functions, or expected exceptions) increment a probe counter stored in `/tmp/.swegemma_repro_probe_count`.
- **2-Probe Cap**: When counter reaches 2, `repro-check` emits:
  `[repro-check] ⚠️ PROBE BUDGET REACHED (2/2 probes used): You have executed 2 exploratory probes without reproducing a defect or failing an assertion. Stop probing! Formulate your defect hypothesis, locate candidate source lines, and call edit_file immediately.`
- **Automatic Reset**: Any defect reproduction (`AssertionError`, missing exception, or `Workspace Runtime Exception`) or passing verification (`✅ PASSED`) automatically resets the probe counter to 0.
- **Rule**: Do not continue probing after 2 exploratory probes. Immediately formulate a candidate fix and invoke `edit_file`.
