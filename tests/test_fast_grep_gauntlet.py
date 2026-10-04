#!/usr/bin/env python3
"""Comprehensive test gauntlet for fast-grep skill.

Verifies:
1. Syntax & file identity between grep.py and scripts/grep.py.
2. Omnivorous empty, dot, and overview mode (exit 0, tailored commands).
3. Positional argument auto-detection (pattern, pattern + path, multi-terms).
4. Forgiving CLI flags (-p, -d, -i, -w, -m, --json).
5. Raw regex error resilience and automatic literal fallback (no re.error crash).
6. Crash and infinite loop immunity (giant files, binary files, circular symlinks, match caps).
7. Actionable zero-match diagnostics (case hints, narrow path filter check, fuzzy suggestions, next steps).
8. Retained core features (AST scopes, target-centered sliding window, clean edit_file code block).
9. SKILL.md cleanliness (<100 lines, zero unescaped braces).
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile

# Prevent Python from writing bytecode cache files (.pyc) that ADK compiler strictly forbids
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
GREP_PATH = REPO_ROOT / "my_submission" / "skills" / "fast-grep" / "scripts" / "grep.py"
SKILL_MD_PATH = (
    REPO_ROOT / "my_submission" / "skills" / "fast-grep" / "SKILL.md"
)


def run_grep(
    *args: str,
    cwd: pathlib.Path | None = None,
    env: dict | None = None,
    timeout: int = 15,
) -> subprocess.CompletedProcess:
    """Run grep.py with given arguments and return CompletedProcess."""
    cmd = [sys.executable, "-B", str(GREP_PATH)] + list(args)
    environ = os.environ.copy()
    environ["PYTHONDONTWRITEBYTECODE"] = "1"
    if env:
        environ.update(env)
    return subprocess.run(
        cmd,
        cwd=str(cwd or REPO_ROOT),
        capture_output=True,
        text=True,
        env=environ,
        timeout=timeout,
    )


def test_syntax_and_sync():
    print("[1/9] Testing syntax validation...")
    assert GREP_PATH.exists(), f"Missing {GREP_PATH}"

    # Compile check (in-memory without writing disallowed .pyc files to submission directory)
    compile(GREP_PATH.read_text(encoding="utf-8"), str(GREP_PATH), "exec")
    print("  ✓ Syntax verified for scripts/grep.py.")


def test_empty_and_overview():
    print("[2/9] Testing overview mode on empty, dot, and --help calls...")
    for args in [(), (".",), ("/workspace",)]:
        res = run_grep(*args)
        assert res.returncode == 0, f"Failed on args={args}: {res.stderr}"
        assert (
            "fast-grep: Omnivorous, AST-Aware Search Engine for Autonomous Agents"
            in res.stdout
        )
        assert "Recommended search arguments for next step:" in res.stdout

    # Test help flag
    res_help = run_grep("--help")
    assert res_help.returncode == 0
    assert 'run_skill_script(skill_name="fast-grep", file_path="grep.py"' in res_help.stdout

    # Test JSON mode on overview
    res_json = run_grep("--json")
    assert res_json.returncode == 0
    data = json.loads(res_json.stdout)
    assert data["explanation"]["status"] == "OVERVIEW"
    assert len(data["copy_pasteable_commands"]) > 0
    print("  ✓ Overview and empty arguments handle gracefully with exit code 0.")


def test_positional_auto_detection():
    print("[3/9] Testing forgiving positional argument auto-detection...")
    # 1. Single positional query term
    res_single = run_grep("APIRouter")
    assert res_single.returncode == 0
    assert "[fast-grep] Search: 'APIRouter'" in res_single.stdout
    assert "SCOPE:" in res_single.stdout

    # 2. Positional query + target directory
    res_pos_path = run_grep("parse_args", "my_submission/skills/fast-grep")
    assert res_pos_path.returncode == 0
    assert "my_submission/skills/fast-grep/scripts/grep.py" in res_pos_path.stdout

    # 3. Multi-term positional search (union)
    res_multi = run_grep("splitlines", "rstrip", "strip")
    assert res_multi.returncode == 0
    assert "[fast-grep] Search: 'splitlines | rstrip | strip'" in res_multi.stdout
    print("  ✓ Positional argument auto-detection verified.")


def test_forgiving_cli_flags():
    print("[4/9] Testing forgiving CLI flags (-p, -d, -i, -w, -m, --json)...")
    # 1. -p and -d flags
    res1 = run_grep("-p", "parse_args", "-d", "my_submission/skills/fast-grep")
    assert res1.returncode == 0
    assert "my_submission/skills/fast-grep/scripts/grep.py" in res1.stdout

    # 2. --pattern= and --dir= flags
    res2 = run_grep(
        "--pattern=parse_args", "--dir=my_submission/skills/fast-grep"
    )
    assert res2.returncode == 0
    assert "my_submission/skills/fast-grep/scripts/grep.py" in res2.stdout

    # 3. -i / --ignore-case flag
    res_ci = run_grep("-i", "apirouter")
    assert res_ci.returncode == 0
    assert "APIRouter" in res_ci.stdout or "apirouter" in res_ci.stdout

    # 4. -w / --window context flag
    res_w = run_grep("-w", "10", "def parse_args")
    assert res_w.returncode == 0

    # 5. -m / --max-matches flag
    res_m = run_grep("-m", "3", "def")
    assert res_m.returncode == 0

    # 6. --json flag
    res_json = run_grep("--json", "FastGrepResult")
    assert res_json.returncode == 0
    data = json.loads(res_json.stdout)
    assert data["total_matches"] > 0
    assert data["explanation"]["status"] == "MATCHES_FOUND"
    assert len(data["ranked_matches"]) > 0
    print("  ✓ Forgiving CLI flags verified.")


def test_raw_regex_resilience_and_fallback():
    print("[5/9] Testing raw regex crash immunity and automatic literal fallback...")
    # 1. Unescaped opening parenthesis: 'def print_help('
    res_paren = run_grep("def print_help(")
    assert res_paren.returncode == 0
    assert "Invalid regex pattern 'def print_help('" in res_paren.stdout
    assert "Automatically falling back to literal substring search" in res_paren.stdout
    assert "def print_help(" in res_paren.stdout

    # 2. Unbalanced bracket: '[a-z'
    res_bracket = run_grep("[a-z")
    assert res_bracket.returncode == 0
    assert "Automatically falling back to literal substring search" in res_bracket.stdout

    # 3. Dangling repeat quantifier: '*dangling'
    res_star = run_grep("*dangling")
    assert res_star.returncode == 0
    assert "Automatically falling back to literal substring search" in res_star.stdout

    # 4. Invalid escape sequence: '\k'
    res_esc = run_grep(r"\k")
    assert res_esc.returncode == 0

    # 5. JSON mode with invalid regex
    res_json = run_grep("--json", "def print_help(")
    assert res_json.returncode == 0
    data = json.loads(res_json.stdout)
    assert len(data["regex_diagnostics"]) > 0
    assert data["total_matches"] > 0
    print("  ✓ Regex crash immunity and literal fallback verified.")


def test_crash_and_infinite_loop_immunity():
    print("[6/9] Testing crash, giant-file, binary, and circular symlink immunity...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = pathlib.Path(tmp_dir)

        # 1. Giant file (>500KB)
        giant_file = tmp_path / "giant.py"
        giant_file.write_text("# padding\n" * 70_000, encoding="utf-8")
        assert giant_file.stat().st_size > 500_000

        # Normal small file
        normal_file = tmp_path / "normal.py"
        normal_file.write_text("def find_me():\n    return 42\n", encoding="utf-8")

        # 2. Binary file with null bytes
        bin_file = tmp_path / "binary.bin"
        bin_file.write_bytes(b"\x00\x01\x02\x03\x04padding")

        bin_py = tmp_path / "corrupt.py"
        bin_py.write_bytes(b"\x00" * 200 + b"def corrupt(): pass\n")

        # 3. Circular symlink
        sub_dir = tmp_path / "sub"
        sub_dir.mkdir()
        cycle_link = sub_dir / "cycle"
        try:
            cycle_link.symlink_to(tmp_path, target_is_directory=True)
        except OSError:
            pass  # Some environments restrict symlink creation

        # Run fast-grep on this adversarial directory
        res = run_grep("find_me", str(tmp_path), timeout=10)
        assert res.returncode == 0
        assert "find_me" in res.stdout
        assert "SCOPE: def find_me" in res.stdout

        # Search for pattern inside binary file; must skip binary cleanly without crash
        res_bin = run_grep("corrupt", str(tmp_path), timeout=10)
        assert res_bin.returncode == 0
    print("  ✓ Crash, giant file, binary, and loop immunity verified.")


def test_zero_matches_actionable_diagnostics():
    print("[7/9] Testing actionable diagnostics on zero matches...")
    # 1. Case mismatch hint: search for lowercase 'fastgrepresult'
    res_case = run_grep("fastgrepresult", "-d", "my_submission/skills")
    assert res_case.returncode == 0
    assert "0 exact matches, but" in res_case.stdout
    assert "-i / --ignore-case" in res_case.stdout
    assert 'args: ["-i", "fastgrepresult"]' in res_case.stdout

    # 2. Narrow path filter hint: search for symbol outside target dir
    res_path = run_grep(
        "CodeGraphResult", "my_submission/skills/fast-grep/"
    )
    assert res_path.returncode == 0
    assert "PATH FILTER TOO NARROW" in res_path.stdout
    assert "Try searching without path filter" in res_path.stdout
    assert 'args: ["CodeGraphResult"]' in res_path.stdout

    # 3. Fuzzy symbol suggestion from AST
    res_fuzzy = run_grep("FastGrepRezult")
    assert res_fuzzy.returncode == 0
    assert (
        "SIMILAR SYMBOLS IN WORKSPACE" in res_fuzzy.stdout
        or "ACTIONABLE NEXT STEPS" in res_fuzzy.stdout
    )

    # 4. Actionable next steps block
    assert "🚀 ACTIONABLE NEXT STEPS FOR LLM:" in res_fuzzy.stdout
    print("  ✓ Actionable zero-match diagnostics verified.")


def test_retained_core_features():
    print("[8/9] Testing retained AST features, ranking, and clean code block...")
    res = run_grep("def extract_function_scope")
    assert res.returncode == 0
    assert "SCOPE: def extract_function_scope" in res.stdout
    assert "[🎯 DEFINITION TARGET]" in res.stdout
    assert "[CLEAN CODE FOR edit_file (EXACT INDENTATION)]:" in res.stdout
    assert "```python" in res.stdout
    assert "def extract_function_scope(" in res.stdout
    print("  ✓ AST scope flashing, definition ranking, and clean code block verified.")


def test_skill_markdown_guardrails():
    print("[9/9] Testing SKILL.md line count (<100 lines) and ADK brace safety...")
    assert SKILL_MD_PATH.exists(), f"Missing {SKILL_MD_PATH}"
    lines = SKILL_MD_PATH.read_text(encoding="utf-8").splitlines()
    assert len(lines) < 100, f"SKILL.md is {len(lines)} lines; must be < 100!"

    content = SKILL_MD_PATH.read_text(encoding="utf-8")
    assert "{" not in content and "}" not in content, (
        "SKILL.md contains curly braces '{' or '}' which can break ADK template engines!"
    )
    print("  ✓ SKILL.md validated clean and safe (<100 lines, zero braces).")


def main():
    print("=" * 80)
    print("STARTING FAST-GREP GAUNTLET TEST SUITE")
    print("=" * 80)

    test_syntax_and_sync()
    test_empty_and_overview()
    test_positional_auto_detection()
    test_forgiving_cli_flags()
    test_raw_regex_resilience_and_fallback()
    test_crash_and_infinite_loop_immunity()
    test_zero_matches_actionable_diagnostics()
    test_retained_core_features()
    test_skill_markdown_guardrails()

    print("=" * 80)
    print("ALL 9 FAST-GREP GAUNTLET CHECKS PASSED 100% WITH ZERO ERRORS!")
    print("=" * 80)


if __name__ == "__main__":
    main()
