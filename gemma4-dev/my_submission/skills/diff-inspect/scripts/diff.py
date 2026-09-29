#!/usr/bin/env python3
"""diff-inspect: Safe, read-only Git status and diff inspector.

Executes `git status --short` and `git diff` against `_swegemma_baseline` (or HEAD)
cleanly without modifying /workspace. Returns concise diff output capped at 100 lines.
Always exits with code 0.

Usage:
    python3 diff.py [optional_path_or_flag]
"""

import os
import pathlib
import shutil
import subprocess
import sys
from typing import List, Tuple


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
            timeout=timeout_secs,
        )
        output = res.stdout if res.stdout else res.stderr
        return res.returncode, output.strip()
    except subprocess.TimeoutExpired:
        return 1, f"Command timed out after {timeout_secs}s: git {' '.join(args)}"
    except Exception as e:
        return 1, f"Git command failed: {e}"


def determine_base_ref(ws: pathlib.Path) -> str:
    """Determine whether to diff against _swegemma_baseline or HEAD."""
    code, _ = run_git_cmd(["rev-parse", "--verify", "_swegemma_baseline"], cwd=ws, timeout_secs=5)
    if code == 0:
        return "_swegemma_baseline"
    code, _ = run_git_cmd(["rev-parse", "--verify", "HEAD"], cwd=ws, timeout_secs=5)
    if code == 0:
        return "HEAD"
    return ""


def main() -> int:
    try:
        ws = get_workspace_dir()

        # Check git repo status
        code, out = run_git_cmd(["rev-parse", "--is-inside-work-tree"], cwd=ws, timeout_secs=5)
        if code != 0 or out.lower() != "true":
            print(f"[diff-inspect] Workspace at '{ws}' is not a git repository.")
            return 0

        # 1. git status --short
        _, status_out = run_git_cmd(["status", "--short"], cwd=ws)

        # 2. git diff
        base_ref = determine_base_ref(ws)
        extra_args = [arg for arg in sys.argv[1:] if arg.strip()]
        diff_cmd = ["diff"]
        if base_ref:
            diff_cmd.append(base_ref)
        if extra_args:
            diff_cmd.extend(extra_args)

        _, diff_out = run_git_cmd(diff_cmd, cwd=ws)

        # Output formatting
        ref_label = f"against {base_ref}" if base_ref else "working tree"
        print(f"=== Git Status ({ws}) ===")
        if status_out:
            print(status_out)
            if "??" in status_out:
                print("\n[NOTE] Untracked files (??) detected! Ensure no scratch files exist in /workspace before calling submit_patch.")
        else:
            print("(clean working tree - no changes)")

        print(f"\n=== Git Diff ({ref_label}) ===")
        if diff_out:
            diff_lines = diff_out.splitlines()
            if len(diff_lines) > 100:
                truncated_diff = "\n".join(diff_lines[:100])
                omitted = len(diff_lines) - 100
                print(truncated_diff)
                print(f"\n... [diff truncated: {omitted} lines omitted; max 100 lines displayed] ...")
            else:
                print(diff_out)
        else:
            print("(no diff)")

    except Exception as e:
        print(f"[diff-inspect] Error: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
