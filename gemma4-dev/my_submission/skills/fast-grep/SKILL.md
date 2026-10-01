---
name: fast-grep
description: Fast codebase regex and keyword search across /workspace with probability ranking, string/buffer verb boosting, call-site highlighting, and automatic AST function flashing for top 3 matches.
---

# fast-grep Skill

Fast, omnivorous codebase search tool for locating strings, regex patterns, function calls, and error messages across `/workspace`.

## Features
- **Relevance & Probability Ranking**: Automatically scores matches so core package definitions and implementations appear at the top, and markdown/docs/changelogs are demoted.
- **Definition-First Priority Ranking**: Definitions of functions, methods, and classes (`def`, `async def`, `class`, and decorators `@`) receive top-tier priority score bumps (+120 to +195 score bump), ensuring root definition targets rank prominently at the very top of search results rather than being drowned out by call sites or comments (preventing wrong-function/wrong-file edits like in `rich_4076`).
- **Exact & Substring Symbol Bonuses**: Matches in definition signatures receive dedicated bonuses (+75 for exact function/class name match, +50 for substring match), guaranteeing direct targets rank #1.
- **Definition & Call-Site Highlighting**: Highlights definition targets with `>>> ... <-- [DEFINITION TARGET]` and `[🎯 DEFINITION TARGET]` headers, and call-sites with `>>> ... <-- [CALL-SITE]` and `[⚡ STRING/BUFFER CALL-SITE]` headers. Top match previews display `[DEF]` tags for instant identification.
- **First-Class Tutorial Code (`docs_src/*.py`)**: Executable tutorial code in `docs_src/*.py` (e.g. FastAPI tutorials) is explicitly exempt from the `-40` documentation demotion penalty, ensuring tutorial definitions and call-sites are treated as first-class Python source files.
- **Auto-Tokenized Multi-Word Queries**: Automatically splits multi-word phrases (e.g. `"preserve newlines"`) into individual tokens for high-recall union/OR search rather than failing with 0 matches on a rigid literal string. Tokens trigger terse keyword expansions automatically.
- **String & Buffer Verb Boosting**: Automatically detects and boosts scores for core Python string and buffer transformation verbs (`splitlines`, `split`, `rstrip`, `strip`, `lstrip`, `replace`, `join`, `partition`, `decode`, `encode`, `from_ansi`).
- **Call-Site & Enclosing Scope Highlighting**: Identifies active call-sites transforming text/buffer variables and marks them with `>>> ... <-- [CALL-SITE]` and `[⚡ STRING/BUFFER CALL-SITE & TRANSFORM SCOPE]` headers.
- **Terse Issue Search Heuristics**: Automatically expands terse problem keywords (e.g., `newlines`, `newline`, `whitespace`, `indent`) to candidate string transformation operations to avoid flooding results with docstrings/comments.
- **Top 3 AST Function Flashing**: Automatically parses Python AST to extract and flash the **top 3 complete enclosing functions** (with exact line numbers) directly in the tool output.
- **Concise Match Index**: Displays a clean summary of all other ranked matches for quick reference.
- **Context-Safe**: Caps large functions at 100 lines with middle folding to preserve the 32K context budget.
- **Never crashes**: Always exits cleanly with code 0.

## Searching Terse Issues (String/Buffer Verbs)

When encountering terse issue descriptions like *"preserve newlines"*, *"strip trailing space"*, or *"corrupted multibyte decoding"*, `fast-grep` auto-tokenizes multi-word queries and activates heuristic expansions. You can also search string transformation operations directly:
- **Line/Splitting operations**: `splitlines`, `split`, `partition`
- **Whitespace/Trimming operations**: `rstrip`, `strip`, `lstrip`
- **Replacement/Joining operations**: `replace`, `join`
- **Encoding/Decoding operations**: `decode`, `encode`, `from_ansi`

`fast-grep` will rank transformation call-sites on buffer variables (`terminal_text.splitlines()`, `text.rstrip()`) at the very top and highlight the exact execution lines.

## How to Run

### Via ADK `run_skill_script`
```python
# Multi-word phrase (auto-tokenized into union search terms):
run_skill_script(
    skill_name="fast-grep",
    file_path="grep.py",
    args=["--query", "preserve newlines"]
)

# Single or multi-term searches (searched across codebase as union/OR):
run_skill_script(
    skill_name="fast-grep",
    file_path="grep.py",
    args=["splitlines", "rstrip", "strip"]
)
```

### Searching a specific subfolder
```python
run_skill_script(
    skill_name="fast-grep",
    file_path="grep.py",
    args=["--query", "preserve newlines", "rich"]
)
```

### Via CLI
```bash
# Multi-word query (auto-tokenized):
python3 grep.py --query "preserve newlines" .

# Positional multi-word query:
python3 grep.py "preserve newlines" .

# Structured JSON output:
python3 grep.py --json --query "preserve newlines" .
```
