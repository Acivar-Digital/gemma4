#!/usr/bin/env python3
"""code-map: AST code structure and symbol call-graph tracer.

Unified skill combining:
1. Symbol call-graph and reference reachability tracer (--symbol <name>, -s, --callers, --callees):
   - Traces definitions, imports, calls, attribute accesses, callers, and callees across repo.
   - Detects class hierarchies: base classes and subclasses inheriting from the queried symbol.
   - Omnivorous: queries precomputed codebase graphs (NetworkX node-link JSON) when available,
     and falls back to / combines with live AST analysis.
   - Provides fuzzy matching suggestions and diagnostics when symbols are missing or private.
   - When a symbol is not found, displays available top-level symbols in the repo and copy-pasteable next steps.
2. Compact AST file and directory skeleton generator (--file <path>, -f, -d, --dir, -t, --tree):
   - Extracts classes, base classes, functions, arguments, return type annotations, docstrings,
     and line ranges [start-end] for a target Python file or directory.
   - For directories, extracts skeletons across modules up to max_lines budget.
   - Diagnoses syntax errors with exact line, column, snippet, and caret pointer.
   - Output-capped to prevent context flooding in 32K token windows.
3. Forgiving positional fallback:
   - If argument is an existing directory or ends in .py, treated as file mode.
   - If argument matches an existing file with .py appended, treated as file mode.
   - If argument contains path separators (/ or \\), treated as file mode.
   - Otherwise, treated as symbol mode.
4. Omnivorous workspace overview on empty args, '.', '/workspace', or -o/--overview:
   - Explains the workspace structure, discovered packages, and key modules.
   - Provides tailored, copy-pasteable example invocations for the current repository.
   - Never crashes or exits 1 on empty calls or unrecognized flags.

100% Pydantic v2 schemas for all structured outputs.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import json
import os
import pathlib
import subprocess
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

sys.dont_write_bytecode = True

# Protect against deeply nested ASTs or deep recursions without stack overflow
try:
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 4000))
except Exception:
    pass

from pydantic import BaseModel, ConfigDict, Field

# Directories to skip when scanning repositories
SKIP_DIRS: Set[str] = {
    "__pycache__",
    "build",
    "dist",
    ".git",
    ".tox",
    ".nox",
    ".venv",
    "venv",
    "env",
    ".eggs",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "wheels",
    "site-packages",
    ".adk_exec",
}


# ==============================================================================
# Pydantic v2 Models: Symbol Tracing (--symbol)
# ==============================================================================


class ReferenceDetail(BaseModel):
    """Detailed location and context for a symbol reference, definition, or import."""

    model_config = ConfigDict(extra="ignore")

    file_path: str = Field(description="Relative file path where the reference occurs")
    line_number: int = Field(description="1-based line number of the reference")
    kind: str = Field(
        description="Reference kind: 'class', 'function', 'method', 'import', 'call', 'attribute', 'subclass', or 'text'"
    )
    context: str = Field(default="", description="Source preview, import statement, or call context")
    caller: Optional[str] = Field(default=None, description="Enclosing caller function/method if applicable")
    callee: Optional[str] = Field(default=None, description="Target callee symbol if applicable")
    bases: Optional[List[str]] = Field(default=None, description="Base classes if symbol is a class definition")
    subclasses: Optional[List[str]] = Field(default=None, description="Subclasses inheriting from this symbol")


class SymbolSuggestion(BaseModel):
    """Candidate symbol suggestion for a missing or misspelled query."""

    model_config = ConfigDict(extra="ignore")

    symbol: str = Field(description="Candidate symbol name or fully qualified path")
    similarity: float = Field(description="Fuzzy match similarity score (0.0 to 1.0)")
    kind: Optional[str] = Field(default=None, description="Inferred or known kind (function, class, method, node)")
    location: Optional[str] = Field(default=None, description="File path or defining location if known")
    reason: Optional[str] = Field(default=None, description="Why this candidate was suggested")
    inspect_command: Optional[str] = Field(
        default=None, description="Exact copy-pasteable command to inspect this candidate symbol"
    )
    file_command: Optional[str] = Field(
        default=None, description="Exact copy-pasteable command to inspect containing file"
    )


class GraphStatus(BaseModel):
    """Diagnostic status of precomputed codebase graph loading."""

    model_config = ConfigDict(extra="ignore")

    graph_loaded: bool = Field(description="Whether a precomputed codebase graph JSON was found and loaded")
    graph_path: Optional[str] = Field(default=None, description="Filesystem path of the loaded graph JSON")
    node_count: int = Field(default=0, description="Total node count in loaded graph")
    edge_count: int = Field(default=0, description="Total edge count in loaded graph")
    fallback_mode: str = Field(default="live_ast", description="Analysis mode ('precomputed_graph', 'live_ast', or 'hybrid')")
    diagnostic_message: Optional[str] = Field(default=None, description="Explanation of graph availability or fallback instructions")


class CodeGraphResult(BaseModel):
    """Complete structured output for code graph symbol tracing and reachability analysis."""

    model_config = ConfigDict(extra="ignore")

    mode: str = Field(default="symbol", description="Analysis mode: 'symbol'")
    query: str = Field(description="Queried symbol or text pattern")
    found: bool = Field(description="Whether the symbol was identified in graph or AST")
    resolved_symbol: Optional[str] = Field(default=None, description="Resolved canonical or node identifier")
    focus: Optional[str] = Field(default=None, description="Optional focus filter: 'callers' or 'callees'")
    explanation: str = Field(description="Deterministic explanation of search outcome")
    inspection_hint: Optional[str] = Field(default=None, description="Guidance for private/internal or imported symbols")
    graph_status: GraphStatus = Field(description="Graph loading diagnostics and fallback details")
    definitions: List[ReferenceDetail] = Field(default_factory=list, description="Symbol definitions")
    imports: List[ReferenceDetail] = Field(default_factory=list, description="Symbol imports")
    calls: List[ReferenceDetail] = Field(default_factory=list, description="Direct call sites and attribute accesses")
    subclasses: List[ReferenceDetail] = Field(default_factory=list, description="Classes inheriting from this symbol")
    text_occurrences: List[ReferenceDetail] = Field(default_factory=list, description="Textual matches across files")
    callers: List[str] = Field(default_factory=list, description="Inbound callers invoking this symbol")
    callees: List[str] = Field(default_factory=list, description="Outbound callees invoked by this symbol")
    caller_callee_summary: Optional[str] = Field(default=None, description="Summary of call graph reachability")
    suggestions: List[SymbolSuggestion] = Field(default_factory=list, description="Closest matching candidates")
    did_you_mean: List[str] = Field(default_factory=list, description="List of top suggested symbol names")
    available_top_symbols: List[str] = Field(
        default_factory=list, description="Available top-level public symbols in the repository"
    )
    next_steps: List[str] = Field(default_factory=list, description="Actionable next commands for the LLM")


# ==============================================================================
# Pydantic v2 Models: File Skeleton (--file) & Repository Overview
# ==============================================================================


class MapDiagnostic(BaseModel):
    """Diagnostic explanation for missing paths, syntax errors, or parsing anomalies."""

    model_config = ConfigDict(extra="ignore")

    level: str = Field(default="error", description="Severity level: 'error', 'warning', or 'info'")
    category: str = Field(
        ...,
        description="Category: 'missing_path', 'syntax_error', 'unparseable_file', 'empty_target', 'encoding_error', 'permission_denied', 'recursion_limit_exceeded'",
    )
    message: str = Field(..., description="Primary explanatory message for the agent")
    target_path: Optional[str] = Field(default=None, description="Target file or directory path where issue occurred")
    line: Optional[int] = Field(default=None, description="1-based line number for AST syntax errors")
    column: Optional[int] = Field(default=None, description="1-based column offset for AST syntax errors")
    snippet: Optional[str] = Field(default=None, description="Source code snippet showing the syntax error location and caret pointer")
    suggestions: List[str] = Field(default_factory=list, description="Closest valid paths or recommended actions")
    guidance: Optional[str] = Field(default=None, description="Deterministic guidance instructions for the agent")


class SymbolItem(BaseModel):
    """Extracted Python symbol (class, function, method, async function)."""

    model_config = ConfigDict(extra="ignore")

    kind: str = Field(..., description="Symbol kind: 'class', 'def', 'async def'")
    name: str = Field(..., description="Identifier name of the symbol")
    signature: str = Field(..., description="Formatted symbol signature including arguments, return type, and line range")
    start_line: int = Field(..., description="Starting line number in source file (1-based)")
    end_line: int = Field(..., description="Ending line number in source file (1-based)")
    docstring: Optional[str] = Field(default=None, description="Formatted one-line docstring summary if present")


class ModuleSummary(BaseModel):
    """AST structure summary for a single Python module file."""

    model_config = ConfigDict(extra="ignore")

    path: str = Field(..., description="Workspace-relative path to the Python source file")
    symbols: List[SymbolItem] = Field(default_factory=list, description="List of extracted symbols in document order")
    symbol_count: int = Field(default=0, description="Total number of extracted symbols in this module")
    syntax_error: Optional[MapDiagnostic] = Field(default=None, description="AST syntax error diagnostic if module could not be parsed")


class RepoLayoutItem(BaseModel):
    """Top-level repository layout item for orienting the agent."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., description="Entry name (directory or file name)")
    rel_path: str = Field(..., description="Workspace-relative path")
    is_dir: bool = Field(..., description="True if directory, False if file")
    summary: str = Field(..., description="Formatted human-readable layout summary entry")


class FileSkeletonResult(BaseModel):
    """Complete structured output for file skeleton mapping session."""

    model_config = ConfigDict(extra="ignore")

    mode: str = Field(default="file", description="Analysis mode: 'file'")
    target: str = Field(..., description="Target file or directory path requested by the agent")
    workspace_root: str = Field(..., description="Absolute workspace root path")
    success: bool = Field(default=True, description="Whether mapping completed successfully without path resolution failures")
    modules: List[ModuleSummary] = Field(default_factory=list, description="List of mapped module summaries")
    total_files: int = Field(default=0, description="Number of successfully mapped Python files")
    total_symbols: int = Field(default=0, description="Total number of symbols across all modules")
    diagnostics: List[MapDiagnostic] = Field(default_factory=list, description="List of diagnostics, syntax errors, or warnings")
    top_level_layout: List[RepoLayoutItem] = Field(default_factory=list, description="Top-level repository structure")
    is_truncated: bool = Field(default=False, description="True if output was truncated to honor max_lines cap")
    rendered_text: str = Field(default="", description="Human/LLM-readable text output")
    next_steps: List[str] = Field(default_factory=list, description="Actionable next commands for the LLM")


class WorkspaceOverviewResult(BaseModel):
    """Complete structured output for workspace repository overview and usage guide."""

    model_config = ConfigDict(extra="ignore")

    mode: str = Field(default="overview", description="Analysis mode: 'overview'")
    workspace_root: str = Field(..., description="Absolute workspace root path")
    success: bool = Field(default=True, description="Whether overview was generated successfully")
    top_level_layout: List[RepoLayoutItem] = Field(default_factory=list, description="Top-level repository structure")
    discovered_packages: List[str] = Field(default_factory=list, description="Discovered Python packages/subdirectories")
    key_modules: List[str] = Field(default_factory=list, description="Key Python module files in workspace")
    sample_symbols: List[str] = Field(default_factory=list, description="Sample discovered public classes and functions")
    copy_pasteable_commands: List[str] = Field(default_factory=list, description="Copy-pasteable invocations tailored to this repo")
    rendered_text: str = Field(default="", description="Human/LLM-readable text output")


# ==============================================================================
# Internal CLI Arguments Schema
# ==============================================================================


class ParsedArgs(BaseModel):
    """Structured internal representation of forgiving CLI arguments."""

    model_config = ConfigDict(extra="ignore")

    symbol: Optional[str] = None
    file: Optional[str] = None
    dir: Optional[str] = None
    target: Optional[str] = None
    overview: bool = False
    tree: bool = False
    callers: Optional[Any] = None
    callees: Optional[Any] = None
    focus: Optional[str] = None
    json: bool = False
    graph: Optional[str] = None
    max_lines: int = 120
    notices: List[str] = Field(default_factory=list)


# ==============================================================================
# Workspace & Target Resolution (Loop-Safe & Symlink-Safe)
# ==============================================================================


def should_skip_dir(name: str) -> bool:
    """Return True if directory should be skipped during walk."""
    if name.startswith(".") or name.startswith("__") or ".adk_exec" in name or name.startswith(".adk_exec"):
        return True
    lower = name.lower()
    if lower in SKIP_DIRS:
        return True
    if "egg-info" in lower:
        return True
    return False


def should_skip_path(p: pathlib.Path, ws: pathlib.Path) -> bool:
    """Return True if path contains any skipped directory components."""
    if ".adk_exec" in p.name or p.name.startswith(".adk_exec"):
        return True
    try:
        rel = p.relative_to(ws)
    except ValueError:
        rel = p
    for part in rel.parts:
        if should_skip_dir(part) or ".adk_exec" in part or part.startswith(".adk_exec"):
            return True
    return False


def safe_walk(
    root_path: pathlib.Path,
    ws_root: pathlib.Path,
    max_depth: int = 15,
    max_dirs: int = 1000,
) -> Any:
    """Cycle-safe, symlink-safe, and depth-bounded generator over directory tree.

    Prevents infinite loops from circular symlinks, directory junctions, runaway depth,
    and massive directory trees.
    """
    visited_inodes: Set[Tuple[int, int]] = set()
    visited_realpaths: Set[str] = set()
    dirs_count = 0

    try:
        real_root = os.path.realpath(str(root_path))
        visited_realpaths.add(real_root)
    except Exception:
        pass

    for dirpath, dirnames, filenames in os.walk(str(root_path), followlinks=False):
        dirs_count += 1
        if dirs_count > max_dirs:
            dirnames.clear()
            return

        curr_p = pathlib.Path(dirpath)
        try:
            real_dir = os.path.realpath(dirpath)
            if real_dir in visited_realpaths and dirpath != str(root_path):
                dirnames.clear()
                continue
            visited_realpaths.add(real_dir)

            stat_res = curr_p.stat()
            inode_key = (stat_res.st_dev, stat_res.st_ino)
            if inode_key in visited_inodes:
                dirnames.clear()
                continue
            visited_inodes.add(inode_key)
        except (OSError, PermissionError):
            dirnames.clear()
            continue

        try:
            rel = curr_p.relative_to(ws_root)
            if len(rel.parts) > max_depth:
                dirnames.clear()
                continue
        except ValueError:
            pass

        # In-place directory filtering: skip ignored dirs and symlink directories
        filtered_dirs: List[str] = []
        for d in dirnames:
            if should_skip_dir(d):
                continue
            full_sub = os.path.join(dirpath, d)
            try:
                if os.path.islink(full_sub):
                    continue
            except (OSError, PermissionError):
                continue
            filtered_dirs.append(d)
        dirnames[:] = filtered_dirs

        yield dirpath, dirnames, filenames


def get_workspace_dir() -> pathlib.Path:
    """Robustly and deterministically locate the active target repository workspace directory."""
    # a) Check caller stack frame for _orig_cwd (set by ADK in _materialize_and_run)
    try:
        f = sys._getframe()
        while f:
            if "_orig_cwd" in f.f_locals and f.f_locals["_orig_cwd"]:
                p = pathlib.Path(f.f_locals["_orig_cwd"])
                if p.is_dir() and (
                    (p / "pyproject.toml").exists()
                    or (p / "setup.py").exists()
                    or (p / ".git").exists()
                ):
                    return p.resolve()
            f = f.f_back
    except Exception:
        pass

    # b) Check environment variable overrides
    for env_var in ("SWEGEMMA_WORKSPACE", "WORKSPACE_DIR"):
        val = os.environ.get(env_var)
        if val:
            p = pathlib.Path(val)
            if p.is_dir():
                return p.resolve()

    # c) Standard competition container workspace (/workspace)
    for p_str in ("/workspace", "/workspace/repo", "/repo", "/app"):
        p = pathlib.Path(p_str)
        if p.is_dir() and (
            (p / "pyproject.toml").exists()
            or (p / "setup.py").exists()
            or (p / ".git").exists()
        ):
            return p.resolve()

    # d) Ascend from current directory looking for repo markers
    curr = pathlib.Path.cwd().resolve()
    for parent in [curr] + list(curr.parents):
        if (
            (parent / "pyproject.toml").exists()
            or (parent / "setup.py").exists()
            or (parent / ".git").exists()
            or (parent / "tasks.jsonl").exists()
        ):
            return parent

    return curr


def resolve_target(target_arg: str, ws: pathlib.Path) -> Tuple[Optional[pathlib.Path], str]:
    """Resolve target path safely against workspace."""
    clean = target_arg.strip()
    if not clean or clean in (".", "/", "/workspace"):
        return ws, clean or "."

    # Check direct relative to workspace
    cand = ws / clean.lstrip("/")
    if cand.exists():
        return cand, clean

    # Check absolute
    try:
        p_abs = pathlib.Path(clean).resolve()
        if p_abs.exists() and (p_abs == ws or ws in p_abs.parents):
            return p_abs, clean
    except Exception:
        pass

    # Check with .py appended if not already present
    if not clean.endswith(".py"):
        cand_py = ws / f"{clean.lstrip('/')}.py"
        if cand_py.is_file():
            return cand_py, f"{clean}.py"

    # Check for glob match inside workspace
    try:
        pattern = f"**/{clean}" if clean.endswith(".py") else f"**/{clean}.py"
        matches = [m for m in ws.glob(pattern) if not should_skip_path(m, ws)]
        if matches:
            return matches[0], clean
        if not clean.endswith(".py"):
            dir_matches = [m for m in ws.glob(f"**/{clean}") if m.is_dir() and not should_skip_path(m, ws)]
            if dir_matches:
                return dir_matches[0], clean
    except Exception:
        pass

    return None, clean


def find_closest_paths(clean_target: str, ws: pathlib.Path) -> List[str]:
    """Find closest existing files and directories to the missing target using fuzzy matching."""
    all_dirs: List[str] = []
    all_files: List[str] = []

    try:
        for root, dirs, files in safe_walk(ws, ws, max_depth=8, max_dirs=600):
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
    exact_bases = [p for p in all_paths if os.path.basename(p) == target_base]
    close_full = difflib.get_close_matches(clean_target, all_paths, n=6, cutoff=0.35)
    close_bases = [
        p
        for p in all_paths
        if os.path.basename(p)
        in difflib.get_close_matches(target_base, [os.path.basename(x) for x in all_paths], n=6, cutoff=0.45)
    ]
    substrings = [p for p in all_paths if target_base.lower() in os.path.basename(p).lower()]

    combined: List[str] = []
    for p in exact_bases + close_full + close_bases + substrings:
        if p not in combined:
            combined.append(p)

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
        if entry.name.startswith(".") or entry.name.startswith("__") or ".adk_exec" in entry.name:
            continue
        if entry.name in ("venv", "wheels", ".git", "__pycache__"):
            continue

        rel = entry.name
        if entry.is_dir():
            py_count = 0
            subdirs = 0
            try:
                for _, d_list, f_list in safe_walk(entry, ws, max_depth=5, max_dirs=300):
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
            items.append(RepoLayoutItem(name=entry.name, rel_path=rel, is_dir=True, summary=summary))
        else:
            items.append(RepoLayoutItem(name=entry.name, rel_path=rel, is_dir=False, summary=f"📄 {entry.name}"))
    return items


def collect_py_files(target_path: pathlib.Path, ws: pathlib.Path, max_files: int = 150) -> List[pathlib.Path]:
    """Collect Python files from target path in deterministic order."""
    if target_path.is_file():
        if target_path.name.endswith(".py") or target_path.suffix == ".py":
            return [target_path]
        return []

    py_files: List[pathlib.Path] = []
    for root, dirs, files in safe_walk(target_path, ws, max_depth=10, max_dirs=600):
        dirs[:] = sorted([d for d in dirs if not should_skip_dir(d)])
        for f in sorted(files):
            if f.endswith(".py") and not f.startswith("."):
                py_files.append(pathlib.Path(root) / f)
                if len(py_files) >= max_files:
                    return py_files
    return py_files


def get_top_repo_symbols(ws: pathlib.Path, max_symbols: int = 12) -> List[str]:
    """Extract top-level public classes and functions across key workspace modules."""
    symbols: List[str] = []
    seen: Set[str] = set()

    # Prioritize non-test core modules
    py_files = collect_py_files(ws, ws, max_files=40)
    core_files = [p for p in py_files if "test" not in p.name.lower() and "test" not in str(p).lower()]
    target_files = core_files if core_files else py_files

    for fpath in target_files[:20]:
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            tree = ast.parse(content, filename=str(fpath))
            for node in tree.body:
                if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                    if node.name not in seen:
                        seen.add(node.name)
                        symbols.append(f"class {node.name}")
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                    if node.name not in seen:
                        seen.add(node.name)
                        symbols.append(f"def {node.name}()")
                if len(symbols) >= max_symbols:
                    return symbols
        except Exception:
            continue

    return symbols


# ==============================================================================
# Graph Discovery & Indexing
# ==============================================================================


def discover_graph_file(
    ws_root: pathlib.Path, explicit_path: Optional[str] = None, query_symbol: Optional[str] = None
) -> Optional[pathlib.Path]:
    """Locate precomputed codebase graph JSON file for the repository."""
    if explicit_path:
        p = pathlib.Path(explicit_path).resolve()
        if p.is_file():
            return p

    for env_var in ("SWEGEMMA_GRAPH_PATH", "GRAPH_PATH", "SWEGEMMA_GRAPH_FILE"):
        val = os.environ.get(env_var)
        if val:
            p = pathlib.Path(val).resolve()
            if p.is_file():
                return p

    search_dirs: List[pathlib.Path] = []
    for env_dir in ("SWEGEMMA_GRAPH_DIR", "GRAPH_DIR", "DATA_DIR"):
        val = os.environ.get(env_dir)
        if val:
            search_dirs.append(pathlib.Path(val).resolve())

    search_dirs.extend([
        ws_root / "graphs",
        ws_root / "data" / "graphs",
        ws_root.parent / "graphs",
        ws_root.parent.parent / "graphs",
        pathlib.Path.cwd().resolve() / "graphs",
        pathlib.Path.cwd().resolve() / "data" / "graphs",
        pathlib.Path("/data/graphs"),
        pathlib.Path("/workspace/graphs"),
        pathlib.Path("/workspace/data/graphs"),
    ])

    repo_cands: List[str] = []
    for name in ("fastapi", "rich", "requests", "httpx", "starlette", "pydantic", "flask"):
        if (ws_root / name).is_dir() or (ws_root / "src" / name).is_dir():
            repo_cands.append(name)
        elif name in ws_root.name.lower():
            repo_cands.append(name)

    commit: Optional[str] = None
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ws_root,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if res.returncode == 0 and res.stdout.strip():
            commit = res.stdout.strip()
    except Exception:
        pass

    for d in search_dirs:
        try:
            if not d.is_dir():
                continue
            json_files = sorted(list(d.glob("*.json")))
            if not json_files:
                continue

            if len(json_files) == 1:
                return json_files[0]

            # 1. Match repository name candidate
            for repo in repo_cands:
                matches = [
                    f for f in json_files
                    if f.name.startswith(f"{repo}_") or f.name.startswith(f"{repo}.")
                ]
                if commit:
                    for m in matches:
                        if commit in m.name:
                            return m
                if matches:
                    return matches[0]

            # 2. Match commit directly if available
            if commit:
                for f in json_files:
                    if commit in f.name:
                        return f

            # 3. Query symbol affinity: check 4 core repo families if in dev/harness environment
            if query_symbol:
                families: Dict[str, pathlib.Path] = {}
                for f in json_files:
                    prefix = f.name.split("_")[0].split(".")[0]
                    if prefix not in families:
                        families[prefix] = f

                for _, rep_path in families.items():
                    try:
                        with open(rep_path, "r", encoding="utf-8", errors="replace") as jf:
                            data = json.load(jf)
                        ids = {str(n.get("id") or "") for n in data.get("nodes", [])}
                        if any(query_symbol in nid for nid in ids):
                            return rep_path
                    except Exception:
                        continue

            if json_files:
                return json_files[0]

        except Exception:
            continue

    return None


def load_and_index_graph(graph_path: pathlib.Path) -> Tuple[Dict[str, Any], int, int]:
    """Load precomputed NetworkX node-link JSON and build fast lookup indexes."""
    try:
        with open(graph_path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
    except Exception:
        return {}, 0, 0

    node_ids: List[str] = []
    node_map: Dict[str, Dict[str, Any]] = {}
    leaf_map: Dict[str, List[str]] = {}
    in_edges: Dict[str, List[str]] = {}
    out_edges: Dict[str, List[str]] = {}

    for n in nodes:
        nid = str(n.get("id") or n.get("name") or "").strip()
        if not nid:
            continue
        node_ids.append(nid)
        node_map[nid] = n
        leaf = nid.split(".")[-1]
        leaf_map.setdefault(leaf, []).append(nid)

    for e in edges:
        src = str(e.get("source") or "").strip()
        tgt = str(e.get("target") or "").strip()
        if src and tgt:
            out_edges.setdefault(src, []).append(tgt)
            in_edges.setdefault(tgt, []).append(src)

    indexes = {
        "node_ids": node_ids,
        "node_map": node_map,
        "leaf_map": leaf_map,
        "in_edges": in_edges,
        "out_edges": out_edges,
    }
    return indexes, len(nodes), len(edges)


def resolve_graph_node(query: str, indexes: Dict[str, Any]) -> Optional[str]:
    """Resolve query symbol against graph nodes using 3-tier boundary matching."""
    if not indexes:
        return None

    node_ids: List[str] = indexes.get("node_ids", [])
    node_map: Dict[str, Any] = indexes.get("node_map", {})
    leaf_map: Dict[str, List[str]] = indexes.get("leaf_map", {})

    # Tier 1: Exact match
    if query in node_map:
        return query

    # Tier 2: Leaf / boundary match
    if query in leaf_map:
        return leaf_map[query][0]

    suffix_dot = f".{query}"
    suffix_semi = f";{query}"
    for nid in node_ids:
        if nid.endswith(suffix_dot) or nid.endswith(suffix_semi):
            return nid

    # Tier 3: Case-insensitive boundary match
    q_low = query.lower()
    suffix_dot_low = f".{q_low}"
    for nid in node_ids:
        nid_low = nid.lower()
        if nid_low == q_low or nid_low.endswith(suffix_dot_low):
            return nid

    return None


# ==============================================================================
# Fuzzy Matching & Candidate Suggestions
# ==============================================================================


def compute_fuzzy_suggestions(
    query: str,
    candidates: List[Tuple[str, Optional[str], Optional[str]]],
    top_n: int = 6,
    cutoff: float = 0.30,
) -> List[SymbolSuggestion]:
    """Rank candidate symbols by fuzzy similarity (difflib SequenceMatcher), generating exact copy-pasteable commands."""
    q_low = query.lower()
    scored: List[Tuple[float, str, Optional[str], Optional[str]]] = []

    # Deduplicate candidate names, keeping richest kind/location
    best_candidate_map: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
    for cand_name, kind, loc in candidates:
        cand_clean = cand_name.strip()
        if not cand_clean or cand_clean == query:
            continue
        if cand_clean not in best_candidate_map:
            best_candidate_map[cand_clean] = (kind, loc)
        else:
            old_kind, old_loc = best_candidate_map[cand_clean]
            if not old_loc and loc:
                best_candidate_map[cand_clean] = (kind or old_kind, loc)
            elif old_kind in ("import", "module", "graph_node") and kind in ("class", "function", "method"):
                best_candidate_map[cand_clean] = (kind, loc or old_loc)

    for cand_clean, (kind, loc) in best_candidate_map.items():
        c_low = cand_clean.lower()
        leaf = cand_clean.split(".")[-1]
        l_low = leaf.lower()

        sim_leaf = difflib.SequenceMatcher(None, q_low, l_low).ratio()
        sim_full = difflib.SequenceMatcher(None, q_low, c_low).ratio()

        sub_boost = 0.0
        if q_low == l_low:
            sub_boost = 1.0
        elif q_low in l_low:
            sub_boost = 0.85
        elif q_low in c_low:
            sub_boost = 0.70

        score = max(sim_leaf, sim_full, sub_boost)
        if score >= cutoff:
            scored.append((score, cand_clean, kind, loc))

    scored.sort(key=lambda x: (x[0], -len(x[1])), reverse=True)

    suggestions: List[SymbolSuggestion] = []
    for score, sym, kind, loc in scored[:top_n]:
        inspect_cmd = f'args: ["--symbol", "{sym}"]'
        file_cmd = None
        if loc and ":" in loc:
            f_path = loc.split(":")[0]
            file_cmd = f'args: ["--file", "{f_path}"]'

        suggestions.append(
            SymbolSuggestion(
                symbol=sym,
                similarity=round(score, 3),
                kind=kind or ("function" if "(" in sym else "symbol"),
                location=loc,
                reason=f"Fuzzy match (similarity: {score:.2f}) to '{query}'",
                inspect_command=inspect_cmd,
                file_command=file_cmd,
            )
        )
    return suggestions


# ==============================================================================
# AST Reference, Reachability & Hierarchy Collector (--symbol mode)
# ==============================================================================


class AstReferenceCollector(ast.NodeVisitor):
    """Parses Python AST to extract definitions, base classes, subclasses, imports, calls, callers, callees."""

    def __init__(self, rel_path: str, clean_symbol: str, max_ast_depth: int = 80):
        self.rel_path = rel_path
        self.clean_symbol = clean_symbol
        self.scope_stack: List[str] = []
        self.current_depth: int = 0
        self.max_ast_depth: int = max_ast_depth

        self.defs: List[ReferenceDetail] = []
        self.imports: List[ReferenceDetail] = []
        self.calls: List[ReferenceDetail] = []
        self.subclasses: List[ReferenceDetail] = []
        self.ast_callers: Set[str] = set()
        self.ast_callees: Set[str] = set()
        self.catalog_symbols: List[Tuple[str, Optional[str], str]] = []

    def generic_visit(self, node: ast.AST):
        if self.current_depth >= self.max_ast_depth:
            return
        self.current_depth += 1
        try:
            super().generic_visit(node)
        finally:
            self.current_depth -= 1

    def visit_ClassDef(self, node: ast.ClassDef):
        loc = f"{self.rel_path}:{node.lineno}"
        self.catalog_symbols.append((node.name, "class", loc))

        base_names: List[str] = []
        for b in node.bases:
            try:
                base_names.append(ast.unparse(b))
            except Exception:
                if isinstance(b, ast.Name):
                    base_names.append(b.id)

        bases_str = f"({', '.join(base_names)})" if base_names else ""

        if node.name == self.clean_symbol:
            self.defs.append(
                ReferenceDetail(
                    file_path=self.rel_path,
                    line_number=node.lineno,
                    kind="class",
                    context=f"class {node.name}{bases_str}:",
                    bases=base_names if base_names else None,
                )
            )

        # Check if this class inherits from clean_symbol (class hierarchy)
        if any(self.clean_symbol == b or b.endswith(f".{self.clean_symbol}") for b in base_names):
            self.subclasses.append(
                ReferenceDetail(
                    file_path=self.rel_path,
                    line_number=node.lineno,
                    kind="subclass",
                    context=f"class {node.name}{bases_str} inherits from {self.clean_symbol}",
                    bases=base_names,
                )
            )

        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._handle_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._handle_function(node)

    def _handle_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
        kind = "method" if self.scope_stack else "function"
        loc = f"{self.rel_path}:{node.lineno}"
        full_scope = ".".join(self.scope_stack + [node.name]) if self.scope_stack else node.name
        self.catalog_symbols.append((node.name, kind, loc))
        self.catalog_symbols.append((full_scope, kind, loc))

        if node.name == self.clean_symbol or full_scope == self.clean_symbol:
            ret_str = ""
            if getattr(node, "returns", None):
                try:
                    ret_str = f" -> {ast.unparse(node.returns)}"
                except Exception:
                    pass
            prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            self.defs.append(
                ReferenceDetail(
                    file_path=self.rel_path,
                    line_number=node.lineno,
                    kind=kind,
                    context=f"{prefix} {node.name}(...){ret_str}",
                )
            )

        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_ImportFrom(self, node: ast.ImportFrom):
        dots = "." * node.level if node.level else ""
        mod = f"{dots}{node.module or ''}"
        mod_prefix = f"from {mod} " if mod else ""
        loc = f"{self.rel_path}:{node.lineno}"
        for a in node.names:
            alias_str = f"import {a.name}" + (f" as {a.asname}" if a.asname else "")
            desc = f"{mod_prefix}{alias_str}".strip()
            self.catalog_symbols.append((a.name, "import", loc))
            if a.asname:
                self.catalog_symbols.append((a.asname, "import", loc))

            if a.name == self.clean_symbol or a.asname == self.clean_symbol:
                self.imports.append(
                    ReferenceDetail(
                        file_path=self.rel_path,
                        line_number=node.lineno,
                        kind="import",
                        context=desc,
                    )
                )

    def visit_Import(self, node: ast.Import):
        loc = f"{self.rel_path}:{node.lineno}"
        for a in node.names:
            mod_parts = a.name.split(".")
            desc = f"import {a.name}" + (f" as {a.asname}" if a.asname else "")
            self.catalog_symbols.append((a.name, "module", loc))
            if a.asname:
                self.catalog_symbols.append((a.asname, "module", loc))

            if (
                a.name == self.clean_symbol
                or self.clean_symbol in mod_parts
                or a.asname == self.clean_symbol
            ):
                self.imports.append(
                    ReferenceDetail(
                        file_path=self.rel_path,
                        line_number=node.lineno,
                        kind="import",
                        context=desc,
                    )
                )

    def visit_Call(self, node: ast.Call):
        func_name = ""
        is_attr = False
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
            is_attr = True

        enclosing = ".".join(self.scope_stack) if self.scope_stack else "<module>"

        if func_name == self.clean_symbol:
            kind_str = f".{self.clean_symbol}()" if is_attr else f"{self.clean_symbol}()"
            self.calls.append(
                ReferenceDetail(
                    file_path=self.rel_path,
                    line_number=node.lineno,
                    kind="call",
                    context=kind_str,
                    caller=enclosing if enclosing != "<module>" else None,
                    callee=self.clean_symbol,
                )
            )
            if enclosing != "<module>":
                self.ast_callers.add(f"{enclosing} ({self.rel_path}:{node.lineno})")

        if (
            self.scope_stack
            and (self.scope_stack[-1] == self.clean_symbol or self.clean_symbol in self.scope_stack)
            and func_name
            and func_name != self.clean_symbol
        ):
            self.ast_callees.add(f"{func_name} ({self.rel_path}:{node.lineno})")

        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        if node.attr == self.clean_symbol:
            enclosing = ".".join(self.scope_stack) if self.scope_stack else "<module>"
            self.calls.append(
                ReferenceDetail(
                    file_path=self.rel_path,
                    line_number=node.lineno,
                    kind="attribute",
                    context=f".{self.clean_symbol}",
                    caller=enclosing if enclosing != "<module>" else None,
                )
            )
        self.generic_visit(node)


def analyze_symbol(
    symbol_name: str,
    target_path: pathlib.Path,
    ws_root: pathlib.Path,
    explicit_graph_path: Optional[str] = None,
    focus: Optional[str] = None,
) -> CodeGraphResult:
    """Analyze symbol references, graph reachability, definitions, and class hierarchy."""
    clean_symbol = symbol_name.strip()
    is_valid_ident = clean_symbol.isidentifier()

    # 1. Discover and load precomputed codebase graph if available
    graph_file = discover_graph_file(ws_root, explicit_graph_path, query_symbol=clean_symbol)
    graph_indexes: Dict[str, Any] = {}
    node_count = 0
    edge_count = 0
    graph_loaded = False

    if graph_file:
        graph_indexes, node_count, edge_count = load_and_index_graph(graph_file)
        if node_count > 0:
            graph_loaded = True

    if graph_loaded:
        graph_status = GraphStatus(
            graph_loaded=True,
            graph_path=str(graph_file),
            node_count=node_count,
            edge_count=edge_count,
            fallback_mode="hybrid",
            diagnostic_message=(
                f"Loaded precomputed codebase graph ({node_count} nodes, {edge_count} edges) "
                f"from {graph_file}."
            ),
        )
    else:
        graph_status = GraphStatus(
            graph_loaded=False,
            graph_path=None,
            node_count=0,
            edge_count=0,
            fallback_mode="live_ast",
            diagnostic_message=(
                "Precomputed codebase graph JSON is missing or inaccessible. "
                "Where graphs live: Precomputed codebase graphs are stored as 'graphs/<repo>.json' "
                "or 'data/graphs/<repo>.json' (NetworkX node-link JSON format). "
                "Fallback instructions: Automatically falling back to live repository AST analysis "
                "across all Python files in the workspace."
            ),
        )

    # 2. Collect files to scan (capped at 400 files to guarantee zero hangs)
    file_list = collect_py_files(target_path, ws_root, max_files=400)

    # 3. Perform live AST scanning & text search
    defs: List[ReferenceDetail] = []
    imports: List[ReferenceDetail] = []
    calls: List[ReferenceDetail] = []
    subclasses: List[ReferenceDetail] = []
    text_matches: List[ReferenceDetail] = []
    ast_callers: Set[str] = set()
    ast_callees: Set[str] = set()
    ast_symbol_catalog: List[Tuple[str, Optional[str], str]] = []

    seen_defs: Set[Tuple[str, int]] = set()
    seen_imports: Set[Tuple[str, int]] = set()
    seen_calls: Set[Tuple[str, int, str]] = set()
    seen_subclasses: Set[Tuple[str, int]] = set()
    seen_text: Set[Tuple[str, int]] = set()

    for full_path in file_list:
        try:
            rel_path = full_path.relative_to(ws_root)
        except ValueError:
            rel_path = full_path

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                source = f.read()
        except UnicodeDecodeError:
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    source = f.read()
            except Exception:
                continue
        except (PermissionError, OSError):
            continue

        if is_valid_ident:
            try:
                tree = ast.parse(source, filename=str(rel_path))
                collector = AstReferenceCollector(str(rel_path), clean_symbol)
                collector.visit(tree)

                for d in collector.defs:
                    key = (d.file_path, d.line_number)
                    if key not in seen_defs:
                        seen_defs.add(key)
                        defs.append(d)

                for imp in collector.imports:
                    key = (imp.file_path, imp.line_number)
                    if key not in seen_imports:
                        seen_imports.add(key)
                        imports.append(imp)

                for c in collector.calls:
                    key = (c.file_path, c.line_number, c.context)
                    if key not in seen_calls:
                        seen_calls.add(key)
                        calls.append(c)

                for sub in collector.subclasses:
                    key = (sub.file_path, sub.line_number)
                    if key not in seen_subclasses:
                        seen_subclasses.add(key)
                        subclasses.append(sub)

                ast_callers.update(collector.ast_callers)
                ast_callees.update(collector.ast_callees)
                ast_symbol_catalog.extend(collector.catalog_symbols)
            except (SyntaxError, ValueError, MemoryError, RecursionError):
                pass

        if clean_symbol.lower() in source.lower():
            for lineno, line in enumerate(source.splitlines(), 1):
                if clean_symbol.lower() in line.lower():
                    clean_line = line.strip()
                    if len(clean_line) > 140:
                        clean_line = clean_line[:137] + "..."
                    key = (str(rel_path), lineno)
                    if key not in seen_text:
                        seen_text.add(key)
                        text_matches.append(
                            ReferenceDetail(
                                file_path=str(rel_path),
                                line_number=lineno,
                                kind="text",
                                context=clean_line,
                            )
                        )
                    if len(text_matches) >= 30:
                        break
            if len(text_matches) >= 30:
                pass

    # 4. Resolve node in graph if loaded
    resolved_symbol: Optional[str] = None
    graph_callers: List[str] = []
    graph_callees: List[str] = []

    if graph_loaded:
        resolved_symbol = resolve_graph_node(clean_symbol, graph_indexes)
        if resolved_symbol:
            in_edges = graph_indexes.get("in_edges", {})
            out_edges = graph_indexes.get("out_edges", {})
            graph_callers = in_edges.get(resolved_symbol, [])
            graph_callees = out_edges.get(resolved_symbol, [])

            class_prefix = f"{resolved_symbol}."
            for nid, callers_list in in_edges.items():
                if nid.startswith(class_prefix):
                    graph_callers.extend(callers_list)
            for nid, callees_list in out_edges.items():
                if nid.startswith(class_prefix):
                    graph_callees.extend(callees_list)

            # If AST definitions were not found, synthesize from graph node content
            if not defs:
                node = graph_indexes.get("node_map", {}).get(resolved_symbol, {})
                node_text = node.get("text", "") or ""
                first_line = node_text.splitlines()[0].strip() if node_text else ""
                mod_parts = resolved_symbol.split(".")
                inferred_file = "/".join(mod_parts[:-1]) + ".py" if len(mod_parts) > 1 else f"{resolved_symbol}.py"
                inferred_kind = "class" if first_line.startswith("class ") else "function"

                defs.append(
                    ReferenceDetail(
                        file_path=inferred_file,
                        line_number=1,
                        kind=inferred_kind,
                        context=first_line if first_line else f"{inferred_kind} {clean_symbol}",
                    )
                )

                for child_nid, child_node in graph_indexes.get("node_map", {}).items():
                    if child_nid.startswith(class_prefix) and "." not in child_nid[len(class_prefix):]:
                        child_name = child_nid[len(class_prefix):]
                        child_text = child_node.get("text", "") or ""
                        c_line = child_text.splitlines()[0].strip() if child_text else f"def {child_name}(...)"
                        defs.append(
                            ReferenceDetail(
                                file_path=inferred_file,
                                line_number=1,
                                kind="method",
                                context=c_line[:120],
                            )
                        )
                        if len(defs) >= 20:
                            break

    # 5. Merge callers and callees
    all_callers: List[str] = []
    for c in list(ast_callers) + graph_callers:
        if c not in all_callers:
            all_callers.append(c)

    all_callees: List[str] = []
    for c in list(ast_callees) + graph_callees:
        if c not in all_callees:
            all_callees.append(c)

    found = bool(resolved_symbol or defs or imports or calls or subclasses)
    if not found and not is_valid_ident and text_matches:
        found = True

    # 6. Explanations, Suggestions, and Top-Level Symbols
    inspection_hint: Optional[str] = None
    suggestions: List[SymbolSuggestion] = []
    did_you_mean: List[str] = []
    top_repo_symbols: List[str] = []
    next_steps: List[str] = []

    if clean_symbol.startswith("_"):
        inspection_hint = (
            f"Symbol '{clean_symbol}' starts with an underscore ('_'), indicating a private or "
            "internal function or attribute. Private symbols are often scoped locally within "
            "their defining module or class body and may not be registered as top-level public nodes "
            "in precomputed code graphs.\n"
            "Recommended inspection actions:\n"
            f"  1. Search definitions with fast-grep: args: ['def {clean_symbol}']\n"
            f"  2. Search attribute accesses: args: ['.{clean_symbol}']\n"
            "  3. Inspect the containing module file directly: args: ['--file', '<path>']."
        )
    elif "." in clean_symbol:
        leaf = clean_symbol.split(".")[-1]
        parent = clean_symbol.rsplit(".", 1)[0]
        inspection_hint = (
            f"Symbol '{clean_symbol}' is a qualified or dotted path. Qualified paths depend on "
            "import bindings and module hierarchies. If the qualified path fails to resolve:\n"
            f"  1. Search for the unqualified leaf symbol: args: ['{leaf}']\n"
            f"  2. Search for the enclosing module or class: args: ['{parent}']\n"
            f"  3. Trace references with fast-grep: args: ['{leaf}']\n"
            "  4. Inspect the parent module file directly: args: ['--file', '<path>']."
        )
    elif not is_valid_ident:
        inspection_hint = (
            f"Query '{clean_symbol}' is not a valid Python identifier. code-map --symbol specializes "
            "in Python AST symbols (classes, functions, methods, variables). For arbitrary text patterns, "
            f"use fast-grep: args: ['{clean_symbol}']"
        )

    if found:
        active_name = resolved_symbol or clean_symbol
        explanation = f"Symbol '{clean_symbol}' was successfully traced across the repository."
        caller_callee_summary = (
            f"Symbol '{active_name}' has {len(all_callers)} inbound caller(s) "
            f"and {len(all_callees)} outbound callee(s)."
        )
        if defs:
            first_def = defs[0]
            next_steps.append(f"Inspect defining module: args: ['--file', '{first_def.file_path}']")
        if focus == "callers" and all_callers:
            next_steps.append(f"Inspect top caller: args: ['--symbol', '{all_callers[0].split()[0]}']")
        elif focus == "callees" and all_callees:
            next_steps.append(f"Inspect top callee: args: ['--symbol', '{all_callees[0].split()[0]}']")
        next_steps.append(f"Search direct calls across repo with fast-grep: args: ['{clean_symbol}']")
    else:
        if graph_loaded:
            explanation = (
                f"Symbol '{clean_symbol}' was not found in the precomputed codebase graph "
                f"({node_count} nodes searched) or workspace AST."
            )
        else:
            explanation = (
                f"Symbol '{clean_symbol}' was not found in the precomputed codebase graph "
                f"(graph JSON was missing or inaccessible) or workspace AST ({len(file_list)} files scanned)."
            )

        candidates: List[Tuple[str, Optional[str], Optional[str]]] = []
        if graph_loaded:
            for nid in graph_indexes.get("node_ids", []):
                mod_parts = nid.split(".")
                inferred_loc = "/".join(mod_parts[:-1]) + ".py" if len(mod_parts) > 1 else None
                candidates.append((nid, "graph_node", inferred_loc))
                leaf = nid.split(".")[-1]
                if leaf:
                    candidates.append((leaf, "graph_node", inferred_loc))

        for sym, kind, loc in ast_symbol_catalog:
            candidates.append((sym, kind, loc))

        suggestions = compute_fuzzy_suggestions(clean_symbol, candidates, top_n=6, cutoff=0.30)
        did_you_mean = [s.symbol for s in suggestions]
        caller_callee_summary = f"Symbol '{clean_symbol}' was not found in the codebase graph."

        # Collect available top-level public symbols from the workspace to guide the LLM
        top_repo_symbols = get_top_repo_symbols(ws_root, max_symbols=12)

        if suggestions:
            top_s = suggestions[0]
            if top_s.inspect_command:
                next_steps.append(f"Try closest suggested symbol: {top_s.inspect_command}")
            if top_s.file_command:
                next_steps.append(f"Inspect candidate file: {top_s.file_command}")
        next_steps.append(f"Search codebase text with fast-grep: args: ['{clean_symbol}']")
        next_steps.append("View repository structure and modules: args: []")

    return CodeGraphResult(
        mode="symbol",
        query=symbol_name,
        found=found,
        resolved_symbol=resolved_symbol,
        focus=focus,
        explanation=explanation,
        inspection_hint=inspection_hint,
        graph_status=graph_status,
        definitions=defs,
        imports=imports,
        calls=calls,
        subclasses=subclasses,
        text_occurrences=text_matches,
        callers=all_callers,
        callees=all_callees,
        caller_callee_summary=caller_callee_summary,
        suggestions=suggestions,
        did_you_mean=did_you_mean,
        available_top_symbols=top_repo_symbols,
        next_steps=next_steps,
    )


def format_symbol_report(result: CodeGraphResult) -> str:
    """Format CodeGraphResult into concise, informative text report with actionable LLM guidance."""
    lines: List[str] = [
        "=" * 80,
        "CODE-MAP: SYMBOL REFERENCE & REACHABILITY REPORT",
        "=" * 80,
        f"QUERY: {result.query}",
        f"STATUS: {'FOUND' if result.found else 'NOT FOUND'}",
    ]

    if result.focus:
        lines.append(f"FOCUS: {result.focus.upper()}")

    if result.resolved_symbol:
        lines.append(f"RESOLVED SYMBOL: {result.resolved_symbol}")

    lines.append(f"EXPLANATION: {result.explanation}")
    lines.append("")

    # If focus == 'callers' or 'callees', highlight them prominently at the top
    if result.focus == "callers":
        lines.append("=" * 40)
        lines.append(f"TARGET INBOUND CALLERS FOR '{result.query}':")
        lines.append("=" * 40)
        if result.callers:
            lines.append(f"  Total Inbound Callers: {len(result.callers)}")
            for clr in result.callers[:30]:
                lines.append(f"  👉 {clr}")
        else:
            lines.append("  (0 direct static callers recorded)")
        lines.append("")
    elif result.focus == "callees":
        lines.append("=" * 40)
        lines.append(f"TARGET OUTBOUND CALLEES FOR '{result.query}':")
        lines.append("=" * 40)
        if result.callees:
            lines.append(f"  Total Outbound Callees: {len(result.callees)}")
            for cle in result.callees[:30]:
                lines.append(f"  👉 {cle}")
        else:
            lines.append("  (0 direct static callees recorded)")
        lines.append("")

    lines.append("GRAPH TOPOLOGY:")
    if result.graph_status.graph_loaded:
        lines.append(f"  {result.graph_status.diagnostic_message}")
    else:
        lines.append("  Precomputed codebase graph JSON is missing or inaccessible.")
        lines.append("  Where graphs live: Precomputed codebase graphs are stored as 'graphs/<repo>.json'")
        lines.append("  or 'data/graphs/<repo>.json' (NetworkX node-link JSON).")
        lines.append("  Fallback instructions: Utilizing live repository AST scan for symbol tracing.")
    lines.append("")

    if result.found:
        lines.append(f"DEFINITIONS ({len(result.definitions)}):")
        if result.definitions:
            for d in result.definitions[:20]:
                bases_info = f" [bases: {', '.join(d.bases)}]" if d.bases else ""
                lines.append(f"  - {d.file_path}:{d.line_number} ({d.kind}): {d.context}{bases_info}")
        else:
            lines.append("  (none found in AST)")
        lines.append("")

        if result.subclasses:
            lines.append(f"CLASS HIERARCHY / SUBCLASSES ({len(result.subclasses)}):")
            for sub in result.subclasses[:15]:
                lines.append(f"  - {sub.file_path}:{sub.line_number}: {sub.context}")
            lines.append("")

        lines.append(f"IMPORTS ({len(result.imports)}):")
        if result.imports:
            for imp in result.imports[:20]:
                lines.append(f"  - {imp.file_path}:{imp.line_number}: {imp.context}")
        else:
            lines.append("  (none)")
        lines.append("")

        lines.append(f"CALLS & ATTRIBUTES ({len(result.calls)}, first 20):")
        if result.calls:
            for c in result.calls[:20]:
                caller_info = f" [caller: {c.caller}]" if c.caller else ""
                lines.append(f"  - {c.file_path}:{c.line_number} ({c.kind}): {c.context}{caller_info}")
        else:
            lines.append("  (none)")
        lines.append("")

        if not result.focus:
            lines.append("CALL GRAPH REACHABILITY:")
            lines.append(f"  {result.caller_callee_summary}")
            if result.callers:
                lines.append(f"  Inbound Callers ({len(result.callers)}, first 10):")
                for clr in result.callers[:10]:
                    lines.append(f"    - {clr}")
            else:
                lines.append("  Inbound Callers: (0 direct static callers recorded)")

            if result.callees:
                lines.append(f"  Outbound Callees ({len(result.callees)}, first 10):")
                for cle in result.callees[:10]:
                    lines.append(f"    - {cle}")
            else:
                lines.append("  Outbound Callees: (0 direct static callees recorded)")
            lines.append("")

        if result.text_occurrences:
            lines.append("TEXT OCCURRENCES (first 15):")
            for t in result.text_occurrences[:15]:
                lines.append(f"  - {t.file_path}:{t.line_number}: {t.context}")
            lines.append("")

    else:
        lines.append("WHY THIS QUERY FAILED:")
        lines.append(f"  Symbol '{result.query}' was not identified in the codebase graph or repository AST.")
        if result.query.startswith("_"):
            lines.append(f"  • Note: Symbol starts with '_', indicating a private/internal function or attribute.")
            lines.append("    Private symbols are often not registered as public graph nodes.")
        elif "." in result.query:
            lines.append(f"  • Note: Symbol contains dots. Dotted path queries depend on exact module import hierarchy.")
        elif not result.query.isidentifier():
            lines.append(f"  • Note: Query '{result.query}' is not a valid Python identifier.")
        else:
            lines.append("  • The symbol name may contain a typo, or the symbol is defined dynamically at runtime.")
        lines.append("")

        lines.append("SUGGESTIONS:")
        if result.suggestions:
            lines.append("  Did you mean one of these symbols?")
            for idx, s in enumerate(result.suggestions, 1):
                loc_str = f" [location: {s.location}]" if s.location else ""
                kind_str = f" ({s.kind})" if s.kind else ""
                lines.append(f"    {idx}. {s.symbol}{kind_str} (similarity: {s.similarity:.2f}){loc_str}")
                if s.inspect_command:
                    lines.append(f"       👉 {s.inspect_command}")
                if s.file_command:
                    lines.append(f"       👉 {s.file_command}")
        else:
            lines.append("  No close fuzzy matches found in codebase graph or repository AST.")
        lines.append("")

        if result.available_top_symbols:
            lines.append("TOP-LEVEL PUBLIC SYMBOLS IN REPOSITORY:")
            for sym in result.available_top_symbols:
                clean_sym = sym.replace("class ", "").replace("def ", "").replace("()", "")
                lines.append(f"  • {sym}  ->  args: ['--symbol', '{clean_sym}']")
            lines.append("")

    if result.inspection_hint:
        lines.append("INSPECTION HINT:")
        for hint_line in result.inspection_hint.splitlines():
            lines.append(f"  {hint_line}")
        lines.append("")

    if result.next_steps:
        lines.append("ACTIONABLE NEXT STEPS:")
        for step in result.next_steps:
            lines.append(f"  👉 {step}")
        lines.append("")

    lines.append("=" * 80)
    return "\n".join(lines)


# ==============================================================================
# AST Formatting & Symbol Extraction (--file mode)
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
    current_depth: int = 0,
    max_depth: int = 8,
) -> List[Tuple[str, str, str, int, int, Optional[str]]]:
    """Extract symbol items from AST statements with recursion bounds.

    Returns list of tuples: (kind, name, signature, start_line, end_line, docstring).
    """
    if current_depth >= max_depth:
        return []

    items: List[Tuple[str, str, str, int, int, Optional[str]]] = []
    for node in body:
        try:
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
                methods = get_symbols(node.body, is_class=True, current_depth=current_depth + 1, max_depth=max_depth)
                items.extend(methods)
        except (RecursionError, MemoryError):
            continue
    return items


def parse_and_map_file(
    py_file: pathlib.Path,
    ws: pathlib.Path,
) -> Tuple[ModuleSummary, Optional[MapDiagnostic]]:
    """Parse a single Python file, extract AST symbols, and diagnose syntax/permission/encoding errors."""
    try:
        rel_display = py_file.relative_to(ws)
    except ValueError:
        rel_display = py_file

    try:
        with open(py_file, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError as e:
        diag = MapDiagnostic(
            level="warning",
            category="encoding_error",
            message=f"File '{rel_display}' contains unparseable binary or invalid UTF-8 encoding: {e}",
            target_path=str(rel_display),
            guidance="Verify file encoding (UTF-8 required) or verify that this is a Python source file.",
        )
        return ModuleSummary(path=str(rel_display), syntax_error=diag), diag
    except PermissionError as e:
        diag = MapDiagnostic(
            level="error",
            category="permission_denied",
            message=f"Permission denied reading file '{rel_display}': {e}",
            target_path=str(rel_display),
            guidance="Check file permissions or run with appropriate access privileges.",
        )
        return ModuleSummary(path=str(rel_display), syntax_error=diag), diag
    except OSError as e:
        diag = MapDiagnostic(
            level="error",
            category="unparseable_file",
            message=f"Failed to read file '{rel_display}': {e}",
            target_path=str(rel_display),
            guidance="Verify file exists and filesystem is accessible.",
        )
        return ModuleSummary(path=str(rel_display), syntax_error=diag), diag

    try:
        tree = ast.parse(content, filename=str(py_file))
    except SyntaxError as e:
        err_line = e.lineno or 1
        err_col = e.offset or 1
        err_msg = e.msg or "invalid syntax"

        content_lines = content.splitlines()
        if e.text:
            source_line = e.text.rstrip("\r\n").expandtabs(4)
        elif 1 <= err_line <= len(content_lines):
            source_line = content_lines[err_line - 1].expandtabs(4)
        else:
            source_line = ""

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
    except RecursionError:
        diag = MapDiagnostic(
            level="warning",
            category="recursion_limit_exceeded",
            message=f"AST nesting depth exceeds limit in '{rel_display}'.",
            target_path=str(rel_display),
            guidance="File contains deeply nested structures; outline skipped to prevent stack overflow.",
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


def generate_file_skeleton(target_str: str, max_lines: int = 120) -> FileSkeletonResult:
    """Generate compact AST skeleton for a target file or directory up to max_lines budget."""
    ws = get_workspace_dir()
    target_path, clean_target = resolve_target(target_str, ws)

    # 1. Target does not exist: Provide actionable diagnostics & suggestions
    if target_path is None or not target_path.exists():
        diag_msg = f"Path '{target_str}' does not exist in /workspace."
        suggestions = find_closest_paths(clean_target, ws)
        layout_items = get_top_level_layout(ws)
        guidance = (
            f"Target '{target_str}' was not found in /workspace. "
            "Review the suggested closest matches or top-level repository layout below to select an existing file."
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
            f"[code-map] {diag_msg}",
            "",
            "WHY THIS FAILED:",
            f"  Target path '{target_str}' does not exist in the active workspace.",
            "  Common causes:",
            "  1. Typo in directory or file name.",
            "  2. Missing folder prefix (e.g. 'src/' or package directory).",
            "  3. Missing or wrong file extension (.py).",
            "",
        ]
        if str(ws) != "/workspace":
            lines.append(f"  (Active workspace root: {ws})")
            lines.append("")
        if suggestions:
            lines.append("💡 Suggested closest existing paths:")
            for s in suggestions:
                lines.append(f"  • {s}")
                clean_s = s.replace("📁 ", "").replace("📄 ", "").rstrip("/")
                lines.append(f"     👉 args: ['--file', '{clean_s}']")
            lines.append("")
        if layout_items:
            lines.append("📂 Top-level repository layout (/workspace):")
            for item in layout_items:
                lines.append(f"  {item.summary}")
            lines.append("")

        next_steps: List[str] = []
        if suggestions:
            for s in suggestions[:3]:
                best = s.replace("📁 ", "").replace("📄 ", "").rstrip("/")
                next_steps.append(f"Inspect closest match: args: ['--file', '{best}']")
        next_steps.append("View repository overview and packages: args: []")

        if next_steps:
            lines.append("👉 Actionable next steps:")
            for step in next_steps:
                lines.append(f"  • {step}")
            lines.append("")

        rendered = "\n".join(lines)
        return FileSkeletonResult(
            mode="file",
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
            next_steps=next_steps,
        )

    # 2. Target exists: Collect .py files (single file or directory)
    py_files = collect_py_files(target_path, ws, max_files=100)

    # Directory has no .py files: Forgivingly list directory contents and point to python code
    if not py_files:
        items_in_dir: List[str] = []
        try:
            if target_path.is_dir():
                for item in sorted(target_path.iterdir()):
                    if not item.name.startswith("."):
                        icon = "📁" if item.is_dir() else "📄"
                        items_in_dir.append(f"{icon} {item.name}")
        except Exception:
            pass

        diag_msg = f"No Python source files (.py) found in target '{target_str}'."
        diag = MapDiagnostic(
            level="warning",
            category="empty_target",
            message=diag_msg,
            target_path=target_str,
            suggestions=items_in_dir[:6],
            guidance="Specify a directory or file that contains Python source code.",
        )
        lines = [
            f"[code-map] {diag_msg}",
            "",
            "WHY THIS FAILED:",
            f"  Target '{target_str}' exists but contains no Python source files (.py).",
            "",
        ]
        if items_in_dir:
            lines.append("Contents of target directory:")
            for itm in items_in_dir[:10]:
                lines.append(f"  {itm}")
            lines.append("")

        layout_items = get_top_level_layout(ws)
        if layout_items:
            lines.append("📂 Directories with Python code (/workspace):")
            for item in layout_items:
                if item.is_dir and ".py" in item.summary:
                    lines.append(f"  {item.summary}")
            lines.append("")

        rendered = "\n".join(lines)
        return FileSkeletonResult(
            mode="file",
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
            next_steps=["Run with args: [] to see packages with Python code"],
        )

    # 3. Target is a single file with syntax error: Special detailed diagnostic
    if len(py_files) == 1:
        mod_summary, diag = parse_and_map_file(py_files[0], ws)
        if diag and diag.category == "syntax_error":
            single_file_lines = [
                f"[code-map: SyntaxError in {mod_summary.path}]",
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
            return FileSkeletonResult(
                mode="file",
                target=target_str,
                workspace_root=str(ws),
                success=True,
                modules=[mod_summary],
                total_files=1,
                total_symbols=0,
                diagnostics=[diag],
                top_level_layout=[],
                is_truncated=False,
                rendered_text=rendered,
                next_steps=[f"Fix syntax error at line {diag.line} using edit_file"],
            )

    # 4. Multi-file or single file AST outline generation with strict max_lines budget
    output_lines: List[str] = []
    modules: List[ModuleSummary] = []
    all_diagnostics: List[MapDiagnostic] = []
    total_symbols = 0
    total_files_parsed = 0
    is_truncated = False

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
    summary_parts = [f"[code-map: {total_symbols} symbols across {total_files_parsed} file(s)"]
    if syntax_err_count > 0:
        summary_parts.append(f" ({syntax_err_count} file(s) had syntax errors)")
    summary_parts.append("]")
    output_lines.append("".join(summary_parts))

    rendered = "\n".join(output_lines)

    next_steps: List[str] = []
    if modules and modules[0].symbols:
        first_sym = modules[0].symbols[0].name
        next_steps.append(f"Trace symbol call-graph: args: ['--symbol', '{first_sym}']")
    if len(py_files) > 1 and is_truncated:
        first_mod = modules[0].path
        next_steps.append(f"Inspect single module outline: args: ['--file', '{first_mod}']")

    return FileSkeletonResult(
        mode="file",
        target=target_str,
        workspace_root=str(ws),
        success=True,
        modules=modules,
        total_files=total_files_parsed,
        total_symbols=total_symbols,
        diagnostics=all_diagnostics,
        top_level_layout=[],
        is_truncated=is_truncated,
        rendered_text=rendered,
        next_steps=next_steps,
    )


# ==============================================================================
# Workspace Repository Overview & Usage Guide (Empty Calls & '.' / '/workspace')
# ==============================================================================


def generate_workspace_overview(ws: pathlib.Path) -> WorkspaceOverviewResult:
    """Generate forgiving repository overview and copy-pasteable usage guide tailored to current workspace."""
    layout_items = get_top_level_layout(ws)

    # Discovered packages: top-level dirs with .py files
    discovered_packages: List[str] = []
    for item in layout_items:
        if item.is_dir and ".py" in item.summary:
            discovered_packages.append(item.name)

    # Discovered sample files
    sample_files = collect_py_files(ws, ws, max_files=15)
    core_files = [p for p in sample_files if "test" not in p.name.lower() and "test" not in str(p).lower()]
    chosen_files = core_files if core_files else sample_files
    key_modules: List[str] = []
    for p in chosen_files[:3]:
        try:
            rel = str(p.relative_to(ws))
            key_modules.append(rel)
        except Exception:
            pass

    # Sample symbols
    sample_symbols = get_top_repo_symbols(ws, max_symbols=6)
    clean_sample_symbols = [
        s.replace("class ", "").replace("def ", "").replace("()", "")
        for s in sample_symbols
    ]

    # Generate tailored copy-pasteable commands
    example_mod = key_modules[0] if key_modules else "example.py"
    example_pkg = discovered_packages[0] if discovered_packages else "."
    example_sym = clean_sample_symbols[0] if clean_sample_symbols else "main"

    commands = [
        f'args: ["--file", "{example_mod}"]           # Compact AST outline of a key module',
        f'args: ["--file", "{example_pkg}"]                 # Map package directory structure',
        f'args: ["--symbol", "{example_sym}"]             # Trace call-graph, callers, callees, definitions',
        f'args: ["--symbol", "{example_sym}", "--callers"]   # Focus specifically on inbound callers',
        f'args: ["{example_mod}"]                  # Positional shorthand (auto-detects file)',
        f'args: ["{example_sym}"]                  # Positional shorthand (auto-detects symbol)',
    ]

    lines: List[str] = [
        "=" * 80,
        "CODE-MAP: WORKSPACE OVERVIEW & ACTIONABLE USAGE GUIDE",
        "=" * 80,
        f"Workspace Root: {ws}",
        "",
        "📂 TOP-LEVEL REPOSITORY LAYOUT:",
    ]
    if layout_items:
        for item in layout_items:
            lines.append(f"  {item.summary}")
    else:
        lines.append("  (empty or inaccessible workspace)")
    lines.append("")

    if discovered_packages:
        lines.append(f"📦 DISCOVERED PACKAGES: {', '.join(discovered_packages)}")
        lines.append("")

    if key_modules:
        lines.append("📄 KEY MODULES:")
        for m in key_modules:
            lines.append(f"  • {m}")
        lines.append("")

    if clean_sample_symbols:
        lines.append("🔍 SAMPLE PUBLIC SYMBOLS:")
        for sym in clean_sample_symbols:
            lines.append(f"  • {sym}")
        lines.append("")

    lines.append("💡 RECOMMENDED TOOL ARGUMENTS:")
    for cmd in commands:
        lines.append(f"  {cmd}")
    lines.append("")
    lines.append("=" * 80)

    rendered = "\n".join(lines)

    return WorkspaceOverviewResult(
        mode="overview",
        workspace_root=str(ws),
        success=True,
        top_level_layout=layout_items,
        discovered_packages=discovered_packages,
        key_modules=key_modules,
        sample_symbols=clean_sample_symbols,
        copy_pasteable_commands=commands,
        rendered_text=rendered,
    )


# ==============================================================================
# Forgiving CLI Argument Parsing
# ==============================================================================


def parse_cli_args(argv: List[str]) -> Tuple[ParsedArgs, List[str]]:
    """Forgivingly and omnivorously parse CLI arguments without ever crashing.

    Handles:
    - Aliases: -s, --symbol, -f, --file, -d, --dir, -o, --overview, -t, --tree, --callers, --callees
    - Typo tolerance: maps flags like --symbl to --symbol via fuzzy matching
    - Unrecognized flags: warns and routes to closest intent or overview
    - Missing flag values: uses defaults gracefully without ArgumentError
    - Seamless positional fallbacks: symbol vs file/dir auto-detection
    """
    notices: List[str] = []
    args = ParsedArgs()

    i = 0
    positional: List[str] = []

    KNOWN_FLAGS = {
        "-s": "symbol",
        "--symbol": "symbol",
        "--sym": "symbol",
        "--symbols": "symbol",
        "--function": "symbol",
        "--fn": "symbol",
        "--class": "symbol",
        "-f": "file",
        "--file": "file",
        "--path": "file",
        "--filepath": "file",
        "-d": "dir",
        "--dir": "dir",
        "--directory": "dir",
        "--folder": "dir",
        "-o": "overview",
        "--overview": "overview",
        "--summary": "overview",
        "--workspace": "overview",
        "-t": "tree",
        "--tree": "tree",
        "--callers": "callers",
        "--caller": "callers",
        "--inbound": "callers",
        "--callees": "callees",
        "--callee": "callees",
        "--outbound": "callees",
        "-j": "json",
        "--json": "json",
        "-g": "graph",
        "--graph": "graph",
        "-n": "max_lines",
        "--max-lines": "max_lines",
        "--limit": "max_lines",
        "--lines": "max_lines",
        "-h": "help",
        "--help": "help",
    }

    while i < len(argv):
        arg = argv[i]
        val = None

        if arg in ("-h", "--help"):
            return ParsedArgs(overview=True), ["help"]

        # Handle --flag=value syntax
        if "=" in arg and arg.startswith("-"):
            flag_part, val = arg.split("=", 1)
        else:
            flag_part = arg

        canon = KNOWN_FLAGS.get(flag_part)

        # Fuzzy match flag typo if starts with - or --
        if not canon and flag_part.startswith("-"):
            clean_flag = flag_part.lstrip("-")
            all_clean = {k.lstrip("-"): v for k, v in KNOWN_FLAGS.items()}
            close = difflib.get_close_matches(clean_flag, list(all_clean.keys()), n=1, cutoff=0.6)
            if close:
                canon = all_clean[close[0]]
                notices.append(f"Interpreted flag '{flag_part}' as '--{close[0]}'.")
            else:
                notices.append(f"Unrecognized option '{flag_part}' ignored.")
                i += 1
                continue

        if canon == "symbol":
            if val is not None:
                args.symbol = val
            elif i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                i += 1
                args.symbol = argv[i]
            else:
                notices.append("Option '--symbol' passed without a value.")
        elif canon == "file":
            if val is not None:
                args.file = val
            elif i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                i += 1
                args.file = argv[i]
            else:
                notices.append("Option '--file' passed without a value.")
        elif canon == "dir":
            if val is not None:
                args.dir = val
            elif i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                i += 1
                args.dir = argv[i]
            else:
                notices.append("Option '--dir' passed without a value.")
        elif canon == "overview":
            args.overview = True
        elif canon == "tree":
            args.tree = True
        elif canon == "callers":
            args.focus = "callers"
            if val is not None:
                args.callers = val
                args.symbol = val
            elif i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                i += 1
                args.callers = argv[i]
                args.symbol = argv[i]
            else:
                args.callers = True
        elif canon == "callees":
            args.focus = "callees"
            if val is not None:
                args.callees = val
                args.symbol = val
            elif i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                i += 1
                args.callees = argv[i]
                args.symbol = argv[i]
            else:
                args.callees = True
        elif canon == "json":
            args.json = True
        elif canon == "graph":
            if val is not None:
                args.graph = val
            elif i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                i += 1
                args.graph = argv[i]
        elif canon == "max_lines":
            lines_val = val
            if lines_val is None and i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                i += 1
                lines_val = argv[i]
            if lines_val:
                try:
                    args.max_lines = int(lines_val)
                except ValueError:
                    notices.append(f"Invalid integer '{lines_val}' for line budget; using default.")
        elif not arg.startswith("-"):
            positional.append(arg)

        i += 1

    if positional:
        args.target = positional[0]

    args.notices = notices
    return args, []


def determine_mode_and_target(
    args: ParsedArgs,
    ws: pathlib.Path,
) -> Tuple[str, str, Optional[str]]:
    """Deterministically and forgivingly resolve analysis mode ('overview', 'file', 'symbol'), target, and focus."""
    # 1. Explicit overview flag
    if args.overview:
        return "overview", ".", None

    # 2. Tree flag: directory tree / file outline
    if args.tree:
        tree_target = args.dir or args.file or args.target or "."
        return "file", tree_target, None

    # 3. Callers / Callees flag with explicit value or focus
    if args.callers:
        sym = args.callers if isinstance(args.callers, str) else (args.symbol or args.target or "")
        if sym:
            return "symbol", sym, "callers"

    if args.callees:
        sym = args.callees if isinstance(args.callees, str) else (args.symbol or args.target or "")
        if sym:
            return "symbol", sym, "callees"

    # 4. Explicit --symbol
    if args.symbol:
        return "symbol", args.symbol, args.focus

    # 5. Explicit --dir
    if args.dir:
        return "file", args.dir, None

    # 6. Explicit --file
    if args.file:
        if args.file in (".", "/", "/workspace"):
            return "overview", ".", None
        return "file", args.file, None

    # 7. Positional argument
    if args.target:
        clean = args.target.strip()
        if not clean or clean in (".", "/", "/workspace"):
            return "overview", ".", None

        # Clearly a file extension or path with separators
        if clean.endswith(".py") or clean.endswith(".pyi") or "/" in clean or "\\" in clean:
            return "file", clean, None

        # Check direct existence as file or directory in workspace
        cand_p = ws / clean
        if cand_p.is_file() or cand_p.is_dir():
            return "file", clean, None

        cand_py = ws / f"{clean}.py"
        if cand_py.is_file():
            return "file", f"{clean}.py", None

        # Check with resolve_target for glob/search matches
        resolved, _ = resolve_target(clean, ws)
        if resolved is not None and resolved.exists():
            return "file", clean, None

        # Otherwise, treat as symbol
        return "symbol", clean, args.focus

    # 8. No arguments passed at all -> overview mode
    return "overview", ".", None


def print_help():
    """Print user/LLM help text."""
    print("""code-map: AST code structure and symbol call-graph tracer.

Tool Invocation:
  run_skill_script(skill_name="code-map", file_path="map.py", args=[...])

Modes:
  --symbol, -s <name>     Trace callers, callees, definitions, and class hierarchy across repository.
  --file, -f <path>       Generate compact AST skeleton for a Python file or directory.
  --dir, -d <path>        Generate AST skeleton for all modules in a directory.
  --tree, -t [path]       Map directory tree structure and module skeletons.
  --overview, -o          Display workspace overview, discovered packages, and key modules.
  --callers [symbol]      Focus on inbound callers for the target symbol.
  --callees [symbol]      Focus on outbound callees for the target symbol.
  <target>                Positional shorthand (auto-detects file, directory, or symbol).
  (empty)                 Displays workspace overview, discovered packages, and tailored commands.

Options:
  --json, -j              Output structured JSON schema (Pydantic v2).
  --max-lines, -n <int>   Maximum lines of symbol output for directory outlines (default: 120).
  --graph, -g <path>      Explicit path to precomputed codebase graph JSON.
  --help, -h              Show this help message and exit.

Recommended Arguments:
  args: []                                      # Repository overview & tailored usage guide
  args: ["--symbol", "APIRouter"]               # Trace symbol callers/callees/definitions
  args: ["-s", "APIRouter", "--callers"]        # Focus on inbound callers of APIRouter
  args: ["-s", "APIRouter", "--callees"]        # Focus on outbound callees of APIRouter
  args: ["--file", "fastapi/routing.py"]        # Compact AST outline of a single file
  args: ["-f", "fastapi"]                       # Map directory modules up to max_lines budget
  args: ["-d", "fastapi"]                       # Directory mapping shorthand
  args: ["APIRouter"]                           # Auto-detected symbol mode
  args: ["fastapi/routing.py"]                  # Auto-detected file mode
  args: ["fastapi"]                             # Auto-detected directory mode
  args: ["--symbol", "APIRouter", "--json"]     # Output structured JSON schema
""")


# ==============================================================================
# CLI Entrypoint
# ==============================================================================


def run_cli(argv: List[str]) -> int:
    """Execute code-map CLI forgivingly."""
    ws_root = get_workspace_dir()
    parsed_args, extra = parse_cli_args(argv)

    if extra and extra[0] == "help":
        print_help()
        return 0

    mode, target_name, focus = determine_mode_and_target(parsed_args, ws_root)

    # Print notices if any (only in non-json mode)
    if parsed_args.notices and not parsed_args.json:
        for note in parsed_args.notices:
            print(f"[code-map note] {note}")
        print("")

    # 1. Overview Mode
    if mode == "overview":
        res_overview = generate_workspace_overview(ws_root)
        if parsed_args.json:
            print(res_overview.model_dump_json(indent=2))
        else:
            print(res_overview.rendered_text)
        return 0

    # 2. File / Directory Skeleton Mode
    if mode == "file":
        res_file = generate_file_skeleton(target_name, max_lines=parsed_args.max_lines)
        if parsed_args.json:
            print(res_file.model_dump_json(indent=2))
        else:
            print(res_file.rendered_text)
        return 0

    # 3. Symbol Mode
    target_path, _ = resolve_target(".", ws_root)
    res_symbol = analyze_symbol(
        symbol_name=target_name,
        target_path=target_path or ws_root,
        ws_root=ws_root,
        explicit_graph_path=parsed_args.graph,
        focus=focus,
    )

    if parsed_args.json:
        print(res_symbol.model_dump_json(indent=2))
    else:
        print(format_symbol_report(res_symbol))

    return 0


def main() -> int:
    try:
        return run_cli(sys.argv[1:])
    except Exception as e:
        # Ultimate fallback: never crash with unhandled exception or leave LLM stranded
        ws = get_workspace_dir()
        overview = generate_workspace_overview(ws)
        print(f"[code-map note] Command completed with fallback due to: {e}")
        print(overview.rendered_text)
        return 0


if __name__ == "__main__":
    sys.exit(main())
