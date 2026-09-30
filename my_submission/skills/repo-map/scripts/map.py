#!/usr/bin/env python3
"""repo-map: Compact AST skeleton generator and repository structure diagnostic tool.

100% Pydantic v2 schemas for all structured outputs:
- RepoMapResult: Complete repository mapping session result
- ModuleSummary: AST structure summary for a single Python module
- SymbolItem: Extracted class, method, or function signatures and line ranges
- MapDiagnostic: Structured diagnostics explaining missing paths or AST syntax errors
- RepoLayoutItem: Top-level repository layout entries for agent orientation

Guarantees:
1. When target path or module does not exist:
   - Explains WHY: "Path 'foo' does not exist in /workspace."
   - Suggests closest existing directories / files (fuzzy matching via difflib).
   - Displays top-level repo layout so the agent immediately sees valid directories.
2. When a file has a syntax error during AST parsing:
   - Catches SyntaxError (and IndentationError), extracts exact line, column, and snippet.
   - Explains why the file could not be parsed (e.g. invalid syntax introduced by an edit).
   - Provides deterministic guidance to repair the file before mapping.
3. Caps output lines (default 120) to prevent context window flooding in 32K token windows.
4. Omnivorous and forgiving: always returns exit code 0.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import os
import pathlib
import sys
from typing import List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field


# ==============================================================================
# 100% Pydantic v2 Models
# ==============================================================================


class MapDiagnostic(BaseModel):
    """Diagnostic explanation for missing paths, syntax errors, or parsing anomalies."""

    model_config = ConfigDict(extra="forbid")

    level: str = Field(
        default="error",
        description="Severity level: 'error', 'warning', or 'info'",
    )
    category: str = Field(
        ...,
        description="Category: 'missing_path', 'syntax_error', 'unparseable_file', 'empty_target'",
    )
    message: str = Field(
        ...,
        description="Primary explanatory message for the agent",
    )
    target_path: Optional[str] = Field(
        default=None,
        description="Target file or directory path where issue occurred",
    )
    line: Optional[int] = Field(
        default=None,
        description="1-based line number for AST syntax errors",
    )
    column: Optional[int] = Field(
        default=None,
        description="1-based column offset for AST syntax errors",
    )
    snippet: Optional[str] = Field(
        default=None,
        description="Source code snippet showing the syntax error location and caret pointer",
    )
    suggestions: List[str] = Field(
        default_factory=list,
        description="Closest valid paths or recommended actions",
    )
    guidance: Optional[str] = Field(
        default=None,
        description="Deterministic guidance instructions for the agent",
    )


class SymbolItem(BaseModel):
    """Extracted Python symbol (class, function, method, async function)."""

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(
        ...,
        description="Symbol kind: 'class', 'def', 'async def'",
    )
    name: str = Field(
        ...,
        description="Identifier name of the symbol",
    )
    signature: str = Field(
        ...,
        description="Formatted symbol signature including arguments, return type, and line range",
    )
    start_line: int = Field(
        ...,
        description="Starting line number in source file (1-based)",
    )
    end_line: int = Field(
        ...,
        description="Ending line number in source file (1-based)",
    )
    docstring: Optional[str] = Field(
        default=None,
        description="Formatted one-line docstring summary if present",
    )


class ModuleSummary(BaseModel):
    """AST structure summary for a single Python module file."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(
        ...,
        description="Workspace-relative path to the Python source file",
    )
    symbols: List[SymbolItem] = Field(
        default_factory=list,
        description="List of extracted symbols in document order",
    )
    symbol_count: int = Field(
        default=0,
        description="Total number of extracted symbols in this module",
    )
    syntax_error: Optional[MapDiagnostic] = Field(
        default=None,
        description="AST syntax error diagnostic if this module could not be parsed",
    )


class RepoLayoutItem(BaseModel):
    """Top-level repository layout item for orienting the agent."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ...,
        description="Entry name (directory or file name)",
    )
    rel_path: str = Field(
        ...,
        description="Workspace-relative path",
    )
    is_dir: bool = Field(
        ...,
        description="True if directory, False if file",
    )
    summary: str = Field(
        ...,
        description="Formatted human-readable layout summary entry",
    )


class RepoMapResult(BaseModel):
    """Complete structured output of the repository mapping session."""

    model_config = ConfigDict(extra="forbid")

    target: str = Field(
        ...,
        description="Target path or query requested by the agent",
    )
    workspace_root: str = Field(
        ...,
        description="Absolute workspace root path",
    )
    success: bool = Field(
        default=True,
        description="Whether mapping completed successfully without path resolution failures",
    )
    modules: List[ModuleSummary] = Field(
        default_factory=list,
        description="List of mapped module summaries",
    )
    total_files: int = Field(
        default=0,
        description="Number of successfully mapped Python files",
    )
    total_symbols: int = Field(
        default=0,
        description="Total number of symbols across all modules",
    )
    diagnostics: List[MapDiagnostic] = Field(
        default_factory=list,
        description="List of diagnostics, syntax errors, or warnings encountered",
    )
    top_level_layout: List[RepoLayoutItem] = Field(
        default_factory=list,
        description="Top-level repository structure",
    )
    is_truncated: bool = Field(
        default=False,
        description="True if output was truncated to honor max_lines cap",
    )
    rendered_text: str = Field(
        default="",
        description="Human/LLM-readable text output as printed to stdout",
    )


# ==============================================================================
# Workspace & Target Resolution
# ==============================================================================

SKIP_DIR_NAMES = {
    "__pycache__",
    ".git",
    ".tox",
    ".nox",
    ".venv",
    "venv",
    "env",
    "build",
    "dist",
    "wheels",
    "site-packages",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}


def should_skip_dir(name: str) -> bool:
    """Return True if directory should be skipped during walk."""
    if name.startswith(".") or name.startswith("__"):
        return True
    lower = name.lower()
    if lower in SKIP_DIR_NAMES:
        return True
    if "egg-info" in lower:
        return True
    return False


def should_skip_path(p: pathlib.Path, ws: pathlib.Path) -> bool:
    """Return True if path contains any skipped directory components."""
    try:
        rel = p.relative_to(ws)
    except ValueError:
        rel = p
    for part in rel.parts:
        if should_skip_dir(part):
            return True
    return False


def get_workspace_dir() -> pathlib.Path:
    """Robustly and deterministically locate the active target repository workspace directory."""
    # a) Check caller stack frame for _orig_cwd (set by ADK in _materialize_and_run)
    try:
        f = sys._getframe()
        while f:
            if "_orig_cwd" in f.f_locals and f.f_locals["_orig_cwd"]:
                p = pathlib.Path(f.f_locals["_orig_cwd"])
                if p.is_dir() and (
                    (p / ".git").exists()
                    or (p / "pyproject.toml").exists()
                    or (p / "setup.py").exists()
                    or (p / "setup.cfg").exists()
                ):
                    return p.resolve()
            f = f.f_back
    except Exception:
        pass

    # b) Environment variable overrides (SWEGEMMA_WORKSPACE or WORKSPACE_DIR)
    for env_var in ("SWEGEMMA_WORKSPACE", "WORKSPACE_DIR"):
        val = os.environ.get(env_var)
        if val:
            p = pathlib.Path(val)
            if p.is_dir():
                return p.resolve()

    # c) Standard competition container workspace (/workspace)
    ws = pathlib.Path("/workspace")
    if ws.is_dir():
        return ws.resolve()

    # d) Current working directory if it contains project or repo markers
    cur = pathlib.Path.cwd().resolve()
    repo_markers = (".git", "pyproject.toml", "setup.py", "setup.cfg", "tasks.jsonl", "agent.yaml")
    if any((cur / marker).exists() for marker in repo_markers):
        return cur

    for parent in cur.parents:
        if any((parent / marker).exists() for marker in repo_markers):
            return parent.resolve()

    return cur


def resolve_target(target_str: str, ws: pathlib.Path) -> Tuple[Optional[pathlib.Path], str]:
    """Resolve target string against workspace or absolute filesystem path.

    Returns (resolved_path, clean_target_str).
    If target does not exist, resolved_path is None.
    """
    raw = str(target_str).strip()
    if not raw or raw == ".":
        return ws, "."

    raw_path = pathlib.Path(raw)
    if raw_path.is_absolute():
        if raw_path.exists():
            return raw_path, raw
        # If absolute path was /workspace/something, try resolving relative to ws
        raw_str = str(raw_path)
        if raw_str.startswith("/workspace/"):
            rel_ws = raw_str[len("/workspace/") :]
            cand = ws / rel_ws
            if cand.exists():
                return cand, rel_ws
            return None, rel_ws
        elif raw_str == "/workspace":
            return ws, "."
        return None, raw

    clean = raw.lstrip("/")
    cand = ws / clean
    if cand.exists():
        return cand, clean

    # Check for glob match inside workspace (e.g. 'routing.py' or 'models.py')
    try:
        matches = [m for m in ws.glob(f"**/{clean}") if not should_skip_path(m, ws)]
        if matches:
            return matches[0], clean
    except Exception:
        pass

    return None, clean


# ==============================================================================
# Diagnostic Helpers: Fuzzy Suggestions & Top-Level Layout
# ==============================================================================


def find_closest_paths(clean_target: str, ws: pathlib.Path) -> List[str]:
    """Find closest existing files and directories to the missing target using fuzzy matching."""
    all_dirs: List[str] = []
    all_files: List[str] = []

    try:
        for root, dirs, files in os.walk(ws):
            dirs[:] = sorted([d for d in dirs if not should_skip_dir(d)])
            rel_dir = os.path.relpath(root, ws)
            if rel_dir != ".":
                all_dirs.append(rel_dir)
            for f in files:
                if f.endswith(".py") and not f.startswith("."):
                    rel_file = os.path.normpath(os.path.join(rel_dir, f)) if rel_dir != "." else f
                    all_files.append(rel_file)
    except Exception:
        pass

    all_paths = all_files + all_dirs
    if not all_paths:
        return []

    target_base = os.path.basename(clean_target)

    # 1. Exact basename match
    exact_bases = [p for p in all_paths if os.path.basename(p) == target_base]

    # 2. Fuzzy match on full relative path
    close_full = difflib.get_close_matches(clean_target, all_paths, n=6, cutoff=0.35)

    # 3. Fuzzy match on basename
    close_bases = [
        p
        for p in all_paths
        if os.path.basename(p)
        in difflib.get_close_matches(target_base, [os.path.basename(x) for x in all_paths], n=6, cutoff=0.45)
    ]

    # 4. Substring matching
    substrings = [p for p in all_paths if target_base.lower() in os.path.basename(p).lower()]

    combined: List[str] = []
    for p in exact_bases + close_full + close_bases + substrings:
        if p not in combined:
            combined.append(p)

    # Format candidates with informative icons
    results: List[str] = []
    for p in combined[:8]:
        if p in all_dirs:
            results.append(f"📁 {p}/")
        else:
            results.append(f"📄 {p}")

    return results


def get_top_level_layout(ws: pathlib.Path) -> List[RepoLayoutItem]:
    """Inspect top-level entries in the workspace and return structured layout items."""
    items: List[RepoLayoutItem] = []
    try:
        entries = sorted(ws.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except Exception:
        return items

    for entry in entries:
        if entry.name.startswith(".") or entry.name.startswith("__"):
            continue
        if entry.name in ("venv", "wheels", ".git", "__pycache__"):
            continue

        rel = entry.name
        if entry.is_dir():
            py_count = 0
            subdirs = 0
            try:
                for _, d_list, f_list in os.walk(entry):
                    d_list[:] = [d for d in d_list if not should_skip_dir(d)]
                    subdirs += len(d_list)
                    for f in f_list:
                        if f.endswith(".py") and not f.startswith("."):
                            py_count += 1
            except Exception:
                pass

            desc_parts: List[str] = []
            if py_count > 0:
                desc_parts.append(f"{py_count} .py file{'s' if py_count != 1 else ''}")
            if subdirs > 0:
                desc_parts.append(f"{subdirs} subdir{'s' if subdirs != 1 else ''}")
            desc_suffix = f" ({', '.join(desc_parts)})" if desc_parts else ""
            summary = f"📁 {entry.name}/{desc_suffix}"
            items.append(
                RepoLayoutItem(
                    name=entry.name,
                    rel_path=rel,
                    is_dir=True,
                    summary=summary,
                )
            )
        else:
            items.append(
                RepoLayoutItem(
                    name=entry.name,
                    rel_path=rel,
                    is_dir=False,
                    summary=f"📄 {entry.name}",
                )
            )
    return items


# ==============================================================================
# AST Formatting & Symbol Extraction
# ==============================================================================


def format_args(args_node: ast.arguments) -> str:
    """Format argument list string from AST node, keeping it concise."""
    try:
        raw = ast.unparse(args_node)
        s = " ".join(raw.split())
        if len(s) > 60:
            s = s[:57] + "..."
        return s
    except Exception:
        pass

    names: List[str] = []
    for a in args_node.posonlyargs + args_node.args:
        names.append(a.arg)
    if args_node.vararg:
        names.append("*" + args_node.vararg.arg)
    for a in args_node.kwonlyargs:
        names.append(a.arg)
    if args_node.kwarg:
        names.append("**" + args_node.kwarg.arg)
    s = ", ".join(names)
    if len(s) > 60:
        s = s[:57] + "..."
    return s


def format_return(ret_node: Optional[ast.AST]) -> str:
    """Format return type annotation string from AST node."""
    if ret_node is None:
        return ""
    try:
        s = ast.unparse(ret_node)
        s = " ".join(s.split())
        return f" -> {s}"
    except Exception:
        return ""


def format_docstring(node: ast.AST, indent: str = "    ") -> Optional[str]:
    """Extract and format a one-line docstring summary."""
    try:
        doc = ast.get_docstring(node)
        if not doc:
            return None
        first_line = doc.strip().split("\n")[0].strip()
        if not first_line:
            return None
        if len(first_line) > 70:
            first_line = first_line[:67] + "..."
        return f'{indent}"""{first_line}"""'
    except Exception:
        return None


def get_symbols(
    body: List[ast.stmt],
    is_class: bool = False,
) -> List[Tuple[str, str, str, int, int, Optional[str]]]:
    """Extract symbol items from AST statements.

    Returns list of tuples: (kind, name, signature, start_line, end_line, docstring).
    """
    items: List[Tuple[str, str, str, int, int, Optional[str]]] = []
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            args_str = format_args(node.args)
            ret_str = format_return(getattr(node, "returns", None))
            start = getattr(node, "lineno", 1)
            end = getattr(node, "end_lineno", start)
            indent = "    " if is_class else "  "
            sig = f"{indent}{prefix} {node.name}({args_str}){ret_str} [{start}-{end}]"
            doc = format_docstring(node, indent=indent + "  ")
            items.append((prefix, node.name, sig, start, end, doc))
        elif isinstance(node, ast.ClassDef):
            bases_str = ""
            if node.bases:
                base_names: List[str] = []
                for b in node.bases:
                    try:
                        base_names.append(ast.unparse(b))
                    except Exception:
                        if isinstance(b, ast.Name):
                            base_names.append(b.id)
                if base_names:
                    bases_str = f"({', '.join(base_names)})"
            start = getattr(node, "lineno", 1)
            end = getattr(node, "end_lineno", start)
            sig = f"  class {node.name}{bases_str} [{start}-{end}]"
            doc = format_docstring(node, indent="    ")
            items.append(("class", node.name, sig, start, end, doc))
            # Extract nested methods within class
            methods = get_symbols(node.body, is_class=True)
            items.extend(methods)
    return items


# ==============================================================================
# Module Parsing & AST Syntax Diagnostic Engine
# ==============================================================================


def parse_and_map_file(
    py_file: pathlib.Path,
    ws: pathlib.Path,
) -> Tuple[ModuleSummary, Optional[MapDiagnostic]]:
    """Parse a single Python file, extract AST symbols, and diagnose syntax errors."""
    try:
        rel_display = py_file.relative_to(ws)
    except ValueError:
        rel_display = py_file

    try:
        with open(py_file, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        diag = MapDiagnostic(
            level="error",
            category="unparseable_file",
            message=f"Failed to read file '{rel_display}': {e}",
            target_path=str(rel_display),
            guidance="Verify file permissions and file encoding.",
        )
        return ModuleSummary(path=str(rel_display), syntax_error=diag), diag

    try:
        tree = ast.parse(content, filename=str(py_file))
    except SyntaxError as e:
        err_line = e.lineno or 1
        err_col = e.offset or 1
        err_msg = e.msg or "invalid syntax"

        # Extract source code line around the error
        content_lines = content.splitlines()
        if e.text:
            source_line = e.text.rstrip("\r\n").expandtabs(4)
        elif 1 <= err_line <= len(content_lines):
            source_line = content_lines[err_line - 1].expandtabs(4)
        else:
            source_line = ""

        # Format caret pointer
        gutter = f"    {err_line} | "
        safe_col = max(1, min(err_col, len(source_line) + 1))
        caret_line = " " * (len(gutter) + safe_col - 1) + "^"
        snippet = f"{gutter}{source_line}\n{caret_line}"

        guidance = (
            f"File '{rel_display}' contains invalid Python syntax at line {err_line}, column {err_col}. "
            "This error prevents AST parsing and was likely introduced by a recent edit_file call "
            "(e.g., unclosed parenthesis/bracket/quote, mismatched indentation, or incomplete statement). "
            f"Inspect line {err_line} or run diff-inspect / git diff to repair syntax."
        )

        diag = MapDiagnostic(
            level="error",
            category="syntax_error",
            message=f"SyntaxError: {err_msg} (line {err_line}, column {err_col})",
            target_path=str(rel_display),
            line=err_line,
            column=err_col,
            snippet=snippet,
            guidance=guidance,
        )
        return ModuleSummary(path=str(rel_display), syntax_error=diag), diag
    except Exception as e:
        diag = MapDiagnostic(
            level="warning",
            category="unparseable_file",
            message=f"AST parse failure in '{rel_display}': {e}",
            target_path=str(rel_display),
            guidance="Inspect file for non-standard Python syntax.",
        )
        return ModuleSummary(path=str(rel_display), syntax_error=diag), diag

    raw_symbols = get_symbols(tree.body)
    symbol_items: List[SymbolItem] = []
    for kind, name, sig, start, end, doc in raw_symbols:
        symbol_items.append(
            SymbolItem(
                kind=kind,
                name=name,
                signature=sig,
                start_line=start,
                end_line=end,
                docstring=doc,
            )
        )

    return (
        ModuleSummary(
            path=str(rel_display),
            symbols=symbol_items,
            symbol_count=len(symbol_items),
        ),
        None,
    )


def collect_py_files(target_path: pathlib.Path, ws: pathlib.Path) -> List[pathlib.Path]:
    """Collect Python files from target path in deterministic order."""
    if target_path.is_file():
        if target_path.name.endswith(".py"):
            return [target_path]
        return []

    py_files: List[pathlib.Path] = []
    for root, dirs, files in os.walk(target_path):
        dirs[:] = sorted([d for d in dirs if not should_skip_dir(d)])
        for f in sorted(files):
            if f.endswith(".py") and not f.startswith("."):
                py_files.append(pathlib.Path(root) / f)
    return py_files


# ==============================================================================
# Missing Path & Empty Target Handlers
# ==============================================================================


def handle_missing_path(
    target_str: str,
    ws: pathlib.Path,
    clean_target: str,
) -> RepoMapResult:
    """Handle missing target path: explain WHY, provide fuzzy suggestions, and display repo layout."""
    # Strict DoD phrase: "Path 'foo' does not exist in /workspace."
    diag_msg = f"Path '{target_str}' does not exist in /workspace."

    suggestions = find_closest_paths(clean_target, ws)
    layout_items = get_top_level_layout(ws)

    guidance = (
        f"Target '{target_str}' was not found in /workspace. "
        "Review the suggested closest matches or top-level repository layout below to select an existing path."
    )

    diag = MapDiagnostic(
        level="error",
        category="missing_path",
        message=diag_msg,
        target_path=target_str,
        suggestions=suggestions,
        guidance=guidance,
    )

    lines: List[str] = [
        f"[repo-map] {diag_msg}",
        "",
    ]

    if str(ws) != "/workspace":
        lines.append(f"  (Active workspace root: {ws})")
        lines.append("")

    if suggestions:
        lines.append("💡 Suggested closest existing paths:")
        for s in suggestions:
            lines.append(f"  • {s}")
        lines.append("")

    if layout_items:
        lines.append("📂 Top-level repository layout (/workspace):")
        for item in layout_items:
            lines.append(f"  {item.summary}")
        lines.append("")

    lines.append("Guidance:")
    py_dirs = [it for it in layout_items if it.is_dir and ".py" in it.summary]
    example_target = py_dirs[0].rel_path if py_dirs else (layout_items[0].rel_path if layout_items else "src")
    lines.append(
        f"  Specify an existing Python file or directory from the layout above, e.g.:\n"
        f'    run_skill_script(skill_name="repo-map", file_path="map.py", args=["{example_target}"])'
    )

    rendered = "\n".join(lines)

    return RepoMapResult(
        target=target_str,
        workspace_root=str(ws),
        success=False,
        modules=[],
        total_files=0,
        total_symbols=0,
        diagnostics=[diag],
        top_level_layout=layout_items,
        is_truncated=False,
        rendered_text=rendered,
    )


def handle_empty_target(
    target_str: str,
    target_path: pathlib.Path,
    ws: pathlib.Path,
) -> RepoMapResult:
    """Handle target that exists but contains no Python source files."""
    try:
        rel_target = target_path.relative_to(ws)
    except ValueError:
        rel_target = target_path

    if target_path.is_file():
        diag_msg = f"Target '{target_str}' is not a Python source file (.py)."
        diag_category = "non_python_file"
    else:
        diag_msg = f"No Python source files (.py) found in directory '{target_str}'."
        diag_category = "empty_target"

    # List items actually present in target directory
    existing_items: List[str] = []
    try:
        if target_path.is_dir():
            for item in sorted(target_path.iterdir()):
                if not item.name.startswith("."):
                    icon = "📁" if item.is_dir() else "📄"
                    existing_items.append(f"{icon} {item.name}")
    except Exception:
        pass

    # Find directories that DO have python files
    py_dirs: List[str] = []
    for root, dirs, files in os.walk(ws):
        dirs[:] = sorted([d for d in dirs if not should_skip_dir(d)])
        if any(f.endswith(".py") and not f.startswith(".") for f in files):
            rel_dir = os.path.relpath(root, ws)
            if rel_dir != ".":
                py_dirs.append(f"📁 {rel_dir}/")

    layout_items = get_top_level_layout(ws)

    diag = MapDiagnostic(
        level="warning",
        category=diag_category,
        message=diag_msg,
        target_path=str(rel_target),
        suggestions=py_dirs[:6],
        guidance="Select a Python file (.py) or directory containing Python files.",
    )

    lines: List[str] = [
        f"[repo-map] {diag_msg}",
        "",
    ]
    if existing_items:
        lines.append(f"Contents of directory '{rel_target}':")
        for it in existing_items[:12]:
            lines.append(f"  {it}")
        lines.append("")

    if py_dirs:
        lines.append("📁 Directories containing Python source files:")
        for pd in py_dirs[:6]:
            lines.append(f"  {pd}")
        lines.append("")

    if layout_items:
        lines.append("📂 Top-level repository layout (/workspace):")
        for item in layout_items:
            lines.append(f"  {item.summary}")
        lines.append("")

    rendered = "\n".join(lines)

    return RepoMapResult(
        target=target_str,
        workspace_root=str(ws),
        success=True,
        modules=[],
        total_files=0,
        total_symbols=0,
        diagnostics=[diag],
        top_level_layout=layout_items,
        is_truncated=False,
        rendered_text=rendered,
    )


# ==============================================================================
# Core Mapping Orchestration
# ==============================================================================


def generate_repo_map(target_str: str, max_lines: int = 120) -> RepoMapResult:
    """Generate repository map result with full diagnostics and strict line capping."""
    ws = get_workspace_dir()
    target_path, clean_target = resolve_target(target_str, ws)

    # 1. Target does not exist
    if target_path is None or not target_path.exists():
        return handle_missing_path(target_str, ws, clean_target)

    # 2. Collect .py files
    py_files = collect_py_files(target_path, ws)
    if not py_files:
        return handle_empty_target(target_str, target_path, ws)

    output_lines: List[str] = []
    modules: List[ModuleSummary] = []
    all_diagnostics: List[MapDiagnostic] = []
    total_symbols = 0
    total_files_parsed = 0
    is_truncated = False

    # Special handling: if targeting a single file with syntax error
    if len(py_files) == 1:
        mod_summary, diag = parse_and_map_file(py_files[0], ws)
        modules.append(mod_summary)
        if diag:
            all_diagnostics.append(diag)
            single_file_lines = [
                f"[repo-map: SyntaxError in {mod_summary.path}]",
                f"  Location: Line {diag.line}, Column {diag.column}",
                f"  Error: {diag.message}",
                "",
                "  Code Snippet:",
            ]
            if diag.snippet:
                single_file_lines.extend(diag.snippet.splitlines())
            if diag.guidance:
                single_file_lines.append("")
                single_file_lines.append(f"  Guidance: {diag.guidance}")

            rendered = "\n".join(single_file_lines)
            return RepoMapResult(
                target=target_str,
                workspace_root=str(ws),
                success=True,
                modules=modules,
                total_files=1,
                total_symbols=0,
                diagnostics=all_diagnostics,
                top_level_layout=get_top_level_layout(ws),
                is_truncated=False,
                rendered_text=rendered,
            )

    for py_file in py_files:
        mod_summary, diag = parse_and_map_file(py_file, ws)
        modules.append(mod_summary)
        if diag:
            all_diagnostics.append(diag)

        file_lines: List[str] = [f"{mod_summary.path}:"]
        if mod_summary.syntax_error:
            err = mod_summary.syntax_error
            file_lines.append(f"  ⚠️  [SyntaxError at line {err.line}, col {err.column}: {err.message}]")
            if err.snippet:
                file_lines.extend(err.snippet.splitlines())
            if err.guidance:
                file_lines.append(f"      Guidance: {err.guidance}")
        else:
            if not mod_summary.symbols:
                continue
            for sym in mod_summary.symbols:
                file_lines.append(sym.signature)
                if sym.docstring:
                    file_lines.append(sym.docstring)

        if len(output_lines) + len(file_lines) > max_lines:
            remaining = len(py_files) - total_files_parsed
            output_lines.append(f"... [Truncated at {max_lines} lines; {remaining} more file(s)]")
            is_truncated = True
            break

        output_lines.extend(file_lines)
        total_symbols += mod_summary.symbol_count
        total_files_parsed += 1

    syntax_err_count = sum(1 for m in modules if m.syntax_error)
    summary_parts = [f"[repo-map: {total_symbols} symbols across {total_files_parsed} file(s)"]
    if syntax_err_count > 0:
        summary_parts.append(f" ({syntax_err_count} file(s) had syntax errors)")
    summary_parts.append("]")
    output_lines.append("".join(summary_parts))

    rendered = "\n".join(output_lines)

    return RepoMapResult(
        target=target_str,
        workspace_root=str(ws),
        success=True,
        modules=modules,
        total_files=total_files_parsed,
        total_symbols=total_symbols,
        diagnostics=all_diagnostics,
        top_level_layout=get_top_level_layout(ws),
        is_truncated=is_truncated,
        rendered_text=rendered,
    )


# ==============================================================================
# CLI Entrypoint
# ==============================================================================


def main() -> int:
    """CLI entrypoint for repo-map."""
    parser = argparse.ArgumentParser(
        prog="repo-map",
        description="repo-map: Compact AST skeleton generator and repository structure diagnostic tool.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python map.py                            # Map entire workspace (up to 120 lines)
  python map.py fastapi/routing.py         # Map a specific module
  python map.py fastapi                    # Map a specific directory
  python map.py nonexistent_dir            # Explain missing path with closest matches & layout
  python map.py --json                     # Output structured JSON (Pydantic v2 model_dump_json)
""",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="Target file or directory path relative to /workspace (default: '.')",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit output as structured JSON matching RepoMapResult schema.",
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        default=120,
        help="Maximum lines of symbol output to display (default: 120).",
    )

    args = parser.parse_args()

    result = generate_repo_map(args.target, max_lines=args.max_lines)

    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        print(result.rendered_text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
