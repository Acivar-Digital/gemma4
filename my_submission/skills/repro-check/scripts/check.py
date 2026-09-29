#!/usr/bin/env python3
"""repro-check: Isolated Python Repro & Defect Verification Runner.

Executes a user-supplied Python assertion or reproduction snippet in /tmp
with PYTHONPATH set to the active workspace.
Guarantees clean git diff (zero scratch files in /workspace) and context-safe output.
Always returns exit code 0.

Usage:
    python3 check.py "<code>"
"""

import ast
import os
import pathlib
import subprocess
import sys
import tempfile


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


def clean_snippet(code: str) -> str:
    """Clean snippet formatting, stripping surrounding markdown codeblocks if present."""
    code = code.strip()
    if code.startswith("```python"):
        code = code[len("```python"):].strip()
    elif code.startswith("```"):
        code = code[len("```"):].strip()
    if code.endswith("```"):
        code = code[:-3].strip()
    return code


def run_code_in_tmp(code: str, ws: pathlib.Path, timeout_secs: int = 10) -> int:
    """Write snippet to a temporary script in /tmp and execute it with workspace PYTHONPATH."""
    env = os.environ.copy()
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{ws}:{existing_pp}" if existing_pp else str(ws)

    # Use a secure temp file in /tmp, strictly outside /workspace
    with tempfile.NamedTemporaryFile("w", suffix="_repro.py", dir="/tmp", delete=False) as tf:
        tf.write(code)
        temp_script = pathlib.Path(tf.name)

    try:
        res = subprocess.run(
            [sys.executable, str(temp_script)],
            cwd=ws,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_secs,
        )

        stdout = res.stdout.strip()
        stderr = res.stderr.strip()

        has_assert = False
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assert):
                    has_assert = True
                    break
        except Exception:
            has_assert = "assert " in code or "assert(" in code

        if res.returncode == 0:
            if has_assert:
                print("[repro-check] ✅ PASSED: All assertions evaluated and passed with zero errors.")
            else:
                print("[repro-check] ℹ️ EXECUTED WITH ZERO ERRORS (BUT NO ASSERTIONS EVALUATED)")
                print("[repro-check] ⚠️ WARNING: Your code contained NO 'assert' statements!")
                print("[repro-check] You CANNOT confirm a bug or fix with print statements alone.")
                print("[repro-check] You MUST add an explicit assert (e.g. assert actual == expected) to reproduce or verify.")
            if stdout:
                print("[repro-check] OUTPUT:")
                for line in stdout.splitlines()[:15]:
                    print(f"  {line}")
        else:
            if "AssertionError" in (stderr or stdout):
                print(f"[repro-check] ❌ ASSERTION FAILED (Defect Confirmed):")
            else:
                print(f"[repro-check] ❌ EXECUTION FAILED (Exit code {res.returncode}):")
            # Extract last few lines of traceback/error
            err_lines = (stderr or stdout).splitlines()
            clean_lines = [l for l in err_lines if l.strip()][-12:]
            for line in clean_lines:
                print(f"  {line}")

        return 0
    except subprocess.TimeoutExpired:
        print(f"[repro-check] ❌ FAILED: Execution timed out after {timeout_secs} seconds.")
        return 0
    except Exception as e:
        print(f"[repro-check] ❌ FAILED to execute script: {e}")
        return 0
    finally:
        temp_script.unlink(missing_ok=True)


def main() -> int:
    if len(sys.argv) < 2:
        print("[repro-check] No Python code snippet provided.")
        print("[repro-check] Usage: python3 check.py \"assert Text.from_ansi('\\n').plain == '\\n'\"")
        return 0

    code = " ".join(sys.argv[1:]) if len(sys.argv) > 2 else sys.argv[1]
    cleaned = clean_snippet(code)

    if not cleaned:
        print("[repro-check] Provided Python code snippet was empty.")
        return 0

    ws = get_workspace_dir()
    run_code_in_tmp(cleaned, ws)
    return 0


if __name__ == "__main__":
    sys.exit(main())
