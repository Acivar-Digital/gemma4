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

## How to Run (via run_skill_script)

Invoke the `run_skill_script` tool and supply these three parameters: `skill_name` (string), `file_path` (string), and `args` (list of strings). Each example below shows them as a JSON object.

### 1. Direct Python Snippet (`--code`)
```json
{
  "skill_name": "repro-check",
  "file_path": "check.py",
  "args": ["--code", "assert 1 == 1"]
}
```

### 2. Base64 Mode (`--b64`)
Eliminates JSON escaping and quote conflicts:
```json
{
  "skill_name": "repro-check",
  "file_path": "check.py",
  "args": ["--b64", "YXNzZXJ0IDQgKyA0ID09IDg="]
}
```

### 3. File Execution (`--file`)
Execute a scratch reproduction script saved in `/tmp`:
```json
{
  "skill_name": "repro-check",
  "file_path": "check.py",
  "args": ["--file", "/tmp/repro.py"]
}
```

### 4. Missing-Validation Defect Verification (`--expect-exception`)
For bugs where invalid input is silently accepted without validation:
```json
{
  "skill_name": "repro-check",
  "file_path": "check.py",
  "args": ["--expect-exception", "ValueError", "--code", "from mypkg import validate; validate(-1)"]
}
```
- **Baseline reproduction**: If baseline code silently completes without raising the exception, `defect_confirmed=True` (exit 1).
- **Post-fix verification**: When the fix causes the exception to be raised, `status=PASSED` (exit 0).

### 5. Configurable Timeout (`--timeout`)
Default timeout is 15s. Infinite loops (`while True: pass`) are killed cleanly via process group signal (`os.killpg`) without hanging:
```json
{
  "skill_name": "repro-check",
  "file_path": "check.py",
  "args": ["--timeout", "5", "--code", "while True: pass"]
}
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
