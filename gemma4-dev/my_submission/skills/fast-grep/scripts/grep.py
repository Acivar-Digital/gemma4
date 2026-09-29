#!/usr/bin/env python3
"""fast-grep: Omnivorous, AST-Aware Search Engine for Autonomous Agents.

Eats ANY input format:
- Single terms, multiple terms (searched as OR/union)
- Unescaped regex or literal code snippets
- Dotted symbols, function calls, or raw keywords
- Automatically skips benchmarks, lockfiles, docs, and non-code spam
- Flashes top 3 enclosing functions with complete decorators via AST
- Always exits 0 and never crashes.
"""

import ast
import os
import pathlib
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Noisy non-code directories that pollute search results
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".tox",
    ".nox",
    ".mypy_cache",
    ".pytest_cache",
    "node_modules",
    "venv",
    ".venv",
    "benchmarks",
    "docs",
    "doc",
    "build",
    "dist",
    "site-packages",
    "__pycache__",
}

# Ignored data/lock/telemetry files that swamp search with hash collisions
SKIP_EXTENSIONS = {
    ".lock",
    ".json",
    ".csv",
    ".tsv",
    ".svg",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".pyc",
    ".whl",
    ".tar",
    ".gz",
    ".tgz",
    ".zip",
    ".so",
    ".dylib",
    ".min.js",
    ".map",
}

ALLOWED_CODE_EXTENSIONS = {
    ".py",
    ".pyi",
    ".md",
    ".rst",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
    ".sh",
    ".bash",
}


def get_workspace_dir() -> pathlib.Path:
    """Deterministically locate the active repository workspace."""
    try:
        f = sys._getframe()
        while f:
            if "_orig_cwd" in f.f_locals:
                p = pathlib.Path(f.f_locals["_orig_cwd"])
                if p.is_dir() and (
                    (p / ".git").exists()
                    or (p / "pyproject.toml").exists()
                    or (p / "setup.py").exists()
                ):
                    return p.resolve()
            f = f.f_back
    except Exception:
        pass

    for env_var in ("SWEGEMMA_WORKSPACE", "WORKSPACE_DIR"):
        val = os.environ.get(env_var)
        if val:
            p = pathlib.Path(val)
            if p.is_dir():
                return p.resolve()

    ws = pathlib.Path("/workspace")
    if ws.is_dir():
        return ws.resolve()

    return pathlib.Path.cwd().resolve()


def clean_search_term(term: str) -> str:
    """Normalize terms without destroying useful symbols."""
    t = term.strip()
    # Strip wrapping quotes if LLM passed '"pattern"' or "'pattern'"
    if len(t) >= 2 and (
        (t.startswith('"') and t.endswith('"'))
        or (t.startswith("'") and t.endswith("'"))
        or (t.startswith("`") and t.endswith("`"))
    ):
        t = t[1:-1].strip()
    return t


def parse_args(args: List[str], ws: pathlib.Path) -> Tuple[List[str], pathlib.Path]:
    """Omnivorous argument parser: handles multiple search terms and optional path target."""
    raw_terms: List[str] = []
    target_path = ws

    for a in args:
        cleaned = clean_search_term(a)
        if not cleaned:
            continue
        # Check if argument is a directory or file in workspace
        cand = ws / cleaned.lstrip("/")
        if cand.exists() and cand != ws:
            target_path = cand
        elif cleaned in (".", "./", "/workspace", "/workspace/"):
            target_path = ws
        else:
            raw_terms.append(cleaned)

    return raw_terms, target_path


def run_git_grep(terms: List[str], target: pathlib.Path, ws: pathlib.Path) -> List[str]:
    """Execute git grep with extended regex and path exclusions."""
    if not (ws / ".git").exists():
        return []

    # Build pattern: if multiple terms, search as OR regex: (term1|term2|term3)
    # Escape metacharacters safely if they look like plain code with parens
    safe_terms = []
    for t in terms:
        # If term has unescaped regex syntax like '(' but not '|', escape it
        if any(c in t for c in "()[]{}?+*") and "|" not in t:
            safe_terms.append(re.escape(t))
        else:
            safe_terms.append(t)

    combined_pattern = "|".join(safe_terms) if len(safe_terms) > 1 else safe_terms[0]

    # Target path relative to workspace
    rel_target = "."
    if target != ws:
        try:
            rel_target = str(target.relative_to(ws))
        except ValueError:
            rel_target = "."

    # Build path exclusions for git grep
    path_args = [rel_target]
    for d in SKIP_DIRS:
        path_args.append(f":(exclude){d}/**")
        path_args.append(f":(exclude)**/{d}/**")
    for ext in SKIP_EXTENSIONS:
        path_args.append(f":(exclude)*{ext}")
        path_args.append(f":(exclude)**/*{ext}")

    # 1. Try extended regex (-E)
    cmd = ["git", "grep", "-n", "-I", "-E", "-e", combined_pattern, "--"] + path_args
    try:
        res = subprocess.run(
            cmd, cwd=ws, capture_output=True, text=True, timeout=10, check=False
        )
        if res.returncode == 0 and res.stdout.strip():
            return [line for line in res.stdout.splitlines() if line.strip()]
    except Exception:
        pass

    # 2. Fallback to fixed-strings (-F) for each term
    all_lines: List[str] = []
    for t in terms:
        cmd_fixed = ["git", "grep", "-n", "-I", "-F", "-e", t, "--"] + path_args
        try:
            res = subprocess.run(
                cmd_fixed, cwd=ws, capture_output=True, text=True, timeout=10, check=False
            )
            if res.returncode == 0 and res.stdout.strip():
                all_lines.extend(res.stdout.splitlines())
        except Exception:
            pass

    return list(dict.fromkeys(all_lines))


def run_python_fallback(terms: List[str], target: pathlib.Path, ws: pathlib.Path) -> List[str]:
    """Pure Python fallback for non-git workspaces with spam filtering."""
    matches: List[str] = []
    root = target if target.is_dir() else ws

    # Compile regexes or literal checkers
    regexes = []
    for t in terms:
        try:
            regexes.append(re.compile(t, re.IGNORECASE))
        except re.error:
            regexes.append(re.compile(re.escape(t), re.IGNORECASE))

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skip dirs in-place
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]

        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in SKIP_EXTENSIONS or ext not in ALLOWED_CODE_EXTENSIONS:
                continue

            full_p = pathlib.Path(dirpath) / fn
            try:
                rel_p = str(full_p.relative_to(ws))
            except ValueError:
                rel_p = str(full_p)

            try:
                with open(full_p, "r", encoding="utf-8", errors="replace") as f:
                    for lineno, line in enumerate(f, start=1):
                        for rx in regexes:
                            if rx.search(line):
                                matches.append(f"{rel_p}:{lineno}:{line.rstrip()}")
                                break
            except Exception:
                continue

            if len(matches) > 300:
                break
        if len(matches) > 300:
            break

    return matches


def score_match(file_path: str, lineno: int, content: str, terms: List[str]) -> int:
    """Calculate relevance score prioritizing core definitions and source code."""
    score = 0
    p_lower = file_path.lower()
    c = content.strip()

    # Prefer python source files
    if file_path.endswith(".py"):
        score += 30
    elif file_path.endswith((".pyi", ".toml")):
        score += 10

    # Demote tests and docs
    if "test" in p_lower:
        score -= 25
    if "doc" in p_lower or file_path.endswith((".md", ".rst")):
        score -= 40
    if "bench" in p_lower or "example" in p_lower:
        score -= 50

    # Boost definitions and calls
    for t in terms:
        t_clean = re.sub(r"[^a-zA-Z0-9_]", "", t)
        if not t_clean:
            continue
        if re.search(rf"\b(def|class)\s+{t_clean}\b", c):
            score += 60
        elif re.search(rf"\b{t_clean}\b", c):
            score += 25
        elif t in c:
            score += 10

    return score


def extract_function_scope(file_path: pathlib.Path, target_line: int) -> Optional[Dict[str, Any]]:
    """Extract enclosing function or class scope including all decorators."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(text, filename=str(file_path))
    except Exception:
        return None

    best_node = None
    best_size = float("inf")

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            # Include decorators in start line
            start = node.lineno
            if node.decorator_list:
                start = min(d.lineno for d in node.decorator_list)
            end = getattr(node, "end_lineno", start + 20)

            if start <= target_line <= end:
                size = end - start
                if size < best_size:
                    best_size = size
                    best_node = (node, start, end)

    if not best_node:
        return None

    node, start, end = best_node
    lines = text.splitlines()[start - 1 : end]
    name = getattr(node, "name", "scope")
    kind = "class" if isinstance(node, ast.ClassDef) else "def"

    return {
        "name": f"{kind} {name}",
        "start_line": start,
        "end_line": end,
        "line_count": len(lines),
        "lines": lines,
    }


def main() -> int:
    try:
        raw_args = sys.argv[1:]
        if not raw_args:
            print("[fast-grep] No search term provided. Usage: run_skill_script('fast-grep', 'grep.py', args=['<term>'])")
            return 0

        ws = get_workspace_dir()
        terms, target = parse_args(raw_args, ws)

        if not terms:
            print("[fast-grep] No valid search terms provided.")
            return 0

        # Execute search: git grep first, then pure Python fallback
        results = run_git_grep(terms, target, ws)
        if not results:
            results = run_python_fallback(terms, target, ws)

        if not results:
            terms_str = ", ".join(repr(t) for t in terms)
            print(f"[fast-grep] 0 matches found for: {terms_str}")
            return 0

        # Parse and rank
        parsed = []
        for r in results:
            parts = r.split(":", 2)
            if len(parts) >= 2 and parts[1].isdigit():
                fp = parts[0]
                lineno = int(parts[1])
                content = parts[2] if len(parts) > 2 else ""
                sc = score_match(fp, lineno, content, terms)
                parsed.append({"file": fp, "lineno": lineno, "content": content, "score": sc})

        parsed.sort(key=lambda m: m["score"], reverse=True)

        # Extract top 3 unique function scopes
        flashed: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
        seen = set()
        for m in parsed:
            p = ws / m["file"]
            if not p.suffix == ".py" or not p.exists():
                continue
            scope = extract_function_scope(p, m["lineno"])
            if scope:
                key = (m["file"], scope["name"])
                if key not in seen:
                    seen.add(key)
                    flashed.append((m, scope))
                    if len(flashed) >= 3:
                        break

        # Output results concisely (capped under ADK 5000 char limit)
        terms_display = " | ".join(terms)
        print(f"[fast-grep] Search: '{terms_display}' ({len(parsed)} matches, top {len(flashed)} scopes flashed):\n")

        for idx, (m, sc) in enumerate(flashed, start=1):
            fp = m["file"]
            qname = sc["name"]
            s_line = sc["start_line"]
            e_line = sc["end_line"]
            lines = sc["lines"]
            total = len(lines)

            print("=" * 80)
            print(f"⭐ TOP {idx} [Score {m['score']:+d}]: {fp}:{m['lineno']} in {qname} (lines {s_line}-{e_line})")
            print("=" * 80)

            # Cap function lines safely
            if total > 50:
                for i, l in enumerate(lines[:35], start=s_line):
                    print(f"{i:4d}: {l}")
                print(f"      ... [{total - 45} lines omitted in large scope] ...")
                for i, l in enumerate(lines[-10:], start=e_line - 9):
                    print(f"{i:4d}: {l}")
            else:
                for i, l in enumerate(lines, start=s_line):
                    print(f"{i:4d}: {l}")
            print()

        # Summary of other ranked matches
        print("-" * 80)
        print("📋 TOP MATCH PREVIEWS:")
        for m in parsed[:15]:
            snippet = m["content"].strip()[:80]
            print(f"  [{m['score']:+3d}] {m['file']}:{m['lineno']}: {snippet}")

        if len(parsed) > 15:
            print(f"  ... ({len(parsed) - 15} additional matches truncated)")

        return 0
    except Exception as e:
        print(f"[fast-grep] Search completed with fallback: {e}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
