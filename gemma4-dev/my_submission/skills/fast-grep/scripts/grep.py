#!/usr/bin/env python3
"""fast-grep: Omnivorous, AST-Aware Search Engine for Autonomous Agents.

Eats ANY input format:
- Single terms, multiple terms (searched as OR/union)
- Unescaped regex or literal code snippets
- Dotted symbols, function calls, or raw keywords
- Automatically skips benchmarks, lockfiles, docs, and non-code spam
- Deterministically explains zero matches with file count and case-insensitive check
- Suggests candidate symbols from AST and repository identifiers via fuzzy matching
- Explains regex syntax errors in plain English and suggests escaped patterns
- 100% Pydantic v2 structured schemas (FastGrepResult, MatchExplanation, FuzzySuggestion, etc.)
- Flashes top 3 enclosing functions with complete decorators via AST
- Boosts common string/buffer transformation methods & verbs
- Highlights call-sites and enclosing scopes where strings/buffers are transformed
- Automatically expands terse issue keywords to candidate string operations
- Always exits 0 and never crashes.
"""

from __future__ import annotations

import ast
import difflib
import os
import pathlib
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

sys.dont_write_bytecode = True

from pydantic import BaseModel, ConfigDict, Field

# ==============================================================================
# Pydantic v2 Output & Diagnostic Schemas
# ==============================================================================


class MatchExplanation(BaseModel):
    """Deterministic explanation for search outcome."""

    model_config = ConfigDict(extra="ignore")

    status: str = Field(
        ...,
        description="Outcome status: MATCHES_FOUND, ZERO_MATCHES, or REGEX_ERROR",
    )
    summary: str = Field(
        ..., description="Human-readable summary of search result"
    )
    case_sensitive: bool = Field(
        default=True, description="Whether search was case-sensitive"
    )
    case_insensitive_count: int = Field(
        default=0, description="Count of matches found ignoring case"
    )
    details: Optional[str] = Field(
        default=None, description="Additional context or diagnostics"
    )


class FuzzySuggestion(BaseModel):
    """AST / repository identifier fuzzy candidate suggestion."""

    model_config = ConfigDict(extra="ignore")

    query: str = Field(..., description="Original query term")
    symbol: str = Field(..., description="Candidate symbol identifier")
    similarity: float = Field(
        ..., description="Fuzzy match similarity score (0.0 to 1.0)"
    )
    kind: Optional[str] = Field(
        default="identifier",
        description="Symbol kind: function, class, variable, identifier",
    )
    source_file: Optional[str] = Field(
        default=None,
        description="Workspace-relative file path containing symbol",
    )


class RegexErrorDiagnostic(BaseModel):
    """Diagnostic detail for invalid regular expression pattern."""

    model_config = ConfigDict(extra="ignore")

    raw_pattern: str = Field(..., description="Raw invalid pattern string")
    error_message: str = Field(..., description="Underlying re.error message")
    position: Optional[int] = Field(
        default=None, description="Error position character offset"
    )
    plain_english_explanation: str = Field(
        ..., description="Plain-English explanation of syntax issue"
    )
    suggested_escaped_regex: str = Field(
        ..., description="Safe, properly escaped regex pattern"
    )


class CaseInsensitiveMatch(BaseModel):
    """Match line discovered when ignoring character casing."""

    model_config = ConfigDict(extra="ignore")

    file: str = Field(..., description="Workspace-relative file path")
    lineno: int = Field(..., description="1-based line number")
    content: str = Field(..., description="Matching line content preview")


class GrepMatch(BaseModel):
    """Individual ranked match line."""

    model_config = ConfigDict(extra="ignore")

    file: str = Field(..., description="Workspace-relative file path")
    lineno: int = Field(..., description="1-based line number")
    content: str = Field(..., description="Matching line content")
    score: int = Field(default=0, description="Relevance ranking score")
    is_call_site: bool = Field(
        default=False, description="Whether line is an active transform call-site"
    )
    scope_name: Optional[str] = Field(
        default=None, description="Enclosing function or class name"
    )


class ASTNodePreview(BaseModel):
    """Top-ranked enclosing AST function or class preview."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(
        ..., description="Scope display name (e.g. def foo, class Bar)"
    )
    kind: str = Field(..., description="Scope type: def or class")
    file: str = Field(..., description="Workspace-relative file path")
    start_line: int = Field(..., description="Starting line number")
    end_line: int = Field(..., description="Ending line number")
    score: int = Field(
        default=0, description="Match score associated with scope"
    )
    code_snippet: str = Field(
        ..., description="Complete or folded source code snippet"
    )


class FastGrepResult(BaseModel):
    """Top-level structured result returned by fast-grep."""

    model_config = ConfigDict(extra="ignore")

    query_terms: List[str] = Field(
        default_factory=list, description="Original query search terms"
    )
    target_path: str = Field(
        ..., description="Target search directory or file path"
    )
    total_files_scanned: int = Field(
        default=0, description="Count of files scanned in target"
    )
    total_matches: int = Field(
        default=0, description="Total matching lines found"
    )
    explanation: MatchExplanation = Field(
        ..., description="Match explanation and diagnostic summary"
    )
    regex_diagnostics: List[RegexErrorDiagnostic] = Field(
        default_factory=list, description="Regex syntax diagnostics"
    )
    case_insensitive_matches: List[CaseInsensitiveMatch] = Field(
        default_factory=list, description="Matches found ignoring case"
    )
    fuzzy_suggestions: List[FuzzySuggestion] = Field(
        default_factory=list, description="Candidate symbol suggestions"
    )
    ranked_matches: List[GrepMatch] = Field(
        default_factory=list, description="Ranked match items"
    )
    top_ast_nodes: List[ASTNodePreview] = Field(
        default_factory=list, description="Top AST scope previews"
    )


# ==============================================================================
# Constants & Heuristics
# ==============================================================================

SKIP_DIRS: Set[str] = {
    "__pycache__",
    "node_modules",
    ".git",
    ".venv",
    "venv",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "build",
    "dist",
    "wheels",
    "snapshots",
    "benchmarks",
    "benchmark",
    "results",
    "docs",
    "doc",
    "htmlcov",
    "site-packages",
}

SKIP_EXTENSIONS: Set[str] = {
    ".lock",
    ".bin",
    ".tar",
    ".gz",
    ".zip",
    ".png",
    ".jpg",
    ".jpeg",
    ".svg",
    ".ico",
    ".pyc",
    ".whl",
    ".json",
    ".csv",
    ".log",
    ".xml",
    ".txt",
    ".yaml",
    ".yml",
    ".md",
    ".rst",
}

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

PYTHON_KEYWORDS: Set[str] = {
    "False",
    "None",
    "True",
    "and",
    "as",
    "assert",
    "async",
    "await",
    "break",
    "class",
    "continue",
    "def",
    "del",
    "elif",
    "else",
    "except",
    "finally",
    "for",
    "from",
    "global",
    "if",
    "import",
    "in",
    "is",
    "lambda",
    "nonlocal",
    "not",
    "or",
    "pass",
    "raise",
    "return",
    "try",
    "while",
    "with",
    "yield",
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


# ==============================================================================
# AST & Scope Inspection Helpers
# ==============================================================================


def get_ast_and_lines(
    full_path: pathlib.Path,
) -> Tuple[Optional[ast.AST], List[str]]:
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


def find_enclosing_node(
    tree: Optional[ast.AST], target_line: int
) -> Optional[Any]:
    """Find innermost function or class enclosing target_line."""
    if not tree:
        return None
    best_node = None
    best_span = float("inf")
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
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
    if re.search(
        r"\.\s*(splitlines|split|rstrip|strip|lstrip|replace|join|partition|rpartition|decode|encode|from_ansi)\s*\(",
        c,
        re.IGNORECASE,
    ):
        return True
    if re.search(
        r"\b(text|line|lines|terminal_text|buffer|output|input|data|content|string|val|raw|payload|chunk|stream|body|msg)\w*\s*\.\s*(splitlines|split|rstrip|strip|lstrip|replace|join|partition|rpartition|decode|encode|from_ansi)\b",
        c,
        re.IGNORECASE,
    ):
        return True
    if re.search(r"\bre\.(split|sub|finditer|findall)\s*\(", c):
        return True
    return False


def is_string_transform_scope(scope_name: str, lines: List[str]) -> bool:
    """Detect if enclosing function or class is dedicated to string/buffer manipulation."""
    s_lower = scope_name.lower()
    if any(v in s_lower for v in STRING_TRANSFORM_VERBS):
        return True
    if any(
        w in s_lower
        for w in ("ansi", "text", "buffer", "decode", "encode", "line", "codec")
    ):
        return True
    for line in lines:
        if is_string_transform_line(line):
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

    for env_var in ("SWEGEMMA_WORKSPACE", "WORKSPACE_DIR", "WORKSPACE"):
        val = os.environ.get(env_var)
        if val:
            p = pathlib.Path(val)
            if p.is_dir():
                return p.resolve()

    ws = pathlib.Path("/workspace")
    if ws.is_dir():
        return ws.resolve()

    return pathlib.Path.cwd().resolve()


def clean_search_term(raw: str) -> str:
    """Normalize terms without destroying useful symbols."""
    cleaned = raw.strip()
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (
        cleaned.startswith("'") and cleaned.endswith("'")
    ):
        cleaned = cleaned[1:-1].strip()
    if cleaned.startswith("`") and cleaned.endswith("`"):
        cleaned = cleaned[1:-1].strip()
    return cleaned


def parse_args(
    args: List[str], ws: pathlib.Path
) -> Tuple[List[str], pathlib.Path, bool, bool]:
    """Extract search terms, target directory/file, and flags."""
    target_path = ws
    raw_terms: List[str] = []
    is_json = False
    is_help = False

    for a in args:
        cleaned = clean_search_term(a)
        if not cleaned:
            continue
        if cleaned in ("--help", "-h"):
            is_help = True
            continue
        if cleaned == "--json":
            is_json = True
            continue

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

    return raw_terms, target_path, is_json, is_help


# ==============================================================================
# Regex Diagnostics & Symbol Extraction
# ==============================================================================


def escape_regex_metachars(pattern: str) -> str:
    """Escape regex special characters while preserving readable spaces and alphanumeric words."""
    return re.sub(r"([()\[\]{}*+?|^$\\.])", r"\\\1", pattern)


def check_regex_syntax(pattern: str) -> Optional[RegexErrorDiagnostic]:
    """Validate regex pattern and produce plain-English diagnostic if invalid."""
    try:
        re.compile(pattern)
        return None
    except re.error as e:
        msg = str(e)
        pos = getattr(e, "pos", None)
        msg_lower = msg.lower()

        if (
            "missing ), unterminated subpattern" in msg_lower
            or "unbalanced parenthesis" in msg_lower
        ):
            plain_english = (
                f"Unclosed or unescaped opening parenthesis '(' at position {pos if pos is not None else 'unknown'}. "
                "In regular expressions, '(' defines a capture group. To match a literal '(', escape it as '\\('."
            )
        elif "missing (" in msg_lower or "unmatched )" in msg_lower:
            plain_english = (
                f"Unmatched closing parenthesis ')' at position {pos if pos is not None else 'unknown'}. "
                "To match a literal ')', escape it as '\\)'."
            )
        elif (
            "unterminated character set" in msg_lower
            or "missing ]" in msg_lower
        ):
            plain_english = (
                f"Unclosed or unescaped character set bracket '[' at position {pos if pos is not None else 'unknown'}. "
                "In regular expressions, '[' starts a character class. To match a literal '[', escape it as '\\['."
            )
        elif "missing [" in msg_lower or "unmatched ]" in msg_lower:
            plain_english = (
                f"Unmatched closing bracket ']' at position {pos if pos is not None else 'unknown'}. "
                "To match a literal ']', escape it as '\\]'."
            )
        elif "nothing to repeat" in msg_lower:
            plain_english = (
                f"Dangling quantifier (*, +, ?, or {{}}) at position {pos if pos is not None else 'unknown'} "
                "without a preceding character or token to repeat. To match literal quantifier symbols, escape them with '\\'."
            )
        elif "multiple repeat" in msg_lower:
            plain_english = (
                f"Consecutive or nested repeat operators at position {pos if pos is not None else 'unknown'}. "
                "Quantifiers cannot be directly chained. To match literal symbols, escape them with '\\'."
            )
        elif "bad escape" in msg_lower or "incomplete escape" in msg_lower:
            plain_english = (
                f"Invalid or incomplete escape sequence at position {pos if pos is not None else 'unknown'}. "
                "Ensure backslashes are properly paired or escape literal backslashes as '\\\\'."
            )
        elif "bad character range" in msg_lower:
            plain_english = (
                f"Invalid character range in brackets at position {pos if pos is not None else 'unknown'} (e.g. [z-a]). "
                "The range start must have an ASCII/Unicode code point less than or equal to the end."
            )
        else:
            plain_english = (
                f"Regular expression syntax error ({msg}) at position {pos if pos is not None else 'unknown'}. "
                "Check pattern syntax or escape special characters with '\\'."
            )

        suggested = escape_regex_metachars(pattern)
        return RegexErrorDiagnostic(
            raw_pattern=pattern,
            error_message=msg,
            position=pos,
            plain_english_explanation=plain_english,
            suggested_escaped_regex=suggested,
        )


def count_files_in_target(target: pathlib.Path, ws: pathlib.Path) -> int:
    """Accurately count searchable files in target directory."""
    if (ws / ".git").exists():
        try:
            rel = "."
            if target != ws:
                try:
                    rel = str(target.relative_to(ws))
                except ValueError:
                    rel = str(target)
            res = subprocess.run(
                ["git", "ls-files", rel],
                cwd=ws,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if res.returncode == 0:
                files = [f for f in res.stdout.splitlines() if f.strip()]
                if files:
                    return len(files)
        except Exception:
            pass

    count = 0
    try:
        for root, dirs, files in os.walk(target):
            dirs[:] = [
                d
                for d in dirs
                if d not in SKIP_DIRS and not d.startswith(".")
            ]
            count += len(
                [
                    f
                    for f in files
                    if not any(f.endswith(ext) for ext in SKIP_EXTENSIONS)
                ]
            )
    except Exception:
        pass
    return max(count, 1)


def extract_candidate_symbols(
    target: pathlib.Path, ws: pathlib.Path, max_files: int = 150
) -> Dict[str, Tuple[str, str]]:
    """Extract symbol names and kinds from AST and source code in the repository.

    Returns:
        Dict mapping symbol_name -> (kind, relative_file_path)
    """
    symbols: Dict[str, Tuple[str, str]] = {}
    search_root = target if target.is_dir() else ws
    scanned_files = 0

    try:
        for root, dirs, files in os.walk(search_root):
            dirs[:] = [
                d
                for d in dirs
                if d not in SKIP_DIRS
                and not d.startswith(".")
                and "test" not in d.lower()
                and "doc" not in d.lower()
            ]
            for f in files:
                if not f.endswith(".py"):
                    continue
                scanned_files += 1
                if scanned_files > max_files:
                    break
                full_p = pathlib.Path(root) / f
                try:
                    rel_p = str(full_p.relative_to(ws))
                except ValueError:
                    rel_p = str(full_p)

                tree, lines = get_ast_and_lines(full_p)
                if tree:
                    for node in ast.walk(tree):
                        if isinstance(
                            node, (ast.FunctionDef, ast.AsyncFunctionDef)
                        ):
                            if node.name not in symbols:
                                symbols[node.name] = ("function", rel_p)
                        elif isinstance(node, ast.ClassDef):
                            if node.name not in symbols:
                                symbols[node.name] = ("class", rel_p)
                        elif isinstance(node, ast.Name) and isinstance(
                            node.ctx, ast.Store
                        ):
                            if (
                                node.id not in symbols
                                and node.id not in PYTHON_KEYWORDS
                                and len(node.id) > 2
                            ):
                                symbols[node.id] = ("variable", rel_p)

                # Extract common identifiers from lines
                for line in lines[:300]:
                    tokens = re.findall(
                        r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b", line
                    )
                    for tok in tokens:
                        if tok not in symbols and tok not in PYTHON_KEYWORDS:
                            symbols[tok] = ("identifier", rel_p)

            if scanned_files > max_files:
                break
    except Exception:
        pass

    return symbols


def get_fuzzy_suggestions(
    query_terms: List[str],
    candidate_symbols: Dict[str, Tuple[str, str]],
    top_n: int = 5,
    cutoff: float = 0.40,
) -> List[FuzzySuggestion]:
    """Find closest matching candidate symbols via fuzzy ratio matching."""
    scored: List[Tuple[float, str, str, str, str]] = []
    seen: Set[str] = set()

    for term in query_terms:
        # Extract meaningful identifiers from the term
        words = [
            w
            for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", term)
            if len(w) > 2 and w.lower() not in PYTHON_KEYWORDS
        ]

        for cand, (kind, fpath) in candidate_symbols.items():
            s1 = difflib.SequenceMatcher(None, term, cand).ratio()
            s2 = difflib.SequenceMatcher(
                None, term.lower(), cand.lower()
            ).ratio()
            best = max(s1, s2 * 0.95)

            for w in words:
                w1 = difflib.SequenceMatcher(None, w, cand).ratio()
                w2 = difflib.SequenceMatcher(
                    None, w.lower(), cand.lower()
                ).ratio()
                best = max(best, w1, w2 * 0.95)

            if best >= cutoff:
                scored.append((best, cand, kind, fpath, term))

    scored.sort(key=lambda x: x[0], reverse=True)

    results: List[FuzzySuggestion] = []
    for best, cand, kind, fpath, term in scored:
        if cand not in seen:
            seen.add(cand)
            results.append(
                FuzzySuggestion(
                    query=term,
                    symbol=cand,
                    similarity=round(best, 3),
                    kind=kind,
                    source_file=fpath,
                )
            )
            if len(results) >= top_n:
                break

    return results


# ==============================================================================
# Search Execution & Scoring
# ==============================================================================


def run_git_grep(
    terms: List[str],
    target: pathlib.Path,
    ws: pathlib.Path,
    case_insensitive: bool = False,
) -> List[str]:
    """Execute git grep with extended regex and path exclusions."""
    if not (ws / ".git").exists():
        return python_walk_fallback(
            terms, target, ws, case_insensitive=case_insensitive
        )

    safe_terms = []
    for t in terms:
        if re.search(r"[()\[\]{}*+?|^$\\.]", t):
            safe_terms.append(re.escape(t))
        else:
            safe_terms.append(t)

    combined_pattern = (
        "|".join(safe_terms) if len(safe_terms) > 1 else safe_terms[0]
    )

    rel_target = "."
    if target != ws:
        try:
            rel_target = str(target.relative_to(ws))
        except ValueError:
            rel_target = "."

    path_args = [rel_target]
    for d in SKIP_DIRS:
        path_args.append(f":(exclude){d}/**")
        path_args.append(f":(exclude)**/{d}/**")
    for ext in SKIP_EXTENSIONS:
        path_args.append(f":(exclude)*{ext}")
        path_args.append(f":(exclude)**/*{ext}")

    # 1. Try extended regex (-E)
    cmd = ["git", "grep", "-n", "-I"]
    if case_insensitive:
        cmd.append("-i")
    cmd.extend(["-E", "-e", combined_pattern, "--"] + path_args)

    try:
        res = subprocess.run(
            cmd,
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return [line for line in res.stdout.splitlines() if line.strip()]
    except Exception:
        pass

    # 2. Fallback to fixed-strings (-F) for each term
    all_lines: List[str] = []
    for t in terms:
        cmd_fixed = ["git", "grep", "-n", "-I"]
        if case_insensitive:
            cmd_fixed.append("-i")
        cmd_fixed.extend(["-F", "-e", t, "--"] + path_args)
        try:
            res = subprocess.run(
                cmd_fixed,
                cwd=ws,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                for line in res.stdout.splitlines():
                    if line.strip() and line not in all_lines:
                        all_lines.append(line)
        except Exception:
            pass

    if all_lines:
        return all_lines

    # 3. Fallback to python walk if git grep failed or was empty
    return python_walk_fallback(
        terms, target, ws, case_insensitive=case_insensitive
    )


def python_walk_fallback(
    terms: List[str],
    target: pathlib.Path,
    ws: pathlib.Path,
    case_insensitive: bool = False,
) -> List[str]:
    """Pure-python fallback scanner when git grep is unavailable."""
    matches: List[str] = []
    flags = re.IGNORECASE if case_insensitive else 0
    compiled: List[re.Pattern] = []
    for t in terms:
        try:
            compiled.append(re.compile(t, flags))
        except re.error:
            compiled.append(re.compile(re.escape(t), flags))

    search_root = target if target.is_dir() else ws

    for root, dirs, files in os.walk(search_root):
        dirs[:] = [
            d
            for d in dirs
            if d not in SKIP_DIRS and not d.startswith(".")
        ]
        for f in sorted(files):
            if any(f.endswith(ext) for ext in SKIP_EXTENSIONS):
                continue
            full_p = pathlib.Path(root) / f
            try:
                rel_p = str(full_p.relative_to(ws))
            except ValueError:
                rel_p = str(full_p)

            try:
                with open(full_p, "r", encoding="utf-8", errors="replace") as fh:
                    for lineno, line in enumerate(fh, start=1):
                        for pattern in compiled:
                            if pattern.search(line):
                                matches.append(
                                    f"{rel_p}:{lineno}:{line.rstrip()}"
                                )
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
    if re.search(r"^\s*(def|class|async\s+def)\s+", content):
        score += 50
    elif re.search(r"\b(def|class)\b", content):
        score += 30

    if "=" in content and not content.strip().startswith("#"):
        score += 10

    # String & Buffer transform verb boosting
    if is_string_transform_line(content):
        score += 40

    # High-relevance call-site patterns
    if re.search(
        r"\b\w+\.(splitlines|split|rstrip|strip|replace|join|partition|decode|encode)\(",
        content,
    ):
        score += 30

    # Streaming/iteration or line generator patterns
    if (
        re.search(r"for\s+\w+\s+in\s+.*(splitlines|split|partition)", c)
        or "yield" in c
    ):
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
            score += 25
        if any(
            w in scope_lower
            for w in ("ansi", "text", "buffer", "decode", "encode")
        ):
            score += 20

    # Prefer terms matching whole words
    for t in terms:
        if re.search(rf"\b{re.escape(t)}\b", content, re.IGNORECASE):
            score += 15

    return score


def extract_function_scope(
    full_path: pathlib.Path, target_line: int
) -> Optional[Dict[str, Any]]:
    """Extract enclosing function or class definition lines."""
    tree, lines = get_ast_and_lines(full_path)
    target_node = find_enclosing_node(tree, target_line)
    if not target_node:
        return None

    start = getattr(target_node, "lineno", target_line)
    end = getattr(target_node, "end_lineno", target_line)

    # Include decorators
    if hasattr(target_node, "decorator_list") and target_node.decorator_list:
        dec_starts = [
            d.lineno for d in target_node.decorator_list if hasattr(d, "lineno")
        ]
        if dec_starts:
            start = min(start, min(dec_starts))

    scope_lines = lines[start - 1 : end]

    kind = (
        "def"
        if isinstance(target_node, (ast.FunctionDef, ast.AsyncFunctionDef))
        else "class"
    )
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


def print_help() -> None:
    """Print clean usage information."""
    print(
        """Usage: python grep.py [options] <pattern...> [path]

fast-grep: Omnivorous, AST-Aware Search Engine for Autonomous Agents.

Positional arguments:
  pattern...       Search term(s) or regex pattern(s). Multiple terms are searched as OR/union.
  path             Optional target directory or file (defaults to /workspace).

Options:
  --help, -h       Show this help message and exit.
  --json           Output results as structured JSON conforming to Pydantic v2 FastGrepResult.

Diagnostics:
  - Zero matches: Deterministically explains file counts, runs case-insensitive search, and suggests top 5 fuzzy candidate symbols from AST.
  - Regex errors: Catches re.error and provides plain-English syntax diagnostics with suggested escaped patterns.
"""
    )


# ==============================================================================
# Main Entry Point
# ==============================================================================


def main() -> int:
    try:
        raw_args = sys.argv[1:]
        if not raw_args:
            print(
                "[fast-grep] No search term provided. Usage: run_skill_script('fast-grep', 'grep.py', args=['<term>'])"
            )
            return 0

        ws = get_workspace_dir()
        terms, target, is_json, is_help = parse_args(raw_args, ws)

        if is_help:
            print_help()
            return 0

        # If target has .git and ws did not, align ws to target
        if (
            target.is_dir()
            and (target / ".git").exists()
            and not (ws / ".git").exists()
        ):
            ws = target

        if not terms:
            print("[fast-grep] No valid search terms provided.")
            return 0

        # Workspace display name
        if target == ws or str(target).startswith("/workspace"):
            target_display = "/workspace"
        else:
            try:
                rel = target.relative_to(ws)
                target_display = f"/workspace/{rel}"
            except ValueError:
                target_display = str(target)

        total_files = count_files_in_target(target, ws)

        # 1. Regex validation and diagnostic checks
        regex_diagnostics: List[RegexErrorDiagnostic] = []
        safe_terms: List[str] = []
        for t in terms:
            diag = check_regex_syntax(t)
            if diag:
                regex_diagnostics.append(diag)
                safe_terms.append(diag.suggested_escaped_regex)
            else:
                safe_terms.append(t)

        # Heuristic expansion for terse issue keywords
        expanded_terms = list(safe_terms)
        expansion_notes = []
        for t in safe_terms:
            t_key = t.lower()
            if t_key in TERSE_ISSUE_EXPANSIONS:
                verbs = [
                    v
                    for v in TERSE_ISSUE_EXPANSIONS[t_key]
                    if v not in expanded_terms
                ]
                if verbs:
                    expanded_terms.extend(verbs)
                    expansion_notes.append(f"'{t}' -> {', '.join(verbs)}")

        # 2. Run primary search (case-sensitive)
        results = run_git_grep(
            expanded_terms, target, ws, case_insensitive=False
        )

        # Print regex syntax diagnostics to console if present (for human/agent view)
        if not is_json and regex_diagnostics:
            for diag in regex_diagnostics:
                print("=" * 80)
                print(
                    f"⚠️ REGEX SYNTAX ERROR DETECTED in pattern '{diag.raw_pattern}':"
                )
                print(f"  Error: {diag.error_message}")
                print(f"  Explanation: {diag.plain_english_explanation}")
                print(
                    f"  Suggested Escaped Regex: '{diag.suggested_escaped_regex}'"
                )
                print("=" * 80)
                print()

        if not is_json and expansion_notes:
            print(
                f"[fast-grep] 💡 Terse issue heuristic expanded: {'; '.join(expansion_notes)}"
            )

        pattern_display = (
            terms[0] if len(terms) == 1 else ", ".join(repr(t) for t in terms)
        )

        # 3. Handle ZERO MATCHES
        if not results:
            # a) Run case-insensitive search
            ci_results = run_git_grep(
                expanded_terms, target, ws, case_insensitive=True
            )
            ci_matches: List[CaseInsensitiveMatch] = []
            for r in ci_results:
                parts = r.split(":", 2)
                if len(parts) >= 2 and parts[1].isdigit():
                    ci_matches.append(
                        CaseInsensitiveMatch(
                            file=parts[0],
                            lineno=int(parts[1]),
                            content=parts[2] if len(parts) > 2 else "",
                        )
                    )

            # b) Extract candidate symbols from AST & repository identifiers
            symbols = extract_candidate_symbols(target, ws)
            fuzzy_suggestions = get_fuzzy_suggestions(
                terms, symbols, top_n=5, cutoff=0.40
            )

            # Formulate structured explanation & result
            status = "REGEX_ERROR" if regex_diagnostics else "ZERO_MATCHES"
            summary_msg = f"Zero matches found for pattern '{pattern_display}' across {total_files} files in {target_display}."
            explanation = MatchExplanation(
                status=status,
                summary=summary_msg,
                case_sensitive=True,
                case_insensitive_count=len(ci_matches),
                details=(
                    f"Found {len(ci_matches)} case-insensitive matches. "
                    f"Generated {len(fuzzy_suggestions)} fuzzy symbol suggestions."
                )
                if (ci_matches or fuzzy_suggestions)
                else None,
            )

            result = FastGrepResult(
                query_terms=terms,
                target_path=target_display,
                total_files_scanned=total_files,
                total_matches=0,
                explanation=explanation,
                regex_diagnostics=regex_diagnostics,
                case_insensitive_matches=ci_matches,
                fuzzy_suggestions=fuzzy_suggestions,
                ranked_matches=[],
                top_ast_nodes=[],
            )

            if is_json:
                print(result.model_dump_json(indent=2))
                return 0

            # Deterministic zero matches explanation
            print(f"[fast-grep] {summary_msg}\n")

            # Case-insensitive report
            if ci_matches:
                ci_list_preview = ", ".join(
                    f"{m.file}:{m.lineno}" for m in ci_matches[:5]
                )
                if len(ci_matches) > 5:
                    ci_list_preview += f", ... (+{len(ci_matches) - 5} more)"
                print(
                    f"Found {len(ci_matches)} matches when ignoring case: [{ci_list_preview}]"
                )
                for m in ci_matches[:10]:
                    print(f"  - {m.file}:{m.lineno}: {m.content.strip()[:80]}")
                if len(ci_matches) > 10:
                    print(
                        f"  ... ({len(ci_matches) - 10} additional case-insensitive matches truncated)"
                    )
                print()

            # Fuzzy symbol suggestions
            if fuzzy_suggestions:
                sym_list = ", ".join(
                    repr(s.symbol) for s in fuzzy_suggestions[:5]
                )
                print(f"Did you mean one of these symbols: [{sym_list}]")
                for s in fuzzy_suggestions[:5]:
                    loc = f" in {s.source_file}" if s.source_file else ""
                    print(
                        f"  - {s.symbol} ({s.kind}{loc}) [similarity: {s.similarity:.2f}]"
                    )
                print()

            return 0

        # 4. Parse and rank MATCHES FOUND
        parsed: List[GrepMatch] = []
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

                sc = score_match(
                    fp, lineno, content, expanded_terms, scope_name=scope_name
                )
                is_call_site = is_string_transform_line(content)
                parsed.append(
                    GrepMatch(
                        file=fp,
                        lineno=lineno,
                        content=content,
                        score=sc,
                        scope_name=scope_name or None,
                        is_call_site=is_call_site,
                    )
                )

        parsed.sort(key=lambda m: m.score, reverse=True)

        # Extract top 3 unique function scopes
        flashed: List[Tuple[GrepMatch, Dict[str, Any]]] = []
        seen = set()
        top_ast_nodes: List[ASTNodePreview] = []

        for m in parsed:
            p = ws / m.file
            if not p.suffix == ".py" or not p.exists():
                continue
            scope = extract_function_scope(p, m.lineno)
            if scope:
                key = (m.file, scope["name"])
                if key not in seen:
                    seen.add(key)
                    flashed.append((m, scope))
                    top_ast_nodes.append(
                        ASTNodePreview(
                            name=scope["name"],
                            kind=scope["kind"],
                            file=m.file,
                            start_line=scope["start_line"],
                            end_line=scope["end_line"],
                            score=m.score,
                            code_snippet="\n".join(scope["lines"]),
                        )
                    )
                    if len(flashed) >= 3:
                        break

        explanation = MatchExplanation(
            status="MATCHES_FOUND",
            summary=f"Found {len(parsed)} matches across {total_files} files in {target_display}.",
            case_sensitive=True,
            case_insensitive_count=0,
            details=f"Top {len(flashed)} enclosing AST scopes flashed.",
        )

        result = FastGrepResult(
            query_terms=terms,
            target_path=target_display,
            total_files_scanned=total_files,
            total_matches=len(parsed),
            explanation=explanation,
            regex_diagnostics=regex_diagnostics,
            case_insensitive_matches=[],
            fuzzy_suggestions=[],
            ranked_matches=parsed,
            top_ast_nodes=top_ast_nodes,
        )

        if is_json:
            print(result.model_dump_json(indent=2))
            return 0

        # Output results concisely (capped under ADK 5000 char limit)
        terms_display = " | ".join(terms)
        print(
            f"[fast-grep] Search: '{terms_display}' ({len(parsed)} matches, top {len(flashed)} scopes flashed):\n"
        )

        for idx, (m, sc) in enumerate(flashed, start=1):
            fp = m.file
            s_name = sc["name"]
            s_line = sc["start_line"]
            e_line = sc["end_line"]
            lines = sc["lines"]
            target_lineno = m.lineno
            is_call_site = m.is_call_site
            is_transform_scope = sc.get("is_transform", False)

            scope_tag = ""
            if is_transform_scope and is_call_site:
                scope_tag = " [⚡ STRING/BUFFER CALL-SITE & TRANSFORM SCOPE]"
            elif is_call_site:
                scope_tag = " [⚡ STRING/BUFFER CALL-SITE]"
            elif is_transform_scope:
                scope_tag = " [STRING/BUFFER TRANSFORM SCOPE]"

            print("=" * 80)
            print(
                f"[{idx}/{len(flashed)}] SCOPE: {s_name} ({sc['kind']}) in {fp}:{s_line}-{e_line}{scope_tag} [score: {m.score:+d}]"
            )
            print("=" * 80)

            def format_line(lineno: int, text: str) -> str:
                if lineno == target_lineno:
                    callout = (
                        "  <-- [CALL-SITE: string/buffer transform]"
                        if is_call_site
                        else "  <-- [MATCH]"
                    )
                    return f"{lineno:4d}: >>> {text}{callout}"
                return f"{lineno:4d}:     {text}"

            # Middle-fold if over 100 lines
            if len(lines) > 100:
                head = lines[:40]
                tail = lines[-40:]
                for i, l in enumerate(head, start=s_line):
                    print(format_line(i, l))
                print(
                    f" ... [{len(lines) - 80} lines folded for context budget] ..."
                )
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
            snippet = m.content.strip()[:75]
            site_tag = " [CALL-SITE]" if m.is_call_site else ""
            print(f"  [{m.score:+3d}] {m.file}:{m.lineno}{site_tag}: {snippet}")

        if len(parsed) > 15:
            print(f"  ... ({len(parsed) - 15} additional matches truncated)")

        return 0
    except Exception as e:
        print(f"[fast-grep] Search completed with fallback: {e}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
