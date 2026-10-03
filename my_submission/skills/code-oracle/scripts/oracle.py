#!/usr/bin/env python3
"""code-oracle: Multi-domain coding assistance oracle for SWE agents.

Provides deterministic diagnostics and inspection tools for domain nuances that
commonly cause subtle bugs or failed assertions in SWE benchmarks:
1. --eval <expr>: Safely evaluates a Python expression in the current environment
   with infinite loop timeout protection, full exception trapping, and actionable
   diagnostics for SyntaxError and NameError.
2. --hex <text>: Hex dump and escape sequence inspector. Decodes raw bytes and
   characters, highlights ANSI escapes, SGR parameters, OSC hyperlinks, and
   invisible control/zero-width characters (\r, \n, \t, \u200d, \ufe0f).
3. --width <text>: Calculates exact terminal cell display width for monospaced
   terminals (handling CJK East Asian Width W/F as 2 cells, ZWJ sequences,
   combining characters, ASCII as 1 cell) and explains which characters cause width mismatches.
4. --html-esc <snippet>: Inspects HTML/template strings. Verifies entity escaping
   (&lt;, &gt;, &amp;, quotes), tag matching (open/close tag balance), and warns if
   unescaped < or > exists inside script tags or attribute values.
5. --schema <file_or_json>: Inspects JSON Schema / OpenAPI schema structure.
   Checks $defs vs definitions, validates $ref pointer resolution (flags dangling
   references with exact corrected paths), checks anyOf with None/null, handles
   non-dict schemas, and protects against recursive $ref cycles.
6. --syntax <file>: Validates AST syntax (ast.parse) and checks that top-level
   module imports can be resolved without executing module side-effects.

Zero external dependencies (pure Python standard library).
"""

from __future__ import annotations

import argparse
import ast
import difflib
import html
from html.parser import HTMLParser
import importlib.util
import json
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import unicodedata
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

sys.dont_write_bytecode = True

# ANSI Escape Regex covering CSI, OSC, and standard 2-byte escape sequences
ANSI_RE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]|\].*?(?:\x07|\x1b\\))")

# HTML void elements that do not have closing tags
VOID_HTML_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}

# Standard JSON Schema data types
VALID_JSON_SCHEMA_TYPES = {
    "string", "number", "integer", "boolean", "array", "object", "null",
}


# ==============================================================================
# Helper Utilities
# ==============================================================================

def read_input_text(input_val: str) -> str:
    """If input_val is an existing file path, read its text, otherwise return input_val.
    
    Also decodes escaped literal backslashes if input appears to be shell-escaped
    (e.g., r'\\x1b[31m' -> actual ESC).
    """
    if not input_val:
        return ""
    try:
        p = pathlib.Path(input_val)
        if p.is_file():
            return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        pass

    # Unescape raw string sequences if user passed literal backslash sequences like \x1b or \u
    if "\\" in input_val:
        try:
            if any(esc in input_val for esc in (r"\x", r"\u", r"\n", r"\r", r"\t")):
                return input_val.encode("utf-8").decode("unicode_escape")
        except Exception:
            pass

    return input_val


def get_workspace_dir(explicit_ws: Optional[str] = None) -> pathlib.Path:
    """Discover workspace directory deterministically."""
    if explicit_ws:
        p = pathlib.Path(explicit_ws)
        if p.is_dir():
            return p.resolve()

    for env_var in ("SWEGEMMA_WORKSPACE", "WORKSPACE_DIR"):
        val = os.environ.get(env_var)
        if val:
            p = pathlib.Path(val)
            if p.is_dir():
                return p.resolve()

    ws_fixed = pathlib.Path("/workspace")
    if ws_fixed.is_dir():
        return ws_fixed.resolve()

    cur = pathlib.Path.cwd().resolve()
    for parent in [cur] + list(cur.parents):
        if (
            (parent / "tasks.jsonl").exists()
            or (parent / "my_submission").exists()
            or (parent / ".git").exists()
            or (parent / "pyproject.toml").exists()
            or (parent / "setup.py").exists()
        ):
            return parent

    return cur


def generate_snippet(
    source_lines: Sequence[str],
    lineno: int,
    column: int,
    context_lines: int = 2,
) -> str:
    """Generate a clean code snippet with line numbers and a visual caret pointer."""
    if not source_lines:
        return ""

    target_idx = max(0, min(len(source_lines) - 1, lineno - 1))
    start_idx = max(0, target_idx - context_lines)
    end_idx = min(len(source_lines), target_idx + context_lines + 1)

    gutter_width = max(len(str(end_idx)), 2)
    blank_gutter = " " * gutter_width

    output_lines: List[str] = []
    for idx in range(start_idx, end_idx):
        cur_line_num = idx + 1
        num_str = str(cur_line_num).rjust(gutter_width)
        line_content = source_lines[idx].rstrip("\r\n")

        if idx == target_idx:
            line_display = line_content.expandtabs(4)
            output_lines.append(f"> {num_str} | {line_display}")
            col = max(1, column)
            prefix = line_content[: col - 1].expandtabs(4)
            caret_indent = " " * len(prefix)
            output_lines.append(f"  {blank_gutter} | {caret_indent}^")
        else:
            line_display = line_content.expandtabs(4)
            output_lines.append(f"  {num_str} | {line_display}")

    return "\n".join(output_lines)


# ==============================================================================
# Mode 1: --eval <expr>
# ==============================================================================

class EvalTimeoutError(TimeoutError):
    """Raised when expression evaluation exceeds execution timeout limit."""
    pass


def _eval_alarm_handler(signum: int, frame: Any) -> None:
    raise EvalTimeoutError("Execution timed out (infinite loop or execution exceeded 5.0s limit).")


def run_eval(expr: str, as_json: bool = False) -> int:
    """Safely evaluates a Python expression or statement in the current environment."""
    if not expr or not expr.strip():
        diag = "No expression provided to --eval. Example: args: ['--eval', 'len([1, 2, 3])']"
        if as_json:
            print(json.dumps({"status": "error", "mode": "eval", "error": diag}, indent=2))
        else:
            print(f"✗ [eval-error] {diag}")
        return 1

    expr_clean = expr.strip()

    # Attempt to compile: try eval first (expression), fallback to exec (statements like loops/assignments)
    is_statement = False
    compiled: Any = None
    try:
        compiled = compile(expr_clean, "<eval>", "eval")
    except SyntaxError as syn_err:
        try:
            compiled = compile(expr_clean, "<eval>", "exec")
            is_statement = True
        except SyntaxError:
            # Genuine syntax error for both eval and exec modes
            snippet = ""
            if syn_err.text:
                snippet = generate_snippet(syn_err.text.splitlines(), syn_err.lineno or 1, syn_err.offset or 1)

            diag = (
                f"SyntaxError in expression: {syn_err.msg} (line {syn_err.lineno}, col {syn_err.offset}).\n"
                f"What is wrong: Python parser encountered invalid syntax near {repr(syn_err.text.strip()) if syn_err.text else 'token'}.\n"
                "Fix: Check for unbalanced parentheses, brackets, or unclosed string quotes. Ensure you passed a valid "
                "expression or statement."
            )
            if as_json:
                print(json.dumps({
                    "status": "error",
                    "mode": "eval",
                    "error_type": "SyntaxError",
                    "message": syn_err.msg,
                    "line": syn_err.lineno,
                    "column": syn_err.offset,
                    "diagnostic": diag,
                    "snippet": snippet,
                }, indent=2))
            else:
                print("=" * 80)
                print("✗ [code-oracle: eval] SyntaxError:")
                print(f"  Message: {syn_err.msg} (col {syn_err.offset})")
                if snippet:
                    print("  Snippet:")
                    for line in snippet.splitlines():
                        print(f"    {line}")
                print(f"\n  Fix: {diag}")
                print("=" * 80)
            return 1
        except (ValueError, RecursionError, MemoryError) as comp_err:
            err_type = type(comp_err).__name__
            diag = (
                f"{err_type} during compilation: {comp_err}.\n"
                "What is wrong: Python compiler encountered an internal limit or invalid character (e.g. null bytes, extreme nesting depth).\n"
                "Fix: Verify expression does not contain null bytes or excessive nesting depth."
            )
            if as_json:
                print(json.dumps({
                    "status": "error",
                    "mode": "eval",
                    "error_type": err_type,
                    "message": str(comp_err),
                    "diagnostic": diag,
                }, indent=2))
            else:
                print("=" * 80)
                print(f"✗ [code-oracle: eval] Compilation {err_type}: {comp_err}")
                print(f"  Fix: {diag}")
                print("=" * 80)
            return 1
    except (ValueError, RecursionError, MemoryError) as comp_err:
        err_type = type(comp_err).__name__
        diag = (
            f"{err_type} during compilation: {comp_err}.\n"
            "What is wrong: Python compiler encountered an internal limit or invalid character (e.g. null bytes, extreme nesting depth).\n"
            "Fix: Verify expression does not contain null bytes or excessive nesting depth."
        )
        if as_json:
            print(json.dumps({
                "status": "error",
                "mode": "eval",
                "error_type": err_type,
                "message": str(comp_err),
                "diagnostic": diag,
            }, indent=2))
        else:
            print("=" * 80)
            print(f"✗ [code-oracle: eval] Compilation {err_type}: {comp_err}")
            print(f"  Fix: {diag}")
            print("=" * 80)
        return 1

    # Prepare standard modules and safe evaluation environment
    eval_globals: Dict[str, Any] = {
        "__builtins__": sys.modules["builtins"].__dict__,
        "json": json,
        "re": re,
        "math": __import__("math"),
        "datetime": __import__("datetime"),
        "collections": __import__("collections"),
        "itertools": __import__("itertools"),
        "pathlib": pathlib,
        "unicodedata": unicodedata,
        "html": html,
        "sys": sys,
        "ast": ast,
    }
    eval_locals: Dict[str, Any] = {}

    # Set timer for timeout / infinite loop protection (5.0 seconds for heavy imports)
    timer_armed = False
    try:
        if hasattr(signal, "SIGALRM") and hasattr(signal, "setitimer"):
            signal.signal(signal.SIGALRM, _eval_alarm_handler)
            signal.setitimer(signal.ITIMER_REAL, 5.0)
            timer_armed = True
    except Exception:
        pass

    try:
        if is_statement:
            exec(compiled, eval_globals, eval_locals)
            new_vars = {k: v for k, v in eval_locals.items() if not k.startswith("__")}
            val = new_vars if new_vars else "Statements executed successfully (no return value)."
        else:
            val = eval(compiled, eval_globals, eval_locals)
    except BaseException as exc:
        exc_type = type(exc).__name__
        exc_msg = str(exc)

        # Construct highly actionable diagnostic for LLM
        if isinstance(exc, (EvalTimeoutError, TimeoutError)):
            exc_type = "TimeoutError"
            action_fix = (
                "Execution timed out. "
                "What is wrong: An infinite loop or long-running computation was detected "
                "(e.g. while True, unbounded loop, or recursive generator). "
                "Fix: Verify loop termination conditions and generator bounds."
            )
        elif isinstance(exc, NameError):
            missing_name = getattr(exc, "name", None)
            if not missing_name:
                m = re.search(r"'([^']+)'", exc_msg)
                if m:
                    missing_name = m.group(1)

            candidates = list(eval_globals.keys()) + dir(__builtins__)
            suggestion = ""
            if missing_name:
                close = difflib.get_close_matches(missing_name, candidates, n=1, cutoff=0.6)
                if close:
                    suggestion = f" Did you mean '{close[0]}'?"

            if missing_name:
                action_fix = (
                    f"NameError: Identifier '{missing_name}' is not defined.{suggestion} "
                    f"What is wrong: The variable or function '{missing_name}' does not exist in the evaluation scope. "
                    f"Fix: Define '{missing_name}' before referencing it, check for typos, or verify if it requires "
                    f"importing a module (e.g. math, sys, os, json)."
                )
            else:
                action_fix = (
                    f"NameError: {exc_msg}. "
                    "What is wrong: An identifier was referenced before being defined. "
                    "Fix: Check for misspelled variable or function names, or import the required module."
                )
        elif isinstance(exc, MemoryError):
            action_fix = (
                "MemoryError: Out of memory during expression evaluation. "
                "What is wrong: The expression attempted to allocate more memory than available. "
                "Fix: Reduce data structure size or use iterators/generators instead of large lists."
            )
        elif isinstance(exc, RecursionError):
            action_fix = (
                "RecursionError: Maximum recursion depth exceeded. "
                "What is wrong: Unbounded or excessively deep recursion was detected. "
                "Fix: Add or check recursive base cases to ensure recursion terminates."
            )
        elif isinstance(exc, ZeroDivisionError):
            action_fix = (
                "ZeroDivisionError: Division or modulo by zero. "
                "What is wrong: An arithmetic operation divided by zero. "
                "Fix: Add a check for zero before dividing or handle denominator == 0."
            )
        elif isinstance(exc, TypeError):
            action_fix = (
                f"TypeError: {exc_msg}. "
                "What is wrong: An invalid type or argument count was passed to an operation or function. "
                "Fix: Verify argument types and function signatures."
            )
        elif isinstance(exc, ValueError):
            action_fix = (
                f"ValueError: {exc_msg}. "
                "What is wrong: An invalid value was passed to a function or operation. "
                "Fix: Check argument formats, ranges, or numeric conversions."
            )
        elif isinstance(exc, KeyError):
            action_fix = (
                f"KeyError: {exc_msg}. "
                "What is wrong: The dictionary key does not exist. "
                "Fix: Check dictionary keys with .keys() or use .get() with a default value."
            )
        elif isinstance(exc, IndexError):
            action_fix = (
                f"IndexError: {exc_msg}. "
                "What is wrong: Sequence index out of range. "
                "Fix: Check sequence length with len() before indexing."
            )
        elif isinstance(exc, AttributeError):
            action_fix = (
                f"AttributeError: {exc_msg}. "
                "What is wrong: The requested attribute or method does not exist on this object. "
                "Fix: Check attribute names with dir() or check for typos."
            )
        elif isinstance(exc, SystemExit):
            action_fix = (
                "SystemExit: Expression attempted to exit the Python process. "
                "What is wrong: sys.exit() was called during evaluation. "
                "Fix: Do not call sys.exit() inside an evaluated expression."
            )
        else:
            action_fix = f"Runtime error during eval(): {exc_type}: {exc_msg}."

        if as_json:
            print(json.dumps({
                "status": "error",
                "mode": "eval",
                "error_type": exc_type,
                "message": exc_msg,
                "diagnostic": action_fix,
            }, indent=2))
        else:
            print("=" * 80)
            print(f"✗ [code-oracle: eval] Runtime {exc_type}:")
            print(f"  Message: {exc_msg}")
            print(f"  Fix:     {action_fix}")
            print("=" * 80)
        return 1
    finally:
        if timer_armed:
            try:
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, signal.SIG_DFL)
            except Exception:
                pass

    val_type = type(val).__name__
    val_repr = repr(val)
    val_str = str(val)

    val_len: Optional[int] = None
    try:
        val_len = len(val)  # type: ignore
    except TypeError:
        val_len = None

    if as_json:
        res = {
            "status": "ok",
            "mode": "eval",
            "expression": expr,
            "type": val_type,
            "repr": val_repr,
            "formatted": val_str,
            "len": val_len,
        }
        print(json.dumps(res, indent=2))
    else:
        print("=" * 80)
        print("✓ [code-oracle: eval] Evaluation Successful:")
        print(f"  Expression : {expr}")
        print(f"  Type       : {val_type}")
        print(f"  Repr       : {val_repr}")
        print(f"  Length     : {val_len if val_len is not None else 'N/A (not sized)'}")
        print(f"  Formatted  : {val_str}")
        print("=" * 80)

    return 0


# ==============================================================================
# Mode 2: --hex <text>
# ==============================================================================

SGR_CODES: Dict[str, str] = {
    "0": "Reset / Normal",
    "1": "Bold / Increased Intensity",
    "2": "Faint / Decreased Intensity",
    "3": "Italic",
    "4": "Underline",
    "7": "Reverse Video",
    "9": "Strikethrough",
    "22": "Normal Intensity (Not Bold/Faint)",
    "23": "Not Italic",
    "24": "Not Underlined",
    "27": "Not Reversed",
    "29": "Not Strikethrough",
    "30": "FG Black", "31": "FG Red", "32": "FG Green", "33": "FG Yellow",
    "34": "FG Blue", "35": "FG Magenta", "36": "FG Cyan", "37": "FG White",
    "39": "FG Default",
    "40": "BG Black", "41": "BG Red", "42": "BG Green", "43": "BG Yellow",
    "44": "BG Blue", "45": "BG Magenta", "46": "BG Cyan", "47": "BG White",
    "49": "BG Default",
    "90": "FG Bright Black (Gray)", "91": "FG Bright Red", "92": "FG Bright Green",
    "93": "FG Bright Yellow", "94": "FG Bright Blue", "95": "FG Bright Magenta",
    "96": "FG Bright Cyan", "97": "FG Bright White",
    "100": "BG Bright Black", "101": "BG Bright Red", "102": "BG Bright Green",
    "103": "BG Bright Yellow", "104": "BG Bright Blue", "105": "BG Bright Magenta",
    "106": "BG Bright Cyan", "107": "BG Bright White",
}


def parse_sgr_params(params_str: str) -> List[str]:
    """Parse SGR parameter string into human-readable descriptions."""
    if not params_str:
        return ["Reset / Normal (default 0)"]
    tokens = params_str.split(";")
    res: List[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in ("38", "48") and i + 1 < len(tokens):
            target = "FG" if t == "38" else "BG"
            mode = tokens[i + 1]
            if mode == "5" and i + 2 < len(tokens):
                color_idx = tokens[i + 2]
                res.append(f"{target} 256-color (#{color_idx})")
                i += 3
                continue
            elif mode == "2" and i + 4 < len(tokens):
                r, g, b = tokens[i + 2], tokens[i + 3], tokens[i + 4]
                res.append(f"{target} TrueColor RGB({r}, {g}, {b})")
                i += 5
                continue
        desc = SGR_CODES.get(t, f"Code {t}")
        res.append(desc)
        i += 1
    return res


def run_hex(input_val: str, as_json: bool = False) -> int:
    """Hex dump and escape sequence inspector."""
    stripped_val = input_val.strip()
    if stripped_val and "\n" not in stripped_val and len(stripped_val) < 256:
        p = pathlib.Path(stripped_val)
        if (p.suffix in (".txt", ".log", ".dat", ".bin", ".out", ".diff", ".patch", ".raw") or "/" in stripped_val) and not p.exists():
            err_msg = f"File '{stripped_val}' not found."
            diag = (
                f"File '{stripped_val}' does not exist on disk.\n"
                "What is wrong: Specified file path could not be located.\n"
                "Fix: Check file path relative to workspace or pass text directly: args: ['--hex', '\\x1b[31mText\\x1b[0m']"
            )
            if as_json:
                print(json.dumps({"status": "error", "mode": "hex", "error_type": "FileNotFoundError", "error": err_msg, "diagnostic": diag}, indent=2))
            else:
                print("=" * 80)
                print(f"✗ [code-oracle: hex] {err_msg}")
                print(f"  {diag}")
                print("=" * 80)
            return 1

    text = read_input_text(input_val)
    raw_bytes = text.encode("utf-8")

    # 1. Generate Hex Dump
    hex_dump_lines: List[str] = []
    for offset in range(0, len(raw_bytes), 16):
        chunk = raw_bytes[offset : offset + 16]
        hex_parts: List[str] = [f"{b:02x}" for b in chunk]
        first_half = " ".join(hex_parts[:8])
        second_half = " ".join(hex_parts[8:])
        hex_col = f"{first_half:<23}  {second_half:<23}".rstrip()

        ascii_col = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        hex_dump_lines.append(f"{offset:08x}  {hex_col:<48}  |{ascii_col}|")

    # 2. Inspect Escape Sequences, Invisible Characters, and Controls
    ansi_sequences: List[Dict[str, Any]] = []
    for match in ANSI_RE.finditer(text):
        seq = match.group(0)
        start, end = match.span()
        kind = "Unknown"
        details: List[str] = []
        if seq.startswith("\x1b["):
            kind = "CSI (Control Sequence Introducer)"
            terminator = seq[-1]
            params = seq[2:-1]
            if terminator == "m":
                kind = "CSI SGR (Select Graphic Rendition)"
                details = parse_sgr_params(params)
            elif terminator == "H":
                kind = "CSI Cursor Position"
            elif terminator == "J":
                kind = "CSI Erase Display"
            elif terminator == "K":
                kind = "CSI Erase in Line"
        elif seq.startswith("\x1b]"):
            kind = "OSC (Operating System Command)"
            if seq.startswith("\x1b]8;;"):
                kind = "OSC 8 Hyperlink"
                url = seq[5:].rstrip("\x07\x1b\\")
                details = [f"Hyperlink Target: {url}"]

        ansi_sequences.append({
            "raw": repr(seq),
            "start": start,
            "end": end,
            "kind": kind,
            "details": details,
        })

    # Inspect invisible and special control characters
    special_chars: List[Dict[str, Any]] = []
    for idx, ch in enumerate(text):
        cp = ord(ch)
        cat = unicodedata.category(ch)
        name = unicodedata.name(ch, "<unnamed>")

        is_special = False
        note = ""

        if ch == "\r":
            is_special = True
            is_followed_by_n = (idx + 1 < len(text) and text[idx + 1] == "\n")
            note = "Carriage Return (CR)" + (" [CRLF pair]" if is_followed_by_n else " [Lone CR - can overwrite line!]")
        elif ch == "\n":
            is_special = True
            note = "Line Feed (LF)"
        elif ch == "\t":
            is_special = True
            note = "Horizontal Tab"
        elif ch == "\u200b":
            is_special = True
            note = "Zero-Width Space (invisible)"
        elif ch == "\u200c":
            is_special = True
            note = "Zero-Width Non-Joiner (ZWNJ)"
        elif ch == "\u200d":
            is_special = True
            note = "Zero-Width Joiner (ZWJ - joins emojis/glyphs)"
        elif ch == "\ufe0e":
            is_special = True
            note = "Variation Selector-15 (text presentation)"
        elif ch == "\ufe0f":
            is_special = True
            note = "Variation Selector-16 (emoji presentation)"
        elif ch == "\ufeff":
            is_special = True
            note = "Zero-Width No-Break Space / Byte Order Mark (BOM)"
        elif ch in ("\u200e", "\u200f"):
            is_special = True
            note = "BiDi Directional Mark (LRM/RLM)"
        elif cat.startswith("C") and cp not in (9, 10, 13):
            is_special = True
            note = f"Control / Format character ({cat})"

        if is_special:
            special_chars.append({
                "index": idx,
                "char": repr(ch),
                "codepoint": f"U+{cp:04X}",
                "name": name,
                "category": cat,
                "note": note,
            })

    # Diagnostics
    diagnostics: List[str] = []
    has_sgr = any("SGR" in s["kind"] for s in ansi_sequences)
    has_reset = any("0" in s["raw"] or "Reset" in " ".join(s["details"]) for s in ansi_sequences)
    if has_sgr and not has_reset:
        diagnostics.append(
            "Unclosed ANSI sequence detected: Formatting enabled without a reset code (\\x1b[0m). "
            "Colors or styles will bleed into subsequent terminal output or test runners."
        )

    lone_cr = [sc for sc in special_chars if "Lone CR" in sc["note"]]
    if lone_cr:
        diagnostics.append(
            f"Detected {len(lone_cr)} lone Carriage Return (\\r) character(s) without \\n. "
            "In terminals, lone \\r moves the cursor to column 0 and overwrites previous text."
        )

    zw_chars = [sc for sc in special_chars if "Zero-Width" in sc["note"]]
    if zw_chars:
        diagnostics.append(
            f"Detected {len(zw_chars)} invisible zero-width character(s) (e.g. {zw_chars[0]['codepoint']}). "
            "These characters are invisible to human inspection but will cause str == expected or len() checks to fail."
        )

    if as_json:
        out = {
            "status": "ok",
            "mode": "hex",
            "total_bytes": len(raw_bytes),
            "total_chars": len(text),
            "hex_dump": hex_dump_lines,
            "ansi_sequences": ansi_sequences,
            "special_characters": special_chars,
            "diagnostics": diagnostics,
        }
        print(json.dumps(out, indent=2))
    else:
        print("=" * 80)
        print("✓ [code-oracle: hex] Hex Dump & Escape Sequence Inspection:")
        print(f"  Total Bytes : {len(raw_bytes)} | Total Characters: {len(text)}")
        print("\n--- HEX DUMP ---")
        for line in hex_dump_lines[:64]:
            print(line)
        if len(hex_dump_lines) > 64:
            print(f"  ... and {len(hex_dump_lines) - 64} more line(s) ({len(raw_bytes) - 1024} bytes; pass --json to view full dump)")

        if ansi_sequences:
            print(f"\n--- ANSI ESCAPE SEQUENCES ({len(ansi_sequences)} found) ---")
            for seq in ansi_sequences:
                det = f" -> {', '.join(seq['details'])}" if seq["details"] else ""
                print(f"  [{seq['start']}:{seq['end']}] {seq['kind']}: {seq['raw']}{det}")

        if special_chars:
            print(f"\n--- INVISIBLE & CONTROL CHARACTERS ({len(special_chars)} found) ---")
            for sc in special_chars:
                print(f"  Index {sc['index']:<4} | {sc['codepoint']} | {sc['name']:<25} | {sc['note']}")

        if diagnostics:
            print("\n--- ACTIONABLE DIAGNOSTICS ---")
            for diag in diagnostics:
                print(f"  ⚠ {diag}")

        print("=" * 80)

    return 0


# ==============================================================================
# Mode 3: --width <text>
# ==============================================================================

def get_char_display_width(ch: str) -> int:
    """Calculate monospaced cell display width of a single character."""
    o = ord(ch)
    cat = unicodedata.category(ch)

    # Combining characters and format marks occupy 0 terminal cells
    if cat in ("Mn", "Me", "Mc", "Cf", "Cc"):
        return 0

    # Skin tone modifiers (U+1F3FB - U+1F3FF) combine with previous emoji
    if 0x1F3FB <= o <= 0x1F3FF:
        return 0

    # East Asian Width Fullwidth (F) and Wide (W) occupy 2 cells
    ea = unicodedata.east_asian_width(ch)
    if ea in ("W", "F"):
        return 2

    # Common emoji ranges occupy 2 cells in monospaced terminal emulators
    if (0x1F300 <= o <= 0x1FAFF) or (0x2600 <= o <= 0x27BF):
        return 2

    return 1


def calculate_terminal_cells(text: str) -> Tuple[int, List[Dict[str, Any]]]:
    """Calculate exact monospaced terminal columns and character-by-character breakdown."""
    clean_text = ANSI_RE.sub("", text)

    breakdown: List[Dict[str, Any]] = []
    total_width = 0
    i = 0
    n = len(clean_text)

    while i < n:
        ch = clean_text[i]
        o = ord(ch)
        cat = unicodedata.category(ch)
        ea = unicodedata.east_asian_width(ch)
        name = unicodedata.name(ch, "<unnamed>")

        # Handle ZWJ sequence: if current char is ZWJ, it and following emoji contribute 0 extra width
        if ch == "\u200d":
            breakdown.append({
                "char": repr(ch),
                "codepoint": f"U+{o:04X}",
                "name": name,
                "category": cat,
                "ea_width": ea,
                "cell_width": 0,
                "note": "Zero-Width Joiner (joins with adjacent glyph)",
            })
            i += 1
            if i < n:
                next_ch = clean_text[i]
                next_o = ord(next_ch)
                breakdown.append({
                    "char": repr(next_ch),
                    "codepoint": f"U+{next_o:04X}",
                    "name": unicodedata.name(next_ch, "<unnamed>"),
                    "category": unicodedata.category(next_ch),
                    "ea_width": unicodedata.east_asian_width(next_ch),
                    "cell_width": 0,
                    "note": "Joined emoji sequence component",
                })
                i += 1
            continue

        base_width = get_char_display_width(ch)

        # Check if immediately followed by emoji presentation selector \ufe0f
        if i + 1 < n and clean_text[i + 1] == "\ufe0f":
            effective_width = max(base_width, 2)
            total_width += effective_width
            breakdown.append({
                "char": repr(ch),
                "codepoint": f"U+{o:04X}",
                "name": name,
                "category": cat,
                "ea_width": ea,
                "cell_width": effective_width,
                "note": "Base symbol (presented as emoji width 2 via \\ufe0f)",
            })
            i += 1
            vs_o = ord(clean_text[i])
            breakdown.append({
                "char": repr(clean_text[i]),
                "codepoint": f"U+{vs_o:04X}",
                "name": unicodedata.name(clean_text[i], "<unnamed>"),
                "category": unicodedata.category(clean_text[i]),
                "ea_width": unicodedata.east_asian_width(clean_text[i]),
                "cell_width": 0,
                "note": "Variation Selector-16 (emoji presentation)",
            })
            i += 1
            continue

        total_width += base_width
        breakdown.append({
            "char": repr(ch),
            "codepoint": f"U+{o:04X}",
            "name": name,
            "category": cat,
            "ea_width": ea,
            "cell_width": base_width,
            "note": "Wide cell" if base_width == 2 else ("Zero width" if base_width == 0 else "Normal cell"),
        })
        i += 1

    return total_width, breakdown


def run_width(input_val: str, as_json: bool = False) -> int:
    """Calculates exact terminal cell display width for monospaced terminals."""
    text = read_input_text(input_val)

    code_points = len(text)
    utf8_bytes = len(text.encode("utf-8"))
    utf16_units = len(text.encode("utf-16-le")) // 2
    columns, breakdown = calculate_terminal_cells(text)

    # Actionable character-level diagnostics if columns != code_points
    diagnostics: List[str] = []
    char_explanations: List[str] = []
    if columns != code_points:
        reasons: List[str] = []
        wide_items = [b for b in breakdown if b["cell_width"] == 2]
        zero_items = [b for b in breakdown if b["cell_width"] == 0]
        ansi_matches = list(ANSI_RE.finditer(text))

        if wide_items:
            reasons.append(f"{len(wide_items)} wide character(s) (CJK/emoji = 2 cells)")
            for item in wide_items[:10]:
                char_explanations.append(
                    f"Character {item['char']} ({item['codepoint']}) occupies 2 terminal cells, whereas len() is 1."
                )
            if len(wide_items) > 10:
                char_explanations.append(f"... and {len(wide_items) - 10} more wide character(s)")

        if zero_items:
            reasons.append(f"{len(zero_items)} zero-width / combining / ZWJ character(s) (0 cells)")
            for item in zero_items[:10]:
                char_explanations.append(
                    f"Character {item['char']} ({item['codepoint']}) occupies 0 terminal cells, whereas len() is 1."
                )
            if len(zero_items) > 10:
                char_explanations.append(f"... and {len(zero_items) - 10} more zero-width character(s)")

        if ansi_matches:
            reasons.append(f"{len(ansi_matches)} ANSI escape sequence(s) (stripped in display = 0 cells)")
            for m in ansi_matches[:5]:
                esc_str = m.group(0)
                char_explanations.append(
                    f"ANSI escape sequence {repr(esc_str)} occupies 0 terminal cells, whereas len() is {len(esc_str)}."
                )

        diagnostics.append(
            f"Terminal display columns ({columns}) differs from Python len() ({code_points}) due to: "
            + "; ".join(reasons) + "."
        )
        diagnostics.extend(char_explanations)
        diagnostics.append(
            "Actionable Fix: In CLI/TUI tools (Rich, prompt_toolkit, table formatters), DO NOT use "
            "len(), str.ljust(), or str.rjust() to align columns. Use cell width (e.g. rich.cells.cell_len() "
            "or wcwidth) to prevent ragged borders and table misalignment."
        )

    if as_json:
        out = {
            "status": "ok",
            "mode": "width",
            "terminal_columns": columns,
            "len_code_points": code_points,
            "utf8_bytes": utf8_bytes,
            "utf16_units": utf16_units,
            "breakdown": breakdown,
            "diagnostics": diagnostics,
        }
        print(json.dumps(out, indent=2))
    else:
        print("=" * 80)
        print("✓ [code-oracle: width] Terminal Cell Display Width:")
        print(f"  Terminal Columns : {columns}")
        print(f"  len(text)        : {code_points} (Unicode code points)")
        print(f"  UTF-8 Bytes      : {utf8_bytes}")
        print(f"  UTF-16 Units     : {utf16_units}")

        if breakdown:
            print("\n--- CHARACTER / GLYPH BREAKDOWN ---")
            print(f"  {'Char':<8} {'CodePoint':<10} {'Width':<7} {'EA':<4} {'Cat':<5} {'Name / Note'}")
            print("  " + "-" * 74)
            for item in breakdown[:50]:
                print(f"  {item['char']:<8} {item['codepoint']:<10} {item['cell_width']:<7} {item['ea_width']:<4} {item['category']:<5} {item['name']} ({item['note']})")
            if len(breakdown) > 50:
                print(f"  ... and {len(breakdown) - 50} more character(s)")

        if char_explanations:
            print("\n--- CHARACTER-LEVEL CELL WIDTH EXPLANATIONS ---")
            for exp in char_explanations:
                print(f"  • {exp}")

        if diagnostics:
            print("\n--- ACTIONABLE DIAGNOSTICS ---")
            for diag in diagnostics:
                print(f"  ℹ {diag}")

        print("=" * 80)

    return 0


# ==============================================================================
# Mode 4: --html-esc <snippet>
# ==============================================================================

class HTMLStructureParser(HTMLParser):
    """HTML Parser that checks tag nesting balance and attribute escaping."""

    def __init__(self):
        super().__init__()
        self.tag_stack: List[Tuple[str, int, int]] = []
        self.errors: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
        self.inside_script: bool = False
        self.inside_style: bool = False

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        t = tag.lower()
        lineno, offset = self.getpos()

        # Check attribute values for unescaped characters
        for attr_name, attr_val in attrs:
            if attr_val is not None:
                if "<" in attr_val:
                    self.warnings.append({
                        "line": lineno,
                        "column": offset,
                        "kind": "UnescapedAngleBracketInAttribute",
                        "message": f"Attribute '{attr_name}' contains raw '<': {attr_val!r}. "
                                   "Fix: Replace '<' with '&lt;' in attribute values.",
                    })
                if ">" in attr_val:
                    self.warnings.append({
                        "line": lineno,
                        "column": offset,
                        "kind": "UnescapedAngleBracketInAttribute",
                        "message": f"Attribute '{attr_name}' contains raw '>': {attr_val!r}. "
                                   "Fix: Replace '>' with '&gt;' in attribute values.",
                    })
                # Check for raw ampersands not part of a valid HTML entity in attributes
                raw_amp = re.findall(r"&(?!([a-zA-Z][a-zA-Z0-9]*|#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6});)", attr_val)
                if raw_amp:
                    self.warnings.append({
                        "line": lineno,
                        "column": offset,
                        "kind": "UnescapedAmpersandInAttribute",
                        "message": f"Attribute '{attr_name}' contains unescaped '&': {attr_val!r}. "
                                   "Fix: Replace raw '&' with '&amp;'.",
                    })

        if t == "script":
            self.inside_script = True
        elif t == "style":
            self.inside_style = True

        if t not in VOID_HTML_TAGS:
            self.tag_stack.append((t, lineno, offset))

    def handle_endtag(self, tag: str):
        t = tag.lower()
        lineno, offset = self.getpos()

        if t == "script":
            self.inside_script = False
        elif t == "style":
            self.inside_style = False

        if t in VOID_HTML_TAGS:
            self.warnings.append({
                "line": lineno,
                "column": offset,
                "kind": "VoidTagClosed",
                "message": f"Void element <{t}> should not have a closing </{t}> tag.",
            })
            return

        if not self.tag_stack:
            self.errors.append({
                "line": lineno,
                "column": offset,
                "kind": "UnmatchedClosingTag",
                "message": f"Found closing tag </{t}> with no corresponding opening tag. Fix: Remove extra </{t}> or add opening <{t}>.",
            })
            return

        top_tag, top_line, top_col = self.tag_stack[-1]
        if top_tag == t:
            self.tag_stack.pop()
        else:
            stack_tags = [item[0] for item in self.tag_stack]
            if t in stack_tags:
                idx = len(stack_tags) - 1 - stack_tags[::-1].index(t)
                unclosed = self.tag_stack[idx + 1 :]
                unclosed_names = ", ".join(f"<{item[0]} line {item[1]}>" for item in unclosed)
                self.errors.append({
                    "line": lineno,
                    "column": offset,
                    "kind": "MisnestedTag",
                    "message": f"Closing tag </{t}> closes element out of order. Unclosed inner elements: {unclosed_names}. Fix: Close inner elements first.",
                })
                self.tag_stack = self.tag_stack[:idx]
            else:
                self.errors.append({
                    "line": lineno,
                    "column": offset,
                    "kind": "UnmatchedClosingTag",
                    "message": f"Closing tag </{t}> does not match current open element <{top_tag} line {top_line}>. Fix: Ensure tags are properly closed.",
                })

    def handle_data(self, data: str):
        lineno, offset = self.getpos()
        if self.inside_script:
            if "<" in data or ">" in data:
                ch = "<" if "<" in data else ">"
                esc_ch = r"\u003c" if ch == "<" else r"\u003e"
                self.warnings.append({
                    "line": lineno,
                    "column": offset,
                    "kind": "RawScriptAngleBrackets",
                    "message": f"Raw '{ch}' detected inside <script> block. "
                               f"Fix: Escape as '{esc_ch}' in templates (Swagger UI/Redoc) "
                               "to prevent premature script termination or XSS.",
                })


def run_html_esc(input_val: str, as_json: bool = False) -> int:
    """Inspects HTML/template strings for entity escaping and tag balance."""
    raw_html = read_input_text(input_val)
    lines = raw_html.splitlines()

    parser = HTMLStructureParser()
    try:
        parser.feed(raw_html)
        parser.close()
    except BaseException as exc:
        parser.errors.append({
            "line": 1,
            "column": 1,
            "kind": "ParserFailure",
            "message": f"HTML parser encountered exception: {exc}. Fix: Check for unbalanced quotes or malformed markup.",
        })

    # Check for remaining unclosed tags at EOF
    if parser.tag_stack:
        for tag, line, col in parser.tag_stack:
            parser.errors.append({
                "line": line,
                "column": col,
                "kind": "UnclosedTag",
                "message": f"Tag <{tag}> opened at line {line} col {col} was never closed before end of document. "
                           f"Fix: Add closing tag </{tag}>.",
            })

    # Scan for raw unescaped ampersands in text (outside valid HTML entities)
    raw_amp_pattern = re.compile(r"&(?!([a-zA-Z][a-zA-Z0-9]*|#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6});)")
    for line_idx, line_str in enumerate(lines, 1):
        for m in raw_amp_pattern.finditer(line_str):
            col = m.start() + 1
            snippet = generate_snippet(lines, line_idx, col, context_lines=1)
            parser.errors.append({
                "line": line_idx,
                "column": col,
                "kind": "UnescapedAmpersand",
                "message": f"Unescaped '&' found at line {line_idx} col {col}. "
                           "Fix: Replace '&' with '&amp;' or use html.escape().",
                "snippet": snippet,
            })

    status_passed = len(parser.errors) == 0

    if as_json:
        out = {
            "status": "passed" if status_passed else "failed",
            "mode": "html-esc",
            "errors": parser.errors,
            "warnings": parser.warnings,
            "total_errors": len(parser.errors),
            "total_warnings": len(parser.warnings),
        }
        print(json.dumps(out, indent=2))
    else:
        print("=" * 80)
        if status_passed and not parser.warnings:
            print("✓ [code-oracle: html-esc] HTML validation clean: all tags balanced & entities escaped.")
        else:
            header = "✗ [code-oracle: html-esc] HTML issues detected:" if not status_passed else "⚠ [code-oracle: html-esc] HTML warnings:"
            print(header)
            # Cap displayed errors at 25 items to prevent flooding on giant files
            for err in parser.errors[:25]:
                print(f"\n  [ERROR] {err['kind']} (line {err['line']}, col {err['column']}):")
                print(f"    {err['message']}")
                if "snippet" in err and err["snippet"]:
                    for s_line in err["snippet"].splitlines():
                        print(f"      {s_line}")
            if len(parser.errors) > 25:
                print(f"\n  ... and {len(parser.errors) - 25} more error(s)")

            for warn in parser.warnings[:25]:
                print(f"\n  [WARN] {warn['kind']} (line {warn['line']}, col {warn['column']}):")
                print(f"    {warn['message']}")
            if len(parser.warnings) > 25:
                print(f"\n  ... and {len(parser.warnings) - 25} more warning(s)")

            print("\nActionable Fixes for SWE Agent:")
            print("  1. Ensure every non-void opening tag has a matching closing tag.")
            print("  2. Replace unescaped '&' with '&amp;' and '<' with '&lt;'.")
            print("  3. Inside script/JSON templates (Swagger UI / Redoc), escape '<' as '\\u003c'.")
        print("=" * 80)

    return 0 if status_passed else 1


# ==============================================================================
# Mode 5: --schema <file_or_json>
# ==============================================================================

def resolve_json_pointer(root: Any, pointer: str) -> Tuple[bool, Any, str]:
    """Resolve a local JSON Pointer against the root document."""
    if not pointer.startswith("#"):
        return False, None, f"Non-local pointer '{pointer}' (external references not resolvable offline)"

    if pointer in ("#", "#/"):
        return True, root, ""

    if not pointer.startswith("#/"):
        return False, None, f"Malformed pointer '{pointer}' (must start with '#/')"

    tokens = pointer[2:].split("/")
    curr = root
    traversed: List[str] = ["#"]

    for token in tokens:
        key = token.replace("~1", "/").replace("~0", "~")
        if isinstance(curr, dict):
            if key in curr:
                curr = curr[key]
                traversed.append(key)
            else:
                curr_path = "/".join(traversed)
                available = ", ".join(repr(k) for k in list(curr.keys())[:10])
                return False, None, f"Key '{key}' not found at '{curr_path}'. Available keys: [{available}]"
        elif isinstance(curr, list):
            if key.isdigit() and int(key) < len(curr):
                curr = curr[int(key)]
                traversed.append(key)
            else:
                curr_path = "/".join(traversed)
                return False, None, f"Index '{key}' out of range at '{curr_path}' (length {len(curr)})"
        else:
            curr_path = "/".join(traversed)
            return False, None, f"Cannot traverse into primitive {type(curr).__name__} at '{curr_path}'"

    return True, curr, ""


def find_all_definition_targets(root: Any) -> Dict[str, str]:
    """Find all declared definition target names and their canonical pointer paths."""
    targets: Dict[str, str] = {}
    if not isinstance(root, dict):
        return targets

    if "$defs" in root and isinstance(root["$defs"], dict):
        for name in root["$defs"].keys():
            targets[name] = f"#/$defs/{name}"

    if "definitions" in root and isinstance(root["definitions"], dict):
        for name in root["definitions"].keys():
            targets[name] = f"#/definitions/{name}"

    if "components" in root and isinstance(root["components"], dict):
        schemas = root["components"].get("schemas")
        if isinstance(schemas, dict):
            for name in schemas.keys():
                targets[name] = f"#/components/schemas/{name}"

    return targets


def inspect_schema_tree(root: Any) -> Dict[str, Any]:
    """Recursively inspect JSON Schema / OpenAPI structure with recursion cycle protection."""
    all_refs: List[Dict[str, Any]] = []
    dangling_refs: List[Dict[str, Any]] = []
    dialect_warnings: List[str] = []
    anyof_issues: List[Dict[str, Any]] = []
    type_health_issues: List[Dict[str, Any]] = []

    has_defs = "$defs" in root if isinstance(root, dict) else False
    has_definitions = "definitions" in root if isinstance(root, dict) else False
    openapi_version = root.get("openapi", "") if isinstance(root, dict) else ""
    json_schema_draft = root.get("$schema", "") if isinstance(root, dict) else ""

    if has_defs and has_definitions:
        dialect_warnings.append(
            "Schema root defines BOTH '$defs' and 'definitions'. Standardize on '$defs' (OpenAPI 3.1 / JSON Schema 2020-12) "
            "or 'definitions' (OpenAPI 3.0 / Draft 7) to prevent reference resolution ambiguity."
        )

    if openapi_version.startswith("3.0") and has_defs:
        dialect_warnings.append(
            f"OpenAPI version is {openapi_version} but uses '$defs'. OpenAPI 3.0 uses 'components/schemas' or 'definitions'. "
            "Pydantic v2 schemas use '$defs' by default; ensure FastAPI / OpenAPI generator adapts dialect."
        )
    elif openapi_version.startswith("3.1") and has_definitions and not has_defs:
        dialect_warnings.append(
            f"OpenAPI version is {openapi_version} (OpenAPI 3.1) but uses legacy 'definitions' instead of '$defs'."
        )

    # Collect all available definition targets to provide exact corrected reference paths
    known_targets = find_all_definition_targets(root)

    # Cycle protection tracking object IDs; iterative stack avoids RecursionError
    seen_ids: Set[int] = set()
    stack: List[Tuple[Any, str]] = [(root, "#")]

    while stack:
        obj, path = stack.pop()
        if id(obj) in seen_ids:
            continue
        seen_ids.add(id(obj))

        if isinstance(obj, dict):
            # Check $ref
            if "$ref" in obj and isinstance(obj["$ref"], str):
                ref_val = obj["$ref"]
                all_refs.append({"location": path, "target": ref_val})
                ok, _, err_msg = resolve_json_pointer(root, ref_val)
                if not ok:
                    # Provide exact corrected reference path
                    target_name = ref_val.rsplit("/", 1)[-1] if "/" in ref_val else ref_val.lstrip("#")
                    hint = ""
                    if target_name in known_targets:
                        correct_path = known_targets[target_name]
                        hint = f" Did you mean '{correct_path}'? Target is defined at '{correct_path}'."
                    else:
                        # Case-insensitive or closest match
                        lower_targets = {k.lower(): v for k, v in known_targets.items()}
                        if target_name.lower() in lower_targets:
                            correct_path = lower_targets[target_name.lower()]
                            hint = f" Did you mean '{correct_path}' (case mismatch)?"
                        elif known_targets:
                            close = difflib.get_close_matches(target_name, list(known_targets.keys()), n=1, cutoff=0.5)
                            if close:
                                correct_path = known_targets[close[0]]
                                hint = f" Did you mean '{correct_path}' (closest match)?"

                    dangling_refs.append({
                        "location": path,
                        "target": ref_val,
                        "error": err_msg + hint,
                    })

            # Check anyOf
            if "anyOf" in obj and isinstance(obj["anyOf"], list):
                has_null_type = False
                has_string_none = False
                for item in obj["anyOf"]:
                    if isinstance(item, dict):
                        item_type = item.get("type")
                        if item_type == "null":
                            has_null_type = True
                        elif item_type == "None" or (item_type is None and "None" in str(item)):
                            has_string_none = True

                if has_string_none:
                    anyof_issues.append({
                        "location": path,
                        "message": "anyOf contains 'None' as type or literal. In JSON Schema, nullability MUST be {'type': 'null'}.",
                    })

                if obj.get("nullable") is True and has_null_type:
                    anyof_issues.append({
                        "location": path,
                        "message": "Schema defines both 'nullable: true' and anyOf: [{'type': 'null'}]. "
                                   "OpenAPI 3.0 uses 'nullable: true'; OpenAPI 3.1 uses 'type: null'. Combining both is redundant/conflicting.",
                    })

            # Check type validity
            if "type" in obj:
                t_val = obj["type"]
                if isinstance(t_val, str):
                    if t_val not in VALID_JSON_SCHEMA_TYPES:
                        type_health_issues.append({
                            "location": path,
                            "invalid_type": t_val,
                            "message": f"Invalid type '{t_val}'. Must be one of {sorted(VALID_JSON_SCHEMA_TYPES)}. "
                                       "Check for Python type leaks (e.g. 'str' -> 'string', 'int' -> 'integer', 'dict' -> 'object').",
                        })
                elif isinstance(t_val, list):
                    for sub_t in t_val:
                        if sub_t not in VALID_JSON_SCHEMA_TYPES:
                            type_health_issues.append({
                                "location": path,
                                "invalid_type": sub_t,
                                "message": f"Invalid type '{sub_t}' in type union array. Must be one of {sorted(VALID_JSON_SCHEMA_TYPES)}.",
                            })

            # Check required list vs properties
            if "required" in obj and isinstance(obj["required"], list) and "properties" in obj and isinstance(obj["properties"], dict):
                props = set(obj["properties"].keys())
                for req in obj["required"]:
                    if isinstance(req, str) and req not in props:
                        type_health_issues.append({
                            "location": path,
                            "message": f"Property '{req}' listed in 'required' is not defined in 'properties'.",
                        })

            # Push children to stack (reversed to preserve document order)
            for k, v in reversed(list(obj.items())):
                stack.append((v, f"{path}/{k}"))

        elif isinstance(obj, list):
            for idx in reversed(range(len(obj))):
                stack.append((obj[idx], f"{path}/{idx}"))

    return {
        "openapi_version": openapi_version,
        "json_schema_draft": json_schema_draft,
        "definitions_container": "$defs" if has_defs else ("definitions" if has_definitions else "none"),
        "total_refs": len(all_refs),
        "dangling_refs": dangling_refs,
        "dialect_warnings": dialect_warnings,
        "anyof_issues": anyof_issues,
        "type_health_issues": type_health_issues,
    }


def run_schema(input_val: str, as_json: bool = False) -> int:
    """Inspects JSON Schema / OpenAPI schema structure."""
    stripped = input_val.strip()
    if stripped and not stripped.startswith(("{", "[")) and (stripped.endswith((".json", ".yaml", ".yml")) or "/" in stripped):
        p = pathlib.Path(stripped)
        if not p.is_file():
            diag = (
                f"File '{stripped}' not found.\n"
                "What is wrong: The specified schema file does not exist on disk.\n"
                "Fix: Check file path relative to workspace or pass inline JSON: args: ['--schema', '{\"type\": \"object\"}']"
            )
            if as_json:
                print(json.dumps({"status": "error", "mode": "schema", "error_type": "FileNotFoundError", "error": f"File '{stripped}' not found.", "diagnostic": diag}, indent=2))
            else:
                print("=" * 80)
                print(f"✗ [code-oracle: schema] File '{stripped}' not found.")
                print(f"  {diag}")
                print("=" * 80)
            return 1

    text = read_input_text(input_val)
    if not text.strip():
        diag = "No schema content provided to --schema."
        if as_json:
            print(json.dumps({"status": "error", "mode": "schema", "error": diag}, indent=2))
        else:
            print(f"✗ [schema-error] {diag}")
        return 1

    try:
        data = json.loads(text)
    except json.JSONDecodeError as jde:
        snippet = generate_snippet(text.splitlines(), jde.lineno, jde.colno, context_lines=2)
        diag = f"Invalid JSON syntax: {jde.msg} (line {jde.lineno}, col {jde.colno})."
        if as_json:
            print(json.dumps({
                "status": "error",
                "mode": "schema",
                "error_type": "JSONDecodeError",
                "message": jde.msg,
                "line": jde.lineno,
                "column": jde.colno,
                "snippet": snippet,
            }, indent=2))
        else:
            print("=" * 80)
            print(f"✗ [code-oracle: schema] {diag}")
            if snippet:
                print("  Snippet:")
                for line in snippet.splitlines():
                    print(f"    {line}")
            print("=" * 80)
        return 1

    # Handle boolean schema (Draft 7+ valid schema)
    if isinstance(data, bool):
        status_str = "passed" if data else "failed"
        msg = f"Boolean schema '{data}': all instances are {'valid' if data else 'invalid'}."
        if as_json:
            print(json.dumps({"status": status_str, "mode": "schema", "boolean_schema": data, "message": msg}, indent=2))
        else:
            print("=" * 80)
            print(f"✓ [code-oracle: schema] {msg}")
            print("=" * 80)
        return 0 if data else 1

    # Handle non-dict schemas cleanly without crashing
    if not isinstance(data, dict):
        diag = (
            f"Invalid schema root type: {type(data).__name__}. "
            "Standard JSON Schemas must be an object/dict (or boolean in Draft 7+).\n"
            "Fix: Wrap definitions and properties in a top-level JSON object: { ... }."
        )
        if as_json:
            print(json.dumps({"status": "error", "mode": "schema", "error": diag}, indent=2))
        else:
            print("=" * 80)
            print(f"✗ [code-oracle: schema] {diag}")
            print("=" * 80)
        return 1

    report = inspect_schema_tree(data)
    dangling_count = len(report["dangling_refs"])
    type_issue_count = len(report["type_health_issues"])
    anyof_issue_count = len(report["anyof_issues"])

    has_errors = dangling_count > 0 or type_issue_count > 0 or anyof_issue_count > 0
    status_str = "failed" if has_errors else "passed"

    if as_json:
        out = {
            "status": status_str,
            "mode": "schema",
            **report,
        }
        print(json.dumps(out, indent=2))
    else:
        print("=" * 80)
        if not has_errors and not report["dialect_warnings"]:
            print("✓ [code-oracle: schema] Schema structure clean: all references resolved & types valid.")
            print(f"  OpenAPI Version : {report['openapi_version'] or 'N/A'}")
            print(f"  Definitions     : {report['definitions_container']}")
            print(f"  References      : {report['total_refs']} checked (0 dangling)")
        else:
            prefix = "✗ [code-oracle: schema] Issues detected in schema:" if has_errors else "⚠ [code-oracle: schema] Schema warnings:"
            print(prefix)
            print(f"  OpenAPI Version : {report['openapi_version'] or 'N/A'}")
            print(f"  Definitions     : {report['definitions_container']}")
            print(f"  Total $ref      : {report['total_refs']}")

            if report["dialect_warnings"]:
                print("\n--- DIALECT WARNINGS ---")
                for dw in report["dialect_warnings"]:
                    print(f"  ⚠ {dw}")

            if report["dangling_refs"]:
                print(f"\n--- DANGLING REFERENCES ({len(report['dangling_refs'])} found) ---")
                for dr in report["dangling_refs"]:
                    print(f"  ✗ Location : {dr['location']}")
                    print(f"    Target   : {dr['target']}")
                    print(f"    Error    : {dr['error']}")

            if report["anyof_issues"]:
                print(f"\n--- ANYOF / NULLABILITY ISSUES ({len(report['anyof_issues'])} found) ---")
                for ai in report["anyof_issues"]:
                    print(f"  ✗ Location : {ai['location']}")
                    print(f"    Message  : {ai['message']}")

            if report["type_health_issues"]:
                print(f"\n--- TYPE HEALTH ISSUES ({len(report['type_health_issues'])} found) ---")
                for ti in report["type_health_issues"]:
                    print(f"  ✗ Location : {ti['location']}")
                    print(f"    Message  : {ti['message']}")

            print("\nActionable Fixes for SWE Agent:")
            print("  1. If $ref targets are missing, check if Pydantic v1 vs v2 changed 'definitions' to '$defs'.")
            print("  2. Ensure nullable fields in OpenAPI 3.1 use anyOf: [{'type': '...'}, {'type': 'null'}].")
            print("  3. Replace Python type names ('str', 'int', 'dict') with JSON Schema primitives ('string', 'integer', 'object').")
        print("=" * 80)

    return 1 if has_errors else 0


# ==============================================================================
# Mode 6: --syntax <file>
# ==============================================================================

class RegexSyntaxChecker(ast.NodeVisitor):
    """AST visitor that checks regex patterns for invalid lookbehinds and syntax."""

    def __init__(self, file_path: str, source_lines: Sequence[str]):
        self.file_path = file_path
        self.source_lines = source_lines
        self.issues: List[Dict[str, Any]] = []

    def visit_Call(self, node: ast.Call):
        re_func = None
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            if node.func.value.id in ("re", "regex"):
                re_func = node.func.attr
        elif isinstance(node.func, ast.Name):
            if node.func.id in ("compile", "search", "match", "sub", "split", "findall"):
                re_func = node.func.id

        if re_func:
            pattern_node = None
            if node.args:
                pattern_node = node.args[0]
            else:
                for kw in node.keywords:
                    if kw.arg == "pattern":
                        pattern_node = kw.value
                        break

            if pattern_node and isinstance(pattern_node, ast.Constant) and isinstance(pattern_node.value, str):
                self._verify_regex(pattern_node.value, pattern_node.lineno, pattern_node.col_offset, f"re.{re_func}()")

        self.generic_visit(node)

    def _verify_regex(self, pattern: str, lineno: int, col: int, context: str):
        try:
            re.compile(pattern)
        except re.error as err:
            self.issues.append({
                "file": self.file_path,
                "line": lineno,
                "column": col + 1,
                "error_type": "RegexSyntaxError",
                "message": f"Invalid regex pattern in {context}: {err.msg}",
                "snippet": generate_snippet(self.source_lines, lineno, col + 1),
            })


def check_top_level_imports(
    tree: ast.AST,
    file_path: pathlib.Path,
    workspace: pathlib.Path,
    source_lines: Sequence[str],
) -> List[Dict[str, Any]]:
    """Verify that top-level module imports can be resolved without side-effects."""
    unresolved: List[Dict[str, Any]] = []

    orig_path = list(sys.path)
    file_parent = str(file_path.parent.resolve())
    ws_str = str(workspace.resolve())

    paths_to_add = [file_parent, ws_str]
    for p in paths_to_add:
        if p not in sys.path:
            sys.path.insert(0, p)

    try:
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_mod = alias.name.split(".")[0]
                    try:
                        spec = importlib.util.find_spec(top_mod)
                        if spec is None:
                            unresolved.append({
                                "file": str(file_path),
                                "line": node.lineno,
                                "column": node.col_offset + 1,
                                "module": alias.name,
                                "error_type": "UnresolvedImport",
                                "message": f"Module '{alias.name}' cannot be resolved in current environment without side-effects.",
                                "snippet": generate_snippet(source_lines, node.lineno, node.col_offset + 1),
                            })
                    except Exception as exc:
                        unresolved.append({
                            "file": str(file_path),
                            "line": node.lineno,
                            "column": node.col_offset + 1,
                            "module": alias.name,
                            "error_type": "ImportResolutionError",
                            "message": f"Failed checking module '{alias.name}': {exc}",
                            "snippet": generate_snippet(source_lines, node.lineno, node.col_offset + 1),
                        })

            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    rel_dir = file_path.parent
                    for _ in range(node.level - 1):
                        rel_dir = rel_dir.parent

                    mod_name = node.module or ""
                    mod_path = rel_dir / (mod_name.replace(".", "/") + ".py")
                    pkg_path = rel_dir / mod_name.replace(".", "/") / "__init__.py"

                    if mod_name and not (mod_path.exists() or pkg_path.exists() or (rel_dir / mod_name).is_dir()):
                        unresolved.append({
                            "file": str(file_path),
                            "line": node.lineno,
                            "column": node.col_offset + 1,
                            "module": f".{mod_name}",
                            "error_type": "UnresolvedRelativeImport",
                            "message": f"Relative import target '{mod_name}' not found at {mod_path} or {pkg_path}.",
                            "snippet": generate_snippet(source_lines, node.lineno, node.col_offset + 1),
                        })
                elif node.module:
                    top_mod = node.module.split(".")[0]
                    try:
                        spec = importlib.util.find_spec(top_mod)
                        if spec is None:
                            unresolved.append({
                                "file": str(file_path),
                                "line": node.lineno,
                                "column": node.col_offset + 1,
                                "module": node.module,
                                "error_type": "UnresolvedImport",
                                "message": f"Module '{node.module}' cannot be resolved in current environment.",
                                "snippet": generate_snippet(source_lines, node.lineno, node.col_offset + 1),
                            })
                    except Exception as exc:
                        unresolved.append({
                            "file": str(file_path),
                            "line": node.lineno,
                            "column": node.col_offset + 1,
                            "module": node.module,
                            "error_type": "ImportResolutionError",
                            "message": f"Failed checking module '{node.module}': {exc}",
                            "snippet": generate_snippet(source_lines, node.lineno, node.col_offset + 1),
                        })
    finally:
        sys.path = orig_path

    return unresolved


def find_git_modified_files(ws: pathlib.Path) -> List[pathlib.Path]:
    """Inspect git status to find modified or untracked .py files."""
    git_bin = shutil.which("git") or "git"
    try:
        res = subprocess.run(
            [git_bin, "status", "--porcelain", "-uall"],
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode != 0:
            return []
    except Exception:
        return []

    found: List[pathlib.Path] = []
    for line in res.stdout.splitlines():
        line = line.rstrip()
        if not line or len(line) < 3:
            continue
        rel = line[3:].strip().strip('"')
        if " -> " in rel:
            rel = rel.split(" -> ")[-1].strip().strip('"')
        if rel.endswith(".py"):
            p = (ws / rel).resolve()
            if p.is_file():
                found.append(p)
    return sorted(list(set(found)))


def run_syntax(target: Optional[str] = None, as_json: bool = False) -> int:
    """Validates AST syntax and checks top-level module import resolution."""
    ws = get_workspace_dir()
    files_to_check: List[pathlib.Path] = []

    if target:
        p = pathlib.Path(target)
        if not p.is_absolute():
            p = (ws / p).resolve()
        if not p.is_file():
            # Search workspace for closest .py file candidates
            py_candidates: List[str] = []
            try:
                for root_dir, dirs, files in os.walk(str(ws)):
                    dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", "node_modules", ".git", "__pycache__")]
                    for f in files:
                        if f.endswith(".py"):
                            full = pathlib.Path(root_dir) / f
                            try:
                                rel = str(full.relative_to(ws))
                                py_candidates.append(rel)
                            except ValueError:
                                pass
            except Exception:
                pass

            target_name = pathlib.Path(target).name
            close_matches = difflib.get_close_matches(target, py_candidates, n=3, cutoff=0.5)
            if not close_matches:
                matched_names = difflib.get_close_matches(target_name, [pathlib.Path(c).name for c in py_candidates], n=3, cutoff=0.5)
                close_matches = [c for c in py_candidates if pathlib.Path(c).name in matched_names]

            suggestion_msg = ""
            if close_matches:
                suggestion_msg = f"\n  Did you mean: {close_matches[0]}?\n  Fix: args: ['--syntax', '{close_matches[0]}']"

            err_msg = f"Target file '{target}' does not exist."
            if as_json:
                print(json.dumps({
                    "status": "error",
                    "mode": "syntax",
                    "error_type": "FileNotFoundError",
                    "error": err_msg,
                    "suggestions": close_matches,
                    "fix": f"args: ['--syntax', '{close_matches[0]}']" if close_matches else None,
                }, indent=2))
            else:
                print("=" * 80)
                print(f"✗ [code-oracle: syntax] {err_msg}{suggestion_msg}")
                print("=" * 80)
            return 1
        files_to_check = [p]
    else:
        files_to_check = find_git_modified_files(ws)
        if not files_to_check:
            msg = "No target file specified and no modified .py files found in git status."
            if as_json:
                print(json.dumps({"status": "passed", "mode": "syntax", "message": msg, "files_checked": 0}, indent=2))
            else:
                print(f"✓ [code-oracle: syntax] {msg}")
            return 0

    all_errors: List[Dict[str, Any]] = []

    for fpath in files_to_check:
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            all_errors.append({
                "file": str(fpath),
                "line": 1,
                "column": 1,
                "error_type": "FileReadError",
                "message": f"Could not read file: {exc}",
                "snippet": "",
            })
            continue

        lines = content.splitlines()

        # AST Parse check
        try:
            tree = ast.parse(content, filename=str(fpath))
        except (SyntaxError, IndentationError, TabError) as syn_err:
            snip = generate_snippet(lines, syn_err.lineno or 1, syn_err.offset or 1)
            all_errors.append({
                "file": str(fpath),
                "line": syn_err.lineno or 1,
                "column": syn_err.offset or 1,
                "error_type": type(syn_err).__name__,
                "message": syn_err.msg,
                "snippet": snip,
            })
            continue
        except (RecursionError, MemoryError, ValueError) as ast_err:
            all_errors.append({
                "file": str(fpath),
                "line": 1,
                "column": 1,
                "error_type": type(ast_err).__name__,
                "message": f"AST parsing failure: {ast_err}",
                "snippet": "",
            })
            continue

        # Regex syntax check
        try:
            regex_checker = RegexSyntaxChecker(str(fpath), lines)
            regex_checker.visit(tree)
            all_errors.extend(regex_checker.issues)
        except RecursionError:
            all_errors.append({
                "file": str(fpath),
                "line": 1,
                "column": 1,
                "error_type": "RecursionError",
                "message": "Maximum AST recursion depth exceeded during regex inspection.",
                "snippet": "",
            })

        # Import resolution check
        import_issues = check_top_level_imports(tree, fpath, ws, lines)
        all_errors.extend(import_issues)

    status_str = "failed" if all_errors else "passed"

    if as_json:
        out = {
            "status": status_str,
            "mode": "syntax",
            "files_checked": [str(f) for f in files_to_check],
            "total_errors": len(all_errors),
            "errors": all_errors,
        }
        print(json.dumps(out, indent=2))
    else:
        print("=" * 80)
        if not all_errors:
            print(f"✓ [code-oracle: syntax] All {len(files_to_check)} Python file(s) passed AST & import verification.")
        else:
            print(f"✗ [code-oracle: syntax] Detected {len(all_errors)} issue(s) across {len(files_to_check)} file(s):")
            for err in all_errors:
                print(f"\n  [{err['error_type']}] {err['file']}:{err['line']}:{err['column']}")
                print(f"  Message: {err['message']}")
                if err["snippet"]:
                    print("  Snippet:")
                    for s_line in err["snippet"].splitlines():
                        print(f"    {s_line}")

            print("\nActionable Fixes for SWE Agent:")
            print("  1. Correct the syntax, indentation, or regex error on the flagged line.")
            print("  2. Verify that top-level imports are available or use guarded/deferred imports inside functions.")
        print("=" * 80)

    return 1 if all_errors else 0


# ==============================================================================
# Overview & CLI Entrypoint
# ==============================================================================

def print_overview():
    """Print clean, compact overview of all 6 modes with copy-pasteable commands."""
    overview_text = """================================================================================
CODE-ORACLE: Multi-Domain Coding Assistance Oracle for SWE Agents
================================================================================

Solves domain nuances (ANSI escapes, Unicode terminal cell widths, HTML escaping,
OpenAPI/JSON Schema validation, AST syntax & import resolution) with actionable
diagnostics for LLMs. Pure Python standard library (zero external dependencies).

SUPPORTED MODES:
  1. -e, --eval <expr>    Safely evaluate Python expressions/statements with loop
                          timeout protection; outputs type, repr, len, and formatted string.
  2. -x, --hex <text>     Hex dump and escape sequence inspector. Decodes raw bytes,
                          ANSI CSI/SGR codes, OSC links, and invisible chars (\\r, \\u200d).
  3. -w, --width <text>   Calculates exact monospaced terminal display width (CJK = 2,
                          emojis = 2, ZWJ = 2, combining = 0) vs len(text).
  4. -H, --html-esc <htm> Verifies HTML entity escaping (&lt;, &gt;, &amp;, quotes), tag
                          matching/balance, and script tag escaping.
  5. -s, --schema <json>  Inspects JSON Schema / OpenAPI structure: checks $defs vs
                          definitions, resolves $ref pointers, checks anyOf nullability.
  6. -S, --syntax <file>  Validates AST syntax (ast.parse), regexes, and checks top-level
                          module import resolution without executing side-effects.

RECOMMENDED ARGUMENT SCHEMAS:
  # 1. Safely evaluate an expression:
  args: ["--eval", 'len("hello world")']
  args: ["1 + 2 * 3"]  # auto-detected

  # 2. Inspect ANSI escapes, hex dump, or invisible characters:
  args: ["--hex", "\\x1b[31;1mError\\x1b[0m\\r\\n"]
  args: ["file_with_hidden_characters.txt"]

  # 3. Calculate terminal display cell width for monospaced layouts:
  args: ["--width", "👨‍👩‍👧‍👦 Family"]
  args: ["-w", "\\x1b[32mClean Output\\x1b[0m"]

  # 4. Inspect HTML template escaping and tag balance:
  args: ["--html-esc", "<div><p>Hello & welcome</p></div>"]
  args: ["templates/swagger_ui.html"]

  # 5. Validate OpenAPI / JSON Schema references and dialect:
  args: ["--schema", "openapi.json"]
  args: ['{"$defs": {"A": {"type": "string"}}, "$ref": "#/$defs/A"}']

  # 6. Validate AST syntax, regex lookbehinds, and top-level imports:
  args: ["--syntax", "rich/text.py"]
  args: ["-S"]  # auto-checks modified files from git status

ADDITIONAL OPTIONS:
  --json, -j              Output results in machine-readable JSON format
  -h, --help              Show this help message and exit
================================================================================
"""
    print(overview_text)


def normalize_cli_args(raw_argv: List[str]) -> Tuple[Dict[str, Any], List[str]]:
    """Normalize CLI arguments, handling forgiving flags, extra dashes, aliases, and loose options."""
    parsed: Dict[str, Any] = {
        "help": False,
        "json": False,
        "mode": None,
        "mode_arg": None,
    }
    positional: List[str] = []

    MODE_FLAGS = {
        # Mode 1: eval
        "e": "eval", "eval": "eval", "evaluate": "eval", "expr": "eval",
        "expression": "eval", "exec": "eval", "execute": "eval", "calc": "eval", "py": "eval",
        # Mode 2: hex
        "x": "hex", "hex": "hex", "hexdump": "hex", "dump": "hex", "bytes": "hex",
        "ansi": "hex", "escape": "hex", "escapes": "hex", "raw": "hex",
        # Mode 3: width
        "w": "width", "width": "width", "cell": "width", "cells": "width",
        "cellwidth": "width", "cell-width": "width", "column": "width",
        "columns": "width", "col": "width", "cols": "width", "display-width": "width", "displaywidth": "width",
        # Mode 4: html-esc
        "H": "html-esc", "htmlesc": "html-esc", "html-esc": "html-esc", "html": "html-esc",
        "htm": "html-esc", "html_esc": "html-esc", "htmlescape": "html-esc",
        "html-escape": "html-esc", "tags": "html-esc", "tag": "html-esc",
        # Mode 5: schema
        "s": "schema", "schema": "schema", "openapi": "schema", "jsonschema": "schema",
        "json-schema": "schema", "defs": "schema", "definitions": "schema", "swagger": "schema", "spec": "schema",
        # Mode 6: syntax
        "S": "syntax", "syntax": "syntax", "ast": "syntax", "check": "syntax",
        "checksyntax": "syntax", "check-syntax": "syntax", "lint": "syntax",
        "imports": "syntax", "import": "syntax", "pycompile": "syntax", "compile": "syntax",
    }

    i = 0
    n = len(raw_argv)
    while i < n:
        token = raw_argv[i]

        # Check if token is a flag
        is_flag = token.startswith("-") and not (len(token) > 1 and token[1].isdigit()) and token != "-"
        if is_flag:
            flag_body = token.lstrip("-")
            flag_val: Optional[str] = None
            if "=" in flag_body:
                flag_body, flag_val = flag_body.split("=", 1)

            # Help check
            if flag_body in ("h", "help", "?"):
                parsed["help"] = True
                i += 1
                continue

            # JSON check
            if flag_body in ("j", "json"):
                parsed["json"] = True
                i += 1
                continue

            # Mode flags check (exact or case-normalized / fuzzy)
            matched_mode: Optional[str] = None
            if flag_body in MODE_FLAGS:
                matched_mode = MODE_FLAGS[flag_body]
            elif len(flag_body) > 1:
                clean_body = flag_body.lower().replace("_", "-")
                if clean_body in MODE_FLAGS:
                    matched_mode = MODE_FLAGS[clean_body]
                else:
                    close = difflib.get_close_matches(clean_body, list(MODE_FLAGS.keys()), n=1, cutoff=0.7)
                    if close:
                        matched_mode = MODE_FLAGS[close[0]]

            if matched_mode:
                parsed["mode"] = matched_mode
                if flag_val is not None:
                    parsed["mode_arg"] = flag_val
                elif i + 1 < n:
                    next_token = raw_argv[i + 1]
                    next_is_flag = next_token.startswith("-") and not (len(next_token) > 1 and next_token[1].isdigit()) and next_token != "-"
                    if parsed["mode"] == "syntax" and next_is_flag:
                        parsed["mode_arg"] = None
                    elif not next_is_flag:
                        parsed["mode_arg"] = next_token
                        i += 1
                i += 1
                continue

            # Loose / unrecognized flag: ignore gracefully rather than crashing
            i += 1
            continue

        positional.append(token)
        i += 1

    return parsed, positional


def main(argv: Optional[List[str]] = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    parsed, positional = normalize_cli_args(raw_argv)

    if parsed["help"]:
        print_overview()
        return 0

    as_json = parsed["json"]
    mode = parsed["mode"]
    mode_arg = parsed["mode_arg"]

    # If explicit mode was provided with extra positional tokens, join them gracefully
    if mode == "eval":
        expr = mode_arg or ""
        if positional:
            expr = (expr + " " + " ".join(positional)).strip()
        return run_eval(expr, as_json=as_json)

    if mode == "hex":
        text = mode_arg or ""
        if positional:
            text = (text + " " + " ".join(positional)).strip()
        return run_hex(text, as_json=as_json)

    if mode == "width":
        text = mode_arg or ""
        if positional:
            text = (text + " " + " ".join(positional)).strip()
        return run_width(text, as_json=as_json)

    if mode == "html-esc":
        snippet = mode_arg or ""
        if positional:
            snippet = (snippet + " " + " ".join(positional)).strip()
        return run_html_esc(snippet, as_json=as_json)

    if mode == "schema":
        schema_in = mode_arg or ""
        if positional:
            schema_in = (schema_in + " " + " ".join(positional)).strip()
        return run_schema(schema_in, as_json=as_json)

    if mode == "syntax":
        target = mode_arg
        if not target and positional:
            target = positional[0]
        return run_syntax(target, as_json=as_json)

    # Positional auto-detection when no explicit mode flag was specified
    if positional:
        pos_arg = " ".join(positional).strip()
        p = pathlib.Path(pos_arg)

        # 1. Existing file auto-detection
        if len(positional) == 1 and p.is_file():
            suffix = p.suffix.lower()
            if suffix == ".py":
                return run_syntax(pos_arg, as_json=as_json)
            elif suffix in (".json", ".yaml", ".yml"):
                return run_schema(pos_arg, as_json=as_json)
            elif suffix in (".html", ".htm", ".xml", ".svg"):
                return run_html_esc(pos_arg, as_json=as_json)
            else:
                return run_hex(pos_arg, as_json=as_json)

        # 2. File extension path detection (even if missing)
        if pos_arg.endswith(".py"):
            return run_syntax(pos_arg, as_json=as_json)
        elif pos_arg.endswith((".json", ".yaml", ".yml")):
            return run_schema(pos_arg, as_json=as_json)
        elif pos_arg.endswith((".html", ".htm", ".xml", ".svg")):
            return run_html_esc(pos_arg, as_json=as_json)
        elif pos_arg.endswith((".txt", ".log", ".out", ".diff", ".patch", ".dat", ".bin", ".raw")):
            return run_hex(pos_arg, as_json=as_json)

        # 3. ANSI escape sequence detection -> --hex
        if "\x1b" in pos_arg or "\033" in pos_arg or r"\x1b" in pos_arg or r"\033" in pos_arg or ANSI_RE.search(pos_arg):
            return run_hex(pos_arg, as_json=as_json)

        # 4. HTML tag / snippet detection -> --html-esc
        if pos_arg.startswith("<") or re.search(r"</?[a-zA-Z][^>]*>", pos_arg):
            return run_html_esc(pos_arg, as_json=as_json)

        # 5. JSON Schema string detection -> --schema
        if pos_arg.startswith("{") and any(k in pos_arg for k in ('"$defs"', '"definitions"', '"openapi"', '"$schema"', '"properties"', '"type"')):
            return run_schema(pos_arg, as_json=as_json)

        # 6. Default: Python expression / statements -> --eval
        return run_eval(pos_arg, as_json=as_json)

    # Empty invocation: print clean overview and exit 0
    print_overview()
    return 0


if __name__ == "__main__":
    sys.exit(main())
