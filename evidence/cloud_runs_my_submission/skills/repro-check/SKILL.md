---
name: repro-check
description: Executes a Python reproduction snippet or test assertion in an isolated process with workspace PYTHONPATH to verify a defect before editing and confirm the fix after editing.
---

# repro-check Skill

Fast, isolated Python verification tool to **reproduce a reported issue** and **confirm your fix**.

## Why Use This?
In SWE-bench and real-world issues, there is **no unit test in the repo for the reported bug yet**.
`blast-radius` only checks regression of existing tests.
`repro-check` directly tests if the **reported defect is confirmed or resolved**.

## How to Run

### 1. Direct Python Snippet (Positional, `--code`, or Multiple Words)
```bash
python3 check.py "assert 1 == 1"
# Multiple unquoted tokens joined automatically:
python3 check.py assert 1 == 1
# Explicit code flag:
python3 check.py --code "from rich.text import Text; assert Text.from_ansi('\\n').plain == '\\n'"
```

### 2. Base64 Mode (`--b64` / `--base64`)
Eliminates JSON escaping and quote conflicts:
```bash
python3 check.py --b64 "YXNzZXJ0IDQgKyA0ID09IDg="
```

### 3. File or Stdin Pipe (`--file`, `repro.py`, stdin)
```bash
python3 check.py /tmp/repro.py
python3 check.py --file /tmp/repro.py
cat /tmp/repro.py | python3 check.py
```

### 4. Missing-Validation Defect Verification (`--expect-exception`, `-e`)
For bugs where invalid input is silently accepted without validation:
```bash
python3 check.py -e ValueError "from mypkg import validate; validate(-1)"
```
- **Baseline reproduction**: If baseline code silently completes without raising the exception, `defect_confirmed=True` (exit 1).
- **Post-fix verification**: When the fix causes the exception to be raised, `status=PASSED` (exit 0).

### 5. Configurable Timeout (`--timeout`, `-t`)
Default timeout is 15s. Infinite loops (`while True: pass`) are killed cleanly via process group signal (`os.killpg`) without hanging:
```bash
python3 check.py -t 5 "while True: pass"
```

## CLI Options & Flags
- `--code, -c <code>`: Code snippet to execute.
- `--b64, --base64 <b64>`: Base64-encoded Python snippet.
- `--file, -f <file>`: Script file path inside `/tmp`.
- `--expect-exception, -e <exc>`: Expected exception class name (e.g. `ValueError`, `KeyError`).
- `--timeout, -t <secs>`: Subprocess timeout in seconds (default: 15s).
- `--stdin, -`: Read script from standard input.
- `--help, -h`: Show usage help (exit 0).

## High-Signal LLM Diagnostics
On `AssertionError`, `repro-check` provides deterministic, structured inspection:
1. **Strings**: Lengths, exact character index of divergence (`Diff at index <i>: actual='...' (hex: 0x...) vs expected='...' (hex: 0x...)`), and decoded ANSI escape breakdown (`\x1b[31m`, CR `\r`, `\t`).
2. **Dicts / JSON**: Missing expected keys, unexpected extra keys, and shared key value differences.
3. **Sequences / Lists**: Length mismatch and first differing element with its index.
4. **Actionable Root Cause Hints**: Concrete `💡 ROOT CAUSE HINT FOR LLM:` explaining *why* the assertion failed and *how* to fix the code.

## Hardening & Guarantees
- **Forgiving Sanitization**: Strips outer markdown fences (```` ```python ... ``` ````), single `'...'`, double `"..."`, triple `'''...'''` / `"""..."""`, and escaped quotes.
- **AST Pre-Parse**: Validates syntax before creating files or running, printing a clean caret pointer without dumping raw Python tracebacks.
- **Crash & Infinite Loop Immunity**: 15s default timeout with process group signal cleanup (`os.killpg`).
- **Strict `/tmp` Containment**: Scratch files remain strictly in `/tmp`, preventing any git pollution.
- **Probe Circuit Breaker**: 2-probe cap on pure exploratory runs without assertions.
