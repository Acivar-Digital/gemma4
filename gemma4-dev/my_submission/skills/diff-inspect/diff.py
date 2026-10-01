#!/usr/bin/env python3
"""diff-inspect: Safe, read-only Git status and diff inspector.

Executes `git status --porcelain` and `git diff` against `HEAD` (or `_swegemma_baseline`)
cleanly without modifying /workspace.

Features:
- Deterministic empty-diff explanations: explains why 0 files modified relative to HEAD
  and why calling submit_patch will fail.
- High-visibility scratch file warnings: detects untracked temporary/repro files
  (e.g., repro.py, test_*.py, tmp*.py) and warns about 'git add -N .' patch pollution.
- Multi-file contamination warnings: alerts when total_files_modified > 1 to prevent
  accidental patch contamination across multiple files.
- File-by-file line diff statistics: additions (+), deletions (-), and file status.
- Risk detection for forbidden harness files (pytest.ini, conftest.py) and test suite files.
- 100% Pydantic v2 structured outputs (DiffInspectResult, FileDiffStat, DiffWarning).
- Context-safe: unified diff preview capped at 100 lines.
- Always exits with code 0.

Usage:
    python3 diff.py [optional_path_or_flag]
    python3 diff.py --json
"""

from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess
import sys
from typing import Any, List, Optional, Tuple

sys.dont_write_bytecode = True

from pydantic import BaseModel, ConfigDict, Field


# ==============================================================================
# 1. Pydantic v2 Models for Structured Inspection
# ==============================================================================

class DiffWarning(BaseModel):
    """Structured warning emitted during git status and diff inspection."""

    model_config = ConfigDict(extra="ignore")

    category: str = Field(
        ...,
        description="Warning category (e.g. DANGER_UNTRACKED_SCRATCH, FORBIDDEN_HARNESS_FILE, TEST_FILE_MODIFIED, EMPTY_DIFF, MULTI_FILE_CONTAMINATION)",
    )
    path: str = Field(
        default="",
        description="File path associated with the warning",
    )
    message: str = Field(
        ...,
        description="High-visibility warning message",
    )
    risk_explanation: str = Field(
        default="",
        description="Detailed explanation of the risk for SWE-bench / Container B evaluation",
    )
    recommended_action: str = Field(
        default="",
        description="Action the agent should take to resolve the warning",
    )


class FileDiffStat(BaseModel):
    """Detailed file-level git diff statistics and safety classifications."""

    model_config = ConfigDict(extra="ignore")

    path: str = Field(
        ...,
        description="Relative file path in workspace",
    )
    status: str = Field(
        default="M",
        description="Git status code (M=modified, A=added, D=deleted, R=renamed, ??=untracked)",
    )
    additions: int = Field(
        default=0,
        ge=0,
        description="Number of lines added",
    )
    deletions: int = Field(
        default=0,
        ge=0,
        description="Number of lines deleted",
    )
    binary: bool = Field(
        default=False,
        description="True if file is binary",
    )
    is_forbidden_harness_file: bool = Field(
        default=False,
        description="True if file is a forbidden harness configuration file (pytest.ini, conftest.py, etc.)",
    )
    is_test_file: bool = Field(
        default=False,
        description="True if file is part of the test suite (e.g. under tests/ or test_*.py)",
    )
    is_scratch_file: bool = Field(
        default=False,
        description="True if file matches temporary/reproduction scratch file patterns",
    )


class DiffInspectResult(BaseModel):
    """Comprehensive, structured evaluation of git diff and workspace cleanliness."""

    model_config = ConfigDict(extra="ignore")

    workspace: str = Field(
        ...,
        description="Absolute path to the workspace directory",
    )
    base_ref: str = Field(
        default="HEAD",
        description="Git base reference used for comparison (e.g. HEAD or _swegemma_baseline)",
    )
    is_clean: bool = Field(
        default=True,
        description="True if diff is clean (0 modified files, 0 additions, 0 deletions)",
    )
    total_files_modified: int = Field(
        default=0,
        ge=0,
        description="Total count of modified, added, or deleted tracked files in diff",
    )
    total_additions: int = Field(
        default=0,
        ge=0,
        description="Total lines added across all modified files",
    )
    total_deletions: int = Field(
        default=0,
        ge=0,
        description="Total lines deleted across all modified files",
    )
    file_stats: list[FileDiffStat] = Field(
        default_factory=list,
        description="File-by-file breakdown of changes and risk classifications",
    )
    untracked_files: list[str] = Field(
        default_factory=list,
        description="List of all untracked files detected via git status --porcelain",
    )
    dangerous_untracked_files: list[str] = Field(
        default_factory=list,
        description="List of untracked files identified as dangerous scratch/repro scripts",
    )
    forbidden_files_modified: list[str] = Field(
        default_factory=list,
        description="List of modified files that are forbidden harness configs or test files",
    )
    warnings: list[DiffWarning] = Field(
        default_factory=list,
        description="Structured warnings highlighting dangerous states, dirty files, or empty diffs",
    )
    summary_explanation: str = Field(
        default="",
        description="Human/agent-readable explanation of why diff is empty or summary of changes",
    )
    can_submit_patch: bool = Field(
        default=False,
        description="True if diff is non-empty and no dangerous scratch files exist in /workspace",
    )
    submit_patch_advice: str = Field(
        default="",
        description="Explicit directive on whether submit_patch should be called or avoided",
    )
    diff_preview: str = Field(
        default="",
        description="Unified diff preview capped at max lines",
    )
    diff_lines_truncated: int = Field(
        default=0,
        ge=0,
        description="Count of diff lines omitted due to context safety cap",
    )


# ==============================================================================
# 2. Risk Classification Helpers
# ==============================================================================

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


def is_scratch_file(path_str: str) -> bool:
    """Identify if a file path matches temporary, reproduction, or scratch script patterns."""
    p = pathlib.Path(path_str)
    name = p.name.lower()

    # Ignore ADK execution wrapper files completely
    if ".adk_exec" in name or name.startswith(".adk_exec"):
        return False

    # Scratch extensions
    if name.endswith((".tmp", ".temp", ".log", ".bak", ".swp", "~")):
        return True

    # Scratch regex patterns on file name
    for pat in SCRATCH_FILE_PATTERNS:
        if re.match(pat, name):
            return True

    # Single-part root files that are python scripts (e.g. repro.py, foo.py, check.py in workspace root)
    if len(p.parts) == 1 and name.endswith(".py"):
        return True

    # Any path containing temporary/scratch directories
    parts_lower = [part.lower() for part in p.parts]
    if any(part in ("tmp", "temp", "scratch") for part in parts_lower):
        return True

    return False


def is_forbidden_harness_file(path_str: str) -> bool:
    """Check if file is a forbidden or high-risk test harness configuration file."""
    p = pathlib.Path(path_str)
    name = p.name.lower()
    if name in FORBIDDEN_HARNESS_FILES:
        return True
    if name == "pyproject.toml":
        return True
    return False


def is_test_file(path_str: str) -> bool:
    """Check if file is part of the test suite."""
    p = pathlib.Path(path_str)
    name = p.name.lower()
    parts_lower = [part.lower() for part in p.parts]
    if any(part in ("tests", "test", "testing") for part in parts_lower):
        return True
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    return False


# ==============================================================================
# 3. Workspace Resolution & Git Command Runners
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


def run_git_cmd(args: List[str], cwd: pathlib.Path, timeout_secs: int = 15) -> Tuple[int, str]:
    """Execute a git command safely in cwd without throwing exceptions."""
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
        output = res.stdout if res.stdout else res.stderr
        return res.returncode, output.strip()
    except subprocess.TimeoutExpired:
        return 1, f"Command timed out after {timeout_secs}s: git {' '.join(args)}"
    except Exception as e:
        return 1, f"Git command failed: {e}"


def determine_base_ref(ws: pathlib.Path) -> str:
    """Determine base reference for diff inspection (defaults to HEAD for submit_patch)."""
    code, _ = run_git_cmd(["rev-parse", "--verify", "HEAD"], cwd=ws, timeout_secs=5)
    if code == 0:
        return "HEAD"
    code, _ = run_git_cmd(["rev-parse", "--verify", "_swegemma_baseline"], cwd=ws, timeout_secs=5)
    if code == 0:
        return "_swegemma_baseline"
    return ""


# ==============================================================================
# 4. Core Inspection Engine
# ==============================================================================

def inspect_diff(ws: pathlib.Path, extra_args: Optional[List[str]] = None) -> DiffInspectResult:
    """Safely inspect git status, untracked files, line diffs, and risk factors."""
    extra_args = [arg for arg in (extra_args or []) if arg.strip()]

    # Verify git repository status
    code, out = run_git_cmd(["rev-parse", "--is-inside-work-tree"], cwd=ws, timeout_secs=5)
    if code != 0 or out.lower() != "true":
        return DiffInspectResult(
            workspace=str(ws),
            base_ref="",
            is_clean=True,
            total_files_modified=0,
            total_additions=0,
            total_deletions=0,
            file_stats=[],
            untracked_files=[],
            dangerous_untracked_files=[],
            forbidden_files_modified=[],
            warnings=[
                DiffWarning(
                    category="NOT_A_GIT_REPO",
                    path=str(ws),
                    message=f"[diff-inspect] Workspace at '{ws}' is not a git repository.",
                    risk_explanation="Cannot run git status or git diff outside a git repository.",
                    recommended_action="Ensure SWEGEMMA_WORKSPACE or cwd points to a valid git repository.",
                )
            ],
            summary_explanation=f"[diff-inspect] Workspace at '{ws}' is not a git repository.",
            can_submit_patch=False,
            submit_patch_advice="Cannot submit patch: workspace is not a git repository.",
            diff_preview="(not a git repository)",
            diff_lines_truncated=0,
        )

    base_ref = determine_base_ref(ws)
    warnings: list[DiffWarning] = []

    # 1. Parse git status --porcelain -uall
    code, status_out = run_git_cmd(
        [
            "status",
            "--porcelain",
            "-uall",
            "--",
            ".",
            ":(exclude)*.adk_exec*",
            ":(exclude)**/.adk_exec*",
        ],
        cwd=ws,
        timeout_secs=10,
    )
    if code != 0:
        code, status_out = run_git_cmd(["status", "--porcelain", "-uall"], cwd=ws, timeout_secs=10)
    if code != 0:
        code, status_out = run_git_cmd(["status", "--porcelain"], cwd=ws, timeout_secs=10)

    untracked_files: list[str] = []
    dangerous_untracked_files: list[str] = []
    status_map: dict[str, str] = {}

    for line in status_out.splitlines():
        line = line.rstrip()
        if not line or len(line) < 3:
            continue
        status_code = line[:2].strip()
        rel_path = line[3:].strip().strip('"')
        if " -> " in rel_path:
            rel_path = rel_path.split(" -> ")[-1].strip().strip('"')

        if ".adk_exec" in rel_path or pathlib.Path(rel_path).name.startswith(".adk_exec"):
            continue

        if line.startswith("??"):
            untracked_files.append(rel_path)
            if is_scratch_file(rel_path):
                dangerous_untracked_files.append(rel_path)
        else:
            status_map[rel_path] = status_code or "M"

    # Emit High-Visibility DANGER warnings for dangerous untracked scratch files
    for d_file in dangerous_untracked_files:
        container_path = f"/workspace/{d_file}"
        warnings.append(
            DiffWarning(
                category="DANGER_UNTRACKED_SCRATCH",
                path=container_path,
                message=(
                    f"⚠️ DANGER: Untracked file detected: `{container_path}`. "
                    f"The harness runs `git add -N . && git diff HEAD`, meaning this scratch file will be submitted "
                    f"in your official patch! Delete it or move it to `/tmp`."
                ),
                risk_explanation=(
                    f"The harness runs 'git add -N . && git diff HEAD' inside /workspace. "
                    f"Any untracked file like '{container_path}' will be automatically added to the git index and included "
                    f"in your official submitted patch. Scratch files pollute the patch and cause evaluation failure."
                ),
                recommended_action=f"Delete '{container_path}' immediately or move it to '/tmp/' using run_command.",
            )
        )

    # Emit notices for any other untracked files
    for u_file in untracked_files:
        if u_file not in dangerous_untracked_files:
            container_path = f"/workspace/{u_file}"
            warnings.append(
                DiffWarning(
                    category="UNTRACKED_FILE",
                    path=container_path,
                    message=(
                        f"ℹ️ NOTICE: Untracked file detected: `{container_path}`. "
                        f"The harness runs `git add -N . && git diff HEAD`, which will include this file in your final patch."
                    ),
                    risk_explanation="Untracked files in /workspace will become part of your patch due to 'git add -N .'.",
                    recommended_action="If this is an intentional new source file for your fix, keep it. Otherwise, remove it.",
                )
            )

    # 2. Parse file-by-file line diff statistics via git diff --numstat
    numstat_cmd = ["diff", "--numstat"]
    if base_ref:
        numstat_cmd.append(base_ref)
    if extra_args:
        numstat_cmd.extend(extra_args)
    numstat_cmd.extend(["--", ".", ":(exclude)*.adk_exec*", ":(exclude)**/.adk_exec*"])

    code, numstat_out = run_git_cmd(numstat_cmd, cwd=ws, timeout_secs=10)
    if code != 0:
        numstat_cmd_fb = ["diff", "--numstat"]
        if base_ref:
            numstat_cmd_fb.append(base_ref)
        if extra_args:
            numstat_cmd_fb.extend(extra_args)
        _, numstat_out = run_git_cmd(numstat_cmd_fb, cwd=ws, timeout_secs=10)

    file_stats: list[FileDiffStat] = []
    forbidden_files_modified: list[str] = []
    total_additions = 0
    total_deletions = 0

    for line in numstat_out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            add_str, del_str, raw_path = parts[0], parts[1], parts[2]
            is_binary = (add_str == "-" and del_str == "-")
            adds = int(add_str) if not is_binary and add_str.isdigit() else 0
            dels = int(del_str) if not is_binary and del_str.isdigit() else 0

            # Normalize renames
            clean_path = raw_path
            if " => " in clean_path:
                clean_path = re.sub(r"\{.*? => (.*?)\}", r"\1", clean_path)
                if " => " in clean_path:
                    clean_path = clean_path.split(" => ")[-1].strip()

            if ".adk_exec" in clean_path or pathlib.Path(clean_path).name.startswith(".adk_exec"):
                continue

            total_additions += adds
            total_deletions += dels

            is_forbidden = is_forbidden_harness_file(clean_path)
            is_test = is_test_file(clean_path)
            is_scratch = is_scratch_file(clean_path)

            if is_forbidden or is_test:
                forbidden_files_modified.append(clean_path)

            file_status = status_map.get(clean_path, "M")

            file_stats.append(
                FileDiffStat(
                    path=clean_path,
                    status=file_status,
                    additions=adds,
                    deletions=dels,
                    binary=is_binary,
                    is_forbidden_harness_file=is_forbidden,
                    is_test_file=is_test,
                    is_scratch_file=is_scratch,
                )
            )

    # Emit warnings for forbidden harness files or modified tests
    for f_path in forbidden_files_modified:
        container_path = f"/workspace/{f_path}"
        if is_forbidden_harness_file(f_path):
            warnings.append(
                DiffWarning(
                    category="FORBIDDEN_HARNESS_FILE",
                    path=container_path,
                    message=f"⚠️ DANGER: Forbidden harness configuration file modified: `{container_path}`",
                    risk_explanation=(
                        f"Modifying harness configuration files like '{f_path}' alters test runner discovery, flags, "
                        f"or hooks in Container B, risking evaluation container crashes or test failure."
                    ),
                    recommended_action=f"Revert changes to '{container_path}' unless explicitly requested.",
                )
            )
        elif is_test_file(f_path):
            warnings.append(
                DiffWarning(
                    category="TEST_FILE_MODIFIED",
                    path=container_path,
                    message=f"⚠️ WARNING: Test file modified: `{container_path}`",
                    risk_explanation=(
                        f"In SWE-bench / SWE-Gemma harness evaluation (Container B), the evaluation suite applies "
                        f"its official test patch and discards or overwrites test-file modifications. Your patch must resolve "
                        f"the defect in the source codebase, not by altering existing test files."
                    ),
                    recommended_action="Ensure your defect fix is implemented in source code. Do not rely on test file edits.",
                )
            )

    # 3. Full diff preview capped at 100 lines
    diff_cmd = ["diff"]
    if base_ref:
        diff_cmd.append(base_ref)
    if extra_args:
        diff_cmd.extend(extra_args)
    diff_cmd.extend(["--", ".", ":(exclude)*.adk_exec*", ":(exclude)**/.adk_exec*"])

    code, diff_out = run_git_cmd(diff_cmd, cwd=ws, timeout_secs=15)
    if code != 0:
        diff_cmd_fb = ["diff"]
        if base_ref:
            diff_cmd_fb.append(base_ref)
        if extra_args:
            diff_cmd_fb.extend(extra_args)
        _, diff_out = run_git_cmd(diff_cmd_fb, cwd=ws, timeout_secs=15)
    diff_lines = diff_out.splitlines() if diff_out else []
    max_diff_lines = 100
    diff_lines_truncated = 0

    if len(diff_lines) > max_diff_lines:
        diff_preview = "\n".join(diff_lines[:max_diff_lines])
        diff_lines_truncated = len(diff_lines) - max_diff_lines
    else:
        diff_preview = diff_out

    # 4. Clean Diff Explanation & Patch Submission Feasibility
    total_files_modified = len(file_stats)
    is_clean = (total_files_modified == 0 and (not diff_out or diff_out.strip() == ""))

    # Multi-file patch contamination check
    if total_files_modified > 1:
        modified_names = [f.path for f in file_stats]
        list_of_files = ", ".join(modified_names)
        warnings.append(
            DiffWarning(
                category="MULTI_FILE_CONTAMINATION",
                path=list_of_files,
                message=(
                    f"⚠️ CAUTION: Multiple files modified ({total_files_modified} files: {list_of_files}). "
                    f"Over 90% of SWE-bench tasks only require modifying 1 file!"
                ),
                risk_explanation=(
                    "Modifying secondary files often breaks unrelated components or indicates an unverified patch. "
                    "Revert secondary edits if the root cause belongs in a single module."
                ),
                recommended_action=(
                    "Run blast-radius on the primary modified file. "
                    "If tests fail, revert your secondary file edits using edit_file."
                ),
            )
        )

    if is_clean:
        clean_msg = "Working tree is clean. 0 files modified relative to git baseline HEAD. Calling submit_patch now will result in an empty patch failure."
        summary_explanation = clean_msg
        warnings.append(
            DiffWarning(
                category="EMPTY_DIFF",
                path="",
                message=clean_msg,
                risk_explanation="Calling submit_patch() with an empty diff terminates the agent turn and results in an automatic zero-score evaluation failure.",
                recommended_action="Use edit_file or write_file to implement the requested defect fix in source files before calling submit_patch().",
            )
        )
        can_submit_patch = False
        submit_patch_advice = (
            "BLOCKED: DO NOT call submit_patch()! Working tree is clean. 0 files modified relative to git baseline HEAD. "
            "Calling submit_patch now will result in an empty patch failure. Edit source files first."
        )
    elif dangerous_untracked_files:
        can_submit_patch = False
        summary_explanation = (
            f"Diff contains {total_files_modified} modified file(s) (+{total_additions}, -{total_deletions}), "
            f"BUT {len(dangerous_untracked_files)} dangerous scratch file(s) exist in /workspace!"
        )
        submit_patch_advice = (
            f"BLOCKED: DO NOT call submit_patch()! Dangerous untracked scratch file(s) detected: "
            f"{', '.join(f'/workspace/{f}' for f in dangerous_untracked_files)}. "
            f"Delete them or move them to /tmp before submitting."
        )
    else:
        can_submit_patch = True
        summary_explanation = (
            f"Diff contains {total_files_modified} modified file(s): "
            f"+{total_additions} additions, -{total_deletions} deletions relative to {base_ref or 'HEAD'}."
        )
        submit_patch_advice = (
            f"READY: Working tree has {total_files_modified} modified file(s) (+{total_additions}, -{total_deletions}) "
            f"with zero dangerous scratch files. Ready for submit_patch()."
        )

    return DiffInspectResult(
        workspace=str(ws),
        base_ref=base_ref or "HEAD",
        is_clean=is_clean,
        total_files_modified=total_files_modified,
        total_additions=total_additions,
        total_deletions=total_deletions,
        file_stats=file_stats,
        untracked_files=untracked_files,
        dangerous_untracked_files=dangerous_untracked_files,
        forbidden_files_modified=forbidden_files_modified,
        warnings=warnings,
        summary_explanation=summary_explanation,
        can_submit_patch=can_submit_patch,
        submit_patch_advice=submit_patch_advice,
        diff_preview=diff_preview,
        diff_lines_truncated=diff_lines_truncated,
    )


# ==============================================================================
# 5. Formatted Agent-Readable Output Generator
# ==============================================================================

def format_inspect_report(result: DiffInspectResult) -> str:
    """Format DiffInspectResult into clean, high-visibility agent diagnostic output."""
    lines: list[str] = []
    ref_label = f"against {result.base_ref}" if result.base_ref else "working tree"

    # Section 1: Workspace & Git Status
    lines.append(f"=== Git Status ({result.workspace}) ===")
    if result.untracked_files or result.file_stats:
        for stat in result.file_stats:
            lines.append(f" {stat.status} {stat.path}")
        for u in result.untracked_files:
            lines.append(f"?? {u}")
    else:
        lines.append("(clean working tree - no changes)")

    # Section 2: Warnings & Safety Alerts
    if result.warnings:
        lines.append(f"\n=== Warnings & Safety Alerts ({len(result.warnings)}) ===")
        for w in result.warnings:
            lines.append(f"\n{w.message}")
            if w.risk_explanation:
                lines.append(f"   Risk: {w.risk_explanation}")
            if w.recommended_action:
                lines.append(f"   Action: {w.recommended_action}")

    # Section 3: File Diff Statistics
    lines.append(f"\n=== File Diff Statistics ({ref_label}) ===")
    if result.is_clean:
        lines.append(result.summary_explanation)
    else:
        lines.append(f"Total files modified: {result.total_files_modified} (+{result.total_additions}, -{result.total_deletions})")
        lines.append("File breakdown:")
        for fs in result.file_stats:
            tags = []
            if fs.is_forbidden_harness_file:
                tags.append("FORBIDDEN CONFIG")
            if fs.is_test_file:
                tags.append("TEST FILE")
            tag_str = f" [{', '.join(tags)}]" if tags else ""
            binary_str = " (binary)" if fs.binary else ""
            lines.append(f"  • {fs.path}: +{fs.additions}, -{fs.deletions} [{fs.status}]{binary_str}{tag_str}")

    # Section 4: Git Diff Preview
    lines.append(f"\n=== Git Diff ({ref_label}) ===")
    if result.diff_preview:
        lines.append(result.diff_preview)
        if result.diff_lines_truncated > 0:
            lines.append(f"\n... [diff truncated: {result.diff_lines_truncated} lines omitted; max 100 lines displayed] ...")
    else:
        lines.append("(no diff)")

    # Section 5: Patch Submission Readiness
    lines.append(f"\n=== Patch Submission Readiness ===")
    lines.append(result.submit_patch_advice)

    return "\n".join(lines)


# ==============================================================================
# 6. Entrypoint
# ==============================================================================

def main() -> int:
    try:
        ws = get_workspace_dir()
        args = sys.argv[1:]

        json_mode = "--json" in args
        filtered_args = [arg for arg in args if arg != "--json"]

        result = inspect_diff(ws, extra_args=filtered_args)

        if json_mode:
            print(result.model_dump_json(indent=2))
        else:
            print(format_inspect_report(result))

    except Exception as e:
        print(f"[diff-inspect] Error: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
