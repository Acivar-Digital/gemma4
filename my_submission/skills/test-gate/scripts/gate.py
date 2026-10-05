#!/usr/bin/env python3
"""test-gate: Consolidated regression test runner, diff inspector, and patch readiness gatekeeper.

Consolidates blast-radius (distance-1 neighbor regression test runner) and diff-inspect
(safe git diff viewer) into a single authoritative gatekeeper skill.

Modes:
  1. Default or blast / --blast / -b:
     - Identifies modified Python files in git working tree.
     - Locates distance-1 neighbor tests (maps source files to test files).
     - Executes pytest on neighbor tests with timeout (default 60s per test file).
     - Reports clear summary: tests run, tests passed, tests failed, and failing traceback snippet.
  2. diff / --diff / -d:
     - Runs safe read-only git diff against HEAD.
     - Verifies NO test files in /workspace were modified. If modified, emits:
       🚨 FORBIDDEN TEST FILE MODIFIED IN /WORKSPACE
       explaining that Container B automatically reverts (discards) test-file modifications during evaluation.
       Instructs exact command: git checkout -- <file>.
     - Summarizes lines added, lines removed, files touched.
     - Diff truncation safety: truncates massive diffs (>80 lines or >6KB) with file-by-file summary.
  3. status / --status / -s:
     - Full patch readiness: modified files, test file safety check, syntax check on touched files,
       and recommendation on whether it is safe to run submit_patch.
     - Emits [✓ READY TO SUBMIT] when patch is 100% clean and ready.
  4. Actionable Diagnostics:
     - If no files modified, tells the LLM cleanly what files exist to test.
     - If tests fail, prints the exact failing test names, line numbers, statements, and guidance.
     - If non-existent flags or arguments passed, explains available options with copy-pasteable examples.
  5. --json / -j:
     - Returns 100% Pydantic v2 structured schemas.

Always exits with code 0.
"""

from __future__ import annotations

import ast
from collections import defaultdict
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

sys.dont_write_bytecode = True

from pydantic import BaseModel, ConfigDict, Field

ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
SKIP_DIRS = {"build", "dist", ".git", "__pycache__", "venv", ".venv", "node_modules", "wheels", ".pytest_cache"}

FORBIDDEN_HARNESS_FILES = {
    "pytest.ini",
    "conftest.py",
    "setup.cfg",
    "tox.ini",
    ".pre-commit-config.yaml",
}

SCRATCH_FILE_PATTERNS = [
    r"^repro.*\.py$",
    r"^.*_repro\.py$",
    r"^reproduce.*\.py$",
    r"^test.*\.py$",
    r"^.*_test\.py$",
    r"^tmp.*\.py$",
    r"^temp.*\.py$",
    r"^scratch.*\.py$",
    r"^run_.*\.py$",
    r"^debug.*\.py$",
    r"^poc.*\.py$",
    r"^solve.*\.py$",
    r"^check.*\.py$",
    r"^verify.*\.py$",
]

MAX_DIFF_LINES = 80
MAX_DIFF_BYTES = 6 * 1024  # 6 KB (6,144 bytes)


def strip_ansi(text: str) -> str:
    """Strip ANSI terminal escape codes from text."""
    return ANSI_ESCAPE.sub("", text)


# ==============================================================================
# Pydantic v2 Data Models
# ==============================================================================

class FailureDetail(BaseModel):
    """Detailed breakdown of an individual test failure."""

    model_config = ConfigDict(extra="ignore")

    test_id: str = Field(..., description="Test node ID, e.g. tests/test_routing.py::test_route")
    test_file: str = Field(default="", description="Path to test file")
    test_name: str = Field(default="", description="Name of test function or method")
    line_number: Optional[int] = Field(default=None, description="Line number of failure")
    error_type: str = Field(default="AssertionError", description="Exception type")
    error_message: str = Field(default="", description="Raw error message")
    failing_statement: str = Field(default="", description="Failing code statement")
    expected: Optional[str] = Field(default=None, description="Expected value")
    actual: Optional[str] = Field(default=None, description="Actual value")
    traceback_snippet: str = Field(default="", description="Cleaned traceback snippet")
    remediation_hint: str = Field(default="", description="Actionable hint for remediation")


class SyntaxErrorDetail(BaseModel):
    """Details of a Python syntax or compilation error."""

    model_config = ConfigDict(extra="ignore")

    file_path: str = Field(..., description="File with syntax error")
    line_number: int = Field(default=1, description="Line number")
    column: int = Field(default=1, description="Column number")
    error_type: str = Field(default="SyntaxError", description="SyntaxError or IndentationError")
    message: str = Field(..., description="Error message from parser")
    snippet: str = Field(default="", description="Code snippet with caret pointer")


class FileChangeStat(BaseModel):
    """File-level git change statistics and safety classifications."""

    model_config = ConfigDict(extra="ignore")

    path: str = Field(..., description="Relative file path")
    status: str = Field(default="M", description="Git status code (M, A, D, R, ??)")
    additions: int = Field(default=0, ge=0, description="Lines added")
    deletions: int = Field(default=0, ge=0, description="Lines deleted")
    binary: bool = Field(default=False, description="Whether file is binary")
    is_test_file: bool = Field(default=False, description="Whether file is part of the test suite")
    is_forbidden: bool = Field(default=False, description="Whether file is a forbidden test/harness file")
    is_scratch_file: bool = Field(default=False, description="Whether file is an untracked scratch file")


class TestGateResult(BaseModel):
    """Authoritative result schema for test-gate CLI."""

    model_config = ConfigDict(extra="ignore")

    mode: str = Field(..., description="Execution mode: blast, diff, status")
    workspace: str = Field(..., description="Resolved workspace root directory")
    success: bool = Field(default=True, description="True if check/run passed cleanly")
    status: str = Field(default="PASSED", description="High-level status code")
    modified_files: List[str] = Field(default_factory=list, description="Modified source files detected")
    untracked_files: List[str] = Field(default_factory=list, description="Untracked files detected")
    test_files_checked: List[str] = Field(default_factory=list, description="Test files executed or identified")
    tests_run: int = Field(default=0, ge=0, description="Count of tests executed")
    tests_passed: int = Field(default=0, ge=0, description="Count of tests passed")
    tests_failed: int = Field(default=0, ge=0, description="Count of tests failed")
    tests_errors: int = Field(default=0, ge=0, description="Count of test errors")
    failures: List[FailureDetail] = Field(default_factory=list, description="Detailed test failure breakdowns")
    file_stats: List[FileChangeStat] = Field(default_factory=list, description="File-by-file diff stats")
    total_files_modified: int = Field(default=0, ge=0, description="Total files touched")
    total_additions: int = Field(default=0, ge=0, description="Total lines added")
    total_deletions: int = Field(default=0, ge=0, description="Total lines deleted")
    forbidden_test_files: List[str] = Field(default_factory=list, description="Modified test files (forbidden in SWE-bench)")
    dangerous_scratch_files: List[str] = Field(default_factory=list, description="Untracked scratch files in /workspace")
    syntax_errors: List[SyntaxErrorDetail] = Field(default_factory=list, description="Syntax errors in touched files")
    can_submit_patch: bool = Field(default=False, description="True if patch is ready and safe for submit_patch")
    summary: str = Field(default="", description="Concise human-readable summary")
    recommendation: str = Field(default="", description="Explicit actionable recommendation")
    diff_preview: str = Field(default="", description="Unified diff preview (capped at 80 lines / 6KB)")


FailureDetail.model_rebuild()
SyntaxErrorDetail.model_rebuild()
FileChangeStat.model_rebuild()
TestGateResult.model_rebuild()


# ==============================================================================
# Helper Functions: Workspace & Classifications
# ==============================================================================

def get_workspace_dir(explicit_ws: Optional[str] = None) -> pathlib.Path:
    """Robustly and deterministically locate the target repository workspace directory."""
    if explicit_ws:
        p = pathlib.Path(explicit_ws)
        if p.is_dir():
            return p.resolve()

    # 1. Check caller stack frame for _orig_cwd (set by ADK harness)
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

    # 2. Environment variable overrides
    for env_var in ("SWEGEMMA_WORKSPACE", "WORKSPACE_DIR"):
        val = os.environ.get(env_var)
        if val:
            p = pathlib.Path(val)
            if p.is_dir():
                return p.resolve()

    # 3. Search upward from current working directory for repository markers
    cur = pathlib.Path.cwd().resolve()
    for parent in [cur] + list(cur.parents):
        if (
            (parent / ".git").exists()
            or (parent / "pyproject.toml").exists()
            or (parent / "setup.py").exists()
            or (parent / "setup.cfg").exists()
        ):
            return parent

    # 4. Standard container workspace fallback
    ws_fixed = pathlib.Path("/workspace")
    if ws_fixed.is_dir():
        return ws_fixed.resolve()

    return cur


def is_git_repo(ws: pathlib.Path) -> bool:
    """Check if directory is inside a valid git working tree."""
    code, _ = run_git_cmd(["rev-parse", "--is-inside-work-tree"], cwd=ws, timeout_secs=5)
    return code == 0


def is_test_file(path_str: str) -> bool:
    """Check if file is part of the test suite."""
    p = pathlib.Path(path_str)
    name = p.name.lower()
    parts_lower = [part.lower() for part in p.parts]

    if any(part in ("tests", "test", "testing") for part in parts_lower):
        return True
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    if name in ("conftest.py", "pytest.ini"):
        return True
    return False


def is_forbidden_harness_file(path_str: str) -> bool:
    """Check if file is a forbidden harness configuration or test configuration."""
    p = pathlib.Path(path_str)
    name = p.name.lower()
    if name in FORBIDDEN_HARNESS_FILES:
        return True
    if is_test_file(path_str):
        return True
    return False


def is_scratch_file(path_str: str) -> bool:
    """Check if file matches temporary, reproduction, or scratch script patterns."""
    p = pathlib.Path(path_str)
    name = p.name.lower()

    if ".adk_exec" in name or name.startswith(".adk_exec"):
        return False
    if name.endswith((".tmp", ".temp", ".log", ".bak", ".swp", "~")):
        return True

    for pat in SCRATCH_FILE_PATTERNS:
        if re.match(pat, name):
            return True

    if len(p.parts) == 1 and name.endswith(".py"):
        # Root-level python scripts not matching standard project files
        if name not in ("setup.py", "conftest.py", "__init__.py"):
            return True

    parts_lower = [part.lower() for part in p.parts]
    if any(part in ("tmp", "temp", "scratch") for part in parts_lower):
        return True

    return False


def run_git_cmd(args: List[str], cwd: pathlib.Path, timeout_secs: int = 15) -> Tuple[int, str]:
    """Execute a git command safely in cwd without raising unhandled exceptions."""
    git_bin = shutil.which("git") or "git"
    try:
        res = subprocess.run(
            [git_bin] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout_secs,
        )
        out = res.stdout if res.stdout else res.stderr
        return res.returncode, out.rstrip()
    except subprocess.TimeoutExpired:
        return 1, f"Git command timed out after {timeout_secs}s: git {' '.join(args)}"
    except Exception as e:
        return 1, f"Git command error: {e}"


def get_git_status_and_files(ws: pathlib.Path) -> Tuple[List[str], List[str], Dict[str, str]]:
    """Query git status to return (modified_files, untracked_files, status_map)."""
    if not is_git_repo(ws):
        return [], [], {}

    code, out = run_git_cmd(
        ["status", "--porcelain", "-uall", "--", ".", ":(exclude)*.adk_exec*", ":(exclude)**/.adk_exec*"],
        cwd=ws,
        timeout_secs=10,
    )
    if code != 0:
        code, out = run_git_cmd(["status", "--porcelain"], cwd=ws, timeout_secs=10)

    modified_files: List[str] = []
    untracked_files: List[str] = []
    status_map: Dict[str, str] = {}

    if code == 0 and out:
        for raw_line in out.splitlines():
            line = raw_line.rstrip()
            if not line:
                continue
            parts = line.strip().split(maxsplit=1)
            if len(parts) < 2:
                continue
            code_str = parts[0]
            rel_path = parts[1].strip('"')
            if " -> " in rel_path:
                rel_path = rel_path.split(" -> ")[-1].strip().strip('"')

            if ".adk_exec" in rel_path or pathlib.Path(rel_path).name.startswith(".adk_exec"):
                continue

            if code_str == "??":
                untracked_files.append(rel_path)
            else:
                status_map[rel_path] = code_str or "M"
                if "D" not in code_str:
                    modified_files.append(rel_path)

    return modified_files, untracked_files, status_map


# ==============================================================================
# Syntax Verification
# ==============================================================================

def generate_syntax_snippet(source_lines: List[str], lineno: int, column: int) -> str:
    """Generate code snippet with visual caret pointer at line and column."""
    if not source_lines:
        return ""
    target_idx = max(0, min(len(source_lines) - 1, lineno - 1))
    start_idx = max(0, target_idx - 1)
    end_idx = min(len(source_lines), target_idx + 2)

    width = max(len(str(end_idx)), 2)
    out: List[str] = []
    for idx in range(start_idx, end_idx):
        line_num = idx + 1
        num_str = str(line_num).rjust(width)
        line_content = source_lines[idx].rstrip("\r\n")
        if idx == target_idx:
            out.append(f"> {num_str} | {line_content.expandtabs(4)}")
            prefix = line_content[: max(0, column - 1)].expandtabs(4)
            out.append(f"  {' ' * width} | {' ' * len(prefix)}^")
        else:
            out.append(f"  {num_str} | {line_content.expandtabs(4)}")
    return "\n".join(out)


def verify_python_syntax(file_path: pathlib.Path) -> Optional[SyntaxErrorDetail]:
    """Parse a Python file using AST and return a SyntaxErrorDetail if invalid."""
    if not file_path.exists() or not file_path.is_file():
        return None
    try:
        raw_bytes = file_path.read_bytes()
    except Exception as e:
        return SyntaxErrorDetail(
            file_path=str(file_path),
            line_number=1,
            column=1,
            error_type="FileReadError",
            message=f"Could not read file: {e}",
            snippet="> 1 | (unreadable file)",
        )

    # Detect binary files containing null bytes
    if b"\x00" in raw_bytes[:4096]:
        return SyntaxErrorDetail(
            file_path=str(file_path),
            line_number=1,
            column=1,
            error_type="BinaryFileError",
            message="File contains binary or null bytes; cannot parse as Python source.",
            snippet="> 1 | (binary file)",
        )

    try:
        source_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        source_text = raw_bytes.decode("latin-1", errors="replace")

    source_lines = source_text.splitlines()

    try:
        ast.parse(raw_bytes, filename=str(file_path))
    except SyntaxError as e:
        lineno = e.lineno or 1
        col = e.offset or 1
        error_type = type(e).__name__
        msg = e.msg or "syntax error"
        snippet = generate_syntax_snippet(source_lines, lineno, col)
        return SyntaxErrorDetail(
            file_path=str(file_path),
            line_number=lineno,
            column=col,
            error_type=error_type,
            message=msg,
            snippet=snippet,
        )
    except Exception as e:
        return SyntaxErrorDetail(
            file_path=str(file_path),
            line_number=1,
            column=1,
            error_type=type(e).__name__,
            message=str(e),
            snippet="> 1 | (parse error)",
        )

    return None


# ==============================================================================
# Neighbor Test Resolution & Blast Radius Discovery
# ==============================================================================

def resolve_docs_src_test_path(path_str: str) -> Optional[str]:
    """Framework-aware path mapping for FastAPI doc tutorials.

    Maps docs_src/<category>/tutorial<N>[_<variant>].py to
    tests/test_tutorial/test_<category>/test_tutorial<N>.py (stripping _py310, _py39, etc.).
    """
    clean_p = path_str.replace("\\", "/").strip().lstrip("/")
    parts = clean_p.split("/")
    if "docs_src" not in parts:
        return None
    idx = parts.index("docs_src")
    subparts = parts[idx + 1:]
    if len(subparts) < 2:
        return None

    category_parts = subparts[:-1]
    filename = subparts[-1]
    stem = filename[:-3] if filename.endswith(".py") else filename

    m = re.match(r"^(tutorial\d+[a-z]?)(?:_.*)?$", stem)
    base_stem = m.group(1) if m else re.sub(r"(_(?:an|py3\d+|py\d+|pv\d+|non_annotated|annotated))+$", "", stem)

    category = "_".join(category_parts)
    clean_category = category[5:] if category.startswith("test_") else category
    return f"tests/test_tutorial/test_{clean_category}/test_{base_stem}.py"


def extract_ast_symbols(file_path: pathlib.Path) -> Set[str]:
    """Extract top-level class and function names from a Python source file."""
    symbols: Set[str] = set()
    if not file_path.exists() or file_path.suffix != ".py":
        return symbols
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(content, filename=str(file_path))
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                symbols.add(node.name)
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not item.name.startswith("__"):
                            symbols.add(item.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("__"):
                    symbols.add(node.name)
    except Exception:
        pass
    return {s for s in symbols if len(s) > 1}


def find_neighbor_tests_for_target(target_path: pathlib.Path, ws: pathlib.Path) -> List[str]:
    """Locate distance-1 neighbor tests for a source target file."""
    try:
        rel_target = target_path.relative_to(ws)
    except ValueError:
        rel_target = target_path

    rel_posix = rel_target.as_posix()
    stem = target_path.stem

    # If target is already a test file, return it directly
    if is_test_file(rel_posix):
        return [rel_posix]

    direct_tests: List[str] = []

    # 1. Framework-aware mapping (e.g. FastAPI docs tutorials)
    docs_cand = resolve_docs_src_test_path(rel_posix)
    if docs_cand:
        cp = ws / docs_cand
        if cp.exists():
            direct_tests.append(cp.relative_to(ws).as_posix())

    # 2. Canonical neighbor candidates
    target_mod_parts = list(rel_target.parts)
    if target_mod_parts and target_mod_parts[-1].endswith(".py"):
        target_mod_parts[-1] = target_mod_parts[-1][:-3]
    full_mod_name = "_".join(target_mod_parts)

    candidates = [
        f"tests/test_{stem}.py",
        f"test/test_{stem}.py",
        f"tests/{stem}_test.py",
        f"test_{stem}.py",
        f"tests/test_{full_mod_name}.py",
    ]
    if len(rel_target.parts) > 1:
        candidates.append(f"tests/{'/'.join(rel_target.parts[:-1])}/test_{stem}.py")

    for cand in candidates:
        cp = ws / cand
        if cp.exists():
            rel_cand = cp.relative_to(ws).as_posix()
            if rel_cand not in direct_tests:
                direct_tests.append(rel_cand)

    # 3. Search repo for test_<stem>.py if not yet resolved
    if not direct_tests:
        try:
            for match in ws.rglob(f"test_{stem}.py"):
                if not any(part in SKIP_DIRS for part in match.parts):
                    direct_tests.append(match.relative_to(ws).as_posix())
                    break
        except Exception:
            pass

    # 4. Symbol-level test scan
    symbols = extract_ast_symbols(target_path)
    if symbols and len(direct_tests) < 4:
        cand_test_files: List[pathlib.Path] = []
        try:
            for p in ws.rglob("*.py"):
                if any(part in SKIP_DIRS for part in p.parts):
                    continue
                if is_test_file(str(p.relative_to(ws))):
                    cand_test_files.append(p)
        except Exception:
            pass

        for tf in cand_test_files:
            rel_tf = tf.relative_to(ws).as_posix()
            if rel_tf in direct_tests:
                continue
            try:
                txt = tf.read_text(encoding="utf-8", errors="replace")
                if any(sym in txt for sym in symbols):
                    direct_tests.append(rel_tf)
                    if len(direct_tests) >= 5:
                        break
            except Exception:
                continue

    # 5. Distance-1 consumer test resolution
    consumer_tests: List[str] = []
    mod_name_dot = ".".join(target_mod_parts)
    try:
        for p in ws.rglob("*.py"):
            if any(part in SKIP_DIRS for part in p.parts) or p == target_path:
                continue
            rel_p = p.relative_to(ws).as_posix()
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
                if stem not in content and mod_name_dot not in content:
                    continue
            except Exception:
                continue

            if is_test_file(rel_p):
                if rel_p not in direct_tests and rel_p not in consumer_tests:
                    consumer_tests.append(rel_p)
            else:
                c_stem = p.stem
                for c_cand in (f"tests/test_{c_stem}.py", f"test/test_{c_stem}.py", f"tests/{c_stem}_test.py"):
                    cp = ws / c_cand
                    if cp.exists():
                        rel_cp = cp.relative_to(ws).as_posix()
                        if rel_cp not in direct_tests and rel_cp not in consumer_tests:
                            consumer_tests.append(rel_cp)
    except Exception:
        pass

    all_tests = direct_tests + consumer_tests
    # Deduplicate and cap to 8 files for fast execution
    seen: Set[str] = set()
    deduped: List[str] = []
    for t in all_tests:
        if t not in seen:
            seen.add(t)
            deduped.append(t)
    return deduped[:8]


# ==============================================================================
# Pytest Runner & Output Parser
# ==============================================================================

def find_pytest_command(ws: pathlib.Path) -> List[str]:
    """Find the most appropriate pytest runner executable."""
    # 1. Active virtualenv or interpreter directory
    for base in (pathlib.Path(sys.executable).parent, pathlib.Path(sys.prefix) / "bin"):
        cand = base / "pytest"
        if cand.is_file() and os.access(cand, os.X_OK):
            return [str(cand)]

    # 2. VIRTUAL_ENV env var
    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        v_cand = pathlib.Path(venv) / "bin" / "pytest"
        if v_cand.is_file() and os.access(v_cand, os.X_OK):
            return [str(v_cand)]

    # 3. Workspace venvs
    for vname in (".venv", "venv"):
        v_cand = ws / vname / "bin" / "pytest"
        if v_cand.is_file() and os.access(v_cand, os.X_OK):
            return [str(v_cand)]

    # 4. Standard container paths
    for vpath in ("/venv", "/opt/venv", "/root/.venv"):
        v_cand = pathlib.Path(vpath) / "bin" / "pytest"
        if v_cand.is_file() and os.access(v_cand, os.X_OK):
            return [str(v_cand)]

    # 5. Check if active interpreter has pytest
    try:
        if importlib.util.find_spec("pytest") is not None:
            return [sys.executable, "-m", "pytest"]
    except Exception:
        pass

    # 6. Fallback PATH
    pytest_bin = shutil.which("pytest")
    if pytest_bin:
        return [pytest_bin]

    return [sys.executable or "python3", "-m", "pytest"]


def run_pytest_suite(test_files: List[str], ws: pathlib.Path, timeout_secs: int = 60) -> Tuple[int, str]:
    """Run pytest on the given test files with workspace in PYTHONPATH and timeout protection."""
    cmd_base = find_pytest_command(ws)
    cmd = cmd_base + ["-vv", "--tb=short", "--disable-warnings"] + test_files

    env = os.environ.copy()
    pp_parts: List[str] = [str(ws)]
    if "/workspace" not in pp_parts:
        pp_parts.append("/workspace")
    existing_pp = env.get("PYTHONPATH", "")
    if existing_pp:
        for p in existing_pp.split(":"):
            if p and p not in pp_parts:
                pp_parts.append(p)
    env["PYTHONPATH"] = ":".join(pp_parts)

    try:
        res = subprocess.run(
            cmd,
            cwd=ws,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_secs,
        )
        return res.returncode, (res.stdout + "\n" + res.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, f"[test-gate] Pytest timed out after {timeout_secs}s on: {', '.join(test_files)}"
    except Exception as e:
        return 1, f"[test-gate] Pytest error: {e}"


def parse_pytest_results(
    raw_output: str,
    ws: pathlib.Path,
    test_files: Optional[List[str]] = None,
    timeout_secs: Optional[int] = None,
) -> Tuple[int, int, int, List[FailureDetail]]:
    """Parse pytest summary and detailed failures from output."""
    clean_out = strip_ansi(raw_output)
    lines = clean_out.splitlines()

    total_passed = 0
    total_failed = 0
    total_errors = 0

    for line in reversed(lines):
        s = line.strip("= ").strip().lower()
        if "passed" in s or "failed" in s or "error" in s:
            pm = re.search(r"(\d+)\s+passed", s)
            if pm:
                total_passed = int(pm.group(1))
            fm = re.search(r"(\d+)\s+failed", s)
            if fm:
                total_failed = int(fm.group(1))
            em = re.search(r"(\d+)\s+error", s)
            if em:
                total_errors = int(em.group(1))
            break

    # Check for timeout condition
    if "timed out after" in clean_out.lower():
        total_failed = max(1, total_failed)
        return (
            total_passed,
            total_failed,
            total_errors,
            [
                FailureDetail(
                    test_id=f"timeout::{test_files[0] if test_files else 'neighbor_tests'}",
                    test_file=test_files[0] if test_files else "",
                    test_name="pytest_timeout",
                    line_number=None,
                    error_type="TimeoutExpired",
                    error_message=clean_out.strip().splitlines()[-1] if clean_out.strip() else "Pytest timed out",
                    failing_statement=f"Execution timed out after {timeout_secs or 60}s",
                    expected="Tests to complete within timeout limit",
                    actual=f"Timed out after {timeout_secs or 60}s",
                    traceback_snippet=clean_out.strip()[:600],
                    remediation_hint=f"Pytest execution timed out after {timeout_secs or 60}s. Check for infinite loops, deadlocks, or slow fixtures. Increase timeout with -t <secs> or --timeout <secs>.",
                )
            ],
        )

    # Parse failure blocks
    header_re = re.compile(r"^_{3,}\s+(.*?)\s+_{3,}$")
    loc_re = re.compile(r"^(.*?):(\d+):\s+in\s+(\S+)")
    assert_eq_re = re.compile(r"(?:AssertionError:\s+)?assert\s+(.+?)\s+==\s+(.+)$")
    err_re = re.compile(r"^E\s+([A-Za-z_][A-Za-z0-9_]*Error|[A-Za-z_][A-Za-z0-9_]*Exception):\s*(.*)$")

    blocks: List[Tuple[str, List[str]]] = []
    current_header: Optional[str] = None
    current_lines: List[str] = []

    for line in lines:
        clean = line.strip()
        m = header_re.match(clean)
        if m:
            if current_header and current_lines:
                blocks.append((current_header, current_lines))
            current_header = m.group(1).strip()
            current_lines = []
        elif current_header is not None:
            if clean.startswith("=") and ("short test summary info" in clean or "failed" in clean or "passed" in clean):
                blocks.append((current_header, current_lines))
                current_header = None
                current_lines = []
            else:
                current_lines.append(line)

    if current_header and current_lines:
        blocks.append((current_header, current_lines))

    failures: List[FailureDetail] = []
    for header, blines in blocks:
        test_file = ""
        line_no = None
        func_name = header
        error_type = "AssertionError"
        error_msg = ""
        failing_stmt = ""
        expected = None
        actual = None
        snippet_lines: List[str] = []

        for bline in blines:
            sline = bline.strip()
            lm = loc_re.match(sline)
            if lm:
                test_file = lm.group(1)
                line_no = int(lm.group(2))
                func_name = lm.group(3)
                continue

            if sline.startswith("E   ") or sline.startswith("E "):
                e_content = sline[2:].strip()
                snippet_lines.append(sline)
                em = err_re.match(sline)
                if em:
                    error_type = em.group(1)
                    error_msg = em.group(2).strip()
                elif "assert " in sline and not error_msg:
                    error_type = "AssertionError"
                    error_msg = e_content

                am = assert_eq_re.search(e_content)
                if am:
                    actual = am.group(1).strip()
                    expected = am.group(2).strip()
            elif sline.startswith("assert ") and not failing_stmt:
                failing_stmt = sline
                snippet_lines.append(sline)

        # Build clean test id
        test_id = f"{test_file}::{func_name}" if test_file else func_name
        tb_snippet = "\n".join(snippet_lines[:8]) if snippet_lines else "\n".join(blines[:6])

        hint = f"Fix implementation in source code causing `{failing_stmt or error_msg or 'failure'}`."
        if expected and actual:
            hint = f"Expected `{expected}` but produced `{actual}`. Align return values or edge case handling."

        failures.append(
            FailureDetail(
                test_id=test_id,
                test_file=test_file,
                test_name=func_name,
                line_number=line_no,
                error_type=error_type,
                error_message=error_msg,
                failing_statement=failing_stmt,
                expected=expected,
                actual=actual,
                traceback_snippet=tb_snippet,
                remediation_hint=hint,
            )
        )

    # Fallback if pytest failed without standard block headers (e.g. collection error)
    if total_failed == 0 and total_errors > 0 and not failures:
        err_lines = [l for l in lines if l.startswith("E   ") or "error" in l.lower()]
        failures.append(
            FailureDetail(
                test_id=test_files[0] if test_files else "pytest_suite",
                test_file=test_files[0] if test_files else "",
                test_name="pytest_error",
                error_type="PytestError",
                error_message=err_lines[0].strip() if err_lines else "Pytest error occurred during suite execution",
                traceback_snippet="\n".join(err_lines[:8]) if err_lines else clean_out[:400],
                remediation_hint="Inspect pytest error output and fix syntax or import errors.",
            )
        )

    return total_passed, total_failed, total_errors, failures


# ==============================================================================
# Mode Handlers: blast, diff, status
# ==============================================================================

def execute_blast(
    ws: pathlib.Path,
    target_args: List[str],
    timeout_per_file: int = 60,
) -> TestGateResult:
    """Execute Mode 1: Distance-1 Neighbor Regression Test Runner."""
    if not is_git_repo(ws) and not target_args:
        return TestGateResult(
            mode="blast",
            workspace=str(ws),
            success=False,
            status="NOT_A_GIT_REPOSITORY",
            summary=f"Workspace '{ws}' is not a git repository.",
            recommendation="Initialize git or specify a valid repository path with --workspace <dir>.",
        )

    modified_files, untracked, _ = get_git_status_and_files(ws)

    # Check for forbidden test files in /workspace
    forbidden_modified: List[str] = [f for f in modified_files if is_forbidden_harness_file(f)]
    for u in untracked:
        if is_test_file(u):
            forbidden_modified.append(u)

    # Determine targets: explicit target args or git modified files
    targets: List[pathlib.Path] = []
    if target_args:
        for targ in target_args:
            p = ws / targ if not pathlib.Path(targ).is_absolute() else pathlib.Path(targ)
            if p.exists():
                targets.append(p)
            else:
                # Try finding across repo
                cands = list(ws.rglob(pathlib.Path(targ).name))
                if cands:
                    targets.append(cands[0])
                else:
                    targets.append(p)
    else:
        for m in modified_files:
            if m.endswith(".py"):
                p = ws / m
                if p.exists():
                    targets.append(p)

    # Actionable diagnostics if no files modified or targets specified
    if not targets:
        sample_files: List[str] = []
        try:
            for py_f in ws.rglob("*.py"):
                if any(part in SKIP_DIRS for part in py_f.parts):
                    continue
                rel = py_f.relative_to(ws).as_posix()
                if not is_test_file(rel):
                    sample_files.append(rel)
                    if len(sample_files) >= 6:
                        break
        except Exception:
            pass

        msg = (
            "No modified files detected in git working tree and no target specified.\n"
            f"Available source modules to test:\n"
            + "\n".join(f"  • {f}" for f in sample_files)
            + '\nUsage: run_skill_script with skill_name: "test-gate", file_path: "gate.py", args: ["--blast", "<path/to/file.py>"]'
            + '\n   or: args: ["--blast", "<path/to/file.py>"]'
        )

        return TestGateResult(
            mode="blast",
            workspace=str(ws),
            success=True,
            status="CLEAN_NO_TARGETS",
            modified_files=[],
            untracked_files=untracked,
            test_files_checked=[],
            tests_run=0,
            tests_passed=0,
            tests_failed=0,
            tests_errors=0,
            failures=[],
            forbidden_test_files=forbidden_modified,
            summary="No modified files detected in working tree.",
            recommendation=msg,
        )

    # Resolve neighbor test files for all targets
    test_files: List[str] = []
    for targ in targets:
        neighbors = find_neighbor_tests_for_target(targ, ws)
        for n in neighbors:
            if n not in test_files:
                test_files.append(n)

    target_names = [t.relative_to(ws).as_posix() if ws in t.parents else t.name for t in targets]

    if not test_files:
        summary = f"UNVERIFIED_NO_TESTS: 0 matching neighbor test files found for target(s): {', '.join(target_names)}."
        rec = "VERIFICATION REQUIRED: No tests were run. Write or execute a targeted test before calling submit_patch()."
        return TestGateResult(
            mode="blast",
            workspace=str(ws),
            success=False,
            status="UNVERIFIED_NO_TESTS",
            modified_files=target_names,
            untracked_files=untracked,
            test_files_checked=[],
            tests_run=0,
            tests_passed=0,
            tests_failed=0,
            tests_errors=0,
            failures=[],
            forbidden_test_files=forbidden_modified,
            summary=summary,
            recommendation=rec,
        )

    timeout = max(timeout_per_file, len(test_files) * timeout_per_file)
    exit_code, raw_output = run_pytest_suite(test_files, ws, timeout_secs=timeout)
    passed_cnt, failed_cnt, err_cnt, failures = parse_pytest_results(
        raw_output,
        ws,
        test_files=test_files,
        timeout_secs=timeout,
    )

    total_run = passed_cnt + failed_cnt + err_cnt
    if total_run == 0 and exit_code != 0:
        failed_cnt = max(1, len(failures) or 1)
        total_run = failed_cnt

    has_forbidden = len(forbidden_modified) > 0
    success = (exit_code == 0 and failed_cnt == 0 and err_cnt == 0 and not has_forbidden)
    status_str = "PASSED" if success else ("BLOCKED_FORBIDDEN_TEST_FILE" if has_forbidden else "FAILED")

    if success:
        summary = f"PASSED: {passed_cnt} test(s) passed across neighbor test suite ({', '.join(test_files)})."
        rec = "Regression gate clean. Changes pass distance-1 neighbor tests."
    else:
        failing_names = [f.test_id for f in failures]
        f_list = ", ".join(failing_names[:5])
        summary = f"FAILED: {failed_cnt} test(s) failed ({f_list}) across {len(test_files)} neighbor test file(s)."
        rec = (
            f"Exact failing tests:\n"
            + "\n".join(f"  ✗ {t}" for t in failing_names)
            + '\nGuidance: Fix the logic causing test failures in your modified files before calling submit_patch(). Inspect the failing statements and expected vs actual values above, then re-run run_skill_script with skill_name: "test-gate", file_path: "gate.py", args: [].'
        )

    return TestGateResult(
        mode="blast",
        workspace=str(ws),
        success=success,
        status=status_str,
        modified_files=target_names,
        untracked_files=untracked,
        test_files_checked=test_files,
        tests_run=total_run,
        tests_passed=passed_cnt,
        tests_failed=failed_cnt,
        tests_errors=err_cnt,
        failures=failures,
        forbidden_test_files=forbidden_modified,
        summary=summary,
        recommendation=rec,
    )


def execute_diff(ws: pathlib.Path, extra_args: Optional[List[str]] = None) -> TestGateResult:
    """Execute Mode 2: Safe Git Diff Viewer & Safety Assertion Gate with Diff Truncation."""
    if not is_git_repo(ws):
        return TestGateResult(
            mode="diff",
            workspace=str(ws),
            success=False,
            status="NOT_A_GIT_REPOSITORY",
            summary=f"Workspace '{ws}' is not a git repository.",
            recommendation="Initialize git or specify a valid repository path with --workspace <dir>.",
        )

    modified_files, untracked, status_map = get_git_status_and_files(ws)

    # 1. Parse git diff --numstat HEAD
    numstat_cmd = ["diff", "--numstat", "HEAD", "--", ".", ":(exclude)*.adk_exec*", ":(exclude)**/.adk_exec*"]
    code, numstat_out = run_git_cmd(numstat_cmd, cwd=ws, timeout_secs=10)
    if code != 0:
        code, numstat_out = run_git_cmd(["diff", "--numstat"], cwd=ws, timeout_secs=10)

    file_stats: List[FileChangeStat] = []
    forbidden_modified: List[str] = []
    dangerous_scratch: List[str] = []
    total_adds = 0
    total_dels = 0

    if code == 0 and numstat_out:
        for line in numstat_out.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                add_str, del_str, raw_p = parts[0], parts[1], parts[2]
                is_bin = (add_str == "-" and del_str == "-")
                adds = int(add_str) if not is_bin and add_str.isdigit() else 0
                dels = int(del_str) if not is_bin and del_str.isdigit() else 0

                clean_p = raw_p
                if " => " in clean_p:
                    clean_p = clean_p.split(" => ")[-1].strip()

                if ".adk_exec" in clean_p:
                    continue

                total_adds += adds
                total_dels += dels

                is_test = is_test_file(clean_p)
                is_forbid = is_forbidden_harness_file(clean_p)
                is_scratch = is_scratch_file(clean_p)

                if is_forbid or is_test:
                    forbidden_modified.append(clean_p)

                file_stats.append(
                    FileChangeStat(
                        path=clean_p,
                        status=status_map.get(clean_p, "M"),
                        additions=adds,
                        deletions=dels,
                        binary=is_bin,
                        is_test_file=is_test,
                        is_forbidden=is_forbid,
                        is_scratch_file=is_scratch,
                    )
                )

    # Check untracked files for scratch files and test files
    for u in untracked:
        if is_scratch_file(u):
            dangerous_scratch.append(u)
        if is_test_file(u):
            forbidden_modified.append(u)

    # 2. Get unified diff preview capped at MAX_DIFF_LINES / MAX_DIFF_BYTES
    diff_cmd = ["diff", "HEAD", "--", ".", ":(exclude)*.adk_exec*", ":(exclude)**/.adk_exec*"]
    if extra_args:
        diff_cmd = ["diff", "HEAD"] + extra_args + ["--", ".", ":(exclude)*.adk_exec*", ":(exclude)**/.adk_exec*"]
    code, diff_out = run_git_cmd(diff_cmd, cwd=ws, timeout_secs=15)
    if code != 0:
        code, diff_out = run_git_cmd(["diff"], cwd=ws, timeout_secs=15)

    diff_lines = diff_out.splitlines() if diff_out else []
    total_diff_lines = len(diff_lines)
    truncated_lines: List[str] = []
    accumulated_bytes = 0
    is_truncated = False

    for idx, line in enumerate(diff_lines):
        line_bytes = len(line.encode("utf-8", errors="replace")) + 1
        if idx >= MAX_DIFF_LINES or (accumulated_bytes + line_bytes > MAX_DIFF_BYTES):
            is_truncated = True
            break
        truncated_lines.append(line)
        accumulated_bytes += line_bytes

    total_files = len(file_stats)

    if is_truncated:
        preview = "\n".join(truncated_lines)
        if preview:
            preview += "\n\n"
        preview += (
            "... [TRUNCATED: Diff preview exceeded 80 lines / 6KB ceiling. "
            "Use read_file to inspect individual modified files directly]\n\n"
            "File-by-file summary of changes:\n"
        )
        for stat in file_stats:
            tag = " [FORBIDDEN TEST]" if stat.is_forbidden else ""
            preview += f"  • {stat.path}: +{stat.additions}, -{stat.deletions} [{stat.status}]{tag}\n"
        preview += f"Total changes: {total_files} file(s) touched (+{total_adds} additions, -{total_dels} deletions)"
    else:
        preview = "\n".join(diff_lines)

    is_clean = (total_files == 0 and not diff_out)

    # Safety Assertions
    has_forbidden = len(forbidden_modified) > 0
    has_scratch = len(dangerous_scratch) > 0

    if has_forbidden:
        status_str = "BLOCKED_FORBIDDEN_TEST_FILE"
        success = False
        summary = (
            f"🚨 FORBIDDEN TEST FILE MODIFIED IN /WORKSPACE ({', '.join(forbidden_modified)})\n"
            f"Container B automatically reverts (discards) test-file modifications during evaluation.\n"
            f"Your patch must resolve the defect exclusively in the source codebase, never by altering existing test files."
        )
        rec = (
            "To revert forbidden test file modifications, run:\n"
            + "\n".join(f"  git checkout -- {f}" for f in forbidden_modified)
        )
    elif is_clean:
        status_str = "CLEAN"
        success = True
        summary = "Working tree is clean. 0 files modified relative to HEAD."
        rec = "No changes to inspect. Implement fix in source files before calling submit_patch()."
    else:
        status_str = "MODIFIED"
        success = True
        summary = f"{total_files} file(s) touched: +{total_adds} additions, -{total_dels} deletions."
        if has_scratch:
            rec = (
                f"⚠️ DANGER: Untracked scratch files in /workspace ({', '.join(dangerous_scratch)}). "
                f"Remove them or move them to /tmp before submitting!"
            )
        else:
            rec = "Diff inspection clean of forbidden test files."

    return TestGateResult(
        mode="diff",
        workspace=str(ws),
        success=success,
        status=status_str,
        modified_files=[f.path for f in file_stats],
        untracked_files=untracked,
        file_stats=file_stats,
        total_files_modified=total_files,
        total_additions=total_adds,
        total_deletions=total_dels,
        forbidden_test_files=forbidden_modified,
        dangerous_scratch_files=dangerous_scratch,
        can_submit_patch=(not has_forbidden and not has_scratch and not is_clean),
        summary=summary,
        recommendation=rec,
        diff_preview=preview or "(no diff)",
    )


def execute_status(ws: pathlib.Path) -> TestGateResult:
    """Execute Mode 3: Full Patch Readiness & Pre-Submission Gate."""
    if not is_git_repo(ws):
        return TestGateResult(
            mode="status",
            workspace=str(ws),
            success=False,
            status="NOT_A_GIT_REPOSITORY",
            summary=f"Workspace '{ws}' is not a git repository.",
            recommendation="Initialize git or specify a valid repository path with --workspace <dir>.",
        )

    diff_res = execute_diff(ws)

    # Collect Python files touched for syntax verification
    modified_py = [f for f in diff_res.modified_files if f.endswith(".py")]
    syntax_errors: List[SyntaxErrorDetail] = []
    for rel_py in modified_py:
        err = verify_python_syntax(ws / rel_py)
        if err:
            syntax_errors.append(err)

    has_forbidden = len(diff_res.forbidden_test_files) > 0
    has_scratch = len(diff_res.dangerous_scratch_files) > 0
    has_syntax_err = len(syntax_errors) > 0
    is_clean = (diff_res.total_files_modified == 0)

    # Determine readiness and final recommendation
    can_submit = False
    if is_clean:
        status_str = "BLOCKED_EMPTY_DIFF"
        summary = "BLOCKED: Working tree is clean (0 files modified relative to HEAD)."
        rec = "Calling submit_patch() now will result in an empty patch failure. Edit source files first."
    elif has_forbidden:
        status_str = "BLOCKED_FORBIDDEN_TEST_FILE"
        summary = (
            f"🚨 FORBIDDEN TEST FILE MODIFIED IN /WORKSPACE: {', '.join(diff_res.forbidden_test_files)}\n"
            f"Container B automatically reverts (discards) test-file modifications during evaluation."
        )
        rec = (
            "Revert forbidden test modifications before submitting:\n"
            + "\n".join(f"  git checkout -- {f}" for f in diff_res.forbidden_test_files)
        )
    elif has_syntax_err:
        status_str = "BLOCKED_SYNTAX_ERROR"
        err_files = [e.file_path for e in syntax_errors]
        summary = f"BLOCKED: Syntax error(s) detected in touched file(s): {', '.join(err_files)}."
        rec = (
            "Fix syntax errors before submitting:\n"
            + "\n".join(f"  • {e.file_path}:{e.line_number} [{e.error_type}]: {e.message}" for e in syntax_errors)
        )
    elif has_scratch:
        status_str = "BLOCKED_DANGEROUS_SCRATCH"
        summary = f"BLOCKED: Dangerous untracked scratch files in /workspace ({', '.join(diff_res.dangerous_scratch_files)})."
        rec = "Delete scratch files or move to /tmp. 'git add -N .' will pollute the official patch."
    else:
        status_str = "READY"
        can_submit = True
        summary = (
            f"READY: Patch is clean and safe to submit! {diff_res.total_files_modified} file(s) touched "
            f"(+{diff_res.total_additions}, -{diff_res.total_deletions})."
        )
        multi_file_note = (
            "\nNote: Over 90% of SWE-bench tasks only require modifying 1 file."
            if diff_res.total_files_modified > 1
            else ""
        )
        rec = f"Patch is verified and [✓ READY TO SUBMIT]. Safe to run submit_patch().{multi_file_note}"

    return TestGateResult(
        mode="status",
        workspace=str(ws),
        success=(can_submit or is_clean),
        status=status_str,
        modified_files=diff_res.modified_files,
        untracked_files=diff_res.untracked_files,
        file_stats=diff_res.file_stats,
        total_files_modified=diff_res.total_files_modified,
        total_additions=diff_res.total_additions,
        total_deletions=diff_res.total_deletions,
        forbidden_test_files=diff_res.forbidden_test_files,
        dangerous_scratch_files=diff_res.dangerous_scratch_files,
        syntax_errors=syntax_errors,
        can_submit_patch=can_submit,
        summary=summary,
        recommendation=rec,
        diff_preview=diff_res.diff_preview,
    )


# ==============================================================================
# Human-Readable Formatting
# ==============================================================================

def format_report(res: TestGateResult) -> str:
    """Format TestGateResult into high-signal human- and agent-readable text."""
    lines: List[str] = []

    if res.mode == "blast":
        lines.append(f"=== [test-gate] Regression Test Gate ({res.status}) ===")
        lines.append(f"Workspace: {res.workspace}")
        if res.modified_files:
            lines.append(f"Target(s): {', '.join(res.modified_files)}")
        if res.test_files_checked:
            lines.append(f"Neighbor test suite ({len(res.test_files_checked)} file(s)): {', '.join(res.test_files_checked)}")
        lines.append(f"Results: {res.tests_run} run | {res.tests_passed} passed | {res.tests_failed} failed | {res.tests_errors} errors")
        lines.append("-" * 75)

        if res.forbidden_test_files:
            lines.append("\n" + "=" * 75)
            lines.append("🚨 FORBIDDEN TEST FILE MODIFIED IN /WORKSPACE")
            for f in res.forbidden_test_files:
                lines.append(f"  • {f}")
            lines.append("Container B automatically reverts (discards) test-file modifications during evaluation.")
            lines.append("Your patch must resolve the defect exclusively in the source codebase, never by altering existing test files.")
            lines.append("To revert forbidden test file modifications, run:")
            for f in res.forbidden_test_files:
                lines.append(f"  git checkout -- {f}")
            lines.append("=" * 75 + "\n")

        if res.failures:
            lines.append("💥 TEST FAILURES DETECTED:")
            for f in res.failures[:5]:
                lines.append(f"  • {f.test_id} [{f.error_type}]")
                if f.line_number:
                    lines.append(f"    Line: {f.line_number}")
                if f.failing_statement:
                    lines.append(f"    Statement: {f.failing_statement}")
                if f.error_message:
                    lines.append(f"    Failure: {f.error_message}")
                if f.expected and f.actual:
                    lines.append(f"    Expected:  {f.expected}")
                    lines.append(f"    Actual:    {f.actual}")
                if f.traceback_snippet:
                    lines.append("    Traceback snippet:")
                    for tb_line in f.traceback_snippet.splitlines()[:4]:
                        lines.append(f"      {tb_line}")
                if f.remediation_hint:
                    lines.append(f"    Guidance: {f.remediation_hint}")
                lines.append("")
            if len(res.failures) > 5:
                lines.append(f"  ... (+{len(res.failures) - 5} additional failure(s) omitted)")
            lines.append("-" * 75)

        lines.append(f"Summary: {res.summary}")
        lines.append(f"Recommendation: {res.recommendation}")

    elif res.mode == "diff":
        lines.append(f"=== [test-gate] Git Diff Inspector ({res.status}) ===")
        lines.append(f"Workspace: {res.workspace}")

        if res.forbidden_test_files:
            lines.append("\n" + "=" * 75)
            lines.append("🚨 FORBIDDEN TEST FILE MODIFIED IN /WORKSPACE")
            for f in res.forbidden_test_files:
                lines.append(f"  • {f}")
            lines.append("Container B automatically reverts (discards) test-file modifications during evaluation.")
            lines.append("Your patch must resolve the defect exclusively in the source codebase, never by altering existing test files.")
            lines.append("To revert forbidden test file modifications, run:")
            for f in res.forbidden_test_files:
                lines.append(f"  git checkout -- {f}")
            lines.append("=" * 75 + "\n")

        if res.dangerous_scratch_files:
            lines.append("⚠️ DANGER: Untracked scratch files in /workspace:")
            for s in res.dangerous_scratch_files:
                lines.append(f"  • {s}")
            lines.append("Move to /tmp or delete immediately.\n")

        lines.append(f"Touched files ({res.total_files_modified}): +{res.total_additions}, -{res.total_deletions}")
        for stat in res.file_stats:
            tag = " [FORBIDDEN TEST]" if stat.is_forbidden else ""
            lines.append(f"  • {stat.path}: +{stat.additions}, -{stat.deletions} [{stat.status}]{tag}")

        lines.append("\n=== Unified Diff Preview ===")
        lines.append(res.diff_preview)
        lines.append("\n" + "-" * 75)
        lines.append(f"Summary: {res.summary}")
        lines.append(f"Recommendation: {res.recommendation}")

    elif res.mode == "status":
        lines.append(f"=== [test-gate] Patch Readiness Status ({res.status}) ===")
        lines.append(f"Workspace: {res.workspace}")

        if res.forbidden_test_files:
            lines.append("\n" + "=" * 75)
            lines.append("🚨 FORBIDDEN TEST FILE MODIFIED IN /WORKSPACE")
            for f in res.forbidden_test_files:
                lines.append(f"  • {f}")
            lines.append("Container B automatically reverts (discards) test-file modifications during evaluation.")
            lines.append("Your patch must resolve the defect exclusively in the source codebase, never by altering existing test files.")
            lines.append("To revert forbidden test file modifications, run:")
            for f in res.forbidden_test_files:
                lines.append(f"  git checkout -- {f}")
            lines.append("=" * 75 + "\n")

        if res.syntax_errors:
            lines.append("\n✗ Syntax Errors Detected:")
            for se in res.syntax_errors:
                lines.append(f"  • {se.file_path}:{se.line_number}:{se.column} [{se.error_type}]: {se.message}")
                if se.snippet:
                    lines.append(se.snippet)

        if res.dangerous_scratch_files:
            lines.append("\n⚠️ Dangerous untracked scratch files:")
            for d in res.dangerous_scratch_files:
                lines.append(f"  • {d}")

        lines.append(f"\nFiles touched ({res.total_files_modified}): +{res.total_additions}, -{res.total_deletions}")
        for stat in res.file_stats:
            tag = " [FORBIDDEN TEST]" if stat.is_forbidden else ""
            lines.append(f"  • {stat.path}: +{stat.additions}, -{stat.deletions} [{stat.status}]{tag}")

        lines.append("\nPatch Submission Readiness:")
        if res.can_submit_patch:
            lines.append("  [✓ READY TO SUBMIT] Safe to run submit_patch().")
        else:
            lines.append("  [✗ BLOCKED] DO NOT run submit_patch(). Address issues above.")

        if res.summary:
            lines.append(f"\nSummary: {res.summary}")
        lines.append(f"\nRecommendation: {res.recommendation}")

    return "\n".join(lines)


def print_usage_guide(invalid_arg: Optional[str] = None):
    """Print available options with copy-pasteable examples."""
    if invalid_arg:
        print(f"[test-gate] ⚠️ Unknown argument or flag: '{invalid_arg}'\n")
    print("test-gate: Authoritative regression runner, diff inspector, and patch readiness gate.\n")
    print("Tool Invocation:")
    print('  run_skill_script with skill_name: "test-gate", file_path: "gate.py", args: [...]\n')
    print("Available Modes & Options:")
    print("  --blast [file], -b, blast    Run distance-1 neighbor tests on modified or target files (default)")
    print("  --diff, -d, diff             Safe read-only git diff with test-file mutation assertion")
    print("  --status, -s, status         Full patch readiness: syntax checks, safety, submit recommendation")
    print("  --json, -j                   Output structured JSON (Pydantic v2)")
    print("  --timeout <sec>, -t <sec>    Pytest execution timeout per test file (default: 60s)")
    print("  --workspace <dir>, -w <dir>  Explicit workspace root directory")
    print("  --help, -h                   Show this help message\n")
    print("Recommended Arguments:")
    print("  args: []                                      # Smart default: check status or run neighbor tests if files modified")
    print('  args: ["diff"]                                # Positional diff inspection')
    print('  args: ["blast"]                               # Positional blast regression')
    print('  args: ["status"]                              # Positional patch readiness')
    print('  args: ["fastapi/routing.py"]                  # Run distance-1 neighbor tests for target file')
    print('  args: ["--diff"]                              # Inspect diff and assert no test files were touched')
    print('  args: ["--status"]                            # Verify syntax, safety, and patch submission readiness')
    print('  args: ["--status", "--json"]                  # Structured patch readiness assessment for agents')
    print('  args: ["-t", "30", "--blast"]                 # Run blast regression with 30s timeout per test file')


# ==============================================================================
# CLI Argument Parser & Entrypoint
# ==============================================================================

def parse_cli_args(argv: List[str]) -> Tuple[str, List[str], bool, Optional[str], int, Optional[str]]:
    """Parse CLI arguments with high forgiveness and positional routing.

    Returns:
        (mode, target_args, json_mode, ws_override, timeout_per_file, unknown_flag)
    """
    mode: Optional[str] = None
    target_args: List[str] = []
    json_mode: bool = False
    ws_override: Optional[str] = None
    timeout_per_file: int = 60
    unknown_flag: Optional[str] = None

    # Check for help first
    if any(a.lower() in ("-h", "--help", "help", "-help") for a in argv):
        return ("help", [], False, None, 60, None)

    i = 0
    while i < len(argv):
        arg = argv[i]
        arg_lower = arg.lower()

        # JSON mode
        if arg in ("--json", "-j"):
            json_mode = True
            i += 1
            continue

        # Timeout options
        if arg in ("--timeout", "-t"):
            if i + 1 < len(argv):
                try:
                    timeout_per_file = max(1, int(argv[i + 1]))
                except ValueError:
                    pass
                i += 2
                continue
            else:
                i += 1
                continue
        if arg.startswith(("--timeout=", "-t=")):
            val = arg.split("=", 1)[1]
            try:
                timeout_per_file = max(1, int(val))
            except ValueError:
                pass
            i += 1
            continue

        # Workspace options
        if arg in ("--workspace", "-w"):
            if i + 1 < len(argv):
                ws_override = argv[i + 1]
                i += 2
                continue
            else:
                i += 1
                continue
        if arg.startswith(("--workspace=", "-w=")):
            ws_override = arg.split("=", 1)[1]
            i += 1
            continue

        # Mode flags
        if arg in ("--diff", "-d"):
            mode = "diff"
            i += 1
            continue
        if arg in ("--status", "-s"):
            mode = "status"
            i += 1
            continue
        if arg in ("--blast", "-b"):
            mode = "blast"
            i += 1
            continue

        # Check for unknown flags (starting with -)
        if arg.startswith("-"):
            unknown_flag = arg
            i += 1
            continue

        # Positional routing
        if arg_lower in ("diff", "inspect"):
            mode = "diff"
            i += 1
            continue
        if arg_lower in ("status", "ready", "check"):
            mode = "status"
            i += 1
            continue
        if arg_lower in ("blast", "test", "tests"):
            mode = "blast"
            i += 1
            continue

        # Ignored loose / filler words
        if arg_lower in ("run", "show", "on", "for", "against"):
            i += 1
            continue

        # Any other positional argument is treated as a target file or git arg
        target_args.append(arg)
        i += 1

    return (mode or "auto", target_args, json_mode, ws_override, timeout_per_file, unknown_flag)


def main() -> int:
    """CLI entrypoint. Always exits 0."""
    try:
        raw_args = sys.argv[1:]
        mode, target_args, json_mode, ws_override, timeout_per_file, unknown_flag = parse_cli_args(raw_args)

        if mode == "help":
            print_usage_guide()
            return 0

        if unknown_flag:
            print_usage_guide(unknown_flag)
            return 0

        ws = get_workspace_dir(ws_override)

        # Smart default resolution for "auto"
        if mode == "auto":
            if target_args:
                mode = "blast"
            else:
                modified_files, _, _ = get_git_status_and_files(ws)
                if modified_files:
                    mode = "blast"
                else:
                    mode = "status"

        if mode == "blast":
            res = execute_blast(ws, target_args, timeout_per_file=timeout_per_file)
        elif mode == "diff":
            res = execute_diff(ws, target_args)
        elif mode == "status":
            res = execute_status(ws)
        else:
            print_usage_guide()
            return 0

        if json_mode:
            print(res.model_dump_json(indent=2))
        else:
            print(format_report(res))

        return 0

    except Exception as e:
        print(f"[test-gate] Unexpected error: {e}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
