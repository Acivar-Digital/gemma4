#!/usr/bin/env python3
"""AST and code-graph symbol reference tracer and reachability analyzer.

Traces where any symbol (function, class, variable, method) or text query
is defined, imported, called, or referenced across the repository.
Omnivorous and forgiving:
- Automatically discovers and loads precomputed codebase graphs (NetworkX node-link JSON).
- If the graph JSON is missing or inaccessible, deterministically explains where graphs
  live ('graphs/<repo>.json' or 'data/graphs/<repo>.json') and falls back to live AST analysis.
- When a symbol is not found, explains WHY and suggests closest matching candidates
  via fuzzy matching (edit distance / Levenshtein).
- Provides actionable diagnostic hints for private/internal symbols ('_') and dotted module paths.
- Explains caller/callee reachability across the code graph.
- 100% Pydantic v2 structured schemas (CodeGraphResult, ReferenceDetail, SymbolSuggestion, etc.).
- Always returns exit code 0 and never crashes.

Usage:
    python3 find_refs.py <symbol_or_query> [search_dir]
    python3 find_refs.py --json <symbol_or_query> [search_dir]
    python3 find_refs.py --help
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

from pydantic import BaseModel, ConfigDict, Field

# Directories to skip when scanning repositories
SKIP_DIRS: Set[str] = {
    "__pycache__",
    "build",
    "dist",
    ".git",
    ".tox",
    ".venv",
    "venv",
    ".eggs",
    ".mypy_cache",
    ".pytest_cache",
    "node_modules",
    "wheels",
}


# ==============================================================================
# Pydantic v2 Schemas
# ==============================================================================


class ReferenceDetail(BaseModel):
    """Detailed location and context for a symbol reference, definition, or import."""

    model_config = ConfigDict(extra="ignore")

    file_path: str = Field(description="Relative file path where the reference occurs")
    line_number: int = Field(description="1-based line number of the reference")
    kind: str = Field(description="Reference kind: 'class', 'function', 'method', 'import', 'call', 'attribute', or 'text'")
    context: str = Field(default="", description="Source preview, import statement, or call context")
    caller: Optional[str] = Field(default=None, description="Enclosing caller function/method if applicable")
    callee: Optional[str] = Field(default=None, description="Target callee symbol if applicable")


class SymbolSuggestion(BaseModel):
    """Candidate symbol suggestion for a missing or misspelled query."""

    model_config = ConfigDict(extra="ignore")

    symbol: str = Field(description="Candidate symbol name or fully qualified path")
    similarity: float = Field(description="Fuzzy match similarity score (0.0 to 1.0)")
    kind: Optional[str] = Field(default=None, description="Inferred or known kind (function, class, method, node)")
    location: Optional[str] = Field(default=None, description="File path or defining location if known")
    reason: Optional[str] = Field(default=None, description="Why this candidate was suggested")


class CallerCalleeConnection(BaseModel):
    """Caller or callee relationship between symbols in the code graph."""

    model_config = ConfigDict(extra="ignore")

    source: str = Field(description="Originating caller symbol or node")
    target: str = Field(description="Target callee symbol or node")
    relation: str = Field(default="calls", description="Edge relationship type ('calls', 'called_by')")
    file_path: Optional[str] = Field(default=None, description="File path where call occurs")
    line_number: Optional[int] = Field(default=None, description="Line number where call occurs")


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

    query: str = Field(description="Queried symbol or text pattern")
    found: bool = Field(description="Whether the symbol was identified in graph or AST")
    resolved_symbol: Optional[str] = Field(default=None, description="Resolved canonical or node identifier")
    explanation: str = Field(description="Deterministic explanation of search outcome")
    inspection_hint: Optional[str] = Field(default=None, description="Guidance for private/internal or imported symbols")
    graph_status: GraphStatus = Field(description="Graph loading diagnostics and fallback details")
    definitions: List[ReferenceDetail] = Field(default_factory=list, description="Symbol definitions")
    imports: List[ReferenceDetail] = Field(default_factory=list, description="Symbol imports")
    calls: List[ReferenceDetail] = Field(default_factory=list, description="Direct call sites and attribute accesses")
    text_occurrences: List[ReferenceDetail] = Field(default_factory=list, description="Textual matches across files")
    callers: List[str] = Field(default_factory=list, description="Inbound callers invoking this symbol")
    callees: List[str] = Field(default_factory=list, description="Outbound callees invoked by this symbol")
    caller_callee_summary: Optional[str] = Field(default=None, description="Summary of call graph reachability")
    suggestions: List[SymbolSuggestion] = Field(default_factory=list, description="Closest matching candidates")
    did_you_mean: List[str] = Field(default_factory=list, description="List of top suggested symbol names")


# ==============================================================================
# Workspace & Target Resolution
# ==============================================================================


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

    # b) Check standard container / benchmark workspace paths
    for p_str in ("/workspace", "/workspace/repo", "/repo", "/app"):
        p = pathlib.Path(p_str)
        if p.is_dir() and (
            (p / "pyproject.toml").exists()
            or (p / "setup.py").exists()
            or (p / ".git").exists()
        ):
            return p.resolve()

    # c) Ascend from current directory looking for repo marker
    curr = pathlib.Path.cwd().resolve()
    for parent in [curr] + list(curr.parents):
        if (
            (parent / "pyproject.toml").exists()
            or (parent / "setup.py").exists()
            or (parent / ".git").exists()
        ):
            return parent

    return curr


def resolve_target(target_arg: str, ws: pathlib.Path) -> pathlib.Path:
    """Resolve target path safely against workspace."""
    clean = target_arg.strip()
    if not clean or clean == ".":
        return ws

    p_abs = pathlib.Path(clean).resolve()
    try:
        if p_abs.exists() and (p_abs == ws or ws in p_abs.parents):
            return p_abs
    except Exception:
        pass

    # Relative to workspace
    cand = ws / clean.lstrip("/")
    if cand.exists():
        return cand

    # Check for glob match inside workspace
    try:
        matches = list(ws.glob(f"**/{clean}"))
        if matches:
            return matches[0]
    except Exception:
        pass

    # Forgiving fallback: default to the whole workspace
    return ws


# ==============================================================================
# Graph Discovery & Indexing
# ==============================================================================


def discover_graph_file(
    ws_root: pathlib.Path, explicit_path: Optional[str] = None
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

            if commit:
                for f in json_files:
                    if commit in f.name:
                        return f
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
    top_n: int = 5,
    cutoff: float = 0.35,
) -> List[SymbolSuggestion]:
    """Rank candidate symbols by fuzzy similarity (edit distance / Levenshtein) to query."""
    q_low = query.lower()
    scored: List[Tuple[float, str, Optional[str], Optional[str]]] = []
    seen: Set[str] = set()

    for cand_name, kind, loc in candidates:
        cand_clean = cand_name.strip()
        if not cand_clean or cand_clean in seen or cand_clean == query:
            continue
        seen.add(cand_clean)

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

    # Sort descending by score, tie-break by shorter symbol length
    scored.sort(key=lambda x: (x[0], -len(x[1])), reverse=True)

    suggestions: List[SymbolSuggestion] = []
    for score, sym, kind, loc in scored[:top_n]:
        suggestions.append(
            SymbolSuggestion(
                symbol=sym,
                similarity=round(score, 3),
                kind=kind or ("function" if "(" in sym else "symbol"),
                location=loc,
                reason=f"Closest fuzzy match (similarity: {score:.2f})",
            )
        )
    return suggestions


# ==============================================================================
# AST Reference & Reachability Collector
# ==============================================================================


class AstReferenceCollector(ast.NodeVisitor):
    """Parses Python AST to extract definitions, imports, calls, callers, callees, and symbol catalog."""

    def __init__(self, rel_path: str, clean_symbol: str):
        self.rel_path = rel_path
        self.clean_symbol = clean_symbol
        self.scope_stack: List[str] = []

        self.defs: List[ReferenceDetail] = []
        self.imports: List[ReferenceDetail] = []
        self.calls: List[ReferenceDetail] = []
        self.ast_callers: Set[str] = set()
        self.ast_callees: Set[str] = set()
        # Catalog of (name, kind, location) for fallback fuzzy matching
        self.catalog_symbols: List[Tuple[str, Optional[str], str]] = []

    def visit_ClassDef(self, node: ast.ClassDef):
        loc = f"{self.rel_path}:{node.lineno}"
        self.catalog_symbols.append((node.name, "class", loc))
        if node.name == self.clean_symbol:
            self.defs.append(
                ReferenceDetail(
                    file_path=self.rel_path,
                    line_number=node.lineno,
                    kind="class",
                    context=f"class {node.name}",
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
            self.defs.append(
                ReferenceDetail(
                    file_path=self.rel_path,
                    line_number=node.lineno,
                    kind=kind,
                    context=f"def {node.name}(...)",
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

        # If the enclosing function is clean_symbol, what it calls is an outbound callee
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


# ==============================================================================
# Core Analysis Engine
# ==============================================================================


def analyze_symbol(
    symbol_name: str,
    target_path: pathlib.Path,
    ws_root: pathlib.Path,
    explicit_graph_path: Optional[str] = None,
) -> CodeGraphResult:
    """Analyze symbol references, graph reachability, and missing-symbol explanations."""
    clean_symbol = symbol_name.strip()
    is_valid_ident = clean_symbol.isidentifier()

    # 1. Discover and load precomputed codebase graph if available
    graph_file = discover_graph_file(ws_root, explicit_graph_path)
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

    # 2. Collect files to scan
    if target_path.is_file():
        file_list = [target_path] if target_path.suffix == ".py" else []
    else:
        file_list = []
        for dirpath, dirnames, filenames in os.walk(target_path):
            dirnames[:] = [
                d for d in dirnames
                if not d.startswith(".")
                and d not in SKIP_DIRS
                and not d.endswith(".egg-info")
            ]
            for fname in sorted(filenames):
                if fname.endswith(".py") and not fname.startswith("."):
                    file_list.append(pathlib.Path(dirpath) / fname)

    # 3. Perform live AST scanning & text search
    defs: List[ReferenceDetail] = []
    imports: List[ReferenceDetail] = []
    calls: List[ReferenceDetail] = []
    text_matches: List[ReferenceDetail] = []
    ast_callers: Set[str] = set()
    ast_callees: Set[str] = set()
    ast_symbol_catalog: List[Tuple[str, Optional[str], str]] = []

    seen_defs: Set[Tuple[str, int]] = set()
    seen_imports: Set[Tuple[str, int]] = set()
    seen_calls: Set[Tuple[str, int, str]] = set()
    seen_text: Set[Tuple[str, int]] = set()

    for full_path in file_list:
        try:
            rel_path = full_path.relative_to(ws_root)
        except ValueError:
            rel_path = full_path

        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
        except OSError:
            continue

        # AST analysis for valid identifiers
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

                ast_callers.update(collector.ast_callers)
                ast_callees.update(collector.ast_callees)
                ast_symbol_catalog.extend(collector.catalog_symbols)
            except (SyntaxError, ValueError, MemoryError, RecursionError):
                pass

        # Text occurrences fallback
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
                    if len(text_matches) >= 50:
                        break

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

            # Also check child methods of class if resolved_symbol is a class
            class_prefix = f"{resolved_symbol}."
            for nid, callers_list in in_edges.items():
                if nid.startswith(class_prefix):
                    graph_callers.extend(callers_list)
            for nid, callees_list in out_edges.items():
                if nid.startswith(class_prefix):
                    graph_callees.extend(callees_list)

    # 5. Merge callers and callees
    all_callers: List[str] = []
    for c in list(ast_callers) + graph_callers:
        if c not in all_callers:
            all_callers.append(c)

    all_callees: List[str] = []
    for c in list(ast_callees) + graph_callees:
        if c not in all_callees:
            all_callees.append(c)

    # Determine if symbol was found
    found = bool(resolved_symbol or defs or imports or calls)
    if not found and not is_valid_ident and text_matches:
        found = True

    # 6. Build explanations, inspection hints, and fuzzy suggestions
    inspection_hint: Optional[str] = None
    suggestions: List[SymbolSuggestion] = []
    did_you_mean: List[str] = []

    if clean_symbol.startswith("_"):
        inspection_hint = (
            f"Symbol '{clean_symbol}' starts with an underscore ('_'), indicating a private or "
            "internal function or attribute. Private symbols are often scoped locally within "
            "their defining module or class body and may not be registered as top-level public nodes "
            "in precomputed code graphs.\n"
            "Recommended inspection actions:\n"
            f"  1. Search definitions with fast-grep: run_skill_script(skill_name='fast-grep', "
            f"file_path='grep.py', args=['def {clean_symbol}'])\n"
            f"  2. Search attribute accesses: run_skill_script(skill_name='fast-grep', "
            f"file_path='grep.py', args=['.{clean_symbol}'])\n"
            "  3. Inspect the containing module file directly using read_file."
        )
    elif "." in clean_symbol:
        leaf = clean_symbol.split(".")[-1]
        parent = clean_symbol.rsplit(".", 1)[0]
        inspection_hint = (
            f"Symbol '{clean_symbol}' is a qualified or dotted path. Qualified paths depend on "
            "import bindings and module hierarchies. If the qualified path fails to resolve:\n"
            f"  1. Search for the unqualified leaf symbol: '{leaf}'\n"
            f"  2. Search for the enclosing module or class: '{parent}'\n"
            f"  3. Trace references with fast-grep: run_skill_script(skill_name='fast-grep', "
            f"file_path='grep.py', args=['{leaf}'])\n"
            "  4. Inspect the parent module file directly using read_file."
        )
    elif not is_valid_ident:
        inspection_hint = (
            f"Query '{clean_symbol}' is not a valid Python identifier. The code-graph skill specializes "
            "in Python AST symbols (classes, functions, methods, variables). For arbitrary text patterns, "
            "regular expressions, or multi-word search, use fast-grep:\n"
            f"  run_skill_script(skill_name='fast-grep', file_path='grep.py', args=['{clean_symbol}'])"
        )

    if found:
        active_name = resolved_symbol or clean_symbol
        explanation = f"Symbol '{clean_symbol}' was successfully traced across the repository."
        caller_callee_summary = (
            f"Symbol '{active_name}' has {len(all_callers)} inbound caller(s) "
            f"and {len(all_callees)} outbound callee(s)."
        )
    else:
        # Construct deterministic explanation why symbol was not found
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

        # Collect candidate symbols for fuzzy suggestions
        candidates: List[Tuple[str, Optional[str], Optional[str]]] = []
        if graph_loaded:
            for nid in graph_indexes.get("node_ids", []):
                candidates.append((nid, "graph_node", None))
                leaf = nid.split(".")[-1]
                if leaf:
                    candidates.append((leaf, "graph_node", None))

        for sym, kind, loc in ast_symbol_catalog:
            candidates.append((sym, kind, loc))

        suggestions = compute_fuzzy_suggestions(clean_symbol, candidates, top_n=5, cutoff=0.35)
        did_you_mean = [s.symbol for s in suggestions]
        caller_callee_summary = f"Symbol '{clean_symbol}' was not found in the codebase graph."

    return CodeGraphResult(
        query=symbol_name,
        found=found,
        resolved_symbol=resolved_symbol,
        explanation=explanation,
        inspection_hint=inspection_hint,
        graph_status=graph_status,
        definitions=defs,
        imports=imports,
        calls=calls,
        text_occurrences=text_matches,
        callers=all_callers,
        callees=all_callees,
        caller_callee_summary=caller_callee_summary,
        suggestions=suggestions,
        did_you_mean=did_you_mean,
    )


# ==============================================================================
# Output Formatting
# ==============================================================================


def format_text_report(result: CodeGraphResult) -> str:
    """Format CodeGraphResult into a concise, deterministic human/LLM-readable text report."""
    lines: List[str] = [
        "=" * 80,
        "CODE-GRAPH: SYMBOL REFERENCE & REACHABILITY REPORT",
        "=" * 80,
        f"QUERY: {result.query}",
        f"STATUS: {'FOUND' if result.found else 'NOT FOUND'}",
    ]

    if result.resolved_symbol:
        lines.append(f"RESOLVED SYMBOL: {result.resolved_symbol}")

    lines.append(f"EXPLANATION: {result.explanation}")
    lines.append("")

    # Graph topology status
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
        # Definitions
        lines.append(f"DEFINITIONS ({len(result.definitions)}):")
        if result.definitions:
            for d in result.definitions[:20]:
                lines.append(f"  - {d.file_path}:{d.line_number} ({d.kind}): {d.context}")
        else:
            lines.append("  (none found in AST)")
        lines.append("")

        # Imports
        lines.append(f"IMPORTS ({len(result.imports)}):")
        if result.imports:
            for imp in result.imports[:20]:
                lines.append(f"  - {imp.file_path}:{imp.line_number}: {imp.context}")
        else:
            lines.append("  (none)")
        lines.append("")

        # Calls & Attributes
        lines.append(f"CALLS & ATTRIBUTES ({len(result.calls)}, first 20):")
        if result.calls:
            for c in result.calls[:20]:
                caller_info = f" [caller: {c.caller}]" if c.caller else ""
                lines.append(f"  - {c.file_path}:{c.line_number} ({c.kind}): {c.context}{caller_info}")
        else:
            lines.append("  (none)")
        lines.append("")

        # Call Graph Reachability
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

        # Text occurrences if available
        if result.text_occurrences:
            lines.append(f"TEXT OCCURRENCES (first 15):")
            for t in result.text_occurrences[:15]:
                lines.append(f"  - {t.file_path}:{t.line_number}: {t.context}")
            lines.append("")

    else:
        # Not found: display suggestions
        lines.append("SUGGESTIONS:")
        if result.suggestions:
            lines.append("  Did you mean one of these symbols:")
            for idx, s in enumerate(result.suggestions, 1):
                loc_str = f", location: {s.location}" if s.location else ""
                kind_str = f", kind: {s.kind}" if s.kind else ""
                lines.append(f"    {idx}. {s.symbol} (similarity: {s.similarity:.2f}{kind_str}{loc_str})")
        else:
            lines.append("  No close fuzzy matches found in codebase graph or repository AST.")
        lines.append("")

    # Inspection hints
    if result.inspection_hint:
        lines.append("INSPECTION HINT:")
        for hint_line in result.inspection_hint.splitlines():
            lines.append(f"  {hint_line}")
        lines.append("")

    lines.append("=" * 80)
    return "\n".join(lines)


# ==============================================================================
# CLI Entrypoint
# ==============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AST and code-graph symbol reference tracer and reachability analyzer.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "symbol_or_query",
        nargs="?",
        default="",
        help="Symbol name (function, class, variable, method) or text query to trace.",
    )
    parser.add_argument(
        "search_dir",
        nargs="?",
        default=".",
        help="Search directory or file path within repository (defaults to '.').",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as formatted JSON adhering to CodeGraphResult Pydantic schema.",
    )
    parser.add_argument(
        "--graph",
        default=None,
        help="Explicit path to precomputed codebase graph JSON.",
    )

    args = parser.parse_args()

    if not args.symbol_or_query or not args.symbol_or_query.strip():
        parser.print_help()
        return 0

    query = args.symbol_or_query.strip()
    search_arg = args.search_dir.strip() if args.search_dir else "."

    ws_root = get_workspace_dir()
    target_path = resolve_target(search_arg, ws_root)

    result = analyze_symbol(
        symbol_name=query,
        target_path=target_path,
        ws_root=ws_root,
        explicit_graph_path=args.graph,
    )

    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        print(format_text_report(result))

    return 0


if __name__ == "__main__":
    sys.exit(main())
