#!/usr/bin/env python3
"""Comprehensive test suite for test-gate skill.

Verifies:
1. Syntax validation and byte-identical synchronization between gate.py and scripts/gate.py.
2. CLI help and unknown option handling with actionable copy-pasteable examples.
3. --blast mode:
   - Clean repo diagnostics (lists available source files to test).
   - Distance-1 neighbor test discovery and passing execution.
   - Test failure reporting with exact failing test names and traceback snippets.
   - 0-test protection (UNVERIFIED_NO_TESTS).
4. --diff mode:
   - Safe read-only git diff against HEAD.
   - Modified file stats and diff previews.
   - CRITICAL SWE-BENCH SAFETY ASSERTION:
     Loud '🚨 FORBIDDEN TEST FILE MODIFIED IN /WORKSPACE' warning and
     revert instructions ('git checkout -- <file>') when test files are touched.
   - Untracked scratch file warning (repro.py, tmp*.py).
5. --status mode:
   - Empty diff patch block.
   - Valid patch readiness recommendation ([✓ READY]).
   - Python AST syntax error detection and patch block ([✗ BLOCKED]).
   - Forbidden test file mutation block ([✗ BLOCKED]).
6. --json mode Pydantic schema compliance across all modes.

Exits code 0 on success.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
GATE_PATH = REPO_ROOT / "my_submission" / "skills" / "test-gate" / "gate.py"
SCRIPTS_GATE_PATH = REPO_ROOT / "my_submission" / "skills" / "test-gate" / "scripts" / "gate.py"


def run_gate(*args: str, cwd: pathlib.Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run gate.py with given arguments and return CompletedProcess."""
    cmd = [sys.executable, str(GATE_PATH)] + list(args)
    environ = os.environ.copy()
    environ["PYTHONPATH"] = f"{REPO_ROOT}:{environ.get('PYTHONPATH', '')}"
    if env:
        environ.update(env)
    return subprocess.run(
        cmd,
        cwd=str(cwd or REPO_ROOT),
        capture_output=True,
        text=True,
        env=environ,
        timeout=30,
    )


def init_mock_repo(path: pathlib.Path):
    """Initialize a mock git repository with an initial commit."""
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "agent@gemma.dev"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Gemma Dev Agent"], cwd=path, check=True, capture_output=True)

    # Initial structure
    src_dir = path / "pkg"
    src_dir.mkdir(parents=True)
    (src_dir / "__init__.py").write_text("")
    (src_dir / "calc.py").write_text(
        "def add(a: int, b: int) -> int:\n"
        "    return a + b\n"
    )

    test_dir = path / "tests"
    test_dir.mkdir(parents=True)
    (test_dir / "test_calc.py").write_text(
        "from pkg.calc import add\n\n"
        "def test_add():\n"
        "    assert add(1, 2) == 3\n"
    )

    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=path, check=True, capture_output=True)


# ==============================================================================
# Tests
# ==============================================================================

def test_syntax_and_byte_identity():
    """DoD 1 & 2: Byte identity and py_compile syntax validation."""
    print("[1/7] Testing syntax validation and file sync...")
    assert GATE_PATH.exists(), f"Missing {GATE_PATH}"
    assert SCRIPTS_GATE_PATH.exists(), f"Missing {SCRIPTS_GATE_PATH}"

    # Byte-for-byte check
    with open(GATE_PATH, "rb") as f1, open(SCRIPTS_GATE_PATH, "rb") as f2:
        assert f1.read() == f2.read(), "gate.py and scripts/gate.py are NOT identical!"

    # Compile check
    res1 = subprocess.run([sys.executable, "-m", "py_compile", str(GATE_PATH)], capture_output=True, text=True)
    assert res1.returncode == 0, f"Compilation failed for gate.py: {res1.stderr}"
    res2 = subprocess.run([sys.executable, "-m", "py_compile", str(SCRIPTS_GATE_PATH)], capture_output=True, text=True)
    assert res2.returncode == 0, f"Compilation failed for scripts/gate.py: {res2.stderr}"
    print("  ✓ gate.py and scripts/gate.py are byte-identical and pass py_compile.")


def test_cli_help_and_unknown_options():
    """Verify help and friendly recovery for unknown options."""
    print("[2/7] Testing CLI help and unknown option handling...")
    for flag in ("--help", "-h"):
        res = run_gate(flag)
        assert res.returncode == 0
        assert "Available Modes & Options:" in res.stdout
        assert "Copy-Pasteable Examples:" in res.stdout

    # Unknown option should explain available options and exit 0
    res_unk = run_gate("--unknown-flag-xyz")
    assert res_unk.returncode == 0
    assert "Unknown argument or flag" in res_unk.stdout
    assert "--blast" in res_unk.stdout
    assert "--diff" in res_unk.stdout
    assert "--status" in res_unk.stdout
    assert "python3 gate.py" in res_unk.stdout
    print("  ✓ Help and unknown flag diagnostics work cleanly with exit code 0.")


def test_blast_mode_regression_runner():
    """Verify --blast mode: clean repo, passed tests, failed tests, 0-test guard."""
    print("[3/7] Testing --blast neighbor regression testing...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_path = pathlib.Path(tmp_dir)
        init_mock_repo(repo_path)
        env = {"SWEGEMMA_WORKSPACE": str(repo_path)}

        # 1. Clean repo (no files modified, no target): tells LLM what files exist
        res_clean = run_gate("--blast", cwd=repo_path, env=env)
        assert res_clean.returncode == 0
        assert "No modified files detected in git working tree" in res_clean.stdout
        assert "pkg/calc.py" in res_clean.stdout
        assert "Usage: python3 gate.py --blast" in res_clean.stdout

        # 2. Modify source file with correct implementation -> tests pass
        calc_file = repo_path / "pkg" / "calc.py"
        calc_file.write_text(
            "def add(a: int, b: int) -> int:\n"
            "    # improved implementation\n"
            "    return a + b\n"
        )
        res_pass = run_gate("--blast", cwd=repo_path, env=env)
        assert res_pass.returncode == 0
        assert "PASSED: 1 test(s) passed" in res_pass.stdout
        assert "tests/test_calc.py" in res_pass.stdout

        # 3. Modify source file with breaking bug -> test fails with traceback snippet
        calc_file.write_text(
            "def add(a: int, b: int) -> int:\n"
            "    return a - b  # buggy!\n"
        )
        res_fail = run_gate("--blast", cwd=repo_path, env=env)
        assert res_fail.returncode == 0
        assert "FAILED: 1 test(s) failed" in res_fail.stdout
        assert "test_calc.py::test_add" in res_fail.stdout
        assert "Exact failing tests:" in res_fail.stdout
        assert "Traceback snippet:" in res_fail.stdout or "assert" in res_fail.stdout

        # 4. Target with no matching tests -> UNVERIFIED_NO_TESTS
        no_test_file = repo_path / "pkg" / "orphan.py"
        no_test_file.write_text("x = 42\n")
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
        res_unver = run_gate("--blast", "pkg/orphan.py", cwd=repo_path, env=env)
        assert res_unver.returncode == 0
        assert "UNVERIFIED_NO_TESTS" in res_unver.stdout
        assert "VERIFICATION REQUIRED" in res_unver.stdout

    print("  ✓ --blast mode verified: passing tests, failure tracebacks, and 0-test guard.")


def test_diff_mode_and_forbidden_test_mutation():
    """Verify --diff mode and CRITICAL SWE-BENCH SAFETY ASSERTION."""
    print("[4/7] Testing --diff mode and forbidden test file mutation assertion...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_path = pathlib.Path(tmp_dir)
        init_mock_repo(repo_path)
        env = {"SWEGEMMA_WORKSPACE": str(repo_path)}

        # 1. Clean repo diff
        res_clean = run_gate("--diff", cwd=repo_path, env=env)
        assert res_clean.returncode == 0
        assert "Working tree is clean" in res_clean.stdout

        # 2. Modify legitimate source file
        calc_file = repo_path / "pkg" / "calc.py"
        calc_file.write_text(
            "def add(a: int, b: int) -> int:\n"
            "    # new comment line\n"
            "    return a + b\n"
        )
        res_mod = run_gate("--diff", cwd=repo_path, env=env)
        assert res_mod.returncode == 0
        assert "1 file(s) touched" in res_mod.stdout
        assert "pkg/calc.py" in res_mod.stdout
        assert "Unified Diff Preview" in res_mod.stdout

        # 3. CRITICAL SWE-BENCH SAFETY ASSERTION:
        # Modify a test file in /workspace
        test_file = repo_path / "tests" / "test_calc.py"
        test_file.write_text(
            "def test_add():\n"
            "    assert True  # modified test file!\n"
        )
        res_forbidden = run_gate("--diff", cwd=repo_path, env=env)
        assert res_forbidden.returncode == 0
        assert "🚨 FORBIDDEN TEST FILE MODIFIED IN /WORKSPACE" in res_forbidden.stdout
        assert "tests/test_calc.py" in res_forbidden.stdout
        assert "Container B discards" in res_forbidden.stdout
        assert "git checkout -- tests/test_calc.py" in res_forbidden.stdout

        # JSON mode check for forbidden mutation
        res_json = run_gate("--diff", "--json", cwd=repo_path, env=env)
        assert res_json.returncode == 0
        data = json.loads(res_json.stdout)
        assert data["can_submit_patch"] is False
        assert "tests/test_calc.py" in data["forbidden_test_files"]
        assert data["status"] == "BLOCKED_FORBIDDEN_TEST_FILE"

    print("  ✓ --diff mode & CRITICAL SWE-BENCH SAFETY ASSERTION verified.")


def test_diff_untracked_scratch_detection():
    """Verify --diff detection of dangerous untracked scratch files."""
    print("[5/7] Testing scratch file detection in --diff mode...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_path = pathlib.Path(tmp_dir)
        init_mock_repo(repo_path)
        env = {"SWEGEMMA_WORKSPACE": str(repo_path)}

        # Create untracked repro script
        repro = repo_path / "repro.py"
        repro.write_text("# temporary repro script\n")

        res = run_gate("--diff", cwd=repo_path, env=env)
        assert res.returncode == 0
        assert "⚠️ DANGER: Untracked scratch files in /workspace" in res.stdout
        assert "repro.py" in res.stdout

        res_json = run_gate("--diff", "--json", cwd=repo_path, env=env)
        data = json.loads(res_json.stdout)
        assert "repro.py" in data["dangerous_scratch_files"]
        assert data["can_submit_patch"] is False

    print("  ✓ Scratch file detection verified.")


def test_status_mode_readiness():
    """Verify --status mode: empty diff, syntax errors, forbidden tests, and ready status."""
    print("[6/7] Testing --status patch readiness evaluation...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_path = pathlib.Path(tmp_dir)
        init_mock_repo(repo_path)
        env = {"SWEGEMMA_WORKSPACE": str(repo_path)}

        # Case A: Empty diff -> blocked
        res_empty = run_gate("--status", cwd=repo_path, env=env)
        assert res_empty.returncode == 0
        assert "BLOCKED" in res_empty.stdout
        assert "[✗ BLOCKED] DO NOT run submit_patch()" in res_empty.stdout

        # Case B: Modified source with valid syntax -> ready
        calc_file = repo_path / "pkg" / "calc.py"
        calc_file.write_text(
            "def add(a: int, b: int) -> int:\n"
            "    return a + b\n\n"
            "def sub(a: int, b: int) -> int:\n"
            "    return a - b\n"
        )
        res_ready = run_gate("--status", cwd=repo_path, env=env)
        assert res_ready.returncode == 0
        assert "[✓ READY] Safe to run submit_patch()." in res_ready.stdout

        # Case C: Modified source with Python SyntaxError -> blocked
        calc_file.write_text(
            "def broken_syntax(a, b:\n"  # missing closing paren
            "    return a + b\n"
        )
        res_syntax = run_gate("--status", cwd=repo_path, env=env)
        assert res_syntax.returncode == 0
        assert "Syntax Errors Detected" in res_syntax.stdout
        assert "[✗ BLOCKED]" in res_syntax.stdout

        # Case D: Forbidden test file modified -> blocked
        # Revert syntax error first
        calc_file.write_text("def add(a: int, b: int) -> int: return a + b\n")
        test_file = repo_path / "tests" / "test_calc.py"
        test_file.write_text("def test_dummy(): pass\n")
        res_forbid = run_gate("--status", cwd=repo_path, env=env)
        assert res_forbid.returncode == 0
        assert "🚨 FORBIDDEN TEST FILE MODIFIED IN /WORKSPACE" in res_forbid.stdout
        assert "[✗ BLOCKED]" in res_forbid.stdout
        assert "git checkout --" in res_forbid.stdout

    print("  ✓ --status patch readiness gate verified across all states.")


def test_json_pydantic_schema_compliance():
    """Verify --json output across all modes adheres to TestGateResult schema."""
    print("[7/7] Testing --json structured output across modes...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_path = pathlib.Path(tmp_dir)
        init_mock_repo(repo_path)
        env = {"SWEGEMMA_WORKSPACE": str(repo_path)}

        # Modify a file
        calc_file = repo_path / "pkg" / "calc.py"
        calc_file.write_text(
            "def add(a: int, b: int) -> int:\n"
            "    return a + b\n"
        )

        for mode_flag in ("--blast", "--diff", "--status"):
            res = run_gate(mode_flag, "--json", cwd=repo_path, env=env)
            assert res.returncode == 0, f"{mode_flag} --json failed: {res.stderr}"
            data = json.loads(res.stdout)
            assert "mode" in data
            assert "workspace" in data
            assert "status" in data
            assert "success" in data
            assert "modified_files" in data
            assert "can_submit_patch" in data
            assert "recommendation" in data

    print("  ✓ Pydantic v2 JSON schema compliance verified.")


def main():
    print("=" * 75)
    print("RUNNING TEST-GATE SKILL VALIDATION SUITE")
    print("=" * 75)

    test_syntax_and_byte_identity()
    test_cli_help_and_unknown_options()
    test_blast_mode_regression_runner()
    test_diff_mode_and_forbidden_test_mutation()
    test_diff_untracked_scratch_detection()
    test_status_mode_readiness()
    test_json_pydantic_schema_compliance()

    print("=" * 75)
    print("ALL 7 TEST SUITES PASSED CLEANLY (EXIT CODE 0)")
    print("=" * 75)
    return 0


if __name__ == "__main__":
    sys.exit(main())
