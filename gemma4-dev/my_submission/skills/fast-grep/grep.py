#!/usr/bin/env python3
"""fast-grep: Omnivorous, AST-Aware Search Engine for Autonomous Agents.

Eats ANY input format:
- Single terms, multiple terms (searched as OR/union)
- Unescaped regex or literal code snippets
- Dotted symbols, function calls, or raw keywords
- Automatically skips benchmarks, lockfiles, docs, and non-code spam
- Flashes top 3 enclosing functions with complete decorators via AST
- Boosts common string/buffer transformation methods & verbs
- Highlights call-sites and enclosing scopes where strings/buffers are transformed
- Automatically expands terse issue keywords to candidate string operations
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

# String transformation methods and verbs commonly involved in terse issues
STRING_TRANSFORM_VERBS: Set[str] = {
    "splitlines",
    "split",
    "rstrip",
    "strip",
    "lstrip",
    "replace",
    "join",
    "partition",
    "rpartition",
    "decode",
    "encode",
    "from_ansi",
}

# Heuristic expansion for terse issue keywords to prevent flooding by doc/comment matches
TERSE_ISSUE_EXPANSIONS: Dict[str, List[str]] = {
    "newline": ["splitlines", "rstrip", "strip", "replace"],
    "newlines": ["splitlines", "rstrip", "strip", "replace"],
    "whitespace": ["strip", "lstrip", "rstrip", "split", "replace"],
    "indent": ["strip", "lstrip", "replace", "splitlines"],
    "indentation": ["strip", "lstrip", "replace", "splitlines"],
    "encoding": ["decode", "encode", "utf-8"],
    "decoding": ["decode", "encode", "utf-8"],
}

_AST_CACHE: Dict[str, Tuple[Optional[ast.AST], List[str]]] = {}


def get_ast_and_lines(full_path: pathlib.Path) -> Tuple[Optional[ast.AST], List[str]]:
    """Parse and cache AST and source lines for a python file."""
    key = str(full_path.resolve())
    if key in _AST_CACHE:
        return _AST_CACHE[key]
    try:
        text = full_path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        tree = ast.parse(text, filename=key)
        _AST_CACHE[key] = (tree, lines)
        return (tree, lines)
    except Exception:
        _AST_CACHE[key] = (None, [])
        return (None, [])


def find_enclosing_node(tree: Optional[ast.AST], target_line: int) -> Optional[Any]:
    """Find innermost function or class enclosing target_line."""
    if not tree:
        return None
    best_node = None
    best_span = float("inf")
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            s = getattr(node, "lineno", None)
            e = getattr(node, "end_lineno", None)
            if s is not None and e is not None and s <= target_line <= e:
                span = e - s
                if span < best_span:
                    best_span = span
                    best_node = node
    return best_node


def is_string_transform_line(content: str) -> bool:
    """Detect if content is an active call-site or statement transforming strings/buffers."""
    c = content
    # Direct method call to a string transform verb (.splitlines(, .decode(, etc.)
    if re.search(
        r"\.\s*(splitlines|split|rstrip|strip|lstrip|replace|join|partition|rpartition|decode|encode|from_ansi)\s*\(",
        c,
        re.IGNORECASE,
    ):
        return True
    # Method called on common buffer/text receiver
    if re.search(
        r"\b(text|line|lines|terminal_text|buffer|output|input|data|content|string|val|raw|payload|chunk|stream|body|msg)\w*\s*\.\s*(splitlines|split|rstrip|strip|lstrip|replace|join|partition|rpartition|decode|encode|from_ansi)\b",
        c,
        re.IGNORECASE,
    ):
        return True
    # re operations (re.split, re.sub)
    if re.search(r"\bre\.(split|sub|finditer|findall)\s*\(", c):
        return True
    return False


def is_string_transform_scope(scope_name: str, lines: List[str]) -> bool:
    """Detect if enclosing function or class is dedicated to string/buffer manipulation."""
    s_lower = scope_name.lower()
    if any(v in s_lower for v in STRING_TRANSFORM_VERBS):
        return True
    if any(w in s_lower for w in ("ansi", "text", "buffer", "decode", "encode", "line", "codec")):
        return True
    for l in lines:
        if is_string_transform_line(l):
            return True
    return False


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
    t = term.strip().strip("'\"")
    return t


def parse_args(args: List[str], ws: pathlib.Path) -> Tuple[List[str], pathlib.Path]:
    """Extract search terms and optional search directory/file."""
    target_path = ws
    raw_terms: List[str] = []

    for a in args:
        cleaned = clean_search_term(a)
        if not cleaned:
            continue
        # Check if argument is a directory or file in workspace or direct absolute path
        cand = ws / cleaned.lstrip("/")
        cand_direct = pathlib.Path(cleaned).resolve()
        if cand.exists() and cand != ws:
            target_path = cand
        elif cand_direct.exists() and cand_direct.is_dir() and cand_direct != ws:
            target_path = cand_direct
        elif cleaned in (".", "./", "/workspace", "/workspace/"):
            target_path = ws
        else:
            raw_terms.append(cleaned)

    return raw_terms, target_path


def run_git_grep(terms: List[str], target: pathlib.Path, ws: pathlib.Path) -> List[str]:
    """Execute git grep with extended regex and path exclusions."""
    if not (ws / ".git").exists():
        return python_walk_fallback(terms, target, ws)

    # Build pattern: if multiple terms, search as OR regex: (term1|term2|term3)
    safe_terms = []
    for t in terms:
        # If term has spaces or special regex chars, escape or wrap
        if re.search(r"[()\[\]{}*+?|^$\\.]", t):
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

    if all_lines:
        # Deduplicate preserving order
        seen = set()
        deduped = []
        for l in all_lines:
            if l not in seen:
                seen.add(l)
                deduped.append(l)
        return deduped

    # 3. Fallback to python walk if git grep failed or was empty
    return python_walk_fallback(terms, target, ws)


def python_walk_fallback(terms: List[str], target: pathlib.Path, ws: pathlib.Path) -> List[str]:
    """Pure Python fallback for non-git directories or environments."""
    matches: List[str] = []
    root = target if target.is_dir() else target.parent
    compiled = []
    for t in terms:
        try:
            compiled.append(re.compile(t, re.IGNORECASE))
        except re.error:
            compiled.append(re.compile(re.escape(t), re.IGNORECASE))

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in SKIP_EXTENSIONS or (ALLOWED_CODE_EXTENSIONS and ext not in ALLOWED_CODE_EXTENSIONS):
                continue

            full_p = pathlib.Path(dirpath) / fn
            try:
                rel_p = str(full_p.relative_to(ws))
            except ValueError:
                rel_p = str(full_p)

            try:
                with open(full_p, "r", encoding="utf-8", errors="replace") as f:
                    for lineno, line in enumerate(f, start=1):
                        for pattern in compiled:
                            if pattern.search(line):
                                matches.append(f"{rel_p}:{lineno}:{line.rstrip()}")
                                break
                        if len(matches) > 300:
                            break
            except Exception:
                continue
            if len(matches) > 300:
                break
        if len(matches) > 300:
            break

    return matches


def score_match(
    file_path: str,
    lineno: int,
    content: str,
    terms: List[str],
    scope_name: str = "",
) -> int:
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
        score -= 40
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

    # Boost scores for common string transformation methods and verbs
    # (splitlines, split, rstrip, strip, replace, join, partition, decode, from_ansi)
    verb_call = re.search(
        r"\.\s*(splitlines|split|rstrip|strip|lstrip|replace|join|partition|rpartition|decode|encode|from_ansi)\s*\(",
        c,
        re.IGNORECASE,
    )
    if verb_call:
        score += 40
        called_verb = verb_call.group(1).lower()
        if any(re.sub(r"[^a-zA-Z0-9_]", "", t).lower() == called_verb for t in terms):
            score += 15

    # Buffer/text receiver transformation
    # e.g., terminal_text.splitlines(), text.splitlines(), line.rstrip()
    if re.search(
        r"\b(text|line|lines|terminal_text|buffer|output|input|data|content|string|val|raw|payload|chunk|stream|body|msg)\w*\s*\.\s*(splitlines|split|rstrip|strip|lstrip|replace|join|partition|rpartition|decode|encode|from_ansi)\b",
        c,
        re.IGNORECASE,
    ):
        score += 30

    # Streaming/iteration or line generator patterns
    # e.g., for line in terminal_text.splitlines():, yield decode_line(line)
    if re.search(r"for\s+\w+\s+in\s+.*(splitlines|split|partition)", c) or "yield" in c:
        score += 20

    # Demote assertion-only and length inspection lines
    if re.search(r"\b(len|assert)\s*\(", c):
        score -= 25

    # Boost string/text-processing modules
    if re.search(
        r"(\b|_)(ansi|text|codec|decode|encode|string|parser|format|stream)(\b|\.py)",
        file_path,
        re.IGNORECASE,
    ):
        score += 25

    # Scope boost if enclosing function/class transforms strings/buffers
    if scope_name:
        scope_lower = scope_name.lower()
        if any(v in scope_lower for v in STRING_TRANSFORM_VERBS):
            score += 40
        elif any(w in scope_lower for w in ("ansi", "text", "buffer", "decode", "encode", "line", "codec")):
            score += 15

    return score


def extract_function_scope(file_path: pathlib.Path, target_line: int) -> Optional[Dict[str, Any]]:
    """Extract enclosing function or class scope including all decorators."""
    tree, lines = get_ast_and_lines(file_path)
    if not tree or not lines:
        return None

    target_node = find_enclosing_node(tree, target_line)
    if not target_node:
        return None

    # Determine start line including decorators
    start = target_node.lineno
    if getattr(target_node, "decorator_list", None):
        start = min(d.lineno for d in target_node.decorator_list)

    end = getattr(target_node, "end_lineno", start + 20)
    scope_lines = lines[start - 1 : end]

    kind = "def" if isinstance(target_node, (ast.FunctionDef, ast.AsyncFunctionDef)) else "class"
    raw_name = target_node.name
    scope_name = f"{kind} {raw_name}"

    is_transform = is_string_transform_scope(scope_name, scope_lines)

    return {
        "name": scope_name,
        "raw_name": raw_name,
        "kind": kind,
        "start_line": start,
        "end_line": end,
        "line_count": len(scope_lines),
        "lines": scope_lines,
        "is_transform": is_transform,
    }


def main() -> int:
    try:
        raw_args = sys.argv[1:]
        if not raw_args:
            print("[fast-grep] No search term provided. Usage: run_skill_script('fast-grep', 'grep.py', args=['<term>'])")
            return 0

        ws = get_workspace_dir()
        terms, target = parse_args(raw_args, ws)
        # If target has .git and ws did not, align ws to target
        if target.is_dir() and (target / ".git").exists() and not (ws / ".git").exists():
            ws = target

        if not terms:
            print("[fast-grep] No valid search terms provided.")
            return 0

        # Heuristic expansion for terse issue keywords
        expanded_terms = list(terms)
        expansion_notes = []
        for t in terms:
            t_key = t.lower()
            if t_key in TERSE_ISSUE_EXPANSIONS:
                verbs = [v for v in TERSE_ISSUE_EXPANSIONS[t_key] if v not in expanded_terms]
                if verbs:
                    expanded_terms.extend(verbs)
                    expansion_notes.append(f"'{t}' -> {', '.join(verbs)}")

        if expansion_notes:
            print(f"[fast-grep] 💡 Terse issue heuristic expanded: {'; '.join(expansion_notes)}")

        # Run git grep with extended regex
        results = run_git_grep(expanded_terms, target, ws)

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

                # Look up enclosing scope name for scoring if python file
                scope_name = ""
                full_p = ws / fp
                if full_p.suffix == ".py" and full_p.exists():
                    tree, _ = get_ast_and_lines(full_p)
                    node = find_enclosing_node(tree, lineno)
                    if node:
                        scope_name = node.name

                sc = score_match(fp, lineno, content, expanded_terms, scope_name=scope_name)
                is_call_site = is_string_transform_line(content)
                parsed.append({
                    "file": fp,
                    "lineno": lineno,
                    "content": content,
                    "score": sc,
                    "scope_name": scope_name,
                    "is_call_site": is_call_site,
                })

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
            s_name = sc["name"]
            s_line = sc["start_line"]
            e_line = sc["end_line"]
            lines = sc["lines"]
            target_lineno = m["lineno"]
            is_call_site = m.get("is_call_site", False)
            is_transform_scope = sc.get("is_transform", False)

            scope_tag = ""
            if is_transform_scope and is_call_site:
                scope_tag = " [⚡ STRING/BUFFER CALL-SITE & TRANSFORM SCOPE]"
            elif is_call_site:
                scope_tag = " [⚡ STRING/BUFFER CALL-SITE]"
            elif is_transform_scope:
                scope_tag = " [⚡ STRING/BUFFER TRANSFORM SCOPE]"

            header = f"⭐ TOP {idx} [Score {m['score']:+d}]: {fp}:{target_lineno} in {s_name} (lines {s_line}-{e_line}){scope_tag}"
            print("=" * 80)
            print(header)
            print("=" * 80)

            def format_line(lineno: int, text: str) -> str:
                if lineno == target_lineno:
                    callout = "  <-- [CALL-SITE: string/buffer transform]" if is_call_site else "  <-- [MATCH]"
                    return f"{lineno:4d}: >>> {text}{callout}"
                return f"{lineno:4d}:     {text}"

            # Middle-fold if over 100 lines
            if len(lines) > 100:
                head = lines[:40]
                tail = lines[-40:]
                for i, l in enumerate(head, start=s_line):
                    print(format_line(i, l))
                print(f" ... [{len(lines) - 80} lines folded for context budget] ...")
                for i, l in enumerate(tail, start=s_line + len(lines) - 40):
                    print(format_line(i, l))
            else:
                for i, l in enumerate(lines, start=s_line):
                    print(format_line(i, l))
            print()

        # Summary of other ranked matches
        print("-" * 80)
        print("📋 TOP MATCH PREVIEWS:")
        for m in parsed[:15]:
            snippet = m["content"].strip()[:75]
            site_tag = " [CALL-SITE]" if m.get("is_call_site") else ""
            print(f"  [{m['score']:+3d}] {m['file']}:{m['lineno']}{site_tag}: {snippet}")

        if len(parsed) > 15:
            print(f"  ... ({len(parsed) - 15} additional matches truncated)")

        return 0
    except Exception as e:
        print(f"[fast-grep] Search completed with fallback: {e}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
