---
name: syntax-guard
description: Fast, zero-dependency Python AST syntax and regex verification tool to catch SyntaxError, IndentationError, unterminated strings, and unescaped regex lookbehinds immediately after editing files.
---

# syntax-guard Skill

Immediate post-edit Python AST syntax and regex verification tool.

## Why Use This?
- **Immediate Post-Edit Validation**: Run `syntax-guard` immediately after calling `edit_file` or `write_file` to catch broken syntax before wasting tool calls on failed test runners or debugging mysterious crashes.
- **Catches Regex & Lookbehind Failures**: Flags unescaped or variable-width regex lookbehinds (e.g. `r"(?<=\n"`, `re.search(r"(?<=a*)b")`) and malformed regex patterns that pass basic string tokenization but crash at runtime.
- **Catches Indentation & String Issues**: Identifies `IndentationError`, `TabError`, and unterminated string literals with visual caret indicators pointing to the exact line and column.
- **Fast & Zero-Dependency (<0.05s)**: Pure Python standard library (`ast`, `sys`, `subprocess`, `argparse`, `re`, `json`). No third-party packages required.
- **Deterministic Exit Codes**: Exits with code `0` when all target files are clean, and exit code `1` when syntax errors are detected.

## How to Run

### 1. Verify a specific edited file
```python
run_skill_script(
    skill_name="syntax-guard",
    file_path="syntax.py",
    args=["path/to/target.py"]
)
```

### 2. Auto-verify all modified files in git status
If no arguments are provided, `syntax-guard` automatically checks all modified and untracked `.py` files in the repository using `git status -s`:
```python
run_skill_script(
    skill_name="syntax-guard",
    file_path="syntax.py"
)
```

### 3. Verify multiple files
```python
run_skill_script(
    skill_name="syntax-guard",
    file_path="syntax.py",
    args=["rich/text.py", "rich/console.py"]
)
```

### 4. Structured JSON output (--json)
```python
run_skill_script(
    skill_name="syntax-guard",
    file_path="syntax.py",
    args=["--json", "path/to/target.py"]
)
```

## CLI Parameters
- `files` (positional, optional): One or more Python files to verify. If omitted, checks all modified/untracked `.py` files from `git status`.
- `--workspace`, `-w` (optional): Workspace directory path (defaults to `SWEGEMMA_WORKSPACE`, `/workspace`, or repository root).
- `--json` (optional): Outputs results as structured JSON.
- `--verbose`, `-v` (optional): Verbose output mode.

## Output Format & Schema

### Human-Readable Console Output (Default)
When errors are detected:
```
✗ [syntax-guard] Syntax error(s) detected in 1 of 1 file(s):

================================================================================
[UnescapedRegexLookbehind] /workspace/rich/text.py:42:24
Type:    UnescapedRegexLookbehind
Message: UnescapedRegexLookbehind: missing ), unterminated subpattern (in re.split())
Snippet:
   41 | def split_lines(text: str):
>  42 |     return re.split(r"(?<=\n", text)
      |                        ^
   43 | 
================================================================================

Fix: Correct syntax error(s) before running tests or calling submit_patch().
```

When all files pass:
```
✓ [syntax-guard] All 1 Python file(s) passed AST syntax verification.
```

### Structured JSON Schema (`--json`)
```json
{
  "status": "PASSED | FAILED",
  "files_checked": [
    "/workspace/rich/text.py"
  ],
  "total_checked": 1,
  "total_errors": 0,
  "errors": [
    {
      "file": "/workspace/rich/text.py",
      "line": 42,
      "column": 24,
      "error_type": "UnescapedRegexLookbehind",
      "message": "UnescapedRegexLookbehind: missing ), unterminated subpattern (in re.split())",
      "snippet": "   41 | def split_lines(text: str):\n>  42 |     return re.split(r\"(?<=\\n\", text)\n      |                        ^\n   43 | "
    }
  ]
}
```

## Guarantees
- **Pure Standard Library**: Zero dependencies outside Python standard library (`ast`, `sys`, `subprocess`, `argparse`, `re`, `json`, `pathlib`).
- **Context-Safe**: Generates compact snippets (3 lines of context max) with clean visual pointers to avoid blowing the LLM context budget.
- **Exit Code Contract**: Returns `0` on clean syntax, returns `1` if any file contains syntax errors.
