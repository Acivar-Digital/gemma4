---
name: fast-grep
description: Fast codebase regex and keyword search across /workspace with probability ranking, definition prioritization, AST function flashing, sliding context window, and clean code blocks for edit_file.
---

# fast-grep Skill

Fast, omnivorous codebase search engine for locating symbols, regex patterns, function calls, and error messages across `/workspace`.

## Features
- **Relevance & Definition-First Ranking**: Scores matches so function and class definitions (`def`, `async def`, `class`, `@decorator`) appear at the top (+120 to +195 score bump) rather than being drowned out by call sites or comments.
- **Symbol Bonuses**: Exact symbol name matches receive +75 bonus and substring matches receive +50 bonus.
- **Forgiving & Omnivorous Arguments**: Accepts positional search term `args: ["pattern"]` or `args: ["pattern", "path"]`, flags `-p`/`--pattern`, `-d`/`--dir`, `-i`/`--ignore-case`, `-w`/`--window`, `-m`/`--max-matches`, and `--json`.
- **Regex-to-Literal Fallback**: When an invalid regex is provided (e.g. unescaped parentheses `def foo(`, unbalanced brackets, or bad escapes), falls back to literal substring search without crashing.
- **Crash & Infinite Loop Immunity**: Limits file scanning to 500KB and 5000 lines per file, detects and skips binary files via null-byte inspection, guards against symlink cycles, and caps total matches to prevent context flooding.
- **Actionable Zero-Match Diagnostics**: When 0 matches are found:
  - Detects if case mismatch occurred and suggests case-insensitive search (`-i`).
  - Detects if path filter was too narrow and reveals occurrences in other repository files.
  - Generates fuzzy symbol candidate suggestions from AST identifiers.
  - Breaks compound queries into tokenized sub-terms.
  - Outputs concrete argument suggestions for the next search call.
- **Top 2 AST Scope Flashing**: Extracts and displays top 2 enclosing functions or classes with complete decorators and line numbers.
- **Target-Centered Sliding Window**: Centers context window around target line (default 15 lines before to 25 lines after, configurable via `-w`).
- **Clean Code Block for `edit_file`**: Provides unadorned code block with exact Python indentation for the top match.
- **Never crashes**: Always exits cleanly with code 0.

## Tool Invocation Contract

Pass the following parameters to `run_skill_script`:

* skill_name: "fast-grep"
* file_path: "grep.py"
* args: List of string arguments

### Common Search Patterns:
1. Search symbol across repository:
   args: ["APIRouter"]
2. Search within specific directory:
   args: ["splitlines", "rich/"]
3. Case-insensitive search:
   args: ["-i", "apirouter"]
4. Search raw snippet (auto literal fallback):
   args: ["def format("]
5. Structured JSON output:
   args: ["--json", "APIRouter"]
