---
name: code-map
description: AST code structure and symbol call-graph tracer. Query with --symbol <name> to trace callers/callees/definitions, or --file <path> for a compact file outline.
---

# code-map Skill

Unified AST code structure and symbol call-graph tracer.
Combines symbol reference reachability tracing across the codebase graph with compact single-file AST skeletons.
Strictly forbids unconstrained full-repository dumping to prevent context window flooding.

## How to Run

### Via ADK `run_skill_script`

#### 1. Symbol Call Graph & Reachability Mode (`--symbol`)
Trace definitions, imports, callers, and callees of a specific symbol across the repository:
```python
run_skill_script(
    skill_name="code-map",
    file_path="map.py",
    args=["--symbol", "APIRouter"]
)
```

#### 2. File Skeleton Mode (`--file`)
Inspect class, method, argument signatures, and line ranges of a single Python file:
```python
run_skill_script(
    skill_name="code-map",
    file_path="map.py",
    args=["--file", "fastapi/routing.py"]
)
```

#### 3. Positional Fallback
- If the argument ends in `.py`, it is automatically treated as `--file`:
  ```python
  run_skill_script(skill_name="code-map", file_path="map.py", args=["fastapi/routing.py"])
  ```
- Otherwise, it is automatically treated as `--symbol`:
  ```python
  run_skill_script(skill_name="code-map", file_path="map.py", args=["APIRouter"])
  ```

## Features & Guarantees

1. **Symbol Tracing (75% Win-Rate Engine)**:
   - Queries precomputed NetworkX codebase graphs when available for instant inbound/outbound reachability.
   - Combines graph results with live AST workspace parsing for definitions, imports, and direct call sites.
   - Diagnoses private symbols (`_foo`) and dotted module paths (`foo.bar`), providing fuzzy matching candidates when queries are misspelled.

2. **Compact File Skeletons**:
   - Outlines classes (with bases), methods, function signatures, return annotations, line numbers `[start-end]`, and docstrings.
   - Catches AST syntax errors (`SyntaxError`/`IndentationError`), pinpointing the exact line, column, and caret pointer.
   - Strict output capping (default 120 lines) to safeguard context budgets.

3. **Context Safety**:
   - Calling `map.py` with empty arguments or attempting whole-repository dumping is explicitly rejected with exit code 1 and helpful usage guidance.

## Exit Codes
- **0 (Success)**: Completed symbol tracing or file skeleton mapping.
- **1 (Error)**: Missing required target argument or attempted whole-repository dump.
