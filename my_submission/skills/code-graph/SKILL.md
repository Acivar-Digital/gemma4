---
name: code-graph
description: Traces where any symbol (function, class, variable) is defined, imported, and called across the repository using AST parsing.
---

# code-graph Skill

Traces where any symbol (function, class, variable) is defined, imported, and called across the repository using AST parsing. Pure Python standard library only, fast (<0.5s), and handles large repos gracefully without recursion depth errors.

## How to Run

### Via ADK `run_skill_script`
```python
run_skill_script(
    skill_name="code-graph",
    file_path="find_refs.py",
    args=["<symbol_name>"]
)
```

Optional second argument `<search_dir>` (defaults to current directory):
```python
run_skill_script(
    skill_name="code-graph",
    file_path="find_refs.py",
    args=["<symbol_name>", "<search_dir>"]
)
```

## Output Format
Produces a concise, structured text report (max 100 lines):
```
SYMBOL: <symbol_name>
DEFINITIONS:
  - <file>:<line> (class/func def)
IMPORTS:
  - <file>:<line> (import ...)
CALLS (first 15):
  - <file>:<line> (call)
```

## Exit Codes
- **0 (Success)**: Completed AST scan and printed references (even if 0 occurrences found).
- **1 (Error)**: Missing required `<symbol_name>` argument or invalid directory path.
