---
name: repo-map
description: Generates a compact AST skeleton (classes, functions, signatures, lines) for a target Python file in /workspace.
---

# repo-map Skill

Generates a compact, deterministic AST skeleton of Python code structures (classes, base classes, functions, arguments, return type annotations, line ranges, and docstrings). Pure Python standard library only, fast (<0.05s), and strictly output-capped to prevent context flooding in 32K token windows.

## How to Run

### Via ADK `run_skill_script`
```python
run_skill_script(
    skill_name="repo-map",
    file_path="map.py",
    args=["<target_file_path>"]
)
```

Target should be a single Python file to inspect its structure and line numbers without mouse-reading:
```python
run_skill_script(
    skill_name="repo-map",
    file_path="map.py",
    args=["path/to/target.py"]
)
```

## Features & Guarantees

1. **AST Signatures & Line Ranges**:
   - Classes and bases: `class MyClass(Base): [start-end]`
   - Top-level and class-level functions: `def func(args...) -> return_type [start-end]`
   - Docstrings: 1-line docstring summary truncated to 80 chars max.
2. **Deterministic & Filtered**:
   - Recursively walks `.py` files in alphabetical order.
   - Automatically skips non-source paths: hidden folders (`.*`), `__pycache__`, `tests`, `test`, `build`, `dist`, and `egg-info`.
3. **Context-Window Safe**:
   - Capped at 120 lines total output so it never overflows the 32K context window.
   - Concludes with concise count summary: `[Showing X symbols across Y files]`.
4. **Resilient & Diagnostic**:
   - 100% Pydantic v2 schemas (`RepoMapResult`, `ModuleSummary`, `MapDiagnostic`, `SymbolItem`, `RepoLayoutItem`).
   - Missing path diagnostics: Explains why path does not exist, provides closest fuzzy suggestions, and renders top-level repo layout.
   - AST syntax diagnostics: Catches `SyntaxError`/`IndentationError`, extracts exact line, column, code snippet with caret pointer, and repair guidance.
   - Always returns exit code 0.
