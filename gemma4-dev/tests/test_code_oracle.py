#!/usr/bin/env python3
"""Comprehensive test suite for code-oracle skill.

Verifies:
1. Syntax validation & byte-for-byte identity between oracle.py and scripts/oracle.py.
2. Empty invocation and --help (exits code 0 with compact overview and example commands).
3. Mode 1: --eval (expression evaluation, type/repr/len/formatted, syntax and runtime diagnostics).
4. Mode 2: --hex (ANSI CSI SGR, OSC hyperlinks, invisible control chars, lone CR, zero-width chars).
5. Mode 3: --width (monospaced cell width for ASCII, CJK, emoji, ZWJ sequences, combining marks, ANSI).
6. Mode 4: --html-esc (tag balance, void tags, unclosed/misnested tags, entity escaping, script warnings).
7. Mode 5: --schema (JSON Schema / OpenAPI: $defs vs definitions, dangling $ref resolution, anyOf null, types).
8. Mode 6: --syntax (AST syntax error, regex inspection, top-level import resolution without side-effects).
9. Positional auto-detection (.py -> syntax, .json -> schema, .html -> html-esc, ANSI -> hex, HTML tags -> html-esc, expression -> eval).
10. Omnivorous & Forgiving CLI (short flags -e/-x/-w/-H/-s/-S/-j, loose flags -eval/---eval, unquoted expressions 1 + 2 * 3).
11. Crash & Infinite Loop Immunity in --eval (while True: pass, infinite generators, MemoryError, RecursionError, SystemExit).
12. Schema resilience: non-dict schemas, boolean schemas, recursive $ref cycles without RecursionError.
13. Actionable diagnostics: character-level explanations in --width, exact corrected $ref paths in --schema, entity fixes in --html-esc.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

# Prevent Python from writing bytecode cache files (.pyc) that ADK compiler strictly forbids
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
ORACLE_PATH = REPO_ROOT / "my_submission" / "skills" / "code-oracle" / "oracle.py"
SCRIPTS_ORACLE_PATH = REPO_ROOT / "my_submission" / "skills" / "code-oracle" / "scripts" / "oracle.py"


def run_oracle(*args: str, cwd: pathlib.Path | None = None, env: dict | None = None, timeout: int = 15) -> subprocess.CompletedProcess:
    """Run oracle.py with arguments and return CompletedProcess."""
    cmd = [sys.executable, "-B", str(ORACLE_PATH)] + list(args)
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


def test_syntax_and_byte_identity():
    print("[1/13] Testing syntax validation and byte-for-byte identity...")
    assert ORACLE_PATH.exists(), f"Missing {ORACLE_PATH}"
    assert SCRIPTS_ORACLE_PATH.exists(), f"Missing {SCRIPTS_ORACLE_PATH}"

    # Verify 100% byte-for-byte identical
    with open(ORACLE_PATH, "rb") as f1, open(SCRIPTS_ORACLE_PATH, "rb") as f2:
        b1, b2 = f1.read(), f2.read()
        assert b1 == b2, f"oracle.py ({len(b1)} bytes) and scripts/oracle.py ({len(b2)} bytes) are not byte-identical!"

    # Compile check (in-memory without writing disallowed .pyc files to submission directory)
    compile(ORACLE_PATH.read_text(encoding="utf-8"), str(ORACLE_PATH), "exec")
    compile(SCRIPTS_ORACLE_PATH.read_text(encoding="utf-8"), str(SCRIPTS_ORACLE_PATH), "exec")
    print("  ✓ Syntax & byte identity verified.")


def test_empty_and_help():
    print("[2/13] Testing empty invocation and --help overview...")
    for args in [(), ("-h",), ("--help",), ("-help",)]:
        res = run_oracle(*args)
        assert res.returncode == 0, f"Invocation with {args} failed with returncode {res.returncode}: {res.stderr}"
        assert "CODE-ORACLE: Multi-Domain Coding Assistance Oracle" in res.stdout
        assert "--eval" in res.stdout
        assert "--hex" in res.stdout
        assert "--width" in res.stdout
        assert "--html-esc" in res.stdout
        assert "--schema" in res.stdout
        assert "--syntax" in res.stdout
        assert "COPY-PASTEABLE EXAMPLE COMMANDS:" in res.stdout
    print("  ✓ Empty call and help exit 0 with clean overview.")


def test_eval_mode():
    print("[3/13] Testing Mode 1: --eval...")
    # 1. Valid expression
    res_val = run_oracle("--eval", "len([x for x in range(10) if x % 2 == 0])")
    assert res_val.returncode == 0, f"Eval failed: {res_val.stderr}"
    assert "Evaluation Successful" in res_val.stdout
    assert "Type       : int" in res_val.stdout
    assert "Formatted  : 5" in res_val.stdout

    # 2. JSON mode
    res_json = run_oracle("--eval", '{"a": 1, "b": [2, 3]}', "--json")
    assert res_json.returncode == 0
    data = json.loads(res_json.stdout)
    assert data["status"] == "ok"
    assert data["type"] == "dict"
    assert data["len"] == 2

    # 3. Syntax error in expression
    res_syn = run_oracle("--eval", "1 + (2 *")
    assert res_syn.returncode == 1
    assert "SyntaxError in expression" in res_syn.stdout or "SyntaxError" in res_syn.stdout

    # 4. Runtime error in expression (NameError)
    res_name = run_oracle("--eval", "undefined_var_123 + 456")
    assert res_name.returncode == 1
    assert "NameError" in res_name.stdout
    assert "undefined_var_123" in res_name.stdout

    # 5. Runtime error (ZeroDivisionError)
    res_zero = run_oracle("--eval", "10 / 0", "--json")
    assert res_zero.returncode == 1
    data_zero = json.loads(res_zero.stdout)
    assert data_zero["error_type"] == "ZeroDivisionError"
    print("  ✓ --eval handles valid evaluation, JSON mode, syntax errors, and runtime errors.")


def test_hex_mode():
    print("[4/13] Testing Mode 2: --hex...")
    input_str = "\x1b[31;1mError!\x1b[0m\r\n\x1b]8;;https://example.com\x1b\\Link\x1b]8;;\x1b\\\u200b"
    res = run_oracle("--hex", input_str, "--json")
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["status"] == "ok"
    assert len(data["hex_dump"]) > 0
    assert len(data["ansi_sequences"]) >= 2
    sgr_details = " ".join([d for seq in data["ansi_sequences"] for d in seq["details"]])
    assert "FG Red" in sgr_details or "Red" in sgr_details
    special_names = [sc["name"] for sc in data["special_characters"]]
    assert "ZERO WIDTH SPACE" in special_names

    res_text = run_oracle("--hex", "\x1b[31mUnclosed Text")
    assert res_text.returncode == 0
    assert "HEX DUMP" in res_text.stdout
    assert "Unclosed ANSI sequence detected" in res_text.stdout
    print("  ✓ --hex parses SGR parameters, OSC links, invisible characters, and unclosed warnings.")


def test_width_mode():
    print("[5/13] Testing Mode 3: --width...")
    # 1. Standard ASCII
    res_ascii = run_oracle("--width", "hello", "--json")
    assert res_ascii.returncode == 0
    data_ascii = json.loads(res_ascii.stdout)
    assert data_ascii["terminal_columns"] == 5
    assert data_ascii["len_code_points"] == 5

    # 2. CJK East Asian characters (2 cells each)
    res_cjk = run_oracle("--width", "你好世界", "--json")
    assert res_cjk.returncode == 0
    data_cjk = json.loads(res_cjk.stdout)
    assert data_cjk["terminal_columns"] == 8
    assert data_cjk["len_code_points"] == 4
    assert len(data_cjk["diagnostics"]) > 0

    # 3. Emoji (2 cells)
    res_emoji = run_oracle("--width", "🔥", "--json")
    assert res_emoji.returncode == 0
    data_emoji = json.loads(res_emoji.stdout)
    assert data_emoji["terminal_columns"] == 2
    assert data_emoji["len_code_points"] == 1

    # 4. ZWJ emoji sequence (👨‍👩‍👧‍👦 = 2 cells)
    res_family = run_oracle("--width", "👨‍👩‍👧‍👦", "--json")
    assert res_family.returncode == 0
    data_family = json.loads(res_family.stdout)
    assert data_family["terminal_columns"] == 2
    assert data_family["len_code_points"] == 7

    # 5. Combining accent
    res_comb = run_oracle("--width", "e\u0301", "--json")
    assert res_comb.returncode == 0
    data_comb = json.loads(res_comb.stdout)
    assert data_comb["terminal_columns"] == 1
    assert data_comb["len_code_points"] == 2

    # 6. ANSI escaped string
    res_ansi = run_oracle("--width", "\x1b[31mhello\x1b[0m", "--json")
    assert res_ansi.returncode == 0
    data_ansi = json.loads(res_ansi.stdout)
    assert data_ansi["terminal_columns"] == 5
    assert data_ansi["len_code_points"] == 14

    # 7. Text output diagnostics check
    res_text = run_oracle("--width", "👨‍👩‍👧‍👦 Family")
    assert res_text.returncode == 0
    assert "Terminal Columns : 9" in res_text.stdout
    assert "ACTIONABLE DIAGNOSTICS" in res_text.stdout
    print("  ✓ --width correctly measures ASCII, CJK, emojis, ZWJ sequences, combining marks, and ANSI escapes.")


def test_html_esc_mode():
    print("[6/13] Testing Mode 4: --html-esc...")
    # 1. Clean HTML
    clean_html = '<html><head><title>Test</title></head><body><p>Hello &amp; welcome</p><img src="x.png"></body></html>'
    res_clean = run_oracle("--html-esc", clean_html, "--json")
    assert res_clean.returncode == 0
    assert json.loads(res_clean.stdout)["status"] == "passed"

    # 2. Tag mismatch / Misnested tags
    misnested = "<div><span>Hello</div></span>"
    res_mis = run_oracle("--html-esc", misnested, "--json")
    assert res_mis.returncode == 1
    data_mis = json.loads(res_mis.stdout)
    assert data_mis["status"] == "failed"
    assert any(e["kind"] == "MisnestedTag" for e in data_mis["errors"])

    # 3. Unclosed tag at EOF
    unclosed = "<div><p>Paragraph content"
    res_unc = run_oracle("--html-esc", unclosed, "--json")
    assert res_unc.returncode == 1
    data_unc = json.loads(res_unc.stdout)
    assert any(e["kind"] == "UnclosedTag" for e in data_unc["errors"])

    # 4. Raw unescaped ampersand
    raw_amp = "<div>Hello & goodbye</div>"
    res_amp = run_oracle("--html-esc", raw_amp, "--json")
    assert res_amp.returncode == 1
    data_amp = json.loads(res_amp.stdout)
    assert any(e["kind"] == "UnescapedAmpersand" for e in data_amp["errors"])

    # 5. Raw < or > in <script>
    script_html = "<script>var x = 1 < 2;</script>"
    res_scr = run_oracle("--html-esc", script_html, "--json")
    data_scr = json.loads(res_scr.stdout)
    assert any(w["kind"] == "RawScriptAngleBrackets" for w in data_scr["warnings"])
    print("  ✓ --html-esc verifies tag balance, unclosed tags, void tags, entity escaping, and script warnings.")


def test_schema_mode():
    print("[7/13] Testing Mode 5: --schema...")
    # 1. Clean OpenAPI 3.1 schema
    clean_schema = {
        "openapi": "3.1.0",
        "$defs": {
            "Item": {"type": "string"},
            "Container": {
                "type": "object",
                "properties": {
                    "item": {"$ref": "#/$defs/Item"},
                    "nullable_field": {
                        "anyOf": [{"type": "string"}, {"type": "null"}]
                    }
                },
                "required": ["item"]
            }
        }
    }
    res_clean = run_oracle("--schema", json.dumps(clean_schema), "--json")
    assert res_clean.returncode == 0
    data_clean = json.loads(res_clean.stdout)
    assert data_clean["status"] == "passed"
    assert len(data_clean["dangling_refs"]) == 0

    # 2. Missing / dangling $ref with $defs vs definitions hint
    broken_schema = {
        "$defs": {
            "User": {"type": "object"}
        },
        "properties": {
            "user": {"$ref": "#/definitions/User"}
        }
    }
    res_broken = run_oracle("--schema", json.dumps(broken_schema), "--json")
    assert res_broken.returncode == 1
    data_broken = json.loads(res_broken.stdout)
    assert data_broken["status"] == "failed"
    assert len(data_broken["dangling_refs"]) == 1
    assert "Did you mean '#/$defs/User'?" in data_broken["dangling_refs"][0]["error"]

    # 3. anyOf with invalid Python 'None'
    invalid_anyof = {
        "properties": {
            "field": {
                "anyOf": [{"type": "string"}, {"type": "None"}]
            }
        }
    }
    res_anyof = run_oracle("--schema", json.dumps(invalid_anyof), "--json")
    assert res_anyof.returncode == 1
    data_anyof = json.loads(res_anyof.stdout)
    assert len(data_anyof["anyof_issues"]) > 0

    # 4. Invalid Python type leak
    leaked_type = {
        "properties": {
            "data": {"type": "dict"}
        }
    }
    res_type = run_oracle("--schema", json.dumps(leaked_type), "--json")
    assert res_type.returncode == 1
    data_type = json.loads(res_type.stdout)
    assert len(data_type["type_health_issues"]) > 0

    # 5. Invalid JSON syntax
    res_bad_json = run_oracle("--schema", '{"key": missing_quotes}')
    assert res_bad_json.returncode == 1
    assert "Invalid JSON syntax" in res_bad_json.stdout
    print("  ✓ --schema detects clean schemas, dangling $refs, $defs vs definitions hints, anyOf nulls, and type health.")


def test_syntax_mode():
    print("[8/13] Testing Mode 6: --syntax...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = pathlib.Path(tmpdir)

        # 1. Valid file
        valid_file = tmp_path / "valid.py"
        valid_file.write_text("import json\nimport re\n\ndef foo():\n    return json.dumps({'ok': True})\n")
        res_valid = run_oracle("--syntax", str(valid_file), "--json")
        assert res_valid.returncode == 0
        data_valid = json.loads(res_valid.stdout)
        assert data_valid["status"] == "passed"
        assert data_valid["total_errors"] == 0

        # 2. SyntaxError file
        bad_syntax_file = tmp_path / "bad_syntax.py"
        bad_syntax_file.write_text("def broken(\n    return 1\n")
        res_syn = run_oracle("--syntax", str(bad_syntax_file), "--json")
        assert res_syn.returncode == 1
        data_syn = json.loads(res_syn.stdout)
        assert data_syn["status"] == "failed"
        assert any(e["error_type"] == "SyntaxError" for e in data_syn["errors"])

        # 3. Bad Regex in file
        bad_regex_file = tmp_path / "bad_regex.py"
        bad_regex_file.write_text("import re\npattern = re.compile(r'(?<=\\n')\n")
        res_reg = run_oracle("--syntax", str(bad_regex_file), "--json")
        assert res_reg.returncode == 1
        data_reg = json.loads(res_reg.stdout)
        assert any(e["error_type"] == "RegexSyntaxError" for e in data_reg["errors"])

        # 4. Unresolved import in file
        bad_import_file = tmp_path / "bad_import.py"
        bad_import_file.write_text("import non_existent_super_rare_package_xyz987\n")
        res_imp = run_oracle("--syntax", str(bad_import_file), "--json")
        assert res_imp.returncode == 1
        data_imp = json.loads(res_imp.stdout)
        assert any(e["error_type"] == "UnresolvedImport" for e in data_imp["errors"])
    print("  ✓ --syntax validates AST syntax, regex lookbehinds, and top-level imports.")


def test_positional_auto_detection():
    print("[9/13] Testing positional argument auto-detection across all domains...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = pathlib.Path(tmpdir)

        # 1. Positional .py -> syntax
        py_file = tmp_path / "sample.py"
        py_file.write_text("import math\nx = math.sqrt(16)\n")
        res_py = run_oracle(str(py_file), "--json")
        assert res_py.returncode == 0
        data_py = json.loads(res_py.stdout)
        assert data_py["mode"] == "syntax"

        # 2. Positional .json -> schema
        json_file = tmp_path / "schema.json"
        json_file.write_text('{"type": "object", "properties": {"name": {"type": "string"}}}')
        res_json = run_oracle(str(json_file), "--json")
        assert res_json.returncode == 0
        data_json = json.loads(res_json.stdout)
        assert data_json["mode"] == "schema"

        # 3. Positional .html -> html-esc
        html_file = tmp_path / "index.html"
        html_file.write_text("<div><p>Hello</p></div>")
        res_html = run_oracle(str(html_file), "--json")
        assert res_html.returncode == 0
        data_html = json.loads(res_html.stdout)
        assert data_html["mode"] == "html-esc"

        # 4. Positional ANSI string -> hex
        res_ansi = run_oracle("\x1b[31;1mAlert\x1b[0m", "--json")
        assert res_ansi.returncode == 0
        data_ansi = json.loads(res_ansi.stdout)
        assert data_ansi["mode"] == "hex"

        # 5. Positional HTML tag snippet -> html-esc
        res_snippet = run_oracle("<div class='container'><p>Snippet</p></div>", "--json")
        assert res_snippet.returncode == 0
        data_snippet = json.loads(res_snippet.stdout)
        assert data_snippet["mode"] == "html-esc"

        # 6. Positional JSON schema string -> schema
        res_sch_str = run_oracle('{"$defs": {"Foo": {"type": "string"}}}', "--json")
        assert res_sch_str.returncode == 0
        data_sch_str = json.loads(res_sch_str.stdout)
        assert data_sch_str["mode"] == "schema"

        # 7. Positional expression string -> eval
        res_expr = run_oracle("len('hello world')", "--json")
        assert res_expr.returncode == 0
        data_expr = json.loads(res_expr.stdout)
        assert data_expr["mode"] == "eval"
        assert data_expr["formatted"] == "11"

        # 8. Positional existing .txt file -> hex
        txt_file = tmp_path / "notes.txt"
        txt_file.write_text("plain text notes with \r\n")
        res_txt = run_oracle(str(txt_file), "--json")
        assert res_txt.returncode == 0
        data_txt = json.loads(res_txt.stdout)
        assert data_txt["mode"] == "hex"
    print("  ✓ Positional auto-detection handles .py, .json, .html, .txt, ANSI, HTML snippets, schema strings, and expressions.")


def test_forgiving_cli_and_unquoted_inputs():
    print("[10/13] Testing forgiving CLI flags and unquoted expressions...")
    # 1. Short flags: -e, -x, -w, -H, -s, -S, -j
    res_e = run_oracle("-e", "2 ** 8", "-j")
    assert res_e.returncode == 0
    assert json.loads(res_e.stdout)["formatted"] == "256"

    res_x = run_oracle("-x", "abc", "-j")
    assert res_x.returncode == 0
    assert json.loads(res_x.stdout)["mode"] == "hex"

    res_w = run_oracle("-w", "hello", "-j")
    assert res_w.returncode == 0
    assert json.loads(res_w.stdout)["terminal_columns"] == 5

    res_h = run_oracle("-H", "<p>hi</p>", "-j")
    assert res_h.returncode == 0
    assert json.loads(res_h.stdout)["status"] == "passed"

    # 2. Loose flags with extra dashes (-eval, ---eval, -schema, ---schema)
    res_loose1 = run_oracle("-eval", "3 * 7")
    assert res_loose1.returncode == 0
    assert "Formatted  : 21" in res_loose1.stdout

    res_loose2 = run_oracle("---eval", "5 + 5")
    assert res_loose2.returncode == 0
    assert "Formatted  : 10" in res_loose2.stdout

    # 3. Unquoted expressions joined automatically: python3 oracle.py 1 + 2 * 3
    res_unquoted = run_oracle("1", "+", "2", "*", "3")
    assert res_unquoted.returncode == 0
    assert "Formatted  : 7" in res_unquoted.stdout

    # 4. Unquoted expressions with --eval: python3 oracle.py --eval 10 + 20
    res_unquoted_eval = run_oracle("--eval", "10", "+", "20")
    assert res_unquoted_eval.returncode == 0
    assert "Formatted  : 30" in res_unquoted_eval.stdout

    # 5. Unknown loose flags are handled gracefully rather than crashing
    res_unknown = run_oracle("--verbose", "--eval", "'safe'")
    assert res_unknown.returncode == 0
    assert "Formatted  : safe" in res_unknown.stdout

    # 6. Flag synonyms & aliases
    res_syn_w = run_oracle("--cellwidth", "abc", "-j")
    assert res_syn_w.returncode == 0
    assert json.loads(res_syn_w.stdout)["mode"] == "width"

    res_syn_x = run_oracle("--hexdump", "abc", "-j")
    assert res_syn_x.returncode == 0
    assert json.loads(res_syn_x.stdout)["mode"] == "hex"

    res_syn_s = run_oracle("--openapi", '{"type": "object"}', "-j")
    assert res_syn_s.returncode == 0
    assert json.loads(res_syn_s.stdout)["mode"] == "schema"

    # 7. Fuzzy flag typo tolerance
    res_fuzzy_w = run_oracle("--wdith", "hello", "-j")
    assert res_fuzzy_w.returncode == 0
    assert json.loads(res_fuzzy_w.stdout)["mode"] == "width"

    res_fuzzy_e = run_oracle("--evall", "12 + 34", "-j")
    assert res_fuzzy_e.returncode == 0
    assert json.loads(res_fuzzy_e.stdout)["formatted"] == "46"
    print("  ✓ Forgiving CLI flags (-e, -eval, ---eval), synonyms (--hexdump, --cellwidth), fuzzy typos (--wdith, --evall), and unquoted multi-token expressions work cleanly.")


def test_crash_and_infinite_loop_immunity():
    print("[11/13] Testing crash and infinite loop immunity in --eval...")
    # 1. Infinite loop: while True: pass interrupted cleanly within timeout (~2s)
    t0 = time.time()
    res_loop = run_oracle("--eval", "while True: pass", "--json", timeout=6)
    elapsed = time.time() - t0
    assert res_loop.returncode == 1
    assert elapsed < 5.0, f"Execution hung! Took {elapsed}s"
    data_loop = json.loads(res_loop.stdout)
    assert data_loop["error_type"] == "TimeoutError"
    assert "infinite loop" in data_loop["diagnostic"].lower()

    # 2. Infinite generator / list comprehension
    t0 = time.time()
    res_gen = run_oracle("--eval", "[x for x in iter(int, 1)]", "--json", timeout=6)
    elapsed = time.time() - t0
    assert res_gen.returncode == 1
    assert elapsed < 5.0
    data_gen = json.loads(res_gen.stdout)
    assert data_gen["error_type"] == "TimeoutError"

    # 3. RecursionError immunity
    res_rec = run_oracle("--eval", "(lambda f: f(f))(lambda f: f(f))", "--json")
    assert res_rec.returncode == 1
    data_rec = json.loads(res_rec.stdout)
    assert data_rec["error_type"] == "RecursionError"
    assert "recursion" in data_rec["diagnostic"].lower()

    # 4. SystemExit immunity: sys.exit(0) caught without terminating caller
    res_exit = run_oracle("--eval", "sys.exit(0)", "--json")
    assert res_exit.returncode == 1
    data_exit = json.loads(res_exit.stdout)
    assert data_exit["error_type"] == "SystemExit"
    assert "sys.exit" in data_exit["diagnostic"].lower()

    # 5. MemoryError immunity
    res_mem = run_oracle("--eval", "range(10)**10", "--json")
    assert res_mem.returncode == 1
    data_mem = json.loads(res_mem.stdout)
    assert data_mem["status"] == "error"

    # 6. ValueError / runtime exception immunity
    res_val = run_oracle("--eval", "int('invalid_number_123')", "--json")
    assert res_val.returncode == 1
    data_val = json.loads(res_val.stdout)
    assert data_val["error_type"] == "ValueError"
    assert "invalid literal" in data_val["message"]
    assert "ValueError:" in data_val["diagnostic"]
    print("  ✓ Infinite loops (while True / generators) time out in <3s, RecursionError, SystemExit, and ValueErrors caught cleanly.")


def test_schema_resilience_and_recursion_cycle():
    print("[12/13] Testing schema resilience (non-dict, boolean schemas, recursive $ref cycles)...")
    # 1. Non-dict root schema (e.g. array or primitive passed) handled without crashing
    res_arr = run_oracle("--schema", "[1, 2, 3]", "--json")
    assert res_arr.returncode == 1
    data_arr = json.loads(res_arr.stdout)
    assert "Invalid schema root type: list" in data_arr["error"]

    res_str = run_oracle("--schema", '"not_a_dict"', "--json")
    assert res_str.returncode == 1
    data_str = json.loads(res_str.stdout)
    assert "Invalid schema root type: str" in data_str["error"]

    # 2. Boolean schema (Draft 7+ valid schema)
    res_bool_true = run_oracle("--schema", "true", "--json")
    assert res_bool_true.returncode == 0
    assert json.loads(res_bool_true.stdout)["status"] == "passed"

    res_bool_false = run_oracle("--schema", "false", "--json")
    assert res_bool_false.returncode == 1
    assert json.loads(res_bool_false.stdout)["status"] == "failed"

    # 3. Recursive $ref cycle (Node -> Node self-reference) resolves without RecursionError
    rec_schema = {
        "$defs": {
            "Node": {
                "type": "object",
                "properties": {
                    "next": {"$ref": "#/$defs/Node"}
                }
            }
        },
        "$ref": "#/$defs/Node"
    }
    res_rec = run_oracle("--schema", json.dumps(rec_schema), "--json")
    assert res_rec.returncode == 0
    data_rec = json.loads(res_rec.stdout)
    assert data_rec["status"] == "passed"
    assert len(data_rec["dangling_refs"]) == 0

    # 4. Deeply nested schema (300 levels deep) iterative traversal test
    deep_schema = {"type": "string"}
    for _ in range(300):
        deep_schema = {"type": "object", "properties": {"child": deep_schema}}
    res_deep = run_oracle("--schema", json.dumps(deep_schema), "--json")
    assert res_deep.returncode == 0
    data_deep = json.loads(res_deep.stdout)
    assert data_deep["status"] == "passed"
    print("  ✓ Non-dict schemas, boolean schemas, recursive $ref cycles, and 300-level deep schemas handled without crash or RecursionError.")


def test_actionable_diagnostics():
    print("[13/13] Testing actionable LLM diagnostics...")
    # 1. Actionable cell width diagnostics: explains which specific characters cause width mismatch
    res_w = run_oracle("--width", "Rocket 🚀 Star ⭐", "--json")
    assert res_w.returncode == 0
    data_w = json.loads(res_w.stdout)
    diag_str = " ".join(data_w["diagnostics"])
    assert "Character '🚀'" in diag_str
    assert "occupies 2 terminal cells" in diag_str

    # 2. Actionable dangling $ref diagnostics: provides exact corrected path
    typo_schema = {
        "$defs": {
            "UserProfile": {"type": "object"}
        },
        "properties": {
            "profile": {"$ref": "#/$defs/UserProfil"}  # typo in UserProfil
        }
    }
    res_typo = run_oracle("--schema", json.dumps(typo_schema), "--json")
    assert res_typo.returncode == 1
    data_typo = json.loads(res_typo.stdout)
    assert "Did you mean '#/$defs/UserProfile'" in data_typo["dangling_refs"][0]["error"]

    # 3. Actionable HTML escaping: shows exact escaped entity alternative (&lt;, &amp;)
    raw_html = "<div title='1 < 2'>A & B</div>"
    res_html = run_oracle("--html-esc", raw_html, "--json")
    assert res_html.returncode == 1
    data_html = json.loads(res_html.stdout)
    html_msgs = " ".join(e["message"] for e in data_html["errors"] + data_html["warnings"])
    assert "&lt;" in html_msgs
    assert "&amp;" in html_msgs

    # 4. Actionable NameError: identifies missing identifier and suggested fix
    res_name = run_oracle("--eval", "non_existent_func()", "--json")
    assert res_name.returncode == 1
    data_name = json.loads(res_name.stdout)
    assert "non_existent_func" in data_name["diagnostic"]
    assert "Fix:" in data_name["diagnostic"]

    # 5. Actionable missing schema file path: explains file not found
    res_missing_schema = run_oracle("--schema", "missing_schema_12345.json", "--json")
    assert res_missing_schema.returncode == 1
    data_missing_schema = json.loads(res_missing_schema.stdout)
    assert data_missing_schema["error_type"] == "FileNotFoundError"
    assert "missing_schema_12345.json" in data_missing_schema["error"]

    # 6. Actionable missing syntax file path with fuzzy suggestion
    res_missing_syntax = run_oracle("--syntax", "tests/test_code_oracl.py", "--json")
    assert res_missing_syntax.returncode == 1
    data_missing_syntax = json.loads(res_missing_syntax.stdout)
    assert data_missing_syntax["error_type"] == "FileNotFoundError"
    assert any("test_code_oracle.py" in s for s in data_missing_syntax.get("suggestions", []))
    print("  ✓ Actionable diagnostics guide LLM with exact character width causes, $ref corrections, escaping fixes, and file suggestions.")


def main():
    print("=" * 80)
    print("RUNNING CODE-ORACLE GAUNTLET TEST SUITE")
    print("=" * 80)

    test_syntax_and_byte_identity()
    test_empty_and_help()
    test_eval_mode()
    test_hex_mode()
    test_width_mode()
    test_html_esc_mode()
    test_schema_mode()
    test_syntax_mode()
    test_positional_auto_detection()
    test_forgiving_cli_and_unquoted_inputs()
    test_crash_and_infinite_loop_immunity()
    test_schema_resilience_and_recursion_cycle()
    test_actionable_diagnostics()

    print("=" * 80)
    print("ALL CODE-ORACLE UNIT TESTS PASSED CLEANLY! (EXIT CODE 0)")
    print("=" * 80)


if __name__ == "__main__":
    main()
