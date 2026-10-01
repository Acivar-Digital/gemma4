#!/usr/bin/env python3
"""fast-grep: Omnivorous, AST-Aware Search Engine for Autonomous Agents.

Eats ANY input format:
- Single terms, compound phrases, multiple terms (searched as OR/union)
- Unescaped regex or literal code snippets (auto-fallback to literal substring on re.error)
- Dotted symbols, function calls, or raw keywords
- Forgiving CLI: positional args, -p/--pattern, -d/--dir, -i/--ignore-case, -w/--window, -m/--max-matches, --json
- Automatically skips benchmarks, lockfiles, docs, binary files, and noise directories
- Crash & loop immunity: bounded file reads (500KB, 5000 lines), symlink cycle protection, capped match output
- Deterministically explains zero matches with file count, narrow-path detection, and case-insensitive check
- Suggests candidate symbols from AST and repository identifiers via fuzzy matching
- Tokenizes compound phrases on failure and checks for sub-term presence
- Explains regex syntax errors in plain English and suggests escaped patterns
- 100% Pydantic v2 structured schemas (FastGrepResult, MatchExplanation, FuzzySuggestion, etc.)
- Flashes top 2 enclosing functions with complete decorators via AST
- Prioritizes function, method, and class definitions at the top of search rankings over call sites
- Boosts common string/buffer transformation methods & verbs
- Highlights call-sites and enclosing scopes where strings/buffers are transformed
- Automatically expands terse issue keywords to candidate string operations
- Detects non-existent paths, warns the LLM, suggests similar files, and falls back to workspace search
- Context-safe: Sliding context window centered on target line, clean code block for edit_file
- Always exits 0 and never crashes or hangs in runaway loops.
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
        description="Outcome status: MATCHES_FOUND, ZERO_MATCHES, REGEX_ERROR, PATH_NOT_FOUND, or OVERVIEW",
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
    other_locations_count: int = Field(
        default=0, description="Count of matches found outside target path"
    )
    details: Optional[str] = Field(
        default=None, description="Additional context or diagnostics"
    )
    skipped_extensions: List[str] = Field(
        default_factory=list, description="Extensions excluded from search"
    )
    skipped_dirs: List[str] = Field(
        default_factory=list, description="Directories excluded from search"
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


class SubtermMatchSummary(BaseModel):
    """Match summary for individual sub-terms of a failed compound query."""

    model_config = ConfigDict(extra="ignore")

    subterm: str = Field(..., description="Subterm token extracted from query")
    match_count: int = Field(..., description="Count of matches found for subterm")
    sample_file: Optional[str] = Field(
        default=None, description="Sample file containing subterm"
    )
    sample_lineno: Optional[int] = Field(
        default=None, description="Sample line number containing subterm"
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


class OtherLocationMatch(BaseModel):
    """Match line discovered in other repository files outside target path."""

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
    is_definition: bool = Field(
        default=False,
        description="Whether line is a function, method, or class definition signature",
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
    other_locations_matches: List[OtherLocationMatch] = Field(
        default_factory=list, description="Matches found in other workspace files"
    )
    fuzzy_suggestions: List[FuzzySuggestion] = Field(
        default_factory=list, description="Candidate symbol suggestions"
    )
    subterm_matches: List[SubtermMatchSummary] = Field(
        default_factory=list,
        description="Matches found for tokenized sub-terms of compound query",
    )
    similar_files: List[str] = Field(
        default_factory=list, description="Relevant workspace files"
    )
    suggestions: List[str] = Field(
        default_factory=list, description="Actionable query reformulation suggestions"
    )
    copy_pasteable_commands: List[str] = Field(
        default_factory=list, description="Copy-pasteable CLI commands for LLM next turn"
    )
    path_warning: Optional[str] = Field(
        default=None, description="Warning if target path was missing or corrected"
    )
    ranked_matches: List[GrepMatch] = Field(
        default_factory=list, description="Ranked match items"
    )
    top_ast_nodes: List[ASTNodePreview] = Field(
        default_factory=list, description="Top AST scope previews"
    )


# ==============================================================================
# Constants & Safety Limits
# ==============================================================================

MAX_FILE_SIZE_BYTES: int = 500_000   # 500 KB limit to prevent OOM on giant dumps
MAX_LINES_PER_FILE: int = 5_000      # Max lines to scan per file
MAX_LINE_LENGTH: int = 1_000         # Max chars per line inspected (prevents ReDoS/OOM)
MAX_RAW_MATCHES: int = 200           # Circuit breaker on raw git/python grep matches
MAX_RANKED_MATCHES: int = 50         # Max ranked matches kept in result
MAX_DISPLAY_PREVIEWS: int = 15       # Max previews shown in console summary
MAX_SCOPES_FLASHED: int = 2          # Top enclosing AST scopes flashed

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
    "embeddings",
    ".adk_exec",
    ".eggs",
    ".beads",
    ".idea",
    ".vscode",
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
    ".safetensors",
    ".whl",
    ".json",
    ".jsonl",
    ".npz",
    ".npy",
    ".csv",
    ".log",
    ".xml",
    ".txt",
    ".yaml",
    ".yml",
    ".md",
    ".rst",
    ".so",
    ".dylib",
    ".dll",
    ".exe",
    ".wasm",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".parquet",
    ".pkl",
    ".pickle",
    ".pdf",
    ".ttf",
    ".woff",
    ".woff2",
    ".eot",
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

COMMON_STOPWORDS: Set[str] = {
    "the",
    "a",
    "an",
    "in",
    "on",
    "of",
    "to",
    "for",
    "with",
    "at",
    "by",
    "from",
    "into",
    "is",
    "are",
    "was",
    "were",
    "it",
    "this",
    "that",
    "these",
    "those",
    "be",
    "been",
    "has",
    "have",
    "had",
    "do",
    "does",
    "did",
    "can",
    "could",
    "should",
    "would",
    "will",
    "not",
    "no",
    "but",
    "and",
    "or",
    "as",
    "if",
}

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
# Binary & Symlink Safety Checks
# ==============================================================================


def is_binary_file(path: pathlib.Path) -> bool:
    """Detect if file is binary by extension or null byte inspection."""
    if any(path.name.endswith(ext) for ext in SKIP_EXTENSIONS):
        return True
    try:
        with open(path, "rb") as f:
            chunk = f.read(1024)
            if b"\0" in chunk:
                return True
    except Exception:
        return True
    return False


# ==============================================================================
# AST & Scope Inspection Helpers
# ==============================================================================


def get_ast_and_lines(
    full_path: pathlib.Path,
) -> Tuple[Optional[ast.AST], List[str]]:
    """Parse and cache AST and source lines for a python file, skipping gigantic or binary files."""
    try:
        real_p = full_path.resolve()
        key = str(real_p)
    except Exception:
        key = str(full_path)

    if key in _AST_CACHE:
        return _AST_CACHE[key]

    try:
        st = full_path.stat()
        if st.st_size > MAX_FILE_SIZE_BYTES or st.st_size == 0:
            _AST_CACHE[key] = (None, [])
            return (None, [])
        if is_binary_file(full_path):
            _AST_CACHE[key] = (None, [])
            return (None, [])
        text = full_path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()[:MAX_LINES_PER_FILE]
        tree = ast.parse("\n".join(lines), filename=key)
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
    for line in lines[:200]:
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


def extract_subterms(phrase: str) -> List[str]:
    """Extract significant non-stopword identifier tokens from a compound query."""
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", phrase)
    subterms: List[str] = []
    for w in words:
        w_clean = w.strip()
        w_lower = w_clean.lower()
        if (
            len(w_clean) >= 3
            and w_lower not in PYTHON_KEYWORDS
            and w_lower not in COMMON_STOPWORDS
            and w_clean not in subterms
        ):
            subterms.append(w_clean)
    return subterms


def find_similar_workspace_files(
    query_str: str, ws: pathlib.Path, max_results: int = 5
) -> List[str]:
    """Find repository files matching or closely resembling query identifiers."""
    all_files: List[str] = []
    try:
        if (ws / ".git").exists():
            res = subprocess.run(
                ["git", "ls-files", ":(exclude)*.adk_exec*"],
                cwd=ws,
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if res.returncode == 0:
                all_files = [
                    f
                    for f in res.stdout.splitlines()
                    if f.endswith(".py")
                    and not any(d in f for d in SKIP_DIRS)
                ]
    except Exception:
        pass

    if not all_files:
        try:
            for root, dirs, files in os.walk(ws, followlinks=False):
                dirs[:] = [
                    d
                    for d in dirs
                    if d not in SKIP_DIRS
                    and not d.startswith(".")
                    and not (".adk_exec" in d or d.startswith(".adk_exec"))
                ]
                for f in files:
                    if f.endswith(".py"):
                        full_p = pathlib.Path(root) / f
                        try:
                            all_files.append(str(full_p.relative_to(ws)))
                        except ValueError:
                            all_files.append(str(full_p))
                if len(all_files) > 1000:
                    break
        except Exception:
            pass

    if not all_files:
        return []

    matches: List[str] = []
    tokens = [t.lower() for t in extract_subterms(query_str)]
    if not tokens:
        tokens = [query_str.lower()]

    for f in all_files:
        f_lower = f.lower()
        stem = pathlib.Path(f).stem.lower()
        if any(t == stem for t in tokens):
            if f not in matches:
                matches.append(f)
        elif any(t in f_lower for t in tokens if len(t) >= 4):
            if f not in matches:
                matches.append(f)
        if len(matches) >= max_results:
            return matches

    filenames = [pathlib.Path(f).name for f in all_files]
    for tok in tokens:
        close = difflib.get_close_matches(tok, filenames, n=3, cutoff=0.5)
        for c in close:
            for f in all_files:
                if pathlib.Path(f).name == c and f not in matches:
                    matches.append(f)
                    if len(matches) >= max_results:
                        return matches

    return matches[:max_results]


# ==============================================================================
# Argument Parsing (Omnivorous, Forgiving CLI)
# ==============================================================================


def looks_like_path(val: str) -> bool:
    """Heuristic to check if an argument was meant as a path."""
    if val in (".", "./", "/workspace", "/workspace/", "..", "../"):
        return True
    if val.startswith(("/", "./", "../", "~/")):
        return True
    if "/" in val or "\\" in val:
        return True
    if any(
        val.endswith(ext)
        for ext in (
            ".py",
            ".pyi",
            ".toml",
            ".json",
            ".md",
            ".txt",
            ".yaml",
            ".yml",
            ".rst",
            ".html",
            ".sh",
            ".c",
            ".h",
            ".cpp",
        )
    ):
        return True
    return False


def resolve_target_path(val: str, ws: pathlib.Path) -> Optional[pathlib.Path]:
    """Resolve a path string relative to ws or absolute if exists, or None if non-existent."""
    if val in (".", "./", "/workspace", "/workspace/"):
        return ws
    cand = ws / val.lstrip("/")
    if cand.exists():
        return cand
    cand_direct = pathlib.Path(val).resolve()
    if cand_direct.exists():
        return cand_direct
    return None


def parse_args(
    args: List[str], ws: pathlib.Path
) -> Tuple[
    List[str],          # terms
    pathlib.Path,       # target_path
    bool,               # is_json
    bool,               # is_help
    bool,               # is_case_insensitive
    int,                # context_window
    int,                # max_matches
    Optional[str],      # invalid_target
    Optional[str],      # raw_phrase
    bool,               # is_overview
]:
    """Extract search terms, target directory/file, and flags with forgiving tolerance."""
    terms: List[str] = []
    target_path = ws
    is_json = False
    is_help = False
    is_case_insensitive = False
    context_window = 40  # default 40 lines (15 before, 25 after)
    max_matches = 50
    invalid_target: Optional[str] = None
    raw_phrase: Optional[str] = None
    explicit_target = False
    explicit_terms = False
    positional_args: List[str] = []

    i = 0
    while i < len(args):
        a = args[i].strip()
        if not a:
            i += 1
            continue

        if a in ("--help", "-h"):
            is_help = True
            i += 1
            continue

        if a == "--json":
            is_json = True
            i += 1
            continue

        if a in ("-i", "--ignore-case", "-case-insensitive", "--case-insensitive"):
            is_case_insensitive = True
            i += 1
            continue

        # -p or --pattern or -q or --query
        if a in ("--pattern", "-p", "--query", "-q"):
            if i + 1 < len(args) and not args[i + 1].startswith("-"):
                i += 1
                val = clean_search_term(args[i])
                if val:
                    terms.append(val)
                    explicit_terms = True
                    if not raw_phrase:
                        raw_phrase = val
            i += 1
            continue

        if any(
            a.startswith(prefix)
            for prefix in ("--pattern=", "-p=", "--query=", "-q=")
        ):
            val = clean_search_term(a.split("=", 1)[1])
            if val:
                terms.append(val)
                explicit_terms = True
                if not raw_phrase:
                    raw_phrase = val
            i += 1
            continue

        # -d or --dir or --path
        if a in ("--dir", "-d", "--path"):
            if i + 1 < len(args) and not args[i + 1].startswith("-"):
                i += 1
                dir_val = clean_search_term(args[i])
                if dir_val:
                    target_cand = resolve_target_path(dir_val, ws)
                    if target_cand is not None:
                        target_path = target_cand
                    else:
                        invalid_target = dir_val
                    explicit_target = True
            i += 1
            continue

        if any(a.startswith(prefix) for prefix in ("--dir=", "-d=", "--path=")):
            dir_val = clean_search_term(a.split("=", 1)[1])
            if dir_val:
                target_cand = resolve_target_path(dir_val, ws)
                if target_cand is not None:
                    target_path = target_cand
                else:
                    invalid_target = dir_val
                explicit_target = True
            i += 1
            continue

        # -w, --window, -c, --context
        if a in ("--window", "-w", "--context", "-c"):
            if i + 1 < len(args) and (
                args[i + 1].isdigit()
                or (args[i + 1].startswith("-") and args[i + 1][1:].isdigit())
            ):
                i += 1
                try:
                    context_window = max(5, min(200, int(args[i])))
                except ValueError:
                    pass
            i += 1
            continue

        if any(
            a.startswith(prefix)
            for prefix in ("--window=", "-w=", "--context=", "-c=")
        ):
            try:
                context_window = max(5, min(200, int(a.split("=", 1)[1])))
            except ValueError:
                pass
            i += 1
            continue

        # -m, --max-matches
        if a in ("--max-matches", "-m"):
            if i + 1 < len(args) and args[i + 1].isdigit():
                i += 1
                try:
                    max_matches = max(1, min(500, int(args[i])))
                except ValueError:
                    pass
            i += 1
            continue

        if any(a.startswith(prefix) for prefix in ("--max-matches=", "-m=")):
            try:
                max_matches = max(1, min(500, int(a.split("=", 1)[1])))
            except ValueError:
                pass
            i += 1
            continue

        # Otherwise it's a positional argument
        cleaned = clean_search_term(a)
        if cleaned:
            positional_args.append(cleaned)
        i += 1

    # Resolve positional arguments
    is_overview = False

    if explicit_terms:
        # User explicitly passed terms via -p/-q; any positional arg is candidate target path
        if not explicit_target and positional_args:
            pos_target = positional_args[0]
            cand = resolve_target_path(pos_target, ws)
            if cand is not None:
                target_path = cand
            else:
                invalid_target = pos_target
    else:
        # Terms were not passed via flags
        if len(positional_args) == 0:
            is_overview = True
        elif len(positional_args) == 1:
            arg = positional_args[0]
            if arg in (".", "./", "/workspace", "/workspace/"):
                is_overview = True
                target_path = ws
            else:
                # Single term search across target
                terms.append(arg)
                raw_phrase = arg
        elif len(positional_args) == 2:
            arg0, arg1 = positional_args[0], positional_args[1]
            if not explicit_target:
                target_cand = resolve_target_path(arg1, ws)
                if target_cand is not None:
                    terms.append(arg0)
                    raw_phrase = arg0
                    target_path = target_cand
                elif looks_like_path(arg1):
                    terms.append(arg0)
                    raw_phrase = arg0
                    invalid_target = arg1
                else:
                    # Multi-term union search across workspace
                    terms.extend([arg0, arg1])
                    raw_phrase = f"{arg0} {arg1}"
            else:
                terms.extend([arg0, arg1])
                raw_phrase = f"{arg0} {arg1}"
        else:
            # >= 3 positional arguments
            if not explicit_target:
                last_arg = positional_args[-1]
                target_cand = resolve_target_path(last_arg, ws)
                if target_cand is not None:
                    target_path = target_cand
                    terms.extend(positional_args[:-1])
                    raw_phrase = " ".join(positional_args[:-1])
                elif looks_like_path(last_arg):
                    invalid_target = last_arg
                    terms.extend(positional_args[:-1])
                    raw_phrase = " ".join(positional_args[:-1])
                else:
                    terms.extend(positional_args)
                    raw_phrase = " ".join(positional_args)
            else:
                terms.extend(positional_args)
                raw_phrase = " ".join(positional_args)

    return (
        terms,
        target_path,
        is_json,
        is_help,
        is_case_insensitive,
        context_window,
        max_matches,
        invalid_target,
        raw_phrase,
        is_overview,
    )


# ==============================================================================
# Regex Diagnostics & Symbol Extraction
# ==============================================================================


def escape_regex_metachars(pattern: str) -> str:
    """Escape regex special characters while preserving readable spaces and alphanumeric words."""
    escaped = re.escape(pattern)
    try:
        re.compile(escaped)
        return escaped
    except re.error:
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
                f"Unclosed opening parenthesis '(' at position {pos if pos is not None else 'unknown'}. "
                "In regex, '(' starts a group. To match literal '(', escape it as '\\('."
            )
        elif "missing (" in msg_lower or "unmatched )" in msg_lower:
            plain_english = (
                f"Unmatched closing parenthesis ')' at position {pos if pos is not None else 'unknown'}. "
                "To match literal ')', escape it as '\\)'."
            )
        elif (
            "unterminated character set" in msg_lower
            or "missing ]" in msg_lower
        ):
            plain_english = (
                f"Unclosed character set bracket '[' at position {pos if pos is not None else 'unknown'}. "
                "To match literal '[', escape it as '\\['."
            )
        elif "missing [" in msg_lower or "unmatched ]" in msg_lower:
            plain_english = (
                f"Unmatched closing bracket ']' at position {pos if pos is not None else 'unknown'}. "
                "To match literal ']', escape it as '\\]'."
            )
        elif "nothing to repeat" in msg_lower:
            plain_english = (
                f"Dangling quantifier (*, +, ?, or {{}}) at position {pos if pos is not None else 'unknown'} "
                "without preceding character or token. To match literal quantifier, escape with '\\'."
            )
        elif "multiple repeat" in msg_lower:
            plain_english = (
                f"Consecutive repeat operators at position {pos if pos is not None else 'unknown'}. "
                "To match literal symbols, escape with '\\'."
            )
        elif "bad escape" in msg_lower or "incomplete escape" in msg_lower:
            plain_english = (
                f"Invalid or incomplete escape sequence at position {pos if pos is not None else 'unknown'}. "
                "Ensure backslashes are properly paired or escape literal backslashes as '\\\\'."
            )
        elif "bad character range" in msg_lower:
            plain_english = (
                f"Invalid character range in brackets at position {pos if pos is not None else 'unknown'} (e.g. [z-a]). "
                "Start character must be <= end character."
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
    """Accurately count searchable files in target directory with loop safeguards."""
    if (ws / ".git").exists():
        try:
            rel = "."
            if target != ws:
                try:
                    rel = str(target.relative_to(ws))
                except ValueError:
                    rel = str(target)
            res = subprocess.run(
                [
                    "git",
                    "ls-files",
                    rel,
                    ":(exclude)*.adk_exec*",
                    ":(exclude)**/.adk_exec*",
                ],
                cwd=ws,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if res.returncode == 0:
                files = [
                    f
                    for f in res.stdout.splitlines()
                    if f.strip()
                    and not (
                        ".adk_exec" in f or f.startswith(".adk_exec")
                    )
                ]
                if files:
                    return len(files)
        except Exception:
            pass

    count = 0
    try:
        for root, dirs, files in os.walk(target, followlinks=False):
            dirs[:] = [
                d
                for d in dirs
                if d not in SKIP_DIRS
                and not d.startswith(".")
                and not (".adk_exec" in d or d.startswith(".adk_exec"))
            ]
            count += len(
                [
                    f
                    for f in files
                    if not any(f.endswith(ext) for ext in SKIP_EXTENSIONS)
                    and not (".adk_exec" in f or f.startswith(".adk_exec"))
                ]
            )
            if count >= 50000:
                break
    except Exception:
        pass
    return max(count, 1)


def extract_candidate_symbols(
    target: pathlib.Path, ws: pathlib.Path, max_files: int = 150
) -> Dict[str, Tuple[str, str]]:
    """Extract symbol names and kinds from AST and source code in the repository."""
    symbols: Dict[str, Tuple[str, str]] = {}
    search_root = target if target.is_dir() else ws
    scanned_files = 0

    try:
        for root, dirs, files in os.walk(search_root, followlinks=False):
            dirs[:] = [
                d
                for d in dirs
                if d not in SKIP_DIRS
                and not d.startswith(".")
                and not (".adk_exec" in d or d.startswith(".adk_exec"))
                and "test" not in d.lower()
                and ("doc" not in d.lower() or "docs_src" in d.lower())
            ]
            for f in files:
                if ".adk_exec" in f or f.startswith(".adk_exec"):
                    continue
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

                try:
                    if full_p.stat().st_size > MAX_FILE_SIZE_BYTES:
                        continue
                except OSError:
                    continue

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

                for line in lines[:300]:
                    tokens = re.findall(
                        r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b", line[:200]
                    )
                    for tok in tokens:
                        if tok not in symbols and tok not in PYTHON_KEYWORDS:
                            symbols[tok] = ("identifier", rel_p)

                if len(symbols) >= 1000:
                    break

            if scanned_files > max_files or len(symbols) >= 1000:
                break
    except Exception:
        pass

    return symbols


def get_fuzzy_suggestions(
    query_terms: List[str],
    candidate_symbols: Dict[str, Tuple[str, str]],
    top_n: int = 5,
    cutoff: float = 0.35,
) -> List[FuzzySuggestion]:
    """Find closest matching candidate symbols via fuzzy ratio matching."""
    scored: List[Tuple[float, str, str, str, str]] = []
    seen: Set[str] = set()

    for term in query_terms:
        words = [
            w
            for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", term)
            if len(w) > 2 and w.lower() not in PYTHON_KEYWORDS
        ]
        if not words:
            words = [term]

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
    max_matches: int = MAX_RAW_MATCHES,
) -> List[str]:
    """Execute git grep with extended regex and literal fallback, with path exclusions."""
    if not (ws / ".git").exists():
        return python_walk_fallback(
            terms,
            target,
            ws,
            case_insensitive=case_insensitive,
            max_matches=max_matches,
        )

    safe_regex_terms: List[str] = []
    for t in terms:
        diag = check_regex_syntax(t)
        if diag:
            safe_regex_terms.append(diag.suggested_escaped_regex)
        else:
            safe_regex_terms.append(t)

    combined_pattern = (
        "|".join(safe_regex_terms)
        if len(safe_regex_terms) > 1
        else safe_regex_terms[0]
    )

    rel_target = "."
    if target != ws:
        try:
            rel_target = str(target.relative_to(ws))
        except ValueError:
            rel_target = str(target)

    path_args = [rel_target]
    for d in SKIP_DIRS:
        path_args.append(f":(exclude){d}/**")
        path_args.append(f":(exclude)**/{d}/**")
    for ext in SKIP_EXTENSIONS:
        path_args.append(f":(exclude)*{ext}")
        path_args.append(f":(exclude)**/*{ext}")
    path_args.append(":(exclude)*.adk_exec*")
    path_args.append(":(exclude)**/.adk_exec*")

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
            clean_lines = []
            for line in res.stdout.splitlines():
                if not line.strip():
                    continue
                matched_file = line.split(":", 1)[0]
                if (
                    ".adk_exec" in matched_file
                    or matched_file.startswith(".adk_exec")
                ):
                    continue
                clean_lines.append(line)
                if len(clean_lines) >= max_matches:
                    break
            if clean_lines:
                return clean_lines
    except Exception:
        pass

    # 2. Fallback to fixed-strings (-F) for each raw term
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
                    if not line.strip():
                        continue
                    matched_file = line.split(":", 1)[0]
                    if (
                        ".adk_exec" in matched_file
                        or matched_file.startswith(".adk_exec")
                    ):
                        continue
                    if line not in all_lines:
                        all_lines.append(line)
                    if len(all_lines) >= max_matches:
                        break
        except Exception:
            pass
        if len(all_lines) >= max_matches:
            break

    if all_lines:
        return all_lines

    # 3. Fallback to python walk if git grep failed or was empty
    return python_walk_fallback(
        terms,
        target,
        ws,
        case_insensitive=case_insensitive,
        max_matches=max_matches,
    )


def python_walk_fallback(
    terms: List[str],
    target: pathlib.Path,
    ws: pathlib.Path,
    case_insensitive: bool = False,
    max_matches: int = MAX_RAW_MATCHES,
) -> List[str]:
    """Pure-python fallback scanner with loop, symlink, giant-file, and ReDoS safeguards."""
    matches: List[str] = []
    flags = re.IGNORECASE if case_insensitive else 0
    compiled: List[re.Pattern] = []
    raw_substrings: List[str] = []

    for t in terms:
        try:
            compiled.append(re.compile(t, flags))
        except re.error:
            try:
                compiled.append(re.compile(escape_regex_metachars(t), flags))
            except re.error:
                pass
        raw_substrings.append(t.lower() if case_insensitive else t)

    search_root = (
        target
        if target.is_dir()
        else (target.parent if target.is_file() else ws)
    )
    visited_inodes: Set[Tuple[int, int]] = set()

    file_list: List[pathlib.Path] = []
    if target.is_file():
        file_list = [target]
    else:
        try:
            for root, dirs, files in os.walk(search_root, followlinks=False):
                dirs[:] = [
                    d
                    for d in dirs
                    if d not in SKIP_DIRS
                    and not d.startswith(".")
                    and not (".adk_exec" in d or d.startswith(".adk_exec"))
                ]
                for f in sorted(files):
                    if ".adk_exec" in f or f.startswith(".adk_exec"):
                        continue
                    if any(f.endswith(ext) for ext in SKIP_EXTENSIONS):
                        continue
                    file_list.append(pathlib.Path(root) / f)
                    if len(file_list) >= 50_000:
                        break
                if len(file_list) >= 50_000:
                    break
        except Exception:
            pass

    for full_p in file_list:
        try:
            st = full_p.stat()
            inode_key = (st.st_dev, st.st_ino)
            if inode_key in visited_inodes:
                continue
            visited_inodes.add(inode_key)

            if st.st_size > MAX_FILE_SIZE_BYTES or st.st_size == 0:
                continue
            if is_binary_file(full_p):
                continue
        except OSError:
            continue

        try:
            rel_p = str(full_p.relative_to(ws))
        except ValueError:
            rel_p = str(full_p)

        try:
            with open(full_p, "r", encoding="utf-8", errors="replace") as fh:
                for lineno, line in enumerate(fh, start=1):
                    if lineno > MAX_LINES_PER_FILE:
                        break
                    line_trunc = line[:MAX_LINE_LENGTH]
                    matched = False

                    for pattern in compiled:
                        try:
                            if pattern.search(line_trunc):
                                matched = True
                                break
                        except Exception:
                            pass

                    if not matched:
                        line_check = (
                            line_trunc.lower()
                            if case_insensitive
                            else line_trunc
                        )
                        for sub in raw_substrings:
                            if sub in line_check:
                                matched = True
                                break

                    if matched:
                        matches.append(
                            f"{rel_p}:{lineno}:{line.rstrip()[:400]}"
                        )
                        if len(matches) >= max_matches:
                            return matches
        except Exception:
            continue

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

    # Demote tests and docs (exempt executable tutorial code in docs_src/*.py)
    if "test" in p_lower:
        score -= 40
    is_docs_src_py = "docs_src" in p_lower and file_path.endswith(".py")
    if not is_docs_src_py and (
        "doc" in p_lower or file_path.endswith((".md", ".rst"))
    ):
        score -= 40
    if "bench" in p_lower or "example" in p_lower:
        score -= 50

    # Priority Tier 1: Function, method, and class definitions
    is_code = not c.startswith(("#", "//", "/*", "*", '"""', "'''"))
    if is_code:
        if re.search(r"\b(async\s+def|def|class)\s+", content):
            score += 60
        elif "@" in content:
            score += 30

        sig_match = re.search(
            r"^\s*(async\s+def|def|class)\s+([A-Za-z0-9_]+)", content
        )
        if sig_match:
            score += 60
            sym_name = sig_match.group(2).lower()
            for t in terms:
                cleaned_t = t.strip().lower()
                if not cleaned_t:
                    continue
                if cleaned_t == sym_name:
                    score += 75
                    break
                elif cleaned_t in sym_name:
                    score += 50
                    break
        elif re.search(r"^\s*@", content):
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

    for t in terms:
        cleaned_t = t.strip()
        if not cleaned_t:
            continue
        if re.match(r"^[A-Za-z0-9_]+$", cleaned_t):
            if re.search(rf"\b{re.escape(cleaned_t)}\b", content, re.IGNORECASE):
                score += 15
        else:
            if cleaned_t.lower() in content.lower():
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
  pattern...             Search term(s), phrase, or regex. Multiple terms are searched as OR/union.
  path                   Optional target directory or file (defaults to /workspace).

Options:
  --help, -h             Show this help message and exit.
  -p, --pattern <term>   Search pattern or regex (supports raw code snippets).
  -q, --query <term>     Search query or phrase (auto-tokenized for subterm checking).
  -d, --dir <path>       Target search directory or file path.
  -i, --ignore-case      Perform case-insensitive search.
  -w, --window <lines>   Context window size centered on target line (default: 40).
  -m, --max-matches <n>  Maximum matches to collect (default: 50).
  --json                 Output results as structured JSON conforming to Pydantic v2 FastGrepResult.

Diagnostics:
  - Zero matches: Explains file count, runs case-insensitive check, tests sub-terms, checks other files, and suggests symbols.
  - Regex errors: Fall back cleanly to literal substring search, warn gently, and return matches.
  - Missing path: Detects missing files/directories, suggests close matches, and falls back to workspace.
"""
    )


def print_overview(target_display: str = "/workspace") -> None:
    """Print helpful, copy-pasteable usage overview when called without pattern."""
    print("=" * 80)
    print("fast-grep: Omnivorous, AST-Aware Search Engine for Autonomous Agents")
    print("=" * 80)
    print("\nUsage:")
    print("  python3 grep.py [options] <pattern...> [path]")
    print("\nTailored copy-pasteable commands for next step:")
    print("  1. Search symbol or phrase:")
    print('     python3 grep.py "def score_match"')
    print("  2. Case-insensitive search:")
    print('     python3 grep.py -i "apirouter"')
    print("  3. Search in specific directory:")
    print('     python3 grep.py "splitlines" src/')
    print("  4. Multi-term union search:")
    print("     python3 grep.py splitlines rstrip strip")
    print("  5. Structured JSON output:")
    print('     python3 grep.py --json "APIRouter"')
    print("\nOptions:")
    print("  -p, --pattern <term>   Search pattern or regex")
    print("  -d, --dir <path>       Target directory or file (defaults to /workspace)")
    print("  -i, --ignore-case      Case-insensitive search")
    print("  -w, --window <lines>   Context window size around target line (default: 40)")
    print("  -m, --max-matches <n>  Maximum matches to collect (default: 50)")
    print("  --json                 Output structured Pydantic v2 JSON")
    print("  -h, --help             Show help message and exit")


# ==============================================================================
# Main Entry Point
# ==============================================================================


def main() -> int:
    try:
        raw_args = sys.argv[1:]
        ws = get_workspace_dir()

        (
            terms,
            target,
            is_json,
            is_help,
            is_case_insensitive,
            context_window,
            max_matches,
            invalid_target,
            raw_phrase,
            is_overview,
        ) = parse_args(raw_args, ws)

        if is_help:
            print_help()
            return 0

        # Align workspace if target has .git
        if (
            target.is_dir()
            and (target / ".git").exists()
            and not (ws / ".git").exists()
        ):
            ws = target

        # Target display name
        if target == ws or str(target).startswith("/workspace"):
            target_display = "/workspace"
        else:
            try:
                rel = target.relative_to(ws)
                target_display = f"/workspace/{rel}"
            except ValueError:
                target_display = str(target)

        total_files = count_files_in_target(target, ws)

        # Overview mode (no terms provided or empty arguments)
        if is_overview or (not terms and not invalid_target):
            overview_cmds = [
                'python3 grep.py "def score_match"',
                'python3 grep.py -i "apirouter"',
                'python3 grep.py "splitlines" src/',
                'python3 grep.py splitlines rstrip strip',
                'python3 grep.py --json "APIRouter"',
            ]
            if is_json:
                explanation = MatchExplanation(
                    status="OVERVIEW",
                    summary=f"No search pattern specified. Showing workspace overview for {target_display}.",
                    case_sensitive=not is_case_insensitive,
                    case_insensitive_count=0,
                    details="fast-grep usage overview",
                    skipped_extensions=sorted(list(SKIP_EXTENSIONS)),
                    skipped_dirs=sorted(list(SKIP_DIRS)),
                )
                result = FastGrepResult(
                    query_terms=[],
                    target_path=target_display,
                    total_files_scanned=total_files,
                    total_matches=0,
                    explanation=explanation,
                    suggestions=[
                        "Provide a search pattern: python3 grep.py '<pattern>'"
                    ],
                    copy_pasteable_commands=overview_cmds,
                )
                print(result.model_dump_json(indent=2))
                return 0
            else:
                print_overview(target_display)
                return 0

        # Handle missing/invalid target path
        path_warning_msg = None
        if invalid_target:
            similar_paths = find_similar_workspace_files(
                invalid_target, ws, max_results=3
            )
            path_warning_msg = (
                f"Target path '{invalid_target}' does not exist in workspace ({ws}). "
                f"Falling back to searching entire workspace."
            )
            if not is_json:
                print(
                    f"[fast-grep] ⚠️ TARGET PATH NOT FOUND: '{invalid_target}' does not exist!"
                )
                if similar_paths:
                    print("  Did you mean one of these files?")
                    for sp in similar_paths:
                        print(f"    - {sp}")
                print(
                    f"  [fast-grep] 🔄 Falling back to searching entire workspace (/workspace)...\n"
                )

        if not terms:
            print(
                "[fast-grep] ⚠️ No valid search terms provided after parsing arguments.\n"
                "Usage: python grep.py [options] <pattern...> [path]\n"
                "Example: python grep.py 'def score_match' ."
            )
            return 0

        # 1. Regex validation and diagnostic checks (with forgiving literal fallback)
        regex_diagnostics: List[RegexErrorDiagnostic] = []
        safe_terms: List[str] = []
        for t in terms:
            diag = check_regex_syntax(t)
            if diag:
                regex_diagnostics.append(diag)
                safe_terms.append(diag.suggested_escaped_regex)
                if not is_json:
                    print(
                        f"[fast-grep] ⚠️ Invalid regex pattern '{diag.raw_pattern}': {diag.error_message}"
                    )
                    print(
                        f"  💡 Automatically falling back to literal substring search."
                    )
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

        # 2. Run primary search
        results = run_git_grep(
            expanded_terms,
            target,
            ws,
            case_insensitive=is_case_insensitive,
            max_matches=max_matches * 2,
        )

        if not is_json and expansion_notes:
            print(
                f"[fast-grep] 💡 Terse issue heuristic expanded: {'; '.join(expansion_notes)}"
            )

        pattern_display = (
            terms[0] if len(terms) == 1 else ", ".join(repr(t) for t in terms)
        )
        first_term = terms[0]

        # 3. Handle ZERO MATCHES
        if not results:
            other_locations_matches: List[OtherLocationMatch] = []
            copy_pasteable_commands: List[str] = []
            suggestions_list: List[str] = []

            # a) Narrow path filter check: check if pattern exists elsewhere in workspace
            if target != ws:
                ws_results = run_git_grep(
                    expanded_terms,
                    ws,
                    ws,
                    case_insensitive=is_case_insensitive,
                    max_matches=10,
                )
                if ws_results:
                    for r in ws_results[:5]:
                        parts = r.split(":", 2)
                        if len(parts) >= 2 and parts[1].isdigit():
                            other_locations_matches.append(
                                OtherLocationMatch(
                                    file=parts[0],
                                    lineno=int(parts[1]),
                                    content=parts[2] if len(parts) > 2 else "",
                                )
                            )
                    cmd = f'python3 grep.py "{first_term}"'
                    if cmd not in copy_pasteable_commands:
                        copy_pasteable_commands.append(cmd)
                    suggestions_list.append(
                        f"Search entire repository: pattern exists in other files outside '{target_display}'"
                    )

            # b) Run case-insensitive search if search was case-sensitive
            ci_matches: List[CaseInsensitiveMatch] = []
            if not is_case_insensitive:
                ci_results = run_git_grep(
                    expanded_terms,
                    target,
                    ws,
                    case_insensitive=True,
                    max_matches=15,
                )
                if not ci_results and target != ws:
                    ci_results = run_git_grep(
                        expanded_terms,
                        ws,
                        ws,
                        case_insensitive=True,
                        max_matches=15,
                    )
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
                if ci_matches:
                    target_arg = (
                        f" {target_display.replace('/workspace/', '').replace('/workspace', '.')}"
                        if target != ws
                        else ""
                    )
                    cmd = f'python3 grep.py -i "{first_term}"{target_arg}'.strip()
                    if cmd not in copy_pasteable_commands:
                        copy_pasteable_commands.append(cmd)
                    suggestions_list.append(
                        f"Ignore case: {len(ci_matches)} matches found with -i / --ignore-case"
                    )

            # c) Test tokenized sub-terms if compound query failed
            subterm_summaries: List[SubtermMatchSummary] = []
            candidate_subterms = []
            if raw_phrase:
                candidate_subterms = extract_subterms(raw_phrase)
            for t in terms:
                for sub in extract_subterms(t):
                    if sub not in candidate_subterms:
                        candidate_subterms.append(sub)

            for sub in candidate_subterms[:6]:
                sub_res = run_git_grep(
                    [sub],
                    target,
                    ws,
                    case_insensitive=True,
                    max_matches=5,
                )
                if not sub_res and target != ws:
                    sub_res = run_git_grep(
                        [sub], ws, ws, case_insensitive=True, max_matches=5
                    )
                if sub_res:
                    first_p = sub_res[0].split(":", 2)
                    sf = first_p[0]
                    sl = (
                        int(first_p[1])
                        if len(first_p) > 1 and first_p[1].isdigit()
                        else None
                    )
                    subterm_summaries.append(
                        SubtermMatchSummary(
                            subterm=sub,
                            match_count=len(sub_res),
                            sample_file=sf,
                            sample_lineno=sl,
                        )
                    )
                    sub_cmd = f'python3 grep.py "{sub}"'
                    if sub_cmd not in copy_pasteable_commands:
                        copy_pasteable_commands.append(sub_cmd)

            # d) Extract candidate symbols from AST & repository identifiers
            symbols = extract_candidate_symbols(target, ws)
            fuzzy_suggestions = get_fuzzy_suggestions(
                terms, symbols, top_n=5, cutoff=0.35
            )
            for fs in fuzzy_suggestions[:2]:
                f_cmd = f'python3 grep.py "{fs.symbol}"'
                if f_cmd not in copy_pasteable_commands:
                    copy_pasteable_commands.append(f_cmd)

            # e) Find similar repository files
            similar_files = find_similar_workspace_files(
                raw_phrase or " ".join(terms), ws, max_results=4
            )
            for sf in similar_files[:2]:
                sf_cmd = f'python3 grep.py "{first_term}" {sf}'
                if sf_cmd not in copy_pasteable_commands:
                    copy_pasteable_commands.append(sf_cmd)

            if not copy_pasteable_commands:
                copy_pasteable_commands.append(
                    f'python3 grep.py -i "{first_term}"'
                )
                copy_pasteable_commands.append(f'python3 grep.py "{first_term}"')

            # Formulate structured explanation & result
            status = (
                "REGEX_ERROR"
                if regex_diagnostics and not safe_terms
                else "ZERO_MATCHES"
            )
            summary_msg = f"Zero matches found for pattern '{pattern_display}' across {total_files} files in {target_display}."
            explanation = MatchExplanation(
                status=status,
                summary=summary_msg,
                case_sensitive=not is_case_insensitive,
                case_insensitive_count=len(ci_matches),
                other_locations_count=len(other_locations_matches),
                details=(
                    f"Found {len(ci_matches)} case-insensitive matches. "
                    f"Found {len(other_locations_matches)} matches in other workspace files. "
                    f"Generated {len(fuzzy_suggestions)} fuzzy symbol suggestions. "
                    f"Tested {len(subterm_summaries)} subterm matches."
                ),
                skipped_extensions=sorted(list(SKIP_EXTENSIONS)),
                skipped_dirs=sorted(list(SKIP_DIRS)),
            )

            result = FastGrepResult(
                query_terms=terms,
                target_path=target_display,
                total_files_scanned=total_files,
                total_matches=0,
                explanation=explanation,
                regex_diagnostics=regex_diagnostics,
                case_insensitive_matches=ci_matches,
                other_locations_matches=other_locations_matches,
                fuzzy_suggestions=fuzzy_suggestions,
                subterm_matches=subterm_summaries,
                similar_files=similar_files,
                suggestions=suggestions_list,
                copy_pasteable_commands=copy_pasteable_commands,
                path_warning=path_warning_msg,
                ranked_matches=[],
                top_ast_nodes=[],
            )

            if is_json:
                print(result.model_dump_json(indent=2))
                return 0

            # Deterministic zero matches explanation
            print(f"[fast-grep] {summary_msg}\n")
            print(
                f"ℹ️ SEARCH CONSTRAINTS & DIAGNOSTICS:\n"
                f"  - Scanned: {total_files} files in {target_display}\n"
                f"  - Skipped non-code extensions: {', '.join(sorted(list(SKIP_EXTENSIONS))[:12])} ...\n"
                f"  - Skipped noise directories: {', '.join(sorted(list(SKIP_DIRS))[:10])} ...\n"
            )

            # 1. Path filter too narrow report
            if other_locations_matches:
                print(
                    f"💡 PATH FILTER TOO NARROW: 0 matches in '{target_display}', but {len(other_locations_matches)} match(es) exist elsewhere in the workspace:"
                )
                for om in other_locations_matches[:5]:
                    print(
                        f"  - {om.file}:{om.lineno}: {om.content.strip()[:80]}"
                    )
                print(
                    f'  Try searching without path filter: python3 grep.py "{first_term}"\n'
                )

            # 2. Case-insensitive report
            if ci_matches:
                print(
                    f'💡 0 exact matches, but {len(ci_matches)} matches exist with -i / --ignore-case! Try: python3 grep.py -i "{pattern_display}"'
                )
                for m in ci_matches[:6]:
                    print(f"  - {m.file}:{m.lineno}: {m.content.strip()[:80]}")
                if len(ci_matches) > 6:
                    print(
                        f"  ... (+{len(ci_matches) - 6} additional case-insensitive matches)"
                    )
                print()

            # 3. Tokenized sub-terms report
            if subterm_summaries:
                print("💡 COMPOUND QUERY FAILED — TOKENIZED SUB-TERM MATCHES:")
                print(
                    f"  The full query '{pattern_display}' had 0 exact matches, but sub-terms exist:"
                )
                for st in subterm_summaries:
                    loc = (
                        f" in {st.sample_file}:{st.sample_lineno}"
                        if st.sample_file
                        else ""
                    )
                    print(
                        f"  - '{st.subterm}': {st.match_count} match(es){loc}"
                    )
                print()

            # 4. Fuzzy symbol suggestions
            if fuzzy_suggestions:
                print("🔍 SIMILAR SYMBOLS IN WORKSPACE (from AST):")
                for s in fuzzy_suggestions[:5]:
                    loc = f" in {s.source_file}" if s.source_file else ""
                    print(
                        f"  - {s.symbol} ({s.kind}{loc}) [similarity: {s.similarity:.2f}]"
                    )
                print()

            # 5. Similar repository files
            if similar_files:
                print("📁 RELEVANT REPOSITORY FILES:")
                for rf in similar_files:
                    print(f"  - {rf}")
                print()

            # 6. Actionable next steps for LLM
            print("🚀 ACTIONABLE NEXT STEPS FOR LLM:")
            for idx, cmd in enumerate(copy_pasteable_commands, start=1):
                print(f"  {idx}. {cmd}")
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
                is_def = bool(
                    not content.strip().startswith(
                        ("#", "//", "/*", "*", '"""', "'''")
                    )
                    and (
                        re.search(r"^\s*(async\s+def|def|class)\s+", content)
                        or re.search(r"^\s*@", content)
                    )
                )
                is_call_site = is_string_transform_line(content) and not is_def
                parsed.append(
                    GrepMatch(
                        file=fp,
                        lineno=lineno,
                        content=content,
                        score=sc,
                        scope_name=scope_name or None,
                        is_call_site=is_call_site,
                        is_definition=is_def,
                    )
                )

        parsed.sort(key=lambda m: m.score, reverse=True)
        ranked_matches = parsed[:max_matches]

        # Extract top 2 unique function scopes
        flashed: List[Tuple[GrepMatch, Dict[str, Any]]] = []
        seen = set()
        top_ast_nodes: List[ASTNodePreview] = []

        for m in ranked_matches:
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
                    if len(flashed) >= MAX_SCOPES_FLASHED:
                        break

        explanation = MatchExplanation(
            status="MATCHES_FOUND",
            summary=f"Found {len(parsed)} matches across {total_files} files in {target_display}.",
            case_sensitive=not is_case_insensitive,
            case_insensitive_count=0,
            other_locations_count=0,
            details=f"Top {len(flashed)} enclosing AST scopes flashed.",
            skipped_extensions=sorted(list(SKIP_EXTENSIONS)),
            skipped_dirs=sorted(list(SKIP_DIRS)),
        )

        result = FastGrepResult(
            query_terms=terms,
            target_path=target_display,
            total_files_scanned=total_files,
            total_matches=len(parsed),
            explanation=explanation,
            regex_diagnostics=regex_diagnostics,
            case_insensitive_matches=[],
            other_locations_matches=[],
            fuzzy_suggestions=[],
            subterm_matches=[],
            similar_files=[],
            suggestions=[],
            copy_pasteable_commands=[],
            path_warning=path_warning_msg,
            ranked_matches=ranked_matches,
            top_ast_nodes=top_ast_nodes,
        )

        if is_json:
            print(result.model_dump_json(indent=2))
            return 0

        # Output results concisely (capped under ADK context limit)
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
            is_def = m.is_definition
            is_transform_scope = sc.get("is_transform", False)

            scope_tag = ""
            if is_def and is_transform_scope:
                scope_tag = " [🎯 DEFINITION TARGET & TRANSFORM SCOPE]"
            elif is_def:
                scope_tag = " [🎯 DEFINITION TARGET]"
            elif is_transform_scope and is_call_site:
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
                truncated_text = text[:300]
                if lineno == target_lineno:
                    if is_def:
                        callout = "  <-- [DEFINITION TARGET]"
                    elif is_call_site:
                        callout = (
                            "  <-- [CALL-SITE: string/buffer transform]"
                        )
                    else:
                        callout = "  <-- [MATCH]"
                    return f"{lineno:4d}: >>> {truncated_text}{callout}"
                return f"{lineno:4d}:     {truncated_text}"

            rel_idx = max(0, min(len(lines) - 1, target_lineno - s_line))
            half_before = max(5, int(context_window * 0.375))
            half_after = max(5, context_window - half_before)

            if len(lines) > (context_window + 5):
                w_start = max(0, rel_idx - half_before)
                w_end = min(len(lines), rel_idx + half_after)
                display_lines = lines[w_start:w_end]
                disp_start_lineno = s_line + w_start
                if w_start > 0:
                    print(
                        f"  ... [{w_start} lines before in {s_name} omitted] ..."
                    )
                for i, l in enumerate(display_lines, start=disp_start_lineno):
                    print(format_line(i, l))
                if w_end < len(lines):
                    print(
                        f"  ... [{len(lines) - w_end} lines after in {s_name} omitted] ..."
                    )
            else:
                display_lines = lines
                w_start = 0
                w_end = len(lines)
                for i, l in enumerate(lines, start=s_line):
                    print(format_line(i, l))

            # Primary top match clean unadorned code block
            if idx == 1:
                clean_snippet = "\n".join(lines[w_start:w_end])
                print("\n[CLEAN CODE FOR edit_file (EXACT INDENTATION)]:")
                print("```python")
                print(clean_snippet)
                print("```")
            print()

        # Summary of other ranked matches
        print("-" * 80)
        print("📋 TOP MATCH PREVIEWS:")
        for m in ranked_matches[:MAX_DISPLAY_PREVIEWS]:
            snippet = m.content.strip()[:75]
            if m.is_definition:
                site_tag = " [DEF]"
            elif m.is_call_site:
                site_tag = " [CALL-SITE]"
            else:
                site_tag = ""
            print(f"  [{m.score:+3d}] {m.file}:{m.lineno}{site_tag}: {snippet}")

        if len(parsed) > MAX_DISPLAY_PREVIEWS:
            print(
                f"  ... ({len(parsed) - MAX_DISPLAY_PREVIEWS} additional matches truncated)"
            )

        return 0
    except Exception as e:
        print(f"[fast-grep] Search completed with fallback: {e}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
