---
name: fast-grep
description: Fast codebase regex and keyword search across /workspace with probability ranking, string/buffer verb boosting, call-site highlighting, and automatic AST function flashing for top 3 matches.
---

# fast-grep Skill

Fast, omnivorous codebase search tool for locating strings, regex patterns, function calls, and error messages across `/workspace`.

## Features
- **Relevance & Probability Ranking**: Automatically scores matches so core package definitions and implementations appear at the top, and markdown/docs/changelogs are demoted.
- **String & Buffer Verb Boosting**: Automatically detects and boosts scores for core Python string and buffer transformation verbs (`splitlines`, `split`, `rstrip`, `strip`, `lstrip`, `replace`, `join`, `partition`, `decode`, `encode`, `from_ansi`).
- **Call-Site & Enclosing Scope Highlighting**: Identifies active call-sites transforming text/buffer variables and marks them with `>>> ... <-- [CALL-SITE]` and `[⚡ STRING/BUFFER CALL-SITE & TRANSFORM SCOPE]` headers.
- **Terse Issue Search Heuristics**: Automatically expands terse problem keywords (e.g., `newlines`, `newline`, `whitespace`, `indent`) to candidate string transformation operations to avoid flooding results with docstrings/comments.
- **Top 3 AST Function Flashing**: Automatically parses Python AST to extract and flash the **top 3 complete enclosing functions** (with exact line numbers) directly in the tool output.
- **Concise Match Index**: Displays a clean summary of all other ranked matches for quick reference.
- **Context-Safe**: Caps large functions at 100 lines with middle folding to preserve the 32K context budget.
- **Never crashes**: Always exits cleanly with code 0.

## Searching Terse Issues (String/Buffer Verbs)

When encountering terse issue descriptions like *"preserve newlines"*, *"strip trailing space"*, or *"corrupted multibyte decoding"*, **do not search literal descriptive words alone** (e.g. searching `"newlines"` directly can flood hundreds of comment/doc lines).

Instead, search for the underlying Python string/buffer operation verbs:
- **Line/Splitting operations**: `splitlines`, `split`, `partition`
- **Whitespace/Trimming operations**: `rstrip`, `strip`, `lstrip`
- **Replacement/Joining operations**: `replace`, `join`
- **Encoding/Decoding operations**: `decode`, `encode`, `from_ansi`

`fast-grep` will rank transformation call-sites on buffer variables (`terminal_text.splitlines()`, `text.rstrip()`) at the very top and highlight the exact execution lines.

## How to Run

### Via ADK `run_skill_script`
```python
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
    args=["splitlines", "rich"]
)
```
