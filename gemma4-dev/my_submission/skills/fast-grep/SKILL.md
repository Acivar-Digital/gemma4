---
name: fast-grep
description: Fast codebase regex and keyword search across /workspace with probability ranking and automatic AST function flashing for top 3 matches.
---

# fast-grep Skill

Fast, omnivorous codebase search tool for locating strings, regex patterns, function calls, and error messages across `/workspace`.

## Features
- **Relevance & Probability Ranking**: Automatically scores matches so core package definitions and implementations appear at the top, and markdown/docs/changelogs are demoted.
- **Top 3 AST Function Flashing**: Automatically parses Python AST to extract and flash the **top 3 complete enclosing functions** (with exact line numbers) directly in the tool output.
- **Concise Match Index**: Displays a clean summary of all other ranked matches for quick reference.
- **Context-Safe**: Caps large functions at 100 lines with middle folding to preserve the 32K context budget.
- **Never crashes**: Always exits cleanly with code 0.

## How to Run

### Via ADK `run_skill_script`
```python
# Single or multi-term searches (searched across codebase as union/OR):
run_skill_script(
    skill_name="fast-grep",
    file_path="grep.py",
    args=["term1", "term2", "term3"]
)
```

### Searching a specific subfolder
```python
run_skill_script(
    skill_name="fast-grep",
    file_path="grep.py",
    args=["<pattern>", "<search_path>"]
)
```
