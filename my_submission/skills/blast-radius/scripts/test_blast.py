#!/usr/bin/env python3
"""blast-radius: Targeted Distance-1 Regression & Blast Radius Test Runner.

Identifies the direct test files and distance-1 consumers (files that import the target),
and runs a micro-targeted pytest execution against only that dependency cluster.
Strictly output-capped (max 30 lines) to prevent context window blowout.
Always returns exit code 0.

Usage:
    python3 test_blast.py [target_file_or_symbol...]
"""

import ast
import os
import pathlib
import shutil
import subprocess
import sys
from typing import List, Set, Tuple


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
    """Omnivorously resolve any given file path against workspace."""
    clean = target_str.strip()
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
    return cand


def get_modified_files(ws: pathlib.Path) -> List[pathlib.Path]:
    """Find files modified in working tree using git status."""
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=5,
        )
        modified = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                rel = parts[-1]
                p = ws / rel
                if p.is_file() and p.suffix == ".py":
                    modified.append(p)
        return modified
    except Exception:
        return []


def find_blast_radius(target_path: pathlib.Path, ws: pathlib.Path) -> Tuple[List[str], List[str]]:
    """Determine distance-1 consumers and relevant test files using AST analysis."""
    try:
        rel_target = target_path.relative_to(ws)
    except ValueError:
        rel_target = target_path

    # If target is already a test file, run it directly
    if ("tests/" in str(rel_target) or str(rel_target).startswith("test_")) and rel_target.suffix == ".py":
        return [str(rel_target)], []

    stem = target_path.stem
    direct_tests: List[str] = []

    # 1. Direct test files matching stem
    for pattern in [f"tests/**/test_{stem}.py", f"tests/**/{stem}_test.py", f"tests/**/test_*{stem}*.py"]:
        for match in sorted(ws.glob(pattern)):
            rel_t = str(match.relative_to(ws))
            if rel_t not in direct_tests:
                direct_tests.append(rel_t)

    # 2. AST scan to find distance-1 consumers (files importing stem or module)
    consumers: List[str] = []
    consumer_tests: List[str] = []
    skip_dirs = {"build", "dist", ".git", "__pycache__", "venv", ".venv", "node_modules", "wheels"}

    for root, dirs, files in os.walk(ws):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in skip_dirs]
        for f in sorted(files):
            if not f.endswith(".py") or f.startswith("."):
                continue
            p = pathlib.Path(root) / f
            try:
                rel_f = str(p.relative_to(ws))
            except ValueError:
                rel_f = str(p)

            if rel_f == str(rel_target):
                continue

            try:
                tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"), filename=rel_f)
                imports_target = False
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for n in node.names:
                            if stem == n.name or n.name.endswith("." + stem):
                                imports_target = True
                                break
                    elif isinstance(node, ast.ImportFrom):
                        mod = node.module or ""
                        if stem in mod.split(".") or any(n.name == stem or stem in n.name for n in node.names):
                            imports_target = True
                            break
                    if imports_target:
                        break

                if imports_target:
                    if "tests/" in rel_f or rel_f.startswith("test_") or "test" in pathlib.Path(rel_f).parts:
                        if rel_f not in consumer_tests:
                            consumer_tests.append(rel_f)
                    else:
                        if rel_f not in consumers:
                            consumers.append(rel_f)
            except Exception:
                continue

    # 3. For source consumers, locate their respective test files
    for c in consumers[:10]:
        c_stem = pathlib.Path(c).stem
        for match in ws.glob(f"tests/**/test_*{c_stem}*.py"):
            c_test = str(match.relative_to(ws))
            if c_test not in consumer_tests and c_test not in direct_tests:
                consumer_tests.append(c_test)

    # Combine: prioritize direct tests, then consumer tests
    all_tests: List[str] = []
    for t in direct_tests + consumer_tests:
        if t not in all_tests:
            all_tests.append(t)

    # Cap to max 6 test files to guarantee fast (<5s) execution
    return all_tests[:6], consumers


def find_pytest_command(ws: pathlib.Path) -> List[str]:
    """Find the most appropriate pytest executable or python -m pytest runner."""
    # 1. Virtualenv pytest matching current interpreter directory
    py_dir = pathlib.Path(sys.executable).parent
    cand_pytest = py_dir / "pytest"
    if cand_pytest.is_file() and os.access(cand_pytest, os.X_OK):
        return [str(cand_pytest)]

    # 2. Pytest on PATH
    pytest_bin = shutil.which("pytest")
    if pytest_bin:
        return [pytest_bin]

    # 3. Subprocess python runner matching current interpreter
    if sys.executable and shutil.which(sys.executable):
        return [sys.executable, "-m", "pytest"]

    # 4. Fallback python interpreters on PATH
    for py_name in ("python3", "python"):
        resolved_py = shutil.which(py_name)
        if resolved_py:
            return [resolved_py, "-m", "pytest"]

    return [sys.executable or "python3", "-m", "pytest"]


def run_pytest(tests: List[str], ws: pathlib.Path, timeout_secs: int = 25) -> Tuple[int, str]:
    """Run pytest on the given test files and capture output with explicit workspace PYTHONPATH."""
    cmd_base = find_pytest_command(ws)
    cmd = cmd_base + ["-q", "--tb=short", "--disable-warnings"] + tests
    env = os.environ.copy()
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{ws}:{existing_pp}" if existing_pp else str(ws)
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
        return 124, f"[blast-radius] Pytest timed out after {timeout_secs}s on {len(tests)} test files."
    except Exception as e:
        return 1, f"[blast-radius] Pytest execution error: {e}"


def parse_pytest_failures(output: str, max_lines: int = 20) -> List[str]:
    """Extract concise failure lines from pytest short output."""
    lines = output.splitlines()
    failures: List[str] = []
    capture = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("FAILED ") or stripped.startswith("ERROR "):
            failures.append(stripped)
        elif "AssertionError:" in line or "Error:" in line:
            clean_err = stripped[:120]
            if clean_err not in failures:
                failures.append(f"  → {clean_err}")

    if not failures:
        # Fallback to last few lines of output
        failures = [l.strip() for l in lines[-10:] if l.strip()]

    return failures[:max_lines]


def main() -> int:
    ws = get_workspace_dir()

    # Determine targets from CLI args or git status
    targets: List[pathlib.Path] = []
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            arg_clean = arg.strip()
            if arg_clean:
                targets.append(resolve_target(arg_clean, ws))
    else:
        targets = get_modified_files(ws)

    if not targets:
        print("[blast-radius] No target files specified and no modified Python files found in git status.")
        print("[blast-radius] Usage: python3 test_blast.py <path/to/file.py>")
        return 0

    all_test_files: List[str] = []
    all_consumers: List[str] = []

    for t in targets:
        tests, consumers = find_blast_radius(t, ws)
        for tst in tests:
            if tst not in all_test_files:
                all_test_files.append(tst)
        for c in consumers:
            if c not in all_consumers:
                all_consumers.append(c)

    # Format header
    target_names = ", ".join(t.relative_to(ws).as_posix() if ws in t.parents else t.name for t in targets)
    print(f"[blast-radius] TARGET(S): {target_names}")
    
    if all_consumers:
        consumer_preview = ", ".join(all_consumers[:5])
        more = f" (+{len(all_consumers)-5} more)" if len(all_consumers) > 5 else ""
        print(f"[blast-radius] DISTANCE-1 CONSUMERS: {consumer_preview}{more}")
    else:
        print("[blast-radius] DISTANCE-1 CONSUMERS: (none detected)")

    if not all_test_files:
        print(f"[blast-radius] ⚠️ No matching test files found for {target_names}.")
        return 0

    test_display = ", ".join(all_test_files[:5])
    print(f"[blast-radius] RUNNING TESTS ({len(all_test_files)} file(s)): {test_display}")

    exit_code, raw_output = run_pytest(all_test_files, ws)

    if exit_code == 0:
        # Extract summary line (e.g. "233 passed in 0.4s")
        summary_line = "All tests passed."
        for line in raw_output.splitlines():
            if "passed" in line:
                summary_line = line.strip()
                break
        print(f"[blast-radius] ✅ PASSED: {summary_line}")
    else:
        print(f"[blast-radius] 💥 REGRESSION DETECTED IN BLAST RADIUS (Exit code: {exit_code}):")
        failures = parse_pytest_failures(raw_output)
        for f in failures:
            print(f"  {f}")
        print("\n[blast-radius] ⚠️ FIX OR REVERT: Changes broke the tests listed above!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
