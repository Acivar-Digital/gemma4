#!/usr/bin/env python3
"""AST-based code-graph symbol reference tracer (stdlib only).

Traces where any symbol (function, class, variable, method) or text query
is defined, imported, called, or referenced across the repository.
Always forgiving and omnivorous: resolves paths safely against the workspace.

Usage:
    python3 find_refs.py <symbol_or_query> [search_dir]
"""

import ast
import os
import pathlib
import sys

# Directories to skip when scanning repositories
SKIP_DIRS = {
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

    # d) Environment variable overrides (SWEGEMMA_WORKSPACE or WORKSPACE_DIR)
    for env_var in ("SWEGEMMA_WORKSPACE", "WORKSPACE_DIR"):
        val = os.environ.get(env_var)
        if val:
            p = pathlib.Path(val)
            if p.is_dir():
                return p.resolve()

    # b) Check standard competition container workspace (/workspace)
    ws = pathlib.Path("/workspace")
    if ws.is_dir():
        return ws.resolve()

    # c) Check current working directory and its parents for repo markers
    cur = pathlib.Path.cwd().resolve()
    for parent in [cur] + list(cur.parents):
        if (
            (parent / ".git").exists()
            or (parent / "pyproject.toml").exists()
            or (parent / "setup.py").exists()
            or (parent / "setup.cfg").exists()
        ):
            return parent

    # e) Fall back safely to current working directory
    return cur


def resolve_target(target_str: str | None, ws: pathlib.Path) -> pathlib.Path:
    """Omnivorously resolve any given search path against the workspace."""
    if not target_str or str(target_str).strip() in (".", "./", "/workspace", "/workspace/"):
        return ws

    clean = str(target_str).strip()
    if clean.startswith("/workspace/"):
        clean = clean[len("/workspace/"):]
    elif clean == "/workspace":
        return ws
    clean = clean.lstrip("/")

    cand = ws / clean
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


def scan_symbol_references(symbol_name: str, target_path: pathlib.Path, ws_root: pathlib.Path) -> int:
    """Scan target_path for AST occurrences and text references of symbol_name."""
    defs = []      # list of (rel_path, lineno, kind_str)
    imports = []   # list of (rel_path, lineno, import_str)
    calls = []     # list of (rel_path, lineno, "call")
    text_matches = [] # list of (rel_path, lineno, line_preview)

    seen_defs = set()
    seen_imports = set()
    seen_calls = set()
    seen_text = set()

    clean_symbol = symbol_name.strip()
    is_valid_ident = clean_symbol.isidentifier()

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

        tree = None
        if is_valid_ident:
            try:
                tree = ast.parse(source, filename=str(rel_path))
            except (SyntaxError, ValueError, MemoryError, RecursionError):
                tree = None

        if tree is not None:
            for node in ast.walk(tree):
                lineno = getattr(node, "lineno", 1)

                # 1. Definitions
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if node.name == clean_symbol:
                        kind = (
                            "class def"
                            if isinstance(node, ast.ClassDef)
                            else ("async func def" if isinstance(node, ast.AsyncFunctionDef) else "func def")
                        )
                        key = (str(rel_path), lineno, kind)
                        if key not in seen_defs:
                            seen_defs.add(key)
                            defs.append(key)

                # 2. Imports
                elif isinstance(node, ast.ImportFrom):
                    matched_aliases = [
                        a for a in node.names
                        if a.name == clean_symbol or a.asname == clean_symbol
                    ]
                    if matched_aliases:
                        dots = "." * node.level if node.level else ""
                        mod = f"{dots}{node.module or ''}"
                        mod_prefix = f"from {mod} " if mod else ""
                        for a in matched_aliases:
                            alias_str = f"import {a.name}" + (f" as {a.asname}" if a.asname else "")
                            desc = f"{mod_prefix}{alias_str}".strip()
                            key = (str(rel_path), lineno, desc)
                            if key not in seen_imports:
                                seen_imports.add(key)
                                imports.append(key)

                elif isinstance(node, ast.Import):
                    for a in node.names:
                        mod_parts = a.name.split(".")
                        if (
                            a.name == clean_symbol
                            or clean_symbol in mod_parts
                            or a.asname == clean_symbol
                        ):
                            alias_str = f"import {a.name}" + (f" as {a.asname}" if a.asname else "")
                            key = (str(rel_path), lineno, alias_str)
                            if key not in seen_imports:
                                seen_imports.add(key)
                                imports.append(key)

                # 3. Calls & Attribute Access
                elif isinstance(node, ast.Call):
                    func = node.func
                    is_call = False
                    if isinstance(func, ast.Name) and func.id == clean_symbol:
                        is_call = True
                    elif isinstance(func, ast.Attribute) and func.attr == clean_symbol:
                        is_call = True

                    if is_call:
                        key = (str(rel_path), lineno, "call")
                        if key not in seen_calls:
                            seen_calls.add(key)
                            calls.append(key)

                elif isinstance(node, ast.Attribute) and node.attr == clean_symbol:
                    key = (str(rel_path), lineno, f".{clean_symbol}")
                    if key not in seen_calls:
                        seen_calls.add(key)
                        calls.append(key)

        # Fallback / text line search
        if clean_symbol.lower() in source.lower():
            for lineno, line in enumerate(source.splitlines(), 1):
                if clean_symbol.lower() in line.lower():
                    clean_line = line.strip()
                    if len(clean_line) > 140:
                        clean_line = clean_line[:137] + "..."
                    key = (str(rel_path), lineno, clean_line)
                    if key not in seen_text:
                        seen_text.add(key)
                        text_matches.append(key)
                    if len(text_matches) >= 50:
                        break

    # Format output
    output_lines = [f"QUERY: {symbol_name}"]
    output_lines.append("DEFINITIONS:")
    if defs:
        for fpath, lno, kind in defs[:20]:
            output_lines.append(f"  - {fpath}:{lno} ({kind})")
    else:
        output_lines.append("  (none)")

    output_lines.append("IMPORTS:")
    if imports:
        for fpath, lno, desc in imports[:20]:
            output_lines.append(f"  - {fpath}:{lno}: {desc}")
    else:
        output_lines.append("  (none)")

    output_lines.append("CALLS & ATTRIBUTES (first 20):")
    if calls:
        for fpath, lno, kind in calls[:20]:
            output_lines.append(f"  - {fpath}:{lno} ({kind})")
    else:
        output_lines.append("  (none)")

    if text_matches:
        output_lines.append("TEXT OCCURRENCES (first 25):")
        for fpath, lno, preview in text_matches[:25]:
            output_lines.append(f"  - {fpath}:{lno}: {preview}")

    print("\n".join(output_lines))
    return 0


def main():
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("Usage: python3 find_refs.py <symbol_or_query> [search_dir]")
        return 0

    symbol_name = sys.argv[1].strip()
    search_arg = sys.argv[2].strip() if len(sys.argv) > 2 else "."

    ws_root = get_workspace_dir()
    target_path = resolve_target(search_arg, ws_root)

    return scan_symbol_references(symbol_name, target_path, ws_root)


if __name__ == "__main__":
    sys.exit(main())
