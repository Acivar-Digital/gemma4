#!/usr/bin/env python3
"""Comprehensive test gauntlet for code-map skill.

Verifies:
1. Syntax & file identity between map.py and scripts/map.py.
2. Positional argument auto-detection (symbol, file with .py, file without .py, directory).
3. Omnivorous empty / dot / /workspace / -o / --overview mode (exit 0, tailored commands).
4. Informative diagnostics for missing symbol (fuzzy suggestions with locations & copy-pasteable commands, top-level symbols, next steps, exit 0).
5. Informative diagnostics for missing file (closest path suggestions with copy-pasteable commands, repo layout, exit 0).
6. Class hierarchy and subclass detection.
7. Loop and cycle safety (circular imports, circular caller/callee, symlink cycle, deep nesting).
8. Directory mapping with line budget limit.
9. Forgiving CLI flag parsing (-s, -f, -d, --dir, -o, --overview, -t, --tree, --callers, --callees, typos, unrecognized flags).
10. Safe error handling (SyntaxError with caret snippet, invalid UTF-8 binary encoding).
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
MAP_PATH = REPO_ROOT / "my_submission" / "skills" / "code-map" / "map.py"
SCRIPTS_MAP_PATH = REPO_ROOT / "my_submission" / "skills" / "code-map" / "scripts" / "map.py"


def run_map(*args: str, cwd: pathlib.Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run map.py with given arguments and return CompletedProcess."""
    cmd = [sys.executable, str(MAP_PATH)] + list(args)
    environ = os.environ.copy()
    if env:
        environ.update(env)
    return subprocess.run(
        cmd,
        cwd=str(cwd or REPO_ROOT),
        capture_output=True,
        text=True,
        env=environ,
        timeout=15,
    )


def test_syntax_and_sync():
    print("[1/10] Testing syntax validation and file sync...")
    assert MAP_PATH.exists(), f"Missing {MAP_PATH}"
    assert SCRIPTS_MAP_PATH.exists(), f"Missing {SCRIPTS_MAP_PATH}"

    # Check byte-for-byte identity
    with open(MAP_PATH, "rb") as f1, open(SCRIPTS_MAP_PATH, "rb") as f2:
        assert f1.read() == f2.read(), "map.py and scripts/map.py are NOT identical!"

    # Compile check
    res1 = subprocess.run([sys.executable, "-m", "py_compile", str(MAP_PATH)], capture_output=True, text=True)
    assert res1.returncode == 0, f"Compilation failed for map.py: {res1.stderr}"
    res2 = subprocess.run([sys.executable, "-m", "py_compile", str(SCRIPTS_MAP_PATH)], capture_output=True, text=True)
    assert res2.returncode == 0, f"Compilation failed for scripts/map.py: {res2.stderr}"
    print("  ✓ Syntax & synchronization verified.")


def test_empty_and_overview():
    print("[2/10] Testing empty call, '.', and workspace overview...")
    for args in [(), (".",), ("/workspace",), ("-o",), ("--overview",)]:
        res = run_map(*args)
        assert res.returncode == 0, f"Call with args={args} failed with returncode {res.returncode}: {res.stderr}"
        assert "CODE-MAP: WORKSPACE OVERVIEW & ACTIONABLE USAGE GUIDE" in res.stdout, f"Header missing in {args}"
        assert "TAILORED COPY-PASTEABLE COMMANDS:" in res.stdout
        assert "python3 map.py --file" in res.stdout
        assert "python3 map.py --symbol" in res.stdout

    # Test JSON mode on overview
    res_json = run_map("--json")
    assert res_json.returncode == 0
    data = json.loads(res_json.stdout)
    assert data["mode"] == "overview"
    assert data["success"] is True
    assert len(data["copy_pasteable_commands"]) > 0
    print("  ✓ Overview and empty arguments handle gracefully with exit code 0.")


def test_positional_auto_detection():
    print("[3/10] Testing forgiving positional argument auto-detection...")
    # Positional symbol
    res_sym = run_map("APIRouter")
    assert res_sym.returncode == 0
    assert "CODE-MAP: SYMBOL REFERENCE & REACHABILITY REPORT" in res_sym.stdout
    assert "QUERY: APIRouter" in res_sym.stdout

    # Positional file ending in .py
    res_file = run_map("docker/telnetlib.py")
    assert res_file.returncode == 0
    assert "docker/telnetlib.py:" in res_file.stdout

    # Positional directory
    res_dir = run_map("docker")
    assert res_dir.returncode == 0
    assert "docker/telnetlib.py:" in res_dir.stdout or "symbols across" in res_dir.stdout

    # Positional file without .py
    res_no_ext = run_map("docker/telnetlib")
    assert res_no_ext.returncode == 0
    assert "docker/telnetlib.py:" in res_no_ext.stdout

    print("  ✓ Positional auto-detection works for symbols, files, directories, and extension-less paths.")


def test_unknown_symbol_diagnostics():
    print("[4/10] Testing unknown symbol actionable diagnostics...")
    res = run_map("--symbol", "NonExistentFoobarFunctionXYZ")
    assert res.returncode == 0
    assert "STATUS: NOT FOUND" in res.stdout
    assert "WHY THIS QUERY FAILED:" in res.stdout
    assert "SUGGESTIONS:" in res.stdout
    assert "TOP-LEVEL PUBLIC SYMBOLS IN REPOSITORY:" in res.stdout
    assert "ACTIONABLE NEXT STEPS:" in res.stdout
    assert "fast-grep" in res.stdout

    # Test JSON output for unknown symbol
    res_json = run_map("--symbol", "NonExistentFoobarFunctionXYZ", "--json")
    assert res_json.returncode == 0
    data = json.loads(res_json.stdout)
    assert data["found"] is False
    assert len(data["available_top_symbols"]) > 0
    assert len(data["next_steps"]) > 0
    print("  ✓ Unknown symbol produces rich diagnostics, top-level symbols, and next steps.")


def test_unknown_file_diagnostics():
    print("[5/10] Testing unknown file actionable diagnostics...")
    res = run_map("--file", "nonexistent_module_foo_bar.py")
    assert res.returncode == 0
    assert "Path 'nonexistent_module_foo_bar.py' does not exist in /workspace." in res.stdout
    assert "WHY THIS FAILED:" in res.stdout
    assert "💡 Suggested closest existing paths:" in res.stdout
    assert "📂 Top-level repository layout (/workspace):" in res.stdout
    assert "👉 Actionable next steps:" in res.stdout

    # Test JSON output for unknown file
    res_json = run_map("--file", "nonexistent_module_foo_bar.py", "--json")
    assert res_json.returncode == 0
    data = json.loads(res_json.stdout)
    assert data["success"] is False
    assert len(data["diagnostics"]) > 0
    assert data["diagnostics"][0]["category"] == "missing_path"
    assert len(data["top_level_layout"]) > 0
    print("  ✓ Unknown file produces closest path suggestions, repo layout, and next steps.")


def test_class_hierarchy_and_subclasses():
    print("[6/10] Testing class hierarchy and subclass tracking...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = pathlib.Path(tmpdir)
        mod_code = """
class BaseService:
    \"\"\"Base service docstring.\"\"\"
    def start(self):
        pass

class CustomService(BaseService):
    \"\"\"Custom implementation.\"\"\"
    def start(self):
        super().start()
"""
        (tmppath / "service.py").write_text(mod_code, encoding="utf-8")

        # Test querying BaseService
        res = run_map("--symbol", "BaseService", cwd=tmppath)
        assert res.returncode == 0
        assert "class BaseService:" in res.stdout
        assert "CLASS HIERARCHY / SUBCLASSES" in res.stdout
        assert "CustomService" in res.stdout

        # Test querying CustomService
        res2 = run_map("--symbol", "CustomService", cwd=tmppath)
        assert res2.returncode == 0
        assert "bases: BaseService" in res2.stdout or "class CustomService(BaseService)" in res2.stdout
    print("  ✓ Base classes and subclass hierarchies extracted accurately.")


def test_loops_cycles_and_nesting():
    print("[7/10] Testing circular imports, recursion, symlink cycles, and deep AST nesting...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = pathlib.Path(tmpdir)

        # 1. Circular imports & mutual caller/callee
        mod_a = """
import mod_b

def func_a():
    mod_b.func_b()

class ClassA:
    def call_b(self):
        mod_b.func_b()
"""
        mod_b = """
import mod_a

def func_b():
    mod_a.func_a()
"""
        (tmppath / "mod_a.py").write_text(mod_a, encoding="utf-8")
        (tmppath / "mod_b.py").write_text(mod_b, encoding="utf-8")

        # 2. Deep AST nesting (25 levels deep)
        deep_lines = []
        for i in range(25):
            indent = "    " * i
            deep_lines.append(f"{indent}class NestedLevel{i}:")
        deep_lines.append(f"{'    '*25}def deep_leaf(): pass")
        (tmppath / "deep_nest.py").write_text("\n".join(deep_lines), encoding="utf-8")

        # 3. Symlink circular directory
        sub_dir = tmppath / "sub"
        sub_dir.mkdir()
        (sub_dir / "leaf.py").write_text("def sub_leaf(): pass", encoding="utf-8")
        try:
            (sub_dir / "loop_link").symlink_to(tmppath, target_is_directory=True)
        except OSError:
            pass

        # 4. .adk_exec directory that should be ignored
        adk_dir = tmppath / ".adk_exec_scratch"
        adk_dir.mkdir()
        (adk_dir / "ignored.py").write_text("def ignored(): pass", encoding="utf-8")

        # Query symbol across circular graph
        res_sym = run_map("--symbol", "func_a", cwd=tmppath)
        assert res_sym.returncode == 0
        assert "func_a" in res_sym.stdout

        # File outline on deeply nested file (must not blow recursion depth)
        res_deep = run_map("--file", "deep_nest.py", cwd=tmppath)
        assert res_deep.returncode == 0
        assert "deep_nest.py:" in res_deep.stdout

        # Overview on circular symlink dir (must terminate immediately without looping)
        res_ov = run_map(cwd=tmppath)
        assert res_ov.returncode == 0
        assert "CODE-MAP: WORKSPACE OVERVIEW" in res_ov.stdout
        assert ".adk_exec" not in res_ov.stdout

    print("  ✓ Zero crash, zero infinite loops on circular imports, caller loops, symlinks, and deep AST.")


def test_directory_mapping():
    print("[8/10] Testing directory mapping with line budget...")
    res = run_map("--file", "docker")
    assert res.returncode == 0
    assert "docker/telnetlib.py:" in res.stdout
    assert "symbols across" in res.stdout
    print("  ✓ Directory mapping handles multi-module budgets smoothly.")


def test_flag_aliases_and_forgiving_cli():
    print("[9/10] Testing flag aliases (-s, -f, -d, --dir, -t, --tree, --callers, --callees) and forgiving parser...")
    # -s alias for symbol
    res_s = run_map("-s", "APIRouter")
    assert res_s.returncode == 0
    assert "QUERY: APIRouter" in res_s.stdout

    # -f alias for file
    res_f = run_map("-f", "docker/telnetlib.py")
    assert res_f.returncode == 0
    assert "docker/telnetlib.py:" in res_f.stdout

    # -d alias for directory
    res_d = run_map("-d", "docker")
    assert res_d.returncode == 0
    assert "docker/telnetlib.py:" in res_d.stdout or "symbols across" in res_d.stdout

    # --dir alias for directory
    res_dir = run_map("--dir", "docker")
    assert res_dir.returncode == 0
    assert "docker/telnetlib.py:" in res_dir.stdout or "symbols across" in res_dir.stdout

    # -t / --tree alias
    res_tree = run_map("-t", "docker")
    assert res_tree.returncode == 0
    assert "docker/telnetlib.py:" in res_tree.stdout or "symbols across" in res_tree.stdout

    # --callers with symbol value
    res_callers = run_map("--callers", "APIRouter")
    assert res_callers.returncode == 0
    assert "FOCUS: CALLERS" in res_callers.stdout
    assert "TARGET INBOUND CALLERS" in res_callers.stdout

    # --callees with symbol value
    res_callees = run_map("--callees", "APIRouter")
    assert res_callees.returncode == 0
    assert "FOCUS: CALLEES" in res_callees.stdout
    assert "TARGET OUTBOUND CALLEES" in res_callees.stdout

    # Symbol with trailing --callers flag
    res_sym_callers = run_map("APIRouter", "--callers")
    assert res_sym_callers.returncode == 0
    assert "FOCUS: CALLERS" in res_sym_callers.stdout

    # Typo tolerance: --symbl fuzzy matches --symbol
    res_typo = run_map("--symbl", "APIRouter")
    assert res_typo.returncode == 0
    assert "QUERY: APIRouter" in res_typo.stdout

    # Unrecognized options: never fail with exit code 2 or ArgumentError
    res_unknown = run_map("--bogus-unrecognized-flag", "APIRouter")
    assert res_unknown.returncode == 0
    assert "QUERY: APIRouter" in res_unknown.stdout
    assert "Unrecognized option '--bogus-unrecognized-flag' ignored." in res_unknown.stdout

    # Solitary unknown flag falls back to overview cleanly
    res_solo_unknown = run_map("--unrecognized-option-only")
    assert res_solo_unknown.returncode == 0
    assert "CODE-MAP: WORKSPACE OVERVIEW" in res_solo_unknown.stdout

    # Flags passed without values handle gracefully without ArgumentError
    res_no_val = run_map("--symbol")
    assert res_no_val.returncode == 0
    assert "CODE-MAP: WORKSPACE OVERVIEW" in res_no_val.stdout

    res_no_val_file = run_map("--file")
    assert res_no_val_file.returncode == 0
    assert "CODE-MAP: WORKSPACE OVERVIEW" in res_no_val_file.stdout

    print("  ✓ Forgiving CLI: all aliases, typo recovery, caller/callee filters, and missing values handled with exit 0.")


def test_safe_error_handling():
    print("[10/10] Testing safe error handling (SyntaxError snippets, invalid UTF-8 binary)...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = pathlib.Path(tmpdir)

        # 1. Invalid Python syntax with caret pointer
        bad_syntax_code = "def broken_func(:\n    pass\n"
        (tmppath / "broken.py").write_text(bad_syntax_code, encoding="utf-8")

        res_syntax = run_map("--file", "broken.py", cwd=tmppath)
        assert res_syntax.returncode == 0
        assert "SyntaxError in broken.py" in res_syntax.stdout
        assert "^" in res_syntax.stdout
        assert "Guidance:" in res_syntax.stdout

        # 2. Binary / invalid UTF-8 file
        (tmppath / "binary.py").write_bytes(b"\x80\x81\xff\xfe\x00\x01\x02")
        res_binary = run_map("--file", "binary.py", cwd=tmppath)
        assert res_binary.returncode == 0
        assert "binary.py" in res_binary.stdout

    print("  ✓ Safe error handling: SyntaxError snippet & binary errors return clean notices without tracebacks.")


def main():
    print("=" * 70)
    print("STARTING CODE-MAP AUDIT & VERIFICATION GAUNTLET")
    print("=" * 70)

    test_syntax_and_sync()
    test_empty_and_overview()
    test_positional_auto_detection()
    test_unknown_symbol_diagnostics()
    test_unknown_file_diagnostics()
    test_class_hierarchy_and_subclasses()
    test_loops_cycles_and_nesting()
    test_directory_mapping()
    test_flag_aliases_and_forgiving_cli()
    test_safe_error_handling()

    print("=" * 70)
    print("ALL 10 GAUNTLET TESTS PASSED CLEANLY (EXIT CODE 0)!")
    print("=" * 70)


if __name__ == "__main__":
    main()
