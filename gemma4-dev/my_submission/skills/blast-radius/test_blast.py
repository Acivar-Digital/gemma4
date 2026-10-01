#!/usr/bin/env python3
"""blast-radius: Targeted Distance-1 Regression & Blast Radius Test Runner.

Identifies the direct test files and distance-1 consumers (files that import the target),
and runs a micro-targeted pytest execution against only that dependency cluster.
Deterministic pytest regression triage: parses assertion failures, extracts actual vs expected
comparisons, explains regression root causes, correlates with modified repo files,
and provides actionable remediation hints.
100% Pydantic v2 structured schemas.
Always returns exit code 0.

Usage:
    python3 test_blast.py [target_file_or_symbol...]
    python3 test_blast.py --help
    python3 test_blast.py --json [target_file_or_symbol...]
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

ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
SKIP_DIRS = {"build", "dist", ".git", "__pycache__", "venv", ".venv", "node_modules", "wheels", ".pytest_cache"}

PREFIX_CONFLICT_ADVISORY = (
    "[blast-radius] ⚠️ DIRECT UNIT TESTS FAILED: Pre-fix assertion baseline conflict suspected, "
    "but verification CANNOT pass while direct tests fail. "
    "If this file was intentionally altered, verify that this is indeed the target file requested by the issue, not a secondary file!"
)


def strip_ansi(text: str) -> str:
    """Strip ANSI terminal escape codes from text."""
    return ANSI_ESCAPE.sub("", text)


class TestFailureDetail(BaseModel):
    """Detailed diagnostic breakdown of an individual pytest test failure."""

    model_config = ConfigDict(extra="ignore")

    test_id: str = Field(..., description="Full pytest test node id, e.g. tests/test_text.py::test_str")
    test_file: str = Field(default="", description="Path to the test file relative to workspace")
    test_name: str = Field(default="", description="Test function or method name")
    line_number: Optional[int] = Field(default=None, description="Line number of failure in test or source file")
    failure_location: str = Field(default="", description="File:line or in-function reference string")
    error_type: str = Field(default="AssertionError", description="Exception type, e.g. AssertionError, AttributeError")
    failing_statement: str = Field(default="", description="Failing source code statement or assertion")
    error_message: str = Field(default="", description="Raw error or assertion message")
    expected: Optional[str] = Field(default=None, description="Extracted expected value or expression")
    actual: Optional[str] = Field(default=None, description="Extracted actual value or expression")
    diff: Optional[str] = Field(default=None, description="Detailed diff between actual and expected")
    captured_stdout: Optional[str] = Field(default=None, description="Captured stdout during test call")
    captured_stderr: Optional[str] = Field(default=None, description="Captured stderr during test call")
    correlated_modifications: List[str] = Field(default_factory=list, description="Modified repo files or symbols linked to this test")
    explanation: str = Field(default="", description="Deterministic root cause explanation of the failure")
    remediation_hint: str = Field(default="", description="Actionable hint on how to fix or revert the issue")
    prefix_conflict_advisory: Optional[str] = Field(
        default=None,
        description="Pre-fix baseline test conflict advisory when direct unit test fails on assertion mismatch",
    )


class FailureDiagnosis(BaseModel):
    """Grouped regression diagnosis explaining the underlying root cause across one or more tests."""

    model_config = ConfigDict(extra="ignore")

    summary: str = Field(..., description="Deterministic regression root cause explanation")
    failing_tests: List[str] = Field(default_factory=list, description="List of test IDs exhibiting this failure pattern")
    suspected_modified_files: List[str] = Field(default_factory=list, description="Modified repo files likely causing this regression")
    common_mismatch: Optional[str] = Field(default=None, description="Shared mismatch description or difference")
    remediation_hint: str = Field(default="", description="Actionable hint on how to remediate the regression")
    prefix_conflict_advisory: Optional[str] = Field(
        default=None,
        description="Pre-fix baseline test conflict advisory when direct unit test fails on assertion mismatch",
    )


class BlastRadiusResult(BaseModel):
    """Overall execution and triage result for blast-radius test run."""

    model_config = ConfigDict(extra="ignore")

    targets: List[str] = Field(default_factory=list, description="Target files or symbols checked")
    modified_files: List[str] = Field(default_factory=list, description="Modified files detected in repo")
    distance1_consumers: List[str] = Field(default_factory=list, description="Direct consumer files importing targets")
    test_files: List[str] = Field(default_factory=list, description="Test files executed")
    direct_test_files: List[str] = Field(default_factory=list, description="Direct test files for targets")
    consumer_test_files: List[str] = Field(default_factory=list, description="Distance-1 consumer test files")
    exit_code: int = Field(default=0, description="Pytest exit code")
    passed: bool = Field(default=True, description="Whether all tests passed")
    status: str = Field(
        default="PASSED",
        description="Overall execution status: PASSED, FAILED, UNVERIFIED_NO_TESTS, FAILED_DIRECT_TESTS_SUSPECTED_CONFLICT",
    )
    summary: str = Field(default="", description="Execution summary line")
    multi_file_warning: Optional[str] = Field(default=None, description="Warning if multiple modified files detected in workspace")
    total_passed: int = Field(default=0, description="Number of passed tests")
    total_failed: int = Field(default=0, description="Number of failed tests")
    total_errors: int = Field(default=0, description="Number of error tests")
    failures: List[TestFailureDetail] = Field(default_factory=list, description="Detailed failure breakdowns")
    diagnoses: List[FailureDiagnosis] = Field(default_factory=list, description="Diagnoses and root-cause explanations")
    prefix_conflict_advisory: Optional[str] = Field(
        default=None,
        description="Pre-fix baseline test conflict advisory if detected across failures",
    )


def clean_test_id(raw_id: str, ws: pathlib.Path) -> str:
    """Normalize test node ID relative to workspace directory."""
    clean = raw_id.strip()
    if "::" in clean:
        path_part, test_part = clean.split("::", 1)
        p = pathlib.Path(path_part)
        try:
            rel = p.resolve().relative_to(ws.resolve())
            return f"{rel.as_posix()}::{test_part}"
        except Exception:
            return f"{p.name}::{test_part}"
    p = pathlib.Path(clean)
    try:
        rel = p.resolve().relative_to(ws.resolve())
        return rel.as_posix()
    except Exception:
        return p.name


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


def resolve_target(target_str: str, ws: pathlib.Path) -> pathlib.Path:
    """Omnivorously resolve any given file path, module name, or symbol against workspace."""
    clean = target_str.strip().strip("'\"")
    if not clean:
        return ws

    # 1. Handle pytest node specifiers (e.g. path/to/file.py::test_func)
    if "::" in clean:
        clean = clean.split("::", 1)[0].strip()

    # 2. Handle /workspace prefix or exact /workspace
    if clean == "/workspace":
        return ws
    if clean.startswith("/workspace/"):
        clean = clean[len("/workspace/"):]

    # 3. Handle absolute paths
    p_abs = pathlib.Path(clean)
    if p_abs.is_absolute():
        if p_abs.exists():
            return p_abs
        try:
            rel = p_abs.relative_to(ws)
            clean = str(rel)
        except ValueError:
            clean = clean.lstrip("/")

    clean = clean.lstrip("/")
    if clean.startswith("./"):
        clean = clean[2:]

    # 4. Direct check: exact path in workspace (file or directory)
    cand = ws / clean
    if cand.exists():
        return cand

    # 5. Direct check with .py extension
    cand_py = ws / f"{clean}.py"
    if cand_py.exists():
        return cand_py

    # 6. Check module name with dot notation (e.g. "rich.ansi", "fastapi.routing", "rich.text.Text")
    if "." in clean and not clean.endswith(".py"):
        parts = clean.split(".")
        for split_idx in range(len(parts), 0, -1):
            subpath = "/".join(parts[:split_idx])
            c_py = ws / f"{subpath}.py"
            if c_py.is_file():
                return c_py
            c_dir = ws / subpath
            if c_dir.is_dir():
                c_init = c_dir / "__init__.py"
                if c_init.is_file():
                    return c_init
                return c_dir

    # 7. Basename lookup across workspace (e.g. "text.py", "routing.py", "models.py")
    target_name = pathlib.Path(clean).name
    if not target_name.endswith(".py"):
        target_name_py = f"{target_name}.py"
    else:
        target_name_py = target_name

    for name_to_search in (target_name_py, target_name):
        try:
            matches = [
                p for p in ws.rglob(name_to_search)
                if not any(part in SKIP_DIRS for part in p.parts)
            ]
            if matches:
                if len(matches) > 1:
                    src_matches = [m for m in matches if "tests" not in m.parts and "test" not in m.parts]
                    if src_matches:
                        return src_matches[0]
                return matches[0]
        except Exception:
            pass

    return cand


def _get_modified_files(ws: Optional[pathlib.Path] = None) -> List[pathlib.Path]:
    """Find files modified in working tree using git status."""
    if ws is None:
        ws = get_workspace_dir()
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode != 0:
            return []

        modified: List[pathlib.Path] = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                rel_path = parts[1]
                if " -> " in rel_path:
                    rel_path = rel_path.split(" -> ")[1].strip()
                rel_path = rel_path.strip('"')
                p = ws / rel_path
                if p.suffix == ".py" and p.exists():
                    modified.append(p)
        return modified
    except Exception:
        return []


get_modified_files = _get_modified_files


def format_multi_file_warning(modified_files: List[Any], target_file: str) -> Optional[str]:
    """Format an informative notice for multi-file changes without alarmist revert warnings."""
    mod_list = [
        m.as_posix() if isinstance(m, pathlib.Path) else str(m)
        for m in modified_files
    ]
    if len(mod_list) <= 1:
        return None
    return (
        f"ℹ️ MULTI-FILE TARGET: {len(mod_list)} repository files modified ({mod_list}). "
        f"Testing blast radius across target(s)."
    )


def resolve_docs_src_test_path(path_str: str) -> Optional[str]:
    """Framework-aware path mapping for FastAPI doc tutorials.

    Maps docs_src/<category>/tutorial<N>[_<variant>].py to
    tests/test_tutorial/test_<category>/test_tutorial<N>.py (stripping _py310, _py39, _an_py310, etc.).
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
    if m:
        base_stem = m.group(1)
    else:
        base_stem = re.sub(r"(_(?:an|py3\d+|py\d+|pv\d+|non_annotated|annotated))+$", "", stem)

    category = "_".join(category_parts)
    clean_category = category[5:] if category.startswith("test_") else category
    return f"tests/test_tutorial/test_{clean_category}/test_{base_stem}.py"


def get_modified_lines_from_git(file_path: pathlib.Path, ws: pathlib.Path) -> Set[int]:
    """Extract line numbers added or modified in file_path via git diff."""
    modified_lines: Set[int] = set()
    try:
        rel_p = file_path.relative_to(ws)
    except ValueError:
        rel_p = file_path

    for git_cmd in [
        ["git", "diff", "-U0", "HEAD", "--", str(rel_p)],
        ["git", "diff", "-U0", "--", str(rel_p)],
    ]:
        try:
            res = subprocess.run(git_cmd, cwd=ws, capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                for line in res.stdout.splitlines():
                    if line.startswith("@@"):
                        m = re.search(r"\+(\d+)(?:,(\d+))?", line)
                        if m:
                            start = int(m.group(1))
                            count = int(m.group(2)) if m.group(2) is not None else 1
                            if count == 0:
                                modified_lines.add(start)
                            else:
                                for lno in range(start, start + count):
                                    modified_lines.add(lno)
                if modified_lines:
                    return modified_lines
        except Exception:
            pass
    return modified_lines


def extract_all_ast_symbols(file_path: pathlib.Path) -> Set[str]:
    """Extract top-level classes, methods, functions, and module-level variables from a Python file."""
    symbols: Set[str] = set()
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
                            symbols.add(f"{node.name}.{item.name}")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("__"):
                    symbols.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        symbols.add(target.id)
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    symbols.add(node.target.id)
    except Exception:
        pass
    return {s for s in symbols if len(s) > 1}


def get_target_symbols(target_path: pathlib.Path, ws: pathlib.Path) -> Set[str]:
    """Extract AST symbols modified in target_path (falling back to all top-level symbols)."""
    if not target_path.exists() or target_path.suffix != ".py":
        return set()

    modified_lines = get_modified_lines_from_git(target_path, ws)
    symbols: Set[str] = set()
    try:
        content = target_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(content, filename=str(target_path))

        if modified_lines:
            for node in tree.body:
                node_start = getattr(node, "lineno", 0)
                node_end = getattr(node, "end_lineno", node_start)
                node_lines = set(range(node_start, node_end + 1))
                if node_lines & modified_lines:
                    if isinstance(node, ast.ClassDef):
                        symbols.add(node.name)
                        for item in node.body:
                            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                item_start = getattr(item, "lineno", 0)
                                item_end = getattr(item, "end_lineno", item_start)
                                if set(range(item_start, item_end + 1)) & modified_lines:
                                    symbols.add(item.name)
                                    symbols.add(f"{node.name}.{item.name}")
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        symbols.add(node.name)
                    elif isinstance(node, ast.Assign):
                        for tgt in node.targets:
                            if isinstance(tgt, ast.Name):
                                symbols.add(tgt.id)
                    elif isinstance(node, ast.AnnAssign):
                        if isinstance(node.target, ast.Name):
                            symbols.add(node.target.id)

        if not symbols:
            symbols = extract_all_ast_symbols(target_path)
    except Exception:
        pass

    return {s for s in symbols if s and not s.startswith("__") and len(s) > 1}


def find_tests_for_symbols(
    symbols: Set[str],
    ws: pathlib.Path,
    exclude_paths: Optional[Set[pathlib.Path]] = None,
    max_test_files: int = 6,
) -> List[str]:
    """Scan test files across workspace for imports or call-sites of target AST symbols."""
    if not symbols:
        return []

    exclude = exclude_paths or set()
    scan_names = set()
    for s in symbols:
        if "." in s:
            scan_names.add(s.split(".")[-1])
            scan_names.add(s.split(".")[0])
        else:
            scan_names.add(s)
    scan_names = {s for s in scan_names if len(s) > 1 and s not in {"self", "cls", "None", "True", "False"}}
    if not scan_names:
        return []

    matched_tests: List[str] = []
    cand_files: List[pathlib.Path] = []
    try:
        for p in ws.rglob("*.py"):
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            if p in exclude:
                continue
            if "tests" in p.parts or "test" in p.parts or p.name.startswith("test_") or p.name.endswith("_test.py"):
                cand_files.append(p)
    except Exception:
        pass

    for tf in cand_files:
        try:
            rel_tf = str(tf.relative_to(ws))
        except ValueError:
            rel_tf = str(tf)

        try:
            content = tf.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        found_in_text = {s for s in scan_names if s in content}
        if not found_in_text:
            continue

        has_symbol_ref = False
        try:
            tree = ast.parse(content, filename=rel_tf)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if alias.name in found_in_text or alias.asname in found_in_text:
                            has_symbol_ref = True
                            break
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in found_in_text or alias.asname in found_in_text:
                            has_symbol_ref = True
                            break
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id in found_in_text:
                        has_symbol_ref = True
                        break
                    elif isinstance(node.func, ast.Attribute) and node.func.attr in found_in_text:
                        has_symbol_ref = True
                        break
                elif isinstance(node, ast.Name) and node.id in found_in_text:
                    if isinstance(getattr(node, "ctx", None), ast.Load):
                        has_symbol_ref = True
                        break
                if has_symbol_ref:
                    break
        except Exception:
            has_symbol_ref = True

        if has_symbol_ref and rel_tf not in matched_tests:
            matched_tests.append(rel_tf)
            if len(matched_tests) >= max_test_files:
                break

    return matched_tests


class BlastRadiusScope(tuple):
    """2-tuple (test_files, consumers) with attribute access for rich dependency metadata."""

    def __new__(
        cls,
        test_files: List[str],
        consumers: List[str],
        direct_tests: Optional[List[str]] = None,
        consumer_tests: Optional[List[str]] = None,
        symbols: Optional[Set[str]] = None,
    ):
        return super().__new__(cls, (test_files, consumers))

    def __init__(
        self,
        test_files: List[str],
        consumers: List[str],
        direct_tests: Optional[List[str]] = None,
        consumer_tests: Optional[List[str]] = None,
        symbols: Optional[Set[str]] = None,
    ):
        self.test_files = test_files
        self.consumers = consumers
        self.direct_tests = direct_tests or []
        self.consumer_tests = consumer_tests or []
        self.symbols = symbols or set()


def extract_repo_symbols(file_path: pathlib.Path) -> Dict[str, Any]:
    """Extract top-level classes (and their methods) and top-level functions from a Python file."""
    symbols: Dict[str, Any] = {"classes": {}, "functions": set()}
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(content, filename=str(file_path))
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                methods = {n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
                symbols["classes"][node.name] = methods
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols["functions"].add(node.name)
    except Exception:
        pass
    return symbols


def find_blast_radius(target_path: pathlib.Path, ws: pathlib.Path) -> BlastRadiusScope:
    """Determine distance-1 consumers and relevant test files using AST analysis and symbol resolution."""
    try:
        rel_target = target_path.relative_to(ws)
    except ValueError:
        rel_target = target_path

    # Target module identity
    stem = target_path.stem
    target_mod_parts = list(rel_target.parts)
    if target_mod_parts and target_mod_parts[-1].endswith(".py"):
        target_mod_parts[-1] = target_mod_parts[-1][:-3]
    full_mod_name = ".".join(target_mod_parts)

    # 1. Direct test file heuristics & framework-aware path mapping
    direct_tests: List[str] = []
    consumer_tests: List[str] = []
    consumers: List[str] = []

    # Framework-aware mapping for docs_src tutorial files
    docs_cand = resolve_docs_src_test_path(str(rel_target))
    if docs_cand:
        cand_p = ws / docs_cand
        if cand_p.exists():
            rel_docs = str(cand_p.relative_to(ws))
            if rel_docs not in direct_tests:
                direct_tests.append(rel_docs)

    if "test" in target_path.name:
        direct_tests.append(str(rel_target))
    else:
        test_cands = [
            f"tests/test_{stem}.py",
            f"test/test_{stem}.py",
            f"tests/{stem}_test.py",
            f"test_{stem}.py",
            f"tests/test_{full_mod_name.replace('.', '_')}.py",
        ]
        if len(rel_target.parts) > 1:
            test_cands.append(f"tests/{'/'.join(rel_target.parts[:-1])}/test_{stem}.py")

        for tc in test_cands:
            cand_p = ws / tc
            if cand_p.exists() and str(cand_p.relative_to(ws)) not in direct_tests:
                direct_tests.append(str(cand_p.relative_to(ws)))

        if not direct_tests and not docs_cand:
            try:
                for match in ws.rglob(f"test_{stem}.py"):
                    if not any(part in SKIP_DIRS for part in match.parts):
                        direct_tests.append(str(match.relative_to(ws)))
                        break
            except Exception:
                pass

    # Symbol-level test resolution: scan test files for imports or call-sites of modified AST symbols
    target_symbols = get_target_symbols(target_path, ws)
    if target_symbols:
        sym_tests = find_tests_for_symbols(
            symbols=target_symbols,
            ws=ws,
            exclude_paths={target_path, ws / rel_target},
            max_test_files=6,
        )
        for st in sym_tests:
            if st not in direct_tests and st not in consumer_tests:
                direct_tests.append(st)

    # 2. Find distance-1 consumers (files importing target)
    try:
        for p in ws.rglob("*.py"):
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            if p == target_path:
                continue

            try:
                rel_f = str(p.relative_to(ws))
            except ValueError:
                rel_f = str(p)

            try:
                content = p.read_text(encoding="utf-8", errors="replace")
                if stem not in content and full_mod_name not in content:
                    continue
                tree = ast.parse(content, filename=rel_f)
            except Exception:
                continue

            imports_target = False
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == full_mod_name or alias.name == stem or alias.name.startswith(f"{full_mod_name}."):
                            imports_target = True
                            break
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    if mod == full_mod_name or mod == stem or mod.endswith(f".{stem}"):
                        imports_target = True
                        break
                    for alias in node.names:
                        if alias.name == stem:
                            imports_target = True
                            break
                if imports_target:
                    break

            if imports_target:
                if "tests" in p.parts or "test" in p.parts or p.name.startswith("test_") or p.name.endswith("_test.py"):
                    if rel_f not in direct_tests and rel_f not in consumer_tests:
                        consumer_tests.append(rel_f)
                else:
                    if rel_f not in consumers:
                        consumers.append(rel_f)
                        c_stem = p.stem
                        for c_cand in (f"tests/test_{c_stem}.py", f"test/test_{c_stem}.py", f"tests/{c_stem}_test.py"):
                            cp = ws / c_cand
                            if cp.exists():
                                try:
                                    rel_cp = str(cp.relative_to(ws))
                                    if rel_cp not in direct_tests and rel_cp not in consumer_tests:
                                        consumer_tests.append(rel_cp)
                                except Exception:
                                    pass
    except Exception:
        pass

    all_tests: List[str] = []
    for t in direct_tests + consumer_tests:
        if t not in all_tests:
            all_tests.append(t)

    # Return BlastRadiusScope (subclass of tuple, capped to max 8 files)
    return BlastRadiusScope(
        all_tests[:8],
        consumers,
        direct_tests=direct_tests,
        consumer_tests=consumer_tests,
        symbols=target_symbols,
    )


def find_pytest_command(ws: pathlib.Path) -> List[str]:
    """Find the most appropriate pytest executable or python -m pytest runner."""
    # 1. Virtualenv pytest matching current interpreter directory or sys.prefix
    for base_p in (pathlib.Path(sys.executable).parent, pathlib.Path(sys.prefix) / "bin"):
        cand_pytest = base_p / "pytest"
        if cand_pytest.is_file() and os.access(cand_pytest, os.X_OK):
            return [str(cand_pytest)]

    # 2. VIRTUAL_ENV environment variable
    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        venv_pytest = pathlib.Path(venv) / "bin" / "pytest"
        if venv_pytest.is_file() and os.access(venv_pytest, os.X_OK):
            return [str(venv_pytest)]
        venv_py = pathlib.Path(venv) / "bin" / "python"
        if venv_py.is_file() and os.access(venv_py, os.X_OK):
            return [str(venv_py), "-m", "pytest"]

    # 3. Check virtualenv directories within workspace (.venv, venv)
    for venv_name in (".venv", "venv"):
        v_cand = ws / venv_name / "bin" / "pytest"
        if v_cand.is_file() and os.access(v_cand, os.X_OK):
            return [str(v_cand)]
        v_py = ws / venv_name / "bin" / "python"
        if v_py.is_file() and os.access(v_py, os.X_OK):
            return [str(v_py), "-m", "pytest"]

    # 4. Known standard container venv locations
    for venv_path in ("/venv", "/opt/venv", "/root/.venv"):
        v_pytest = pathlib.Path(venv_path) / "bin" / "pytest"
        if v_pytest.is_file() and os.access(v_pytest, os.X_OK):
            return [str(v_pytest)]
        v_py = pathlib.Path(venv_path) / "bin" / "python"
        if v_py.is_file() and os.access(v_py, os.X_OK):
            return [str(v_py), "-m", "pytest"]

    # 5. Check if active interpreter has pytest module available
    try:
        if importlib.util.find_spec("pytest") is not None:
            return [sys.executable, "-m", "pytest"]
    except Exception:
        pass

    # 6. Pytest on PATH
    pytest_bin = shutil.which("pytest")
    if pytest_bin:
        return [pytest_bin]

    # 7. Subprocess python runner matching current interpreter
    if sys.executable and shutil.which(sys.executable):
        return [sys.executable, "-m", "pytest"]

    # 8. Fallback python interpreters on PATH
    for py_name in ("python3", "python"):
        resolved_py = shutil.which(py_name)
        if resolved_py:
            return [resolved_py, "-m", "pytest"]

    return [sys.executable or "python3", "-m", "pytest"]


def run_pytest(tests: List[str], ws: pathlib.Path, timeout_secs: int = 25) -> Tuple[int, str]:
    """Run pytest on test files with verbose diff output and workspace PYTHONPATH."""
    cmd_base = find_pytest_command(ws)
    # Use -vv --tb=short --disable-warnings to ensure untruncated assertion diffs
    cmd = cmd_base + ["-vv", "--tb=short", "--disable-warnings"] + tests
    env = os.environ.copy()
    existing_pp = env.get("PYTHONPATH", "")

    pp_parts: List[str] = [str(ws)]
    if "/workspace" not in pp_parts:
        pp_parts.append("/workspace")
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
        return 1, f"[blast-radius] Pytest timed out after {timeout_secs}s on: {', '.join(tests)}"
    except Exception as e:
        return 1, f"[blast-radius] Pytest execution error: {e}"


def explain_mismatch(actual: Optional[str], expected: Optional[str], error_type: str, error_msg: str, statement: str) -> str:
    """Deterministically explain why an assertion or check failed."""
    # Check boundary assertion defect in statement or error_msg
    boundary_patterns = (
        "assert '' == '\\n'",
        'assert "" == "\\n"',
        "assert '' == \"\\n\"",
        'assert "" == \'\\n\'',
        "assert '\\n' == ''",
        'assert "\\n" == ""',
        "assert '\\n' == \"\"",
        'assert "\\n" == \'\'',
    )
    if any(p in statement for p in boundary_patterns) or any(p in error_msg for p in boundary_patterns):
        return (
            "BOUNDARY DEFECT: The function returned an empty string '' when a newline '\\n' was expected. "
            "Check if string tokenization or stripping collapsed empty lines."
        )

    if actual is not None and expected is not None:
        act_raw = actual.strip("'\"")
        exp_raw = expected.strip("'\"")

        # 0. Degenerate boundary mismatch (empty string vs newline, e.g. assert '' == '\n' or vice-versa)
        is_empty_act = actual in ("''", '""', "") or act_raw == ""
        is_nl_exp = expected in ("'\\n'", '"\\n"', "\\n", "\n") or exp_raw in ("\\n", "\n")
        is_nl_act = actual in ("'\\n'", '"\\n"', "\\n", "\n") or act_raw in ("\\n", "\n")
        is_empty_exp = expected in ("''", '""', "") or exp_raw == ""

        if (is_empty_act and is_nl_exp) or (is_nl_act and is_empty_exp):
            return (
                "BOUNDARY DEFECT: The function returned an empty string '' when a newline '\\n' was expected. "
                "Check if string tokenization or stripping collapsed empty lines."
            )

        # 1. Newline mismatch
        act_has_nl = actual.endswith(("\\n'", '\\n"', "\\n")) or "\\n" in actual
        exp_has_nl = expected.endswith(("\\n'", '\\n"', "\\n")) or "\\n" in expected
        if act_has_nl and not exp_has_nl:
            return "The function under test returned an extra newline."
        if exp_has_nl and not act_has_nl:
            return "The function under test is missing an expected trailing newline."

        # 2. Whitespace mismatch
        if act_raw.strip() == exp_raw.strip() and act_raw != exp_raw:
            return "The actual string differs only by leading or trailing whitespace."

        # 3. Suffix / Prefix mismatch
        if act_raw.startswith(exp_raw) and len(act_raw) > len(exp_raw):
            extra = act_raw[len(exp_raw):]
            if len(extra) <= 25:
                return f"The function under test returned unexpected trailing content ({repr(extra)})."
            return "The function under test returned extra unexpected trailing content."
        if exp_raw.startswith(act_raw) and len(exp_raw) > len(act_raw):
            missing = exp_raw[len(act_raw):]
            if len(missing) <= 25:
                return f"The actual output was truncated or missing expected suffix ({repr(missing)})."
            return "The actual output was truncated or missing expected content."

        # 4. Numeric / HTTP status code mismatch
        if actual.isdigit() and expected.isdigit():
            if "status_code" in statement or "status" in statement:
                return f"HTTP status code mismatch: expected HTTP {expected} but received HTTP {actual}."
            return f"Numeric return value mismatch: expected {expected} but got {actual}."

        # 5. Dict item mismatch
        if "{" in actual and "{" in expected:
            return "Dictionary mismatch: one or more key-value pairs differed between actual and expected."

        # 6. List / sequence mismatch
        if "[" in actual and "[" in expected:
            return "Sequence mismatch: list elements or ordering differed between actual and expected."

        # 7. Boolean mismatch
        if actual in ("True", "False") or expected in ("True", "False"):
            return f"Boolean result mismatch: expected {expected} but received {actual}."

        return f"Expected {expected} but got {actual}."

    if error_type == "AssertionError":
        if "assert False" in statement or "assert not " in statement:
            return "Assertion condition evaluated to False unexpectedly."
        if " in " in statement:
            return "Item was not found in expected container."
        return error_msg or "Assertion condition failed."

    if error_type == "AttributeError":
        return f"AttributeError: {error_msg}."
    if error_type == "TypeError":
        return f"TypeError: {error_msg}."
    if error_type in ("ImportError", "ModuleNotFoundError"):
        return f"Import failure: {error_msg}."
    if error_type == "KeyError":
        return f"KeyError: {error_msg} (missing required dictionary key)."
    if error_type == "IndexError":
        return f"IndexError: {error_msg} (sequence index out of range)."

    return f"{error_type}: {error_msg}" if error_msg else error_type


def correlate_test_with_modified(
    test_file_path: pathlib.Path,
    test_func_name: str,
    locations: List[Tuple[str, int, str]],
    failing_statement: str,
    modified_files: List[pathlib.Path],
    ws: pathlib.Path,
) -> List[str]:
    """Correlate a failing test with modified repo files, classes, and methods."""
    correlations: List[str] = []

    # 1. Traceback frame correlation (did exception originate in modified file?)
    for loc_file, loc_line, loc_func in locations:
        loc_p = pathlib.Path(loc_file)
        for mod_p in modified_files:
            try:
                rel_mod = mod_p.relative_to(ws).as_posix()
            except ValueError:
                rel_mod = mod_p.as_posix()
            if loc_file == str(mod_p) or loc_file == str(rel_mod) or loc_p.name == mod_p.name:
                correlations.append(
                    f"Triggered exception inside modified file '{rel_mod}:{loc_line}' in function/method '{loc_func}'"
                )

    if correlations:
        return correlations

    # 2. Inspect test function body and imports via AST
    if test_file_path.exists():
        try:
            tree = ast.parse(test_file_path.read_text(encoding="utf-8", errors="replace"), filename=str(test_file_path))
            target_func_node = None
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == test_func_name:
                    target_func_node = node
                    break

            called_names: Set[str] = set()
            called_attrs: Set[str] = set()
            if target_func_node:
                for sub in ast.walk(target_func_node):
                    if isinstance(sub, ast.Call):
                        if isinstance(sub.func, ast.Name):
                            called_names.add(sub.func.id)
                        elif isinstance(sub.func, ast.Attribute):
                            called_attrs.add(sub.func.attr)
                    elif isinstance(sub, ast.Name):
                        called_names.add(sub.id)
                    elif isinstance(sub, ast.Attribute):
                        called_attrs.add(sub.attr)

            for mod_p in modified_files:
                try:
                    rel_mod = mod_p.relative_to(ws).as_posix()
                except ValueError:
                    rel_mod = mod_p.as_posix()
                symbols = extract_repo_symbols(mod_p)

                for cls_name, methods in symbols["classes"].items():
                    if cls_name in called_names or cls_name in failing_statement:
                        matched_method = None
                        if "str(" in failing_statement or "__str__" in failing_statement:
                            if "__str__" in methods:
                                matched_method = "__str__"
                        elif "repr(" in failing_statement or "__repr__" in failing_statement:
                            if "__repr__" in methods:
                                matched_method = "__repr__"
                        if not matched_method:
                            for m in methods:
                                if m in called_attrs or m in failing_statement:
                                    matched_method = m
                                    break
                        if matched_method:
                            correlations.append(
                                f"Failing test '{test_func_name}' calls '{cls_name}.{matched_method}' which was modified in '{rel_mod}'"
                            )
                        else:
                            correlations.append(
                                f"Failing test '{test_func_name}' calls '{cls_name}' which was modified in '{rel_mod}'"
                            )

                for fn_name in symbols["functions"]:
                    if fn_name in called_names or fn_name in failing_statement:
                        correlations.append(
                            f"Failing test '{test_func_name}' calls function '{fn_name}' which was modified in '{rel_mod}'"
                        )

                if not correlations:
                    mod_stem = mod_p.stem
                    if mod_stem in test_file_path.read_text(encoding="utf-8", errors="replace"):
                        correlations.append(
                            f"Failing test file '{test_file_path.name}' exercises modified file '{rel_mod}'"
                        )
        except Exception:
            pass

    if not correlations and modified_files:
        for mod_p in modified_files:
            try:
                rel = mod_p.relative_to(ws).as_posix()
            except ValueError:
                rel = mod_p.as_posix()
            correlations.append(f"Direct blast radius of modified file '{rel}'")

    return correlations


def get_grouping_target(corrs: List[str]) -> str:
    """Extract a canonical grouping target string across failures."""
    if not corrs:
        return "repo"
    c = corrs[0]
    m = re.search(r"calls '([^']+)' which was modified in '([^']+)'", c)
    if m:
        return f"{m.group(2)}::{m.group(1)}"
    m2 = re.search(r"inside modified file '([^']+)' in function/method '([^']+)'", c)
    if m2:
        file_part = m2.group(1).split(":")[0]
        return f"{file_part}::{m2.group(2)}"
    m3 = re.search(r"modified file '([^']+)'", c)
    if m3:
        return m3.group(1)
    return c


def clean_remediation_target(corr: str) -> str:
    """Extract clean target symbol and file for remediation hints."""
    m = re.search(r"calls '([^']+)' which was modified in '([^']+)'", corr)
    if m:
        return f"'{m.group(1)}' in '{m.group(2)}'"
    m2 = re.search(r"inside modified file '([^']+)' in function/method '([^']+)'", corr)
    if m2:
        return f"'{m2.group(2)}' in '{m2.group(1)}'"
    m3 = re.search(r"modified file '([^']+)'", corr)
    if m3:
        return f"'{m3.group(1)}'"
    return corr


def is_direct_unit_test(
    test_ref: str | pathlib.Path,
    modified_files: List[pathlib.Path],
    targets: List[pathlib.Path],
    direct_test_files: Optional[List[str]] = None,
) -> bool:
    """Check if test_ref directly tests one of the modified repo components."""
    if not test_ref:
        return False
    raw_str = str(test_ref).strip()
    if "::" in raw_str:
        raw_str = raw_str.split("::", 1)[0]
    p = pathlib.Path(raw_str)
    t_stem = p.stem.lower()
    t_name = p.name.lower()
    t_posix = p.as_posix().lower()

    # 1. Direct match with direct_test_files resolved during blast discovery
    if direct_test_files:
        for dt in direct_test_files:
            clean_dt = str(dt).strip()
            if "::" in clean_dt:
                clean_dt = clean_dt.split("::", 1)[0]
            if raw_str == clean_dt or raw_str.endswith(clean_dt) or clean_dt.endswith(raw_str):
                return True
            if pathlib.Path(clean_dt).stem.lower() == t_stem:
                return True

    all_mods = list(targets or []) + list(modified_files or [])
    for mod_p in all_mods:
        if not mod_p:
            continue
        m_p = pathlib.Path(mod_p)
        m_str = str(m_p)

        # Check docs_src framework mapping
        docs_test = resolve_docs_src_test_path(m_str)
        if docs_test:
            if docs_test.lower() == raw_str.lower() or raw_str.lower().endswith(docs_test.lower()) or docs_test.lower().endswith(raw_str.lower()):
                return True
            if pathlib.Path(docs_test).stem.lower() == t_stem:
                return True

        m_stem = m_p.stem.lower()
        if not m_stem or m_stem in ("__init__", "conftest", "test", "tests"):
            continue

        # Check tutorial variant stem (e.g. tutorial001_py310 -> tutorial001)
        m_tut = re.match(r"^(tutorial\d+[a-z]?)(?:_.*)?$", m_stem)
        if m_tut:
            tut_base = m_tut.group(1)
            if t_stem in (f"test_{tut_base}", f"{tut_base}_test", tut_base):
                return True

        m_clean = m_stem.lstrip("_")

        # Direct matching heuristics (e.g. tests/test_ansi.py testing rich/ansi.py)
        if t_stem in (f"test_{m_stem}", f"{m_stem}_test", m_stem, f"test_{m_clean}", f"{m_clean}_test", m_clean):
            return True
        if t_name in (f"test_{m_stem}.py", f"{m_stem}_test.py", f"{m_stem}.py", f"test_{m_clean}.py", f"{m_clean}_test.py"):
            return True
        if t_stem.startswith(f"test_{m_stem}") or t_stem.endswith(f"_{m_stem}"):
            return True
        if m_clean and (t_stem.startswith(f"test_{m_clean}") or t_stem.endswith(f"_{m_clean}")):
            return True
        if f"/test_{m_stem}.py" in t_posix or f"/{m_stem}_test.py" in t_posix:
            return True
        if m_clean and (f"/test_{m_clean}.py" in t_posix or f"/{m_clean}_test.py" in t_posix):
            return True

    return False


def is_assertion_mismatch(
    error_type: str,
    actual: Optional[str] = None,
    expected: Optional[str] = None,
    diff: Optional[str] = None,
    explanation: str = "",
    statement: str = "",
    error_msg: str = "",
) -> bool:
    """Check if the failure is an assertion mismatch (e.g. sequence length, string diff, equality)."""
    non_assert_errors = {
        "AttributeError",
        "TypeError",
        "ImportError",
        "ModuleNotFoundError",
        "KeyError",
        "IndexError",
        "NameError",
        "SyntaxError",
        "IndentationError",
        "ZeroDivisionError",
        "FileNotFoundError",
        "PermissionError",
        "TimeoutError",
        "RuntimeError",
        "RecursionError",
        "UnboundLocalError",
        "NotImplementedError",
    }
    if error_type in non_assert_errors:
        return False

    is_assert_type = (error_type == "AssertionError") or statement.strip().startswith("assert") or ("assert " in statement)
    if not is_assert_type:
        return False

    if actual is not None and expected is not None:
        return True
    if diff is not None and diff.strip():
        return True
    if any(k in statement for k in ("==", "!=", " in ", "len(", ">", "<")):
        return True
    expl_lower = explanation.lower()
    if any(k in expl_lower for k in ("mismatch", "expected", "got", "differed", "extra", "missing", "boundary defect", "returned", "differs")):
        return True
    if any(k in error_msg.lower() for k in ("assert", "differing", "contains", "equal", "==", "!=")):
        return True
    return True


def generate_remediation_hint(
    error_type: str,
    explanation: str,
    correlated_modifications: List[str],
    failing_statement: str,
    expected: Optional[str],
    actual: Optional[str],
    locations: List[Tuple[str, int, str]],
    prefix_conflict_advisory: Optional[str] = None,
) -> str:
    """Generate an actionable remediation hint based on diagnosis and correlation."""
    frame_mod = None
    for loc_file, loc_line, loc_func in locations:
        if any(cm in loc_file for cm in correlated_modifications):
            frame_mod = (loc_file, loc_line, loc_func)
            break

    target_ref = clean_remediation_target(correlated_modifications[0]) if correlated_modifications else "modified files"

    if "BOUNDARY DEFECT" in explanation:
        base_hint = f"Check {target_ref}: boundary condition or empty input mismatch. Verify edge-case handling in data transformation."
    elif error_type == "AttributeError":
        if frame_mod:
            base_hint = f"Check '{frame_mod[2]}' in '{frame_mod[0]}:{frame_mod[1]}': verify object is not None and attribute exists before access."
        else:
            base_hint = f"Check {target_ref}: verify object initialization and attribute definitions."
    elif error_type == "TypeError":
        if frame_mod:
            base_hint = f"Check signature at '{frame_mod[0]}:{frame_mod[1]}' in '{frame_mod[2]}': adjust parameter count/types to match callers."
        else:
            base_hint = f"Check {target_ref}: ensure function/method signatures align with existing test callers."
    elif error_type in ("ImportError", "ModuleNotFoundError"):
        base_hint = f"Check {target_ref}: verify imported symbol exists, is exported, and not misspelled/renamed."
    elif error_type == "KeyError":
        base_hint = f"Check {target_ref}: ensure modified code populates the required dictionary key."
    elif expected and actual:
        base_hint = f"Review {target_ref}: expected {expected} but produced {actual}."
    else:
        base_hint = f"Review recent modifications in {target_ref} affecting `{failing_statement or 'this test'}`."

    if prefix_conflict_advisory:
        return f"{base_hint}\n  {prefix_conflict_advisory}"
    return base_hint


def parse_pytest_output(
    raw_output: str,
    ws: pathlib.Path,
    modified_files: List[pathlib.Path],
    targets: List[pathlib.Path],
    test_files: List[str],
    exit_code: int,
    consumer_test_files: Optional[List[str]] = None,
    direct_test_files: Optional[List[str]] = None,
) -> BlastRadiusResult:
    """Parse pytest failure blocks into rich Pydantic v2 diagnostic schemas."""
    clean_out = strip_ansi(raw_output)
    lines = clean_out.splitlines()

    # Regex patterns
    header_re = re.compile(r"^_{3,}\s+(.*?)\s+_{3,}$")
    loc_re = re.compile(r"^(.*?):(\d+):\s+in\s+(\S+)")
    assert_eq_re = re.compile(r"(?:AssertionError:\s+)?assert\s+(.+?)\s+==\s+(.+)$")
    assert_in_re = re.compile(r"(?:AssertionError:\s+)?assert\s+(.+?)\s+in\s+(.+)$")
    assert_ne_re = re.compile(r"(?:AssertionError:\s+)?assert\s+(.+?)\s+!=\s+(.+)$")
    err_re = re.compile(r"^E\s+([A-Za-z_][A-Za-z0-9_]*Error|[A-Za-z_][A-Za-z0-9_]*Exception):\s*(.*)$")

    # Extract test counts from summary line
    total_passed = 0
    total_failed = 0
    total_errors = 0
    summary_line = ""
    for line in reversed(lines):
        s = line.strip("= ").strip()
        if "passed" in s.lower() or "failed" in s.lower() or "error" in s.lower():
            summary_line = s
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

    # Extract short test summary info items
    summary_failures: Dict[str, str] = {}
    in_summary = False
    for line in lines:
        clean = line.strip()
        if clean.startswith("="):
            if "short test summary info" in clean:
                in_summary = True
                continue
            elif in_summary:
                in_summary = False
        if in_summary:
            if clean.startswith("FAILED ") or clean.startswith("ERROR "):
                parts = clean.split(maxsplit=2)
                if len(parts) >= 2:
                    test_id = clean_test_id(parts[1], ws)
                    msg = parts[2].lstrip("- :").strip() if len(parts) > 2 else ""
                    summary_failures[test_id] = msg

    # Partition output into failure blocks
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

    failures: List[TestFailureDetail] = []

    for header, blines in blocks:
        locations: List[Tuple[str, int, str]] = []
        statement = ""
        error_type = "AssertionError"
        error_msg = ""
        e_lines: List[str] = []
        stdout_lines: List[str] = []
        stderr_lines: List[str] = []
        capture_mode: Optional[str] = None

        for bline in blines:
            sline = bline.strip()
            if "Captured stdout call" in sline:
                capture_mode = "stdout"
                continue
            elif "Captured stderr call" in sline:
                capture_mode = "stderr"
                continue
            elif sline.startswith("-----------------------------") and capture_mode:
                capture_mode = None
                continue

            if capture_mode == "stdout":
                stdout_lines.append(bline)
                continue
            elif capture_mode == "stderr":
                stderr_lines.append(bline)
                continue

            lm = loc_re.match(sline)
            if lm:
                locations.append((lm.group(1), int(lm.group(2)), lm.group(3)))
                continue

            if sline.startswith("E   ") or sline.startswith("E "):
                e_content = sline[2:].strip()
                e_lines.append(e_content)
                em = err_re.match(sline)
                if em:
                    error_type = em.group(1)
                    error_msg = em.group(2).strip()
                elif "assert " in sline and not error_msg:
                    error_type = "AssertionError"
                    error_msg = e_content
            elif sline.startswith("assert ") or (bline.startswith("    ") and not bline.startswith("    in ") and not statement):
                if not statement and ("assert " in sline or any(c in sline for c in ("=", "(", ")", "raise "))):
                    statement = sline

        test_file_str = ""
        line_no: Optional[int] = None
        func_name = header
        if locations:
            test_file_str = locations[0][0]
            line_no = locations[0][1]
            func_name = locations[0][2]

        test_id_cand = f"{pathlib.Path(test_file_str).name}::{func_name}"
        for s_id in summary_failures:
            if s_id.endswith(f"::{func_name}") or func_name in s_id:
                test_id_cand = s_id
                break

        test_fpath = pathlib.Path(test_file_str)
        if not test_fpath.is_absolute():
            test_fpath = ws / test_file_str

        # Extract actual vs expected from E lines
        actual_val: Optional[str] = None
        expected_val: Optional[str] = None
        for el in e_lines:
            am = assert_eq_re.search(el)
            if am:
                actual_val = am.group(1).strip()
                expected_val = am.group(2).strip()
                break
            am_in = assert_in_re.search(el)
            if am_in:
                actual_val = am_in.group(1).strip()
                expected_val = f"in {am_in.group(2).strip()}"
                break
            am_ne = assert_ne_re.search(el)
            if am_ne:
                actual_val = am_ne.group(1).strip()
                expected_val = f"!= {am_ne.group(2).strip()}"
                break

        diff_str: Optional[str] = None
        diff_lines = [
            l for l in e_lines
            if l.startswith(("- ", "+ ", "? ", "Differing items", "Common items", "Left contains", "Right contains"))
        ]
        if diff_lines:
            diff_str = "\n".join(diff_lines[:10])

        corrs = correlate_test_with_modified(test_fpath, func_name, locations, statement, modified_files, ws)
        expl = explain_mismatch(actual_val, expected_val, error_type, error_msg, statement)

        # Check for pre-fix test conflict advisory
        candidate_test_refs = [test_file_str, test_id_cand]
        for loc_f, _, _ in locations:
            if "test" in loc_f.lower():
                candidate_test_refs.append(loc_f)

        is_direct = any(is_direct_unit_test(t_ref, modified_files, targets, direct_test_files=direct_test_files) for t_ref in candidate_test_refs if t_ref)
        is_mismatch = is_assertion_mismatch(error_type, actual_val, expected_val, diff_str, expl, statement, error_msg)
        prefix_advisory: Optional[str] = PREFIX_CONFLICT_ADVISORY if (is_direct and is_mismatch) else None

        hint = generate_remediation_hint(
            error_type,
            expl,
            corrs,
            statement,
            expected_val,
            actual_val,
            locations,
            prefix_conflict_advisory=prefix_advisory,
        )

        loc_str = f"{clean_test_id(test_file_str, ws)}:{line_no}: in {func_name}" if line_no else f"{clean_test_id(test_file_str, ws)}: in {func_name}"

        failures.append(TestFailureDetail(
            test_id=test_id_cand,
            test_file=clean_test_id(test_file_str, ws),
            test_name=func_name,
            line_number=line_no,
            failure_location=loc_str,
            error_type=error_type,
            failing_statement=statement,
            error_message=error_msg,
            expected=expected_val,
            actual=actual_val,
            diff=diff_str,
            captured_stdout="\n".join(stdout_lines[:5]) if stdout_lines else None,
            captured_stderr="\n".join(stderr_lines[:5]) if stderr_lines else None,
            correlated_modifications=corrs,
            explanation=expl,
            remediation_hint=hint,
            prefix_conflict_advisory=prefix_advisory,
        ))

    # Fallback if pytest returned failure but no structured blocks were parsed
    if exit_code != 0 and not failures:
        fallback_msg = "\n".join(lines[-6:]).strip() if lines else "Pytest failed with exit code"
        failures.append(TestFailureDetail(
            test_id="pytest::execution",
            test_file=test_files[0] if test_files else "",
            test_name="execution",
            error_type="PytestError",
            failing_statement="",
            error_message=fallback_msg,
            explanation=f"Pytest failed with exit code {exit_code}: {fallback_msg}",
            remediation_hint="Review test execution errors above or check test environment.",
        ))

    # Group common failures into FailureDiagnosis objects
    diag_groups = defaultdict(list)
    for f in failures:
        group_target = get_grouping_target(f.correlated_modifications)
        k = (f.error_type, f.explanation, group_target)
        diag_groups[k].append(f)

    diagnoses: List[FailureDiagnosis] = []
    for (err_t, expl, grp_tgt), items in diag_groups.items():
        t_ids = [it.test_id for it in items]
        all_corrs: List[str] = []
        for it in items:
            for c in it.correlated_modifications:
                if c not in all_corrs:
                    all_corrs.append(c)

        if len(items) == 1:
            it = items[0]
            if "BOUNDARY DEFECT" in expl:
                summ = f"REGRESSION ROOT CAUSE: In `{it.test_id}`, {expl}"
            elif it.expected and it.actual:
                summ = f"REGRESSION ROOT CAUSE: In `{it.test_id}`, assertion failed: expected {it.expected} but got {it.actual}. {expl}"
            else:
                summ = f"REGRESSION ROOT CAUSE: In `{it.test_id}`, {expl}"
        else:
            t_names = [it.test_name for it in items]
            corr_summary = f" Shared regression in `{grp_tgt}`." if grp_tgt != "repo" else ""
            if "BOUNDARY DEFECT" in expl:
                summ = f"REGRESSION ROOT CAUSE: Across {len(items)} tests ({', '.join(t_names[:3])}), {expl}{corr_summary}"
            else:
                summ = f"REGRESSION ROOT CAUSE: Across {len(items)} tests ({', '.join(t_names[:3])}), assertion failed: {expl}{corr_summary}"

        # Collect prefix conflict advisory across items in this group
        group_prefix_advisory = next((it.prefix_conflict_advisory for it in items if it.prefix_conflict_advisory), None)
        item_with_advisory = next((it for it in items if it.prefix_conflict_advisory), None)
        diag_hint = item_with_advisory.remediation_hint if item_with_advisory else items[0].remediation_hint

        diagnoses.append(FailureDiagnosis(
            summary=summ,
            failing_tests=t_ids,
            suspected_modified_files=all_corrs,
            common_mismatch=expl,
            remediation_hint=diag_hint,
            prefix_conflict_advisory=group_prefix_advisory,
        ))

    # String format targets and modified files
    t_strs = []
    for t in targets:
        try:
            t_strs.append(t.relative_to(ws).as_posix())
        except ValueError:
            t_strs.append(t.as_posix() if hasattr(t, "as_posix") else str(t))

    m_strs = []
    for m in modified_files:
        try:
            m_strs.append(m.relative_to(ws).as_posix())
        except ValueError:
            m_strs.append(m.as_posix() if hasattr(m, "as_posix") else str(m))

    target_file = t_strs[0] if len(t_strs) == 1 else (", ".join(t_strs) if t_strs else (m_strs[0] if m_strs else "target"))
    multi_file_info = format_multi_file_warning(modified_files, target_file)

    # Evaluate smart verdict: pre-fix baseline conflicts vs real regressions
    all_failures_in_direct_tests = True
    all_failures_assertion_mismatches = True
    consumer_failures: List[TestFailureDetail] = []

    non_conflict_errors = {
        "AttributeError",
        "TypeError",
        "ImportError",
        "ModuleNotFoundError",
        "KeyError",
        "IndexError",
        "NameError",
        "SyntaxError",
        "IndentationError",
        "ZeroDivisionError",
        "FileNotFoundError",
        "PermissionError",
        "TimeoutError",
        "RuntimeError",
        "RecursionError",
        "UnboundLocalError",
        "NotImplementedError",
        "PytestError",
    }

    for f in failures:
        in_direct = is_direct_unit_test(
            f.test_file or f.test_id,
            modified_files,
            targets,
            direct_test_files=direct_test_files,
        )
        if not in_direct:
            all_failures_in_direct_tests = False
            consumer_failures.append(f)

        is_mismatch = is_assertion_mismatch(
            f.error_type,
            f.actual,
            f.expected,
            f.diff,
            f.explanation,
            f.failing_statement,
            f.error_message,
        ) or bool(f.prefix_conflict_advisory)

        if f.error_type in non_conflict_errors or not is_mismatch:
            all_failures_assertion_mismatches = False

    if exit_code == 0:
        if total_passed == 0 and total_failed == 0 and total_errors == 0:
            status = "UNVERIFIED_NO_TESTS"
            passed = False
            base_summary = (
                f"UNVERIFIED_NO_TESTS: 0 tests executed across {test_files}. "
                f"Verification required before submission."
            )
        else:
            status = "PASSED"
            passed = True
            base_summary = summary_line or "All tests passed."
    elif (
        failures
        and all_failures_in_direct_tests
        and len(consumer_failures) == 0
    ):
        status = "FAILED_DIRECT_TESTS_SUSPECTED_CONFLICT"
        passed = False
        base_summary = (
            f"FAILED_DIRECT_TESTS_SUSPECTED_CONFLICT: "
            f"Direct unit tests failed ({len(failures)} mismatch(es)/failure(s)), "
            f"while distance-1 consumer tests passed. Verification CANNOT pass while direct tests fail."
        )
    else:
        status = "FAILED"
        passed = False
        base_summary = summary_line or f"{len(failures)} test(s) failed."

    final_summary = f"{multi_file_info} | {base_summary}" if multi_file_info else base_summary
    if status == "FAILED_DIRECT_TESTS_SUSPECTED_CONFLICT":
        overall_prefix_advisory = (
            "[blast-radius] ⚠️ DIRECT UNIT TESTS FAILED: Pre-fix assertion baseline conflict suspected, "
            "but verification CANNOT pass while direct tests fail. "
            "If this file was intentionally altered, verify that this is indeed the target file requested by the issue, not a secondary file!"
        )
    else:
        overall_prefix_advisory = next((d.prefix_conflict_advisory for d in diagnoses if d.prefix_conflict_advisory), None)

    return BlastRadiusResult(
        targets=t_strs,
        modified_files=m_strs,
        distance1_consumers=[],
        test_files=test_files,
        direct_test_files=direct_test_files or [],
        consumer_test_files=consumer_test_files or [],
        exit_code=exit_code,
        passed=passed,
        status=status,
        summary=final_summary,
        multi_file_warning=multi_file_info,
        total_passed=total_passed,
        total_failed=total_failed or (len(failures) if exit_code != 0 else 0),
        total_errors=total_errors,
        failures=failures,
        diagnoses=diagnoses,
        prefix_conflict_advisory=overall_prefix_advisory,
    )


def format_failure_report(result: BlastRadiusResult, max_lines: int = 40) -> str:
    """Format a clean, deterministic, context-capped triage report."""
    out_lines: List[str] = []
    if result.status == "FAILED_DIRECT_TESTS_SUSPECTED_CONFLICT":
        out_lines.append(f"[blast-radius] ⚠️ DIRECT UNIT TESTS FAILED (Exit code: {result.exit_code}):")
        out_lines.append("=" * 80)
    else:
        out_lines.append(f"[blast-radius] 💥 REGRESSION DETECTED IN BLAST RADIUS (Exit code: {result.exit_code}):")
        out_lines.append("=" * 80)

    if len(result.modified_files) > 1:
        out_lines.append(f"ℹ️ Modified files under test: {', '.join(result.modified_files)}")
        out_lines.append("-" * 80)

    for diag in result.diagnoses[:3]:
        out_lines.append(diag.summary)
        if diag.suspected_modified_files:
            corr_desc = diag.suspected_modified_files[0]
            if corr_desc.startswith("Failing test") or corr_desc.startswith("Triggered exception"):
                out_lines.append(f"  • Root cause correlation: {corr_desc}")
            else:
                out_lines.append(f"  • Correlated repo file(s): `{corr_desc}`")

        # Find representative failure detail for this diagnosis
        rep_fail = None
        for f in result.failures:
            if f.test_id in diag.failing_tests:
                rep_fail = f
                break

        if rep_fail:
            if rep_fail.failing_statement:
                loc_hint = f" (line {rep_fail.line_number})" if rep_fail.line_number else ""
                out_lines.append(f"  • Failing statement: `{rep_fail.failing_statement}`{loc_hint}")
            if rep_fail.expected and rep_fail.actual:
                out_lines.append(f"  • Expected: {rep_fail.expected}")
                out_lines.append(f"  • Actual:   {rep_fail.actual}")
            if rep_fail.diff:
                out_lines.append("  • Diff:")
                for dl in rep_fail.diff.splitlines()[:5]:
                    out_lines.append(f"      {dl}")
            if rep_fail.captured_stdout:
                stdout_first = rep_fail.captured_stdout.strip().splitlines()[0]
                out_lines.append(f"  • Captured stdout: {stdout_first[:100]}")
            if rep_fail.captured_stderr:
                stderr_first = rep_fail.captured_stderr.strip().splitlines()[0]
                out_lines.append(f"  • Captured stderr: {stderr_first[:100]}")

        if diag.remediation_hint:
            out_lines.append(f"  • Remediation hint: {diag.remediation_hint}")
        if diag.prefix_conflict_advisory and diag.prefix_conflict_advisory not in (diag.remediation_hint or ""):
            out_lines.append(f"  {diag.prefix_conflict_advisory}")
        out_lines.append("-" * 80)

    if len(result.diagnoses) > 3:
        remaining = len(result.diagnoses) - 3
        out_lines.append(f"  ... (+{remaining} additional failure group(s) truncated for clarity)")

    footer_lines: List[str] = []
    if result.status == "FAILED_DIRECT_TESTS_SUSPECTED_CONFLICT":
        footer_lines.append("=" * 80)
        footer_lines.append(
            "[blast-radius] ⚠️ DIRECT UNIT TESTS FAILED: Pre-fix assertion baseline conflict suspected, "
            "but verification CANNOT pass while direct tests fail. "
            "If this file was intentionally altered, verify that this is indeed the target file requested by the issue, not a secondary file!"
        )
    else:
        footer_lines.append("[blast-radius] ⚠️ FIX OR REVERT: Changes broke the tests listed above!")

    if len(out_lines) + len(footer_lines) > max_lines:
        allowed = max(1, max_lines - len(footer_lines) - 1)
        out_lines = out_lines[:allowed] + ["  ... (+ additional failure details truncated for length)"]

    return "\n".join(out_lines + footer_lines)


def main() -> int:
    """Main CLI entrypoint. Always returns exit code 0."""
    try:
        # Check for help flag
        if any(arg in ("-h", "--help") for arg in sys.argv[1:]):
            print("Usage: python3 test_blast.py [target_file_or_symbol...]")
            print("\nOptions:")
            print("  -h, --help    Show this help message and exit")
            print("  --json        Output structured diagnosis as JSON")
            return 0

        json_mode = "--json" in sys.argv[1:]
        raw_args = [arg for arg in sys.argv[1:] if arg not in ("--json", "-h", "--help")]

        ws = get_workspace_dir()

        # Determine targets from CLI args or git status
        targets: List[pathlib.Path] = []
        if raw_args:
            for arg in raw_args:
                arg_clean = arg.strip()
                if arg_clean:
                    targets.append(resolve_target(arg_clean, ws))
        else:
            targets = _get_modified_files(ws)

        if not targets:
            print("[blast-radius] ⚠️ No modified files detected and no target specified.")
            print("[blast-radius] Usage: python3 test_blast.py <path/to/file.py>")
            return 0

        all_test_files: List[str] = []
        all_consumers: List[str] = []
        all_direct_tests: List[str] = []
        all_consumer_tests: List[str] = []

        for t in targets:
            scope = find_blast_radius(t, ws)
            tests, consumers = scope[:2]
            directs = getattr(scope, "direct_tests", [])
            cons_tests = getattr(scope, "consumer_tests", [])

            for tst in tests:
                if tst not in all_test_files:
                    all_test_files.append(tst)
            for c in consumers:
                if c not in all_consumers:
                    all_consumers.append(c)
            for dt in directs:
                if dt not in all_direct_tests:
                    all_direct_tests.append(dt)
            for ct in cons_tests:
                if ct not in all_consumer_tests:
                    all_consumer_tests.append(ct)

        # Format target names
        def format_target_name(t: pathlib.Path) -> str:
            try:
                return t.relative_to(ws).as_posix()
            except ValueError:
                return t.name

        target_names = ", ".join(format_target_name(t) for t in targets)
        if not json_mode:
            all_repo_modified = _get_modified_files(ws)
            if len(all_repo_modified) > 1:
                all_mod_names = [format_target_name(m) for m in all_repo_modified]
                print(f"[blast-radius] ℹ️ MULTI-FILE TARGET: {len(all_repo_modified)} files modified ({all_mod_names}).")
            print(f"[blast-radius] TARGET(S): {target_names}")
            if all_consumers:
                consumer_preview = ", ".join(all_consumers[:5])
                more = f" (+{len(all_consumers)-5} more)" if len(all_consumers) > 5 else ""
                print(f"[blast-radius] DISTANCE-1 CONSUMERS: {consumer_preview}{more}")
            else:
                print("[blast-radius] DISTANCE-1 CONSUMERS: (none detected)")

        if not all_test_files:
            target_str = format_target_name(targets[0]) if targets else "target"
            mod_names = [format_target_name(t) for t in targets]
            empty_summary = (
                f"UNVERIFIED_NO_TESTS: 0 matching test files found for modified target(s) ({target_names}). "
                f"Verification required before submission."
            )
            multi_file_info = format_multi_file_warning(targets, target_str)

            if not json_mode:
                if multi_file_info:
                    print(f"[blast-radius] {multi_file_info}")
                print(f"[blast-radius] ⚠️ STATUS: UNVERIFIED_NO_TESTS")
                print(f"[blast-radius] ⚠️ No matching test files found for {target_names}.")
                print(f"[blast-radius] ⚠️ VERIFICATION REQUIRED: 0 tests were executed. Do NOT submit patch without running or writing verification tests!")
            else:
                empty_res = BlastRadiusResult(
                    targets=[format_target_name(t) for t in targets],
                    modified_files=[format_target_name(t) for t in targets],
                    distance1_consumers=all_consumers,
                    test_files=[],
                    direct_test_files=[],
                    consumer_test_files=[],
                    exit_code=0,
                    passed=False,
                    status="UNVERIFIED_NO_TESTS",
                    summary=empty_summary,
                    multi_file_warning=multi_file_info,
                )
                print(empty_res.model_dump_json(indent=2))
            return 0

        test_display = ", ".join(all_test_files[:5])
        if not json_mode:
            print(f"[blast-radius] RUNNING TESTS ({len(all_test_files)} file(s)): {test_display}")

        exit_code, raw_output = run_pytest(all_test_files, ws)
        modified_in_repo = _get_modified_files(ws) or targets

        result = parse_pytest_output(
            raw_output=raw_output,
            ws=ws,
            modified_files=modified_in_repo,
            targets=targets,
            test_files=all_test_files,
            exit_code=exit_code,
            consumer_test_files=all_consumer_tests,
            direct_test_files=all_direct_tests,
        )
        result.distance1_consumers = all_consumers
        result.direct_test_files = all_direct_tests
        result.consumer_test_files = all_consumer_tests

        if json_mode:
            print(result.model_dump_json(indent=2))
        elif result.status == "FAILED_DIRECT_TESTS_SUSPECTED_CONFLICT":
            print(format_failure_report(result, max_lines=40))
        elif result.status == "UNVERIFIED_NO_TESTS":
            print(f"[blast-radius] ⚠️ STATUS: UNVERIFIED_NO_TESTS")
            print(f"[blast-radius] {result.summary}")
            print(f"[blast-radius] ⚠️ VERIFICATION REQUIRED: 0 tests were executed. Do NOT submit patch without verification!")
        elif exit_code == 0 and result.passed:
            print(f"[blast-radius] ✅ PASSED: {result.summary}")
        else:
            print(format_failure_report(result, max_lines=40))

        return 0
    except Exception as e:
        print(f"[blast-radius] ⚠️ Error running blast radius tests: {e}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
