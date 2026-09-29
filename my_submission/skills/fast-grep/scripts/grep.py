#!/usr/bin/env python3
"""fast-grep: Ranked AST-Aware Keyword and Regex Search across Workspace.

Searches codebase via git grep (with pure Python fallback), ranks matches by
architectural relevance (core definitions > references > tests > docs),
and automatically flashes the top 3 complete, deterministic enclosing Python
functions using AST parsing.

Always returns exit code 0.

Usage:
    python3 grep.py <pattern> [search_path]
"""

import ast
import os
import pathlib
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

SKIP_DIRS = {
    "__pycache__",
    "build",
    "dist",
    ".git",
    ".tox",
    ".nox",
    ".mypy_cache",
    ".pytest_cache",
    "node_modules",
    "venv",
    ".venv",
}

TEXT_EXTENSIONS = {
    ".py",
    ".md",
    ".rst",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".ini",
    ".cfg",
    ".sh",
    ".bash",
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
    """Resolve any given search path against the workspace."""
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

    try:
        matches = list(ws.glob(f"**/{clean}"))
        if matches:
            return matches[0]
    except Exception:
        pass

    return ws


def run_git_grep(pattern: str, search_target: pathlib.Path, ws: pathlib.Path) -> List[str] | None:
    """Attempt fast git grep if git is available."""
    try:
        rel_target = search_target.relative_to(ws)
        path_arg = str(rel_target) if str(rel_target) != "." else ""
    except ValueError:
        path_arg = ""

    cmd = ["git", "grep", "-n", "-i", "-I", "--line-number", pattern]
    if path_arg:
        cmd.extend(["--", path_arg])

    try:
        res = subprocess.run(
            cmd,
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if res.returncode in (0, 1):
            return res.stdout.strip().splitlines() if res.stdout.strip() else []
    except Exception:
        pass
    return None


def run_python_grep(pattern: str, search_target: pathlib.Path, ws: pathlib.Path, max_matches: int = 150) -> List[str]:
    """Pure Python fallback for regex and text searching."""
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error:
        regex = re.compile(re.escape(pattern), re.IGNORECASE)

    matches: List[str] = []

    if search_target.is_file():
        file_list = [search_target]
    else:
        file_list = []
        for root, dirs, files in os.walk(search_target):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in SKIP_DIRS and not d.endswith(".egg-info")]
            for f in sorted(files):
                if f.startswith("."):
                    continue
                ext = os.path.splitext(f)[1].lower()
                if ext in TEXT_EXTENSIONS or f in ("Makefile", "Dockerfile", "pyproject.toml", "setup.cfg"):
                    file_list.append(pathlib.Path(root) / f)

    for p in file_list:
        if len(matches) >= max_matches:
            break
        try:
            rel_display = p.relative_to(ws)
        except ValueError:
            rel_display = p

        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                for line_idx, line in enumerate(f, 1):
                    if regex.search(line):
                        matches.append(f"{rel_display}:{line_idx}:{line.rstrip()}")
                        if len(matches) >= max_matches:
                            break
        except Exception:
            continue

    return matches


def score_match(file_path: str, lineno: int, content: str, pattern: str) -> int:
    """Compute probability/relevance score for ranking search matches."""
    score = 0
    # 1. Path scoring
    if "docs/" in file_path or file_path.endswith((".md", ".rst", ".txt")):
        score -= 50
    elif "test" in file_path:
        score += 10
    elif file_path.endswith(".py"):
        score += 50
        if not (file_path.startswith("examples/") or file_path.startswith("benchmarks/")):
            score += 20

    # 2. Definition vs reference scoring
    if re.search(r"^\s*(def|class)\s+", content):
        score += 40
        clean_pat = re.sub(r"[^a-zA-Z0-9_]", "", pattern)
        if clean_pat and re.search(rf"^\s*(def|class)\s+{clean_pat}\b", content, re.IGNORECASE):
            score += 30

    return score


def extract_function_scope(file_path: pathlib.Path, target_line: int) -> Optional[Dict[str, Any]]:
    """Extract the complete, deterministic enclosing Python function using AST."""
    if not file_path.is_file() or file_path.suffix != ".py":
        return None

    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(file_path))
    except Exception:
        return None

    parent_map = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parent_map[child] = parent

    candidates = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                if node.lineno <= target_line <= node.end_lineno:
                    candidates.append(node)

    if not candidates:
        return None

    # Pick innermost enclosing function
    candidates.sort(key=lambda n: n.end_lineno - n.lineno)
    best = candidates[0]

    # Resolve qualified name (e.g. ClassName.method_name)
    name_parts = [best.name]
    curr = parent_map.get(best)
    while curr:
        if isinstance(curr, ast.ClassDef):
            name_parts.insert(0, curr.name)
        curr = parent_map.get(curr)

    qual_name = ".".join(name_parts)
    raw_lines = source.splitlines()
    fn_lines = raw_lines[best.lineno - 1 : best.end_lineno]

    return {
        "name": qual_name,
        "start_line": best.lineno,
        "end_line": best.end_lineno,
        "line_count": len(fn_lines),
        "lines": fn_lines,
    }


def main() -> int:
    if len(sys.argv) < 2:
        print("[fast-grep] No search pattern provided.")
        print("Usage: python3 grep.py <pattern> [search_path]")
        return 0

    pattern = sys.argv[1].strip()
    target_arg = sys.argv[2].strip() if len(sys.argv) > 2 else "."

    ws = get_workspace_dir()
    search_target = resolve_target(target_arg, ws)

    # 1. Execute search
    results = run_git_grep(pattern, search_target, ws)
    if results is None:
        results = run_python_grep(pattern, search_target, ws)

    if not results:
        print(f"[fast-grep] 0 matches found for pattern: '{pattern}' in {search_target.name or '.'}")
        return 0

    # 2. Parse and rank matches by probability/relevance
    parsed_matches = []
    for r in results:
        parts = r.split(":", 2)
        if len(parts) >= 2 and parts[1].isdigit():
            file_s = parts[0]
            line_i = int(parts[1])
            content_s = parts[2] if len(parts) > 2 else ""
            sc = score_match(file_s, line_i, content_s, pattern)
            parsed_matches.append({
                "file": file_s,
                "lineno": line_i,
                "content": content_s,
                "score": sc,
                "raw": r,
            })

    parsed_matches.sort(key=lambda m: m["score"], reverse=True)

    # 3. Extract top 3 unique enclosing functions via AST
    seen_funcs: Set[Tuple[str, str]] = set()
    flashed_funcs: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []

    for m in parsed_matches:
        p = ws / m["file"]
        if not p.suffix == ".py":
            continue
        scope = extract_function_scope(p, m["lineno"])
        if scope:
            key = (m["file"], scope["name"])
            if key not in seen_funcs:
                seen_funcs.add(key)
                flashed_funcs.append((m, scope))
                if len(flashed_funcs) == 3:
                    break

    # 4. Display flashed top 3 functions
    print(f"[fast-grep] Pattern: '{pattern}' ({len(parsed_matches)} total matches, top 3 functions flashed):\n")

    if flashed_funcs:
        for idx, (m, sc) in enumerate(flashed_funcs, 1):
            f_path = m["file"]
            q_name = sc["name"]
            s_line = sc["start_line"]
            e_line = sc["end_line"]
            total_l = sc["line_count"]
            lines = sc["lines"]

            print("=" * 80)
            print(f"⭐ TOP {idx} [Score {m['score']:+d}]: {f_path} (lines {s_line}-{e_line}) | {q_name} ({total_l} lines)")
            print("=" * 80)

            # Cap huge functions (e.g. >100 lines) safely to preserve context budget
            if total_l > 100:
                for i, line in enumerate(lines[:70], start=s_line):
                    print(f"{i:4d}: {line}")
                omitted = total_l - 90
                print(f"      ... [{omitted} lines omitted in large function] ...")
                for i, line in enumerate(lines[-20:], start=e_line - 19):
                    print(f"{i:4d}: {line}")
            else:
                for i, line in enumerate(lines, start=s_line):
                    print(f"{i:4d}: {line}")
            print()

    # 5. Display concise list of remaining/other matches
    print("-" * 80)
    print("📋 ALL RANKED MATCHES (Top 25 summary):")
    for m in parsed_matches[:25]:
        content_preview = m["content"].strip()[:70]
        print(f"  [{m['score']:+3d}] {m['file']}:{m['lineno']}: {content_preview}")

    if len(parsed_matches) > 25:
        print(f"  ... ({len(parsed_matches) - 25} more matches truncated)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
