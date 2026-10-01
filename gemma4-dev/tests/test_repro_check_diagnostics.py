#!/usr/bin/env python3
"""Comprehensive unit test suite for repro-check deep assertion diagnostics.

Verifies:
1. Syntax validation and byte-for-byte identity between check.py and scripts/check.py.
2. String assertion failure with ANSI escapes (Actual, Expected, Diff at index with hex, escape breakdown, root cause hint).
3. String assertion failure with control characters (CR vs LF, hex divergence, escape breakdown).
4. Dictionary/JSON mismatch (missing keys, extra keys, shared key value differences, root cause hint).
5. Sequence/List mismatch (length difference, first differing element with index, root cause hint).
6. Clean passing assertion (exit code 0, PASSED header).
7. Hardened features regression (base64 mode, outer quote sanitization, AST pre-parse syntax error, path containment).
"""

from __future__ import annotations

import base64
import os
import pathlib
import subprocess
import sys

# Prevent Python from writing bytecode cache files (.pyc) that ADK compiler strictly forbids
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
CHECK_PY = REPO_ROOT / "my_submission" / "skills" / "repro-check" / "check.py"
SCRIPTS_CHECK_PY = REPO_ROOT / "my_submission" / "skills" / "repro-check" / "scripts" / "check.py"


def run_check(*args: str, env: dict | None = None, stdin_data: str | None = None) -> subprocess.CompletedProcess:
    """Run check.py with given arguments and return CompletedProcess."""
    cmd = [sys.executable, "-B", str(CHECK_PY)] + list(args)
    environ = os.environ.copy()
    environ["PYTHONDONTWRITEBYTECODE"] = "1"
    environ["PYTHONPATH"] = f"{REPO_ROOT}:{environ.get('PYTHONPATH', '')}"
    if env:
        environ.update(env)
    return subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=environ,
        input=stdin_data,
        timeout=30,
    )


def test_syntax_and_byte_identity() -> None:
    print("[1/10] Testing syntax validation and byte-for-byte identity...")
    assert CHECK_PY.exists(), f"Missing {CHECK_PY}"
    assert SCRIPTS_CHECK_PY.exists(), f"Missing {SCRIPTS_CHECK_PY}"

    # Byte-for-byte identity
    with open(CHECK_PY, "rb") as f1, open(SCRIPTS_CHECK_PY, "rb") as f2:
        content1 = f1.read()
        content2 = f2.read()
    assert content1 == content2, "check.py and scripts/check.py are NOT byte-identical!"

    # Compile check (in-memory without writing disallowed .pyc files to submission directory)
    compile(CHECK_PY.read_text(encoding="utf-8"), str(CHECK_PY), "exec")
    compile(SCRIPTS_CHECK_PY.read_text(encoding="utf-8"), str(SCRIPTS_CHECK_PY), "exec")
    print("  ✓ Syntax & byte identity verified.")


def test_string_assertion_with_ansi_escapes() -> None:
    print("[2/10] Testing string assertion failure with ANSI escapes...")
    code = "assert '\\x1b[31mError\\x1b[0m' == 'Error'"
    res = run_check(code)
    assert res.returncode == 1, f"Expected exit 1, got {res.returncode}. Output:\n{res.stdout}"

    out = res.stdout
    # Verify Actual and Expected with lengths
    assert "Actual:   '\\x1b[31mError\\x1b[0m' (length 14)" in out, f"Actual line missing in:\n{out}"
    assert "Expected: 'Error' (length 5)" in out, f"Expected line missing in:\n{out}"

    # Verify exact character index divergence with hex representation
    assert "Diff at index 0: actual='\\x1b' (hex: 0x1b) vs expected='E' (hex: 0x45)" in out, f"Hex diff missing in:\n{out}"

    # Verify ANSI escape breakdown
    assert "📟 ANSI & CONTROL ESCAPE BREAKDOWN:" in out, f"Escape breakdown header missing in:\n{out}"
    assert "31m" in out and "Red text" in out, f"SGR 31m decode missing in:\n{out}"
    assert "0m" in out and "Reset / Normal" in out, f"SGR 0m decode missing in:\n{out}"

    # Verify Root Cause Hint for LLM
    assert "💡 ROOT CAUSE HINT FOR LLM:" in out, f"Root cause hint header missing in:\n{out}"
    assert "ANSI styling/escape codes" in out, f"ANSI hint advice missing in:\n{out}"

    print("  ✓ String assertion failure with ANSI escapes and hex breakdown verified.")


def test_string_assertion_with_control_characters() -> None:
    print("[3/10] Testing string assertion failure with control characters (CR vs LF)...")
    code = "assert 'line1\\r\\nline2' == 'line1\\nline2'"
    res = run_check(code)
    assert res.returncode == 1, f"Expected exit 1, got {res.returncode}. Output:\n{res.stdout}"

    out = res.stdout
    # Verify hex divergence for CR (0x0d) vs LF (0x0a)
    assert "Diff at index 5: actual='\\r' (hex: 0xd) vs expected='\\n' (hex: 0xa)" in out, f"CR/LF hex diff missing in:\n{out}"
    assert "📟 ANSI & CONTROL ESCAPE BREAKDOWN:" in out, f"Escape breakdown header missing in:\n{out}"
    assert "0x0d: CR (carriage return)" in out or "carriage return" in out, f"CR decode missing in:\n{out}"
    assert "💡 ROOT CAUSE HINT FOR LLM:" in out, f"Root cause hint header missing in:\n{out}"

    print("  ✓ String assertion with control characters verified.")


def test_dict_assertion_mismatch() -> None:
    print("[4/10] Testing dict/JSON mismatch diagnostics...")
    code = """
actual_dict = {'status': 'ok', 'extra_field': 42}
expected_dict = {'status': 'error', 'missing_field': 'required'}
assert actual_dict == expected_dict
"""
    res = run_check(code)
    assert res.returncode == 1, f"Expected exit 1, got {res.returncode}. Output:\n{res.stdout}"

    out = res.stdout
    assert "📋 DICTIONARY / JSON MISMATCH:" in out, f"Dict mismatch header missing in:\n{out}"
    assert "Missing keys (in expected but not actual):" in out, f"Missing keys section missing in:\n{out}"
    assert "'missing_field'" in out, f"Missing key 'missing_field' not listed in:\n{out}"
    assert "Extra keys (in actual but not expected):" in out, f"Extra keys section missing in:\n{out}"
    assert "'extra_field'" in out, f"Extra key 'extra_field' not listed in:\n{out}"
    assert "Value differences for shared keys:" in out, f"Value differences section missing in:\n{out}"
    assert "Key 'status':" in out, f"Key 'status' difference missing in:\n{out}"
    assert "💡 ROOT CAUSE HINT FOR LLM:" in out, f"Root cause hint header missing in:\n{out}"
    assert "Dictionary mismatch" in out, f"Dict hint text missing in:\n{out}"

    print("  ✓ Dict/JSON mismatch diagnostics verified.")


def test_sequence_assertion_mismatch() -> None:
    print("[5/10] Testing sequence/list mismatch diagnostics...")
    code = "assert [1, 20, 3] == [1, 2, 3, 4]"
    res = run_check(code)
    assert res.returncode == 1, f"Expected exit 1, got {res.returncode}. Output:\n{res.stdout}"

    out = res.stdout
    assert "📋 SEQUENCE / LIST MISMATCH:" in out, f"Sequence mismatch header missing in:\n{out}"
    assert "Length difference:" in out, f"Length difference missing in:\n{out}"
    assert "Actual length:   3" in out, f"Actual length missing in:\n{out}"
    assert "Expected length: 4" in out, f"Expected length missing in:\n{out}"
    assert "First differing element at index 1:" in out, f"First differing element line missing in:\n{out}"
    assert "Actual:   20" in out, f"Actual item 20 missing in:\n{out}"
    assert "Expected: 2" in out, f"Expected item 2 missing in:\n{out}"
    assert "💡 ROOT CAUSE HINT FOR LLM:" in out, f"Root cause hint header missing in:\n{out}"

    print("  ✓ Sequence/list mismatch diagnostics verified.")


def test_valid_assertion_passes() -> None:
    print("[6/10] Testing clean valid assertion execution...")
    code = "assert 2 + 2 == 4\nassert 'hello'.upper() == 'HELLO'"
    res = run_check(code)
    assert res.returncode == 0, f"Expected exit 0, got {res.returncode}. Stderr:\n{res.stderr}\nStdout:\n{res.stdout}"
    assert "[repro-check] ✅ PASSED:" in res.stdout, f"PASSED header missing in:\n{res.stdout}"
    print("  ✓ Valid assertion execution passed cleanly with exit code 0.")


def test_hardened_features_regression() -> None:
    print("[7/10] Testing regression on hardened features (--b64, quote stripping, syntax errors, /tmp isolation)...")

    # 1. Base64 execution
    raw_snippet = "assert 7 * 6 == 42"
    b64_payload = base64.b64encode(raw_snippet.encode("utf-8")).decode("utf-8")
    res_b64 = run_check("--b64", b64_payload)
    assert res_b64.returncode == 0, f"Base64 execution failed: {res_b64.stdout}\n{res_b64.stderr}"
    assert "[repro-check] ✅ PASSED:" in res_b64.stdout

    # 2. Outer redundant quote stripping
    quoted_code = "\"assert 'sanitized' == 'sanitized'\""
    res_quote = run_check(quoted_code)
    assert res_quote.returncode == 0, f"Quote stripping failed: {res_quote.stdout}\n{res_quote.stderr}"
    assert "[repro-check] ✅ PASSED:" in res_quote.stdout

    # 3. AST pre-parse syntax check
    res_syntax = run_check("def unclosed_function(")
    assert res_syntax.returncode == 1, f"Expected exit 1 on syntax error, got {res_syntax.returncode}"
    assert "SYNTAX_ERROR" in res_syntax.stdout or "SyntaxError" in res_syntax.stdout

    # 4. Path containment check
    assert not (REPO_ROOT / "tmp").exists() or not any((REPO_ROOT / "tmp").iterdir()), "Accidental /workspace/tmp pollution detected!"

    print("  ✓ Hardened features regression tests passed.")


def test_infinite_loop_timeout() -> None:
    print("[8/10] Testing infinite loop immunity and timeout termination (os.killpg)...")
    import time
    t0 = time.time()
    res = run_check("-t", "2", "while True: pass")
    duration = time.time() - t0
    assert res.returncode == 1, f"Expected exit 1 on timeout, got {res.returncode}. Output:\n{res.stdout}\nStderr:\n{res.stderr}"
    assert duration < 6, f"Timeout took too long ({duration:.2f}s), should terminate in ~2s!"
    out = res.stdout
    assert "⏱️ Execution timed out after 2s (possible infinite loop in repro script)" in out, f"Timeout message missing in:\n{out}"
    print("  ✓ Infinite loop terminated cleanly via os.killpg after 2s.")


def test_omnivorous_forgiving_cli_and_fences() -> None:
    print("[9/10] Testing omnivorous CLI, markdown fences, quotes, and input styles...")

    # 1. Markdown code fence with language tag
    res_fence1 = run_check("```python\nassert 10 + 10 == 20\n```")
    assert res_fence1.returncode == 0, f"Markdown fence failed: {res_fence1.stdout}\n{res_fence1.stderr}"
    assert "[repro-check] ✅ PASSED:" in res_fence1.stdout

    # 2. Markdown code fence without language tag
    res_fence2 = run_check("```\nassert 15 + 15 == 30\n```")
    assert res_fence2.returncode == 0, f"Generic fence failed: {res_fence2.stdout}\n{res_fence2.stderr}"
    assert "[repro-check] ✅ PASSED:" in res_fence2.stdout

    # 3. Triple double quotes wrapping code
    res_triple = run_check('"""assert 25 + 25 == 50"""')
    assert res_triple.returncode == 0, f"Triple quotes failed: {res_triple.stdout}\n{res_triple.stderr}"
    assert "[repro-check] ✅ PASSED:" in res_triple.stdout

    # 4. Triple single quotes wrapping code
    res_triple_s = run_check("'''assert 35 + 35 == 70'''")
    assert res_triple_s.returncode == 0, f"Triple single quotes failed: {res_triple_s.stdout}\n{res_triple_s.stderr}"
    assert "[repro-check] ✅ PASSED:" in res_triple_s.stdout

    # 5. Escaped quotes wrapping code
    res_esc = run_check('\\"assert 45 + 45 == 90\\"')
    assert res_esc.returncode == 0, f"Escaped quotes failed: {res_esc.stdout}\n{res_esc.stderr}"
    assert "[repro-check] ✅ PASSED:" in res_esc.stdout

    # 6. Multiple positional arguments joined cleanly
    res_multi = run_check("assert", "1", "+", "2", "==", "3")
    assert res_multi.returncode == 0, f"Multiple positional tokens failed: {res_multi.stdout}\n{res_multi.stderr}"
    assert "[repro-check] ✅ PASSED:" in res_multi.stdout

    # 7. Explicit --code / -c flag
    res_code = run_check("--code", "assert 'apple'.upper() == 'APPLE'")
    assert res_code.returncode == 0, f"--code flag failed: {res_code.stdout}\n{res_code.stderr}"
    assert "[repro-check] ✅ PASSED:" in res_code.stdout

    res_c = run_check("-c", "assert 'banana'.title() == 'Banana'")
    assert res_c.returncode == 0, f"-c flag failed: {res_c.stdout}\n{res_c.stderr}"
    assert "[repro-check] ✅ PASSED:" in res_c.stdout

    # 8. File path directly as positional argument
    temp_script = pathlib.Path("/tmp/test_repro_scratch.py")
    temp_script.write_text("assert 100 // 10 == 10\n", encoding="utf-8")
    try:
        res_file_pos = run_check(str(temp_script))
        assert res_file_pos.returncode == 0, f"File positional argument failed: {res_file_pos.stdout}\n{res_file_pos.stderr}"
        assert "[repro-check] ✅ PASSED:" in res_file_pos.stdout

        res_file_flag = run_check("--file", str(temp_script))
        assert res_file_flag.returncode == 0, f"--file flag failed: {res_file_flag.stdout}\n{res_file_flag.stderr}"
        assert "[repro-check] ✅ PASSED:" in res_file_flag.stdout
    finally:
        temp_script.unlink(missing_ok=True)

    # 9. Stdin pipe
    res_stdin = run_check(stdin_data="assert 'stdin'.upper() == 'STDIN'\n")
    assert res_stdin.returncode == 0, f"Stdin pipe failed: {res_stdin.stdout}\n{res_stdin.stderr}"
    assert "[repro-check] ✅ PASSED:" in res_stdin.stdout

    print("  ✓ Omnivorous CLI, fences, quotes, flags, files, and stdin verified.")


def test_ast_preparse_syntax_error_caret() -> None:
    print("[10/10] Testing clean AST pre-parse error formatting and caret pointer...")
    res = run_check("def broken_syntax(")
    assert res.returncode == 1, f"Expected exit 1 on syntax error, got {res.returncode}"
    out = res.stdout
    assert "SYNTAX_ERROR" in out or "SyntaxError" in out, f"SYNTAX_ERROR missing in:\n{out}"
    assert "^" in out, f"Caret pointer missing in:\n{out}"
    assert "line 1" in out, f"Line number missing in:\n{out}"
    assert "Traceback (most recent call last)" not in out, f"Raw traceback leaked in output:\n{out}"
    assert "Traceback (most recent call last)" not in res.stderr, f"Raw traceback leaked in stderr:\n{res.stderr}"
    print("  ✓ Clean syntax error with caret pointer and no traceback leak verified.")


def main() -> int:
    print("======================================================================")
    print("REPRO-CHECK DEEP ASSERTION DIAGNOSTICS TEST SUITE")
    print("======================================================================")
    try:
        test_syntax_and_byte_identity()
        test_string_assertion_with_ansi_escapes()
        test_string_assertion_with_control_characters()
        test_dict_assertion_mismatch()
        test_sequence_assertion_mismatch()
        test_valid_assertion_passes()
        test_hardened_features_regression()
        test_infinite_loop_timeout()
        test_omnivorous_forgiving_cli_and_fences()
        test_ast_preparse_syntax_error_caret()
        print("======================================================================")
        print("✅ ALL 10 TEST SUITES PASSED CLEANLY (exit code 0)")
        print("======================================================================")
        return 0
    except AssertionError as exc:
        print(f"\n❌ TEST SUITE FAILED: {exc}")
        return 1
    except Exception as exc:
        print(f"\n💥 UNEXPECTED ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
