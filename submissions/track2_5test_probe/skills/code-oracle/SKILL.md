---
name: code-oracle
description: Multi-domain coding oracle for Python expression evaluation, ANSI/hex inspection, Unicode terminal cell width, HTML escaping & tag balance, JSON Schema/OpenAPI validation, and AST syntax/import checking.
---

# code-oracle Skill

Multi-domain coding oracle designed for SWE agents to verify domain nuances that trigger subtle test failures without repo-specific hardcoding. Zero external dependencies.

## Tool Invocation Contract

Pass the following parameters to `run_skill_script`:
* skill_name: "code-oracle"
* file_path: "oracle.py"
* args: List of string arguments

## Supported Modes & Argument Patterns

### 1. Safely Evaluate Python Expressions (`-e`, `--eval`)
Evaluates expressions/statements in a sandbox with infinite-loop timeout protection (2.0s limit) and actionable error diagnostics:
```yaml
args: ["--eval", "len([x for x in range(10) if x % 2 == 0])"]
args: ["1 + 2 * 3"]  # auto-detected expression
```
*Outputs: Type, `repr()`, `len()`, formatted string, and actionable runtime diagnostics.*

### 2. Hex Dump & ANSI / Escape Inspector (`-x`, `--hex`)
Inspects raw bytes, ANSI CSI/SGR styling (`\x1b[31;1m`), OSC 8 hyperlinks, and invisible characters (`\r`, `\n`, `\t`, `\u200d`, `\ufe0f`):
```yaml
args: ["--hex", "\\x1b[31;1mError\\x1b[0m\\r\\n"]
args: ["path/to/file_with_hidden_characters.txt"]
```
*Flags unclosed ANSI styles, lone `\r` line overwrites, and invisible zero-width spaces.*

### 3. Terminal Cell Display Width (`-w`, `--width`)
Calculates exact monospaced terminal columns (handling CJK Wide `W`/`F` as 2 cells, emojis as 2 cells, ZWJ sequences as 2 cells, combining marks as 0 cells, ANSI escapes as 0 cells) vs `len(text)`:
```yaml
args: ["--width", "👨‍👩‍👧‍👦 Family"]
args: ["-w", "\\x1b[32mClean Output\\x1b[0m"]
```
*Explains character-level width causes (e.g. `Character '🚀' occupies 2 terminal cells, whereas len() is 1`).*

### 4. HTML Entity & Tag Balance (`-H`, `--html-esc`)
Verifies HTML entity escaping (`&lt;`, `&gt;`, `&amp;`), tag balance/nesting, and script tags:
```yaml
args: ["--html-esc", "<div><p>Hello & welcome</p></div>"]
args: ["<div class=\"btn\">Click</div>"]  # auto-detected
```
*Flags unclosed tags, misnested elements, raw ampersands, and raw `<`/`>` inside scripts.*

### 5. OpenAPI & JSON Schema Validator (`-s`, `--schema`)
Inspects JSON Schema / OpenAPI structure, checks `$defs` vs `definitions`, resolves local `$ref` pointers with exact corrected path suggestions, checks `anyOf` with `null`, handles boolean/non-dict schemas, and prevents recursive `$ref` cycles:
```yaml
args: ["--schema", "openapi.json"]
args: ["schema.json"]
```
*Catches Pydantic v1 vs v2 `$defs`/`definitions` migration bugs and invalid type leaks.*

### 6. AST Syntax & Import Checker (`-S`, `--syntax`)
Validates AST syntax (`ast.parse`), catches regex lookbehind issues, and checks top-level module import resolution without executing module side-effects:
```yaml
args: ["--syntax", "rich/text.py"]
args: ["-S"]  # auto-checks modified files from git status
```

### 7. Overview & Diagnostics (Empty Invocation)
Invoking with empty arguments `args: []` prints a clean, compact overview of all 6 modes with recommended argument examples and exits code 0.

## Options & Auto-Detection
- `--json`, `-j`: Outputs structured JSON for automated pipelines and agent evaluation.
- Forgiving flags: `-e`, `-x`, `-w`, `-H`, `-s`, `-S`, `-j`, `-eval`, `---eval`.
- Positional auto-detection: `.py` -> syntax, `.json` / schema string -> schema, `.html` / tags -> html-esc, ANSI -> hex, unquoted tokens / expressions -> eval.
