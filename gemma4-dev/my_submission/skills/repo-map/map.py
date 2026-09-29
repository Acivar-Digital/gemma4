#!/usr/bin/env python3
"""repo-map: Compact AST skeleton generator for Python codebases.

Pure Python standard library only.
Extracts classes, methods, functions, signatures, docstrings, and line ranges.
Caps total output to 120 lines to prevent context window flooding.
Always forgiving and omnivorous: resolves paths safely against the workspace.
"""

import ast
import os
import pathlib
import sys
from typing import List, Optional, Tuple


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


def should_skip_dir(name: str) -> bool:
    """Return True if directory should be skipped during walk."""
    if name.startswith(".") or name.startswith("__"):
        return True
    lower = name.lower()
    if lower in ("tests", "test", "build", "dist", "venv", "wheels", "site-packages"):
        return True
    if "egg-info" in lower:
        return True
    return False


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
        doc = ast.get_docstring(node, clean=True)
        if not doc:
            return None
        first_line = doc.split("\n")[0].strip()
        if not first_line:
            return None
        if len(first_line) > 70:
            first_line = first_line[:67] + "..."
        return f'{indent}"""{first_line}"""'
    except Exception:
        return None


def get_symbols(body: List[ast.stmt], is_class: bool = False) -> List[Tuple[str, Optional[str]]]:
    """Extract symbol signatures and docstrings from AST statements."""
    items: List[Tuple[str, Optional[str]]] = []
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
            items.append((sig, doc))
        elif isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.unparse(b) for b in node.bases)
            bases_str = f"({bases})" if bases else ""
            start = getattr(node, "lineno", 1)
            end = getattr(node, "end_lineno", start)
            sig = f"  class {node.name}{bases_str}: [{start}-{end}]"
            doc = format_docstring(node, indent="    ")
            items.append((sig, doc))
            methods = get_symbols(node.body, is_class=True)
            items.extend(methods)
    return items


def collect_py_files(target_path: pathlib.Path) -> List[pathlib.Path]:
    """Collect Python files sorted alphabetically."""
    if target_path.is_file():
        return [target_path] if target_path.suffix == ".py" else []
    py_files: List[pathlib.Path] = []
    for root, dirs, files in os.walk(target_path):
        dirs[:] = sorted([d for d in dirs if not should_skip_dir(d)])
        for f in sorted(files):
            if f.endswith(".py") and not f.startswith("."):
                py_files.append(pathlib.Path(root) / f)
    return py_files


def main() -> int:
    ws = get_workspace_dir()
    os.chdir(ws)

    target_str = sys.argv[1] if len(sys.argv) > 1 else "."
    target_path = resolve_target(target_str, ws)

    py_files = collect_py_files(target_path)
    if not py_files:
        print(f"[repo-map] No Python source files found for '{target_str}'. Workspace root: {ws.name}")
        return 0

    max_lines = 120
    output_lines: List[str] = []
    total_symbols = 0
    total_files = 0

    for py_file in py_files:
        try:
            rel_display = py_file.relative_to(ws)
        except ValueError:
            rel_display = py_file

        try:
            with open(py_file, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            tree = ast.parse(content, filename=str(py_file))
        except Exception:
            continue

        symbols = get_symbols(tree.body)
        if not symbols:
            continue

        file_header = f"{rel_display}:"
        file_lines = [file_header]
        file_sym_count = 0

        for sig, doc in symbols:
            file_lines.append(sig)
            file_sym_count += 1
            if doc:
                file_lines.append(doc)

        if len(output_lines) + len(file_lines) > max_lines:
            output_lines.append(f"... [Truncated at {max_lines} lines; {len(py_files) - total_files} more files]")
            break

        output_lines.extend(file_lines)
        total_symbols += file_sym_count
        total_files += 1

    summary = f"\n[repo-map: {total_symbols} symbols across {total_files} file(s)]"
    output_lines.append(summary)
    print("\n".join(output_lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
