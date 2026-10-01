---
name: code-map
description: AST code structure and symbol call-graph tracer. Query with --symbol <name> (or -s/--callers/--callees), --file <path> (or -f/-d/--tree), or positional shorthand.
---

# code-map Skill

Unified AST code structure, class hierarchy, and symbol call-graph tracer.
Omnivorous & forgiving: auto-detects positional arguments, supports flexible flag aliases (`-s`, `-f`, `-d`, `--dir`, `--tree`, `--overview`, `--callers`, `--callees`), and provides actionable diagnostics with exact copy-pasteable next steps.

## How to Run

### Via ADK `run_skill_script`

#### 1. Workspace Overview & Repository Guide (Empty, `.`, or `-o`)
```python
run_skill_script(skill_name="code-map", file_path="map.py", args=[])
```

#### 2. Symbol Tracing & Reachability (`--symbol`, `-s`, `--callers`, `--callees`)
Trace definitions (with base classes), subclasses, imports, callers, and callees across the repository:
```python
run_skill_script(skill_name="code-map", file_path="map.py", args=["--symbol", "APIRouter"])
run_skill_script(skill_name="code-map", file_path="map.py", args=["--callers", "APIRouter"])
```

#### 3. Compact File & Directory Skeletons (`--file`, `-f`, `-d`, `--dir`, `--tree`)
Inspect class signatures, methods, return annotations, docstrings, and line ranges `[start-end]`:
```python
run_skill_script(skill_name="code-map", file_path="map.py", args=["--file", "fastapi/routing.py"])
run_skill_script(skill_name="code-map", file_path="map.py", args=["-d", "fastapi"])
```

#### 4. Omnivorous Positional Auto-Detection
- Existing file, `.py` extension, or path with `/`: treated as file outline:
  ```python
  run_skill_script(skill_name="code-map", file_path="map.py", args=["fastapi/routing.py"])
  run_skill_script(skill_name="code-map", file_path="map.py", args=["fastapi"])
  ```
- Symbol identifier: treated as symbol search:
  ```python
  run_skill_script(skill_name="code-map", file_path="map.py", args=["APIRouter"])
  ```

## Core Guarantees

1. **Omnivorous & Forgiving CLI**:
   - Accepts aliases (`-s`, `-f`, `-d`, `--dir`, `--overview`, `-t`, `--tree`, `--callers`, `--callees`).
   - Tolerate flag typos and unrecognized options without crashing (`argparse.ArgumentError` is eliminated).
2. **Actionable Diagnostics ("Tell the LLM what is wrong & how to fix it")**:
   - Missing symbol: fuzzy matching with `difflib`, closest candidate symbols with file/line locations, and exact copy-pasteable commands to inspect them.
   - Missing file: closest path suggestions and workspace layout with copy-pasteable commands.
   - Explains *why* the query failed and *what concrete action* to take next.
3. **Crash & Loop Immunity**:
   - Inode & realpath tracking, symlink immunity (`followlinks=False`), and bounded directory limits prevent filesystem hangs.
   - Catches `SyntaxError`, `UnicodeDecodeError`, and `PermissionError` cleanly without tracebacks.
   - AST recursion depth bounds protect against deeply nested code.

## Exit Codes
- **0 (Success / Actionable Diagnostics)**: Always exits 0 with structured results or recovery steps.
