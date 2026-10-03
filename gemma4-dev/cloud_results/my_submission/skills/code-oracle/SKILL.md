---
name: code-oracle
description: Multi-domain coding oracle for Python expression evaluation, ANSI/hex inspection, Unicode terminal cell width, HTML escaping & tag balance, JSON Schema/OpenAPI validation, and AST syntax/import checking.
---

# code-oracle Skill

Multi-domain coding oracle designed for SWE agents to verify domain nuances that trigger subtle test failures without repo-specific hardcoding. Zero external dependencies.

## Supported Modes & Forgiving CLI

### 1. Safely Evaluate Python Expressions (`-e`, `--eval`)
Evaluates expressions/statements in a sandbox with infinite-loop timeout protection (2.0s limit) and actionable error diagnostics:
```bash
python3 oracle.py --eval 'len([x for x in range(10) if x % 2 == 0])'
python3 oracle.py 1 + 2 * 3  # unquoted auto-evaluation
```
*Outputs: Type, `repr()`, `len()`, formatted string, and actionable runtime diagnostics.*

### 2. Hex Dump & ANSI / Escape Inspector (`-x`, `--hex`)
Inspects raw bytes, ANSI CSI/SGR styling (`\x1b[31;1m`), OSC 8 hyperlinks, and invisible characters (`\r`, `\n`, `\t`, `\u200d`, `\ufe0f`):
```bash
python3 oracle.py --hex $'\x1b[31;1mError\x1b[0m\r\n'
python3 oracle.py path/to/file_with_hidden_characters.txt
```
*Flags unclosed ANSI styles, lone `\r` line overwrites, and invisible zero-width spaces.*

### 3. Terminal Cell Display Width (`-w`, `--width`)
Calculates exact monospaced terminal columns (handling CJK Wide `W`/`F` as 2 cells, emojis as 2 cells, ZWJ sequences as 2 cells, combining marks as 0 cells, ANSI escapes as 0 cells) vs `len(text)`:
```bash
python3 oracle.py --width '👨‍👩‍👧‍👦 Family'
python3 oracle.py -w $'\\x1b[32mClean Output\\x1b[0m'
```
*Explains character-level width causes (e.g. `Character '🚀' occupies 2 terminal cells, whereas len() is 1`).*

### 4. HTML Entity & Tag Balance (`-H`, `--html-esc`)
Verifies HTML entity escaping (`&lt;`, `&gt;`, `&amp;`), tag balance/nesting, and script tags:
```bash
python3 oracle.py --html-esc '<div><p>Hello & welcome</p></div>'
python3 oracle.py '<div class="btn">Click</div>'  # auto-detected
```
*Flags unclosed tags, misnested elements, raw ampersands, and raw `<`/`>` inside scripts.*

### 5. OpenAPI & JSON Schema Validator (`-s`, `--schema`)
Inspects JSON Schema / OpenAPI structure, checks `$defs` vs `definitions`, resolves local `$ref` pointers with exact corrected path suggestions, checks `anyOf` with `null`, handles boolean/non-dict schemas, and prevents recursive `$ref` cycles:
```bash
python3 oracle.py --schema openapi.json
python3 oracle.py schema.json
```
*Catches Pydantic v1 vs v2 `$defs`/`definitions` migration bugs and invalid type leaks.*

### 6. AST Syntax & Import Checker (`-S`, `--syntax`)
Validates AST syntax (`ast.parse`), catches regex lookbehind issues, and checks top-level module import resolution without executing module side-effects:
```bash
python3 oracle.py --syntax rich/text.py
python3 oracle.py -S  # auto-checks modified files from git status
```

### 7. Overview & Diagnostics (Empty Invocation)
Invoking `python3 oracle.py` without arguments prints a clean, compact overview of all 6 modes with copy-pasteable example commands and exits code 0.

## Options & Auto-Detection
- `--json`, `-j`: Outputs structured JSON for automated pipelines and agent evaluation.
- Forgiving flags: `-e`, `-x`, `-w`, `-H`, `-s`, `-S`, `-j`, `-eval`, `---eval`.
- Positional auto-detection: `.py` -> syntax, `.json` / schema string -> schema, `.html` / tags -> html-esc, ANSI -> hex, unquoted tokens / expressions -> eval.
