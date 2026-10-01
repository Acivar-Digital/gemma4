---
name: code-map
description: AST code structure and symbol call-graph tracer. Query with --symbol <name> to trace callers/callees/definitions/subclasses, or --file <path> for a compact file/directory outline.
---

# code-map Skill

Unified AST code structure and symbol call-graph tracer.
Combines symbol reference reachability tracing across the codebase graph with compact file and directory AST skeletons.
Omnivorous, forgiving, and informative: never crashes on empty arguments, auto-detects positional arguments, and provides actionable diagnostics with copy-pasteable next steps.

## How to Run

### Via ADK `run_skill_script`

#### 1. Workspace Overview & Tailored Usage Guide (Empty or `.`)
Orient in the workspace, discover packages, and view copy-pasteable commands tailored to this repo:
```python
run_skill_script(
    skill_name="code-map",
    file_path="map.py",
    args=[]
)
```

#### 2. Symbol Call Graph & Reachability Mode (`--symbol`)
Trace definitions (with base classes), subclasses, imports, callers, and callees across the repository:
```python
run_skill_script(
    skill_name="code-map",
    file_path="map.py",
    args=["--symbol", "APIRouter"]
)
```

#### 3. File & Directory Skeleton Mode (`--file`)
Inspect class hierarchies, methods, argument signatures, and line ranges of a Python file or directory:
```python
run_skill_script(
    skill_name="code-map",
    file_path="map.py",
    args=["--file", "fastapi/routing.py"]
)
```

#### 4. Forgiving Positional Auto-Detection
- Existing file, `.py` extension, or path with `/`: automatically treated as `--file`:
  ```python
  run_skill_script(skill_name="code-map", file_path="map.py", args=["fastapi/routing.py"])
  run_skill_script(skill_name="code-map", file_path="map.py", args=["fastapi"])
  ```
- Symbol name: automatically treated as `--symbol`:
  ```python
  run_skill_script(skill_name="code-map", file_path="map.py", args=["APIRouter"])
  ```

## Features & Guarantees

1. **Symbol Tracing & Class Hierarchies**:
   - Queries precomputed NetworkX codebase graphs when available for instant inbound/outbound reachability.
   - Combines graph results with live AST workspace parsing for definitions (including base classes), subclasses, imports, and direct call sites.
   - Diagnoses private symbols (`_foo`) and dotted module paths (`foo.bar`).
   - If a symbol is missing: provides fuzzy matching candidates (`did_you_mean`), lists available top-level public symbols in the repo, and provides copy-pasteable next steps.

2. **Compact File & Directory Skeletons**:
   - Outlines classes (with base classes), methods, function signatures, return annotations, line numbers `[start-end]`, and docstrings.
   - Supports directory mapping up to `max_lines` budget (default: 120 lines).
   - Catches AST syntax errors (`SyntaxError`/`IndentationError`), pinpointing the exact line, column, snippet, and caret pointer.

3. **Loop-Safe & Symlink-Safe**:
   - Explicit `followlinks=False` and inode tracking to prevent filesystem circular loops.
   - Bounded AST recursion depth and capped file processing.

4. **Omnivorous & Forgiving Execution**:
   - Zero crashes or exit 1 on empty calls or `.`; produces actionable repository layout and copy-pasteable example commands.

## Exit Codes
- **0 (Success / Actionable Diagnostics)**: Completed symbol tracing, file outline, or workspace overview with actionable next steps.
