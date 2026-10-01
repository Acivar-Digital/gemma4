---
name: code-oracle
description: Multi-domain coding oracle for Python expression evaluation, ANSI/hex inspection, Unicode terminal cell width, HTML escaping & tag balance, JSON Schema/OpenAPI validation, and AST syntax/import checking.
---

# code-oracle Skill

Multi-domain coding oracle designed for SWE agents to verify domain nuances that trigger subtle test failures without repo-specific hardcoding. Zero external dependencies.

## Supported Modes & Examples

### 1. Safely Evaluate Python Expressions (`--eval`)
Evaluates expressions in a sandbox with standard builtins and modules (`json`, `re`, `math`, `datetime`, etc.):
```bash
python3 oracle.py --eval 'len([x for x in range(10) if x % 2 == 0])'
python3 oracle.py --eval 'json.dumps({"status": "ok", "items": [1, 2]})'
```
*Outputs: Type, `repr()`, `len()`, formatted string, and actionable runtime diagnostics.*

### 2. Hex Dump & ANSI / Escape Inspector (`--hex`)
Inspects raw bytes, ANSI CSI/SGR styling (`\x1b[31;1m`), OSC 8 hyperlinks, and invisible characters (`\r`, `\n`, `\t`, `\u200d`, `\ufe0f`):
```bash
python3 oracle.py --hex $'\x1b[31;1mError\x1b[0m\r\n'
python3 oracle.py --hex path/to/file_with_hidden_characters.txt
```
*Flags unclosed ANSI styles, lone `\r` line overwrites, and invisible zero-width spaces.*

### 3. Terminal Cell Display Width (`--width`)
Calculates exact monospaced terminal columns (handling CJK Wide `W`/`F` as 2 cells, emojis as 2 cells, ZWJ sequences as 2 cells, combining marks as 0 cells, ANSI escapes as 0 cells) vs `len(text)`:
```bash
python3 oracle.py --width '👨‍👩‍👧‍👦 Family'
python3 oracle.py --width $'\x1b[32mClean Output\x1b[0m'
```
*Prevents table border misalignment and padding bugs in Rich/CLI tools.*

### 4. HTML Entity & Tag Balance (`--html-esc`)
Verifies HTML entity escaping (`&lt;`, `&gt;`, `&amp;`), tag balance/nesting, and script tags:
```bash
python3 oracle.py --html-esc '<div><p>Hello & welcome</p></div>'
python3 oracle.py --html-esc templates/swagger_ui.html
```
*Flags unclosed tags, misnested elements, raw ampersands, and raw `<`/`>` inside scripts.*

### 5. OpenAPI & JSON Schema Validator (`--schema`)
Inspects JSON Schema / OpenAPI structure, checks `$defs` vs `definitions`, resolves local `$ref` pointers (flags dangling references), checks `anyOf` with `null`, and validates schema health:
```bash
python3 oracle.py --schema openapi.json
python3 oracle.py --schema '{"$defs": {"Item": {"type": "string"}}, "$ref": "#/$defs/Item"}'
```
*Catches Pydantic v1 vs v2 `$defs`/`definitions` migration bugs and invalid type leaks.*

### 6. AST Syntax & Import Checker (`--syntax`)
Validates AST syntax (`ast.parse`), catches regex lookbehind issues, and checks top-level module import resolution without executing module side-effects:
```bash
python3 oracle.py --syntax rich/text.py
python3 oracle.py --syntax  # auto-checks modified files from git status
```

### 7. Overview & Diagnostics (Empty Invocation)
Invoking `python3 oracle.py` without arguments prints a clean, compact overview of all 6 modes with copy-pasteable example commands and exits code 0.

## Options
- `--json`: Outputs structured JSON for automated pipelines and agent evaluation.
- Positional auto-detection: `.py` -> `--syntax`, `.json` -> `--schema`, `.html` -> `--html-esc`.
