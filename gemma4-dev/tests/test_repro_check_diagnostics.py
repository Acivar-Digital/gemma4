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

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
CHECK_PY = REPO_ROOT / "my_submission" / "skills" / "repro-check" / "check.py"
SCRIPTS_CHECK_PY = REPO_ROOT / "my_submission" / "skills" / "repro-check" / "scripts" / "check.py"


def run_check(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run check.py with given arguments and return CompletedProcess."""
    cmd = [sys.executable, str(CHECK_PY)] + list(args)
    environ = os.environ.copy()
    environ["PYTHONPATH"] = f"{REPO_ROOT}:{environ.get('PYTHONPATH', '')}"
    if env:
        environ.update(env)
    return subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=environ,
        timeout=30,
    )


def test_syntax_and_byte_identity() -> None:
    print("[1/7] Testing syntax validation and byte-for-byte identity...")
    assert CHECK_PY.exists(), f"Missing {CHECK_PY}"
    assert SCRIPTS_CHECK_PY.exists(), f"Missing {SCRIPTS_CHECK_PY}"

    # Byte-for-byte identity
    with open(CHECK_PY, "rb") as f1, open(SCRIPTS_CHECK_PY, "rb") as f2:
        content1 = f1.read()
        content2 = f2.read()
    assert content1 == content2, "check.py and scripts/check.py are NOT byte-identical!"

    # Compile check
    res1 = subprocess.run([sys.executable, "-m", "py_compile", str(CHECK_PY)], capture_output=True, text=True)
    assert res1.returncode == 0, f"Compilation failed for check.py: {res1.stderr}"

    res2 = subprocess.run([sys.executable, "-m", "py_compile", str(SCRIPTS_CHECK_PY)], capture_output=True, text=True)
    assert res2.returncode == 0, f"Compilation failed for scripts/check.py: {res2.stderr}"

    print("  ✓ Syntax & byte identity verified.")


def test_string_assertion_with_ansi_escapes() -> None:
    print("[2/7] Testing string assertion failure with ANSI escapes...")
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
    print("[3/7] Testing string assertion failure with control characters (CR vs LF)...")
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
    print("[4/7] Testing dict/JSON mismatch diagnostics...")
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
    print("[5/7] Testing sequence/list mismatch diagnostics...")
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
    print("[6/7] Testing clean valid assertion execution...")
    code = "assert 2 + 2 == 4\nassert 'hello'.upper() == 'HELLO'"
    res = run_check(code)
    assert res.returncode == 0, f"Expected exit 0, got {res.returncode}. Stderr:\n{res.stderr}\nStdout:\n{res.stdout}"
    assert "[repro-check] ✅ PASSED:" in res.stdout, f"PASSED header missing in:\n{res.stdout}"
    print("  ✓ Valid assertion execution passed cleanly with exit code 0.")


def test_hardened_features_regression() -> None:
    print("[7/7] Testing regression on hardened features (--b64, quote stripping, syntax errors, /tmp isolation)...")

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
        print("======================================================================")
        print("✅ ALL 7 TEST SUITES PASSED CLEANLY (exit code 0)")
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
