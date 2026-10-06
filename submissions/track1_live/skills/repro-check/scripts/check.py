#!/usr/bin/env python3
"""repro-check: Omnivorous Defect Reproduction & Verification Engine.

V2 Upgrades:
- Native `--expect-exception <ExceptionType>` support:
  Deterministically catches missing-validation defects (defect_confirmed=True when not raised,
  status=PASSED when fix causes the exception to be raised).
- Base64 decode support via `--b64` / `--base64` to cleanly bypass shell/JSON quote escaping.
- Input quote and fence sanitization (strips redundant outer quotes, markdown blocks, and JSON escaped quotes).
- AST pre-parse syntax validation: verifies syntax prior to scratch file generation or execution.
- Raw multiline script execution via `--file`, `--stdin`, or pipes into isolated `/tmp` cwd,
  avoiding CLI quote escaping and emoji truncation.
- Path Containment Guard: Strictly isolates scratch files in `/tmp` and prevents/cleans any
  accidental `/workspace/tmp/...` files that could pollute git status.
- Prioritizes /workspace and /workspace/src in PYTHONPATH.

Omnivorous core features:
- Auto-asserts bare comparison expressions: `a == b` -> `assert a == b`
- Auto-invokes uncalled test functions: `def test_...():`
- Auto-heals unterminated string literals with raw unescaped newlines in `'...'` and `"..."`
- Omnivorous assert acceptance: executions without explicit `assert` that exit 0 are accepted as valid passes
- Bypasses 2-probe circuit breaker when workspace contains modified files (post-edit verification)
- Strips markdown fences (```py, ```python, etc.) and auto-dedents
- Deterministic failure explanations: introspects failing frame, local variables, actual/expected values, char diffs
- Structured 100% Pydantic v2 models for all diagnostic outputs
- Exits 0 on pass, exits 1 on fail/syntax error.
"""

from __future__ import annotations

import ast
import base64
import contextlib
import difflib
import inspect
import io
import json
import linecache
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
import textwrap
import types
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field

PROBE_COUNT_FILE = pathlib.Path("/tmp/.swegemma_repro_probe_count")
PROBE_HISTORY_FILE = pathlib.Path("/tmp/.repro_probe_history.json")

OP_MAP = {
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
    ast.Is: "is",
    ast.IsNot: "is not",
    ast.In: "in",
    ast.NotIn: "not in",
}


# =============================================================================
# 100% Pydantic v2 Structured Diagnostic Models
# =============================================================================

class VariableInfo(BaseModel):
    """Inspected variable details from stack frame."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., description="Variable name")
    type_name: str = Field(..., description="Variable type name")
    value_repr: str = Field(..., description="String representation with visible escape codes")
    length: Optional[int] = Field(default=None, description="Length of sequence or collection if applicable")


class StackFrameInfo(BaseModel):
    """Inspected call stack frame details."""

    model_config = ConfigDict(extra="ignore")

    filename: str = Field(..., description="File path of execution frame")
    lineno: int = Field(..., description="Line number")
    function_name: str = Field(..., description="Function or module name")
    code_context: Optional[str] = Field(default=None, description="Source code line")
    arguments: Dict[str, VariableInfo] = Field(default_factory=dict, description="Function arguments")
    local_variables: Dict[str, VariableInfo] = Field(default_factory=dict, description="Local variables in frame")


class AssertionDiagnostic(BaseModel):
    """Deterministic failure diagnostic for an assertion failure."""

    model_config = ConfigDict(extra="ignore")

    assertion_code: str = Field(..., description="Source code of the failing assertion")
    op: str = Field(default="==", description="Comparison operator (==, !=, in, etc.)")
    actual_type: str = Field(..., description="Type name of actual value")
    actual_repr: str = Field(..., description="Actual value with visible escape codes")
    actual_length: Optional[int] = Field(default=None, description="Length of actual value if applicable")
    expected_type: str = Field(..., description="Type name of expected value")
    expected_repr: str = Field(..., description="Expected value with visible escape codes")
    expected_length: Optional[int] = Field(default=None, description="Length of expected value if applicable")
    char_diff: Optional[str] = Field(default=None, description="Character-by-character or unified diff")
    first_diff_index: Optional[int] = Field(default=None, description="First index where values differ")
    divergence_detail: Optional[str] = Field(default=None, description="Exact divergence detail with hex characters")
    escape_breakdown: Optional[str] = Field(default=None, description="Decoded ANSI escape sequences and control characters")
    dict_diff_summary: Optional[str] = Field(default=None, description="Detailed dictionary diff summary")
    sequence_diff_summary: Optional[str] = Field(default=None, description="Detailed sequence diff summary")
    root_cause_hint: Optional[str] = Field(default=None, description="Actionable root cause hint for LLM")
    message: Optional[str] = Field(default=None, description="Assertion failure message")
    explanation: str = Field(..., description="Plain-English explanation of why assertion failed")
    remediation_hint: Optional[str] = Field(default=None, description="Actionable remediation hint for common defects")


class ExceptionDiagnostic(BaseModel):
    """Deterministic failure diagnostic for an unhandled runtime exception."""

    model_config = ConfigDict(extra="ignore")

    exception_type: str = Field(..., description="Exception class name")
    exception_message: str = Field(..., description="Exception error message")
    failing_file: str = Field(..., description="File where exception occurred")
    failing_line: int = Field(..., description="Line number where exception occurred")
    failing_code: Optional[str] = Field(default=None, description="Failing source line code")
    operation_description: str = Field(..., description="Plain-English explanation of operation that failed")
    call_stack: List[StackFrameInfo] = Field(default_factory=list, description="Call stack frames")


class DiagnosticReport(BaseModel):
    """Full structured reproduction report."""

    model_config = ConfigDict(extra="ignore")

    status: str = Field(..., description="Status: passed, PASSED, missing_exception, assertion_error, runtime_exception, syntax_error, probe_budget_reached, probe_run, missing_assertion, duplicate_probe, timeout, error")
    exit_code: int = Field(default=0, description="Process exit code")
    summary: str = Field(..., description="High-level diagnostic summary")
    assertion_diagnostic: Optional[AssertionDiagnostic] = Field(default=None, description="Details if assertion failed")
    exception_diagnostic: Optional[ExceptionDiagnostic] = Field(default=None, description="Details if exception occurred")
    local_variables: Dict[str, VariableInfo] = Field(default_factory=dict, description="Local variables in failing frame")
    raw_stdout: str = Field(default="", description="Captured stdout")
    raw_stderr: str = Field(default="", description="Captured stderr")


class ReproCheckInput(BaseModel):
    """Structured input parameters for reproduction check."""

    model_config = ConfigDict(extra="ignore")

    code: str = Field(..., description="Reproduction script code")
    args: List[str] = Field(default_factory=list, description="Original CLI arguments")
    timeout_secs: int = Field(default=15, description="Timeout in seconds")
    workspace_dir: Optional[str] = Field(default=None, description="Path to active workspace")


class ReproCheckOutput(BaseModel):
    """Top-level structured output of repro-check."""

    model_config = ConfigDict(extra="ignore")

    success: bool = Field(..., description="True if verification passed cleanly")
    defect_confirmed: bool = Field(..., description="True if defect was reproduced via assertion or exception")
    category: str = Field(..., description="Category: passed, assertion_failure, workspace_exception, runtime_exception, syntax_error, probe_budget_reached, probe_run, missing_assertion, duplicate_probe, general_failure, missing_exception")
    report: DiagnosticReport = Field(..., description="Structured diagnostic report")
    rendered_output: str = Field(..., description="Rendered human/agent readable text")


VariableInfo.model_rebuild()
StackFrameInfo.model_rebuild()
AssertionDiagnostic.model_rebuild()
ExceptionDiagnostic.model_rebuild()
DiagnosticReport.model_rebuild()
ReproCheckInput.model_rebuild()
ReproCheckOutput.model_rebuild()


# =============================================================================
# Custom Assertion Exception for Zero-Loss Evaluation
# =============================================================================

class ReproAssertionError(AssertionError):
    """Carries exact evaluated operands and failing frame for deterministic explanation."""

    def __init__(
        self,
        actual: Any,
        expected: Any,
        op: str,
        code_str: str,
        lineno: int,
        msg: str = "",
        frame: Optional[types.FrameType] = None,
    ):
        super().__init__(msg or f"Assertion failed: {code_str}")
        self.actual = actual
        self.expected = expected
        self.op = op
        self.code_str = code_str
        self.lineno = lineno
        self.msg = msg
        self.frame = frame


# =============================================================================
# Value Formatting and Diff Helpers
# =============================================================================

def format_value_repr(val: Any, max_len: int = 300) -> str:
    """Format value representation with visible escape codes and safe length cap."""
    try:
        r = repr(val)
        if len(r) > max_len:
            return r[:max_len] + f"... [truncated, total {len(r)} chars]"
        return r
    except Exception:
        return f"<{type(val).__name__} (unprintable)>"


def get_length(val: Any) -> Optional[int]:
    """Safely obtain length of sequence or collection."""
    try:
        return len(val)
    except Exception:
        return None


def introspect_variable(name: str, val: Any) -> VariableInfo:
    """Convert an arbitrary Python runtime variable into a VariableInfo model."""
    return VariableInfo(
        name=name,
        type_name=type(val).__name__,
        value_repr=format_value_repr(val),
        length=get_length(val),
    )


def extract_frame_info(frame: types.FrameType, lineno: int) -> StackFrameInfo:
    """Extract argument and local variable details from a call stack frame."""
    co = frame.f_code
    filename = co.co_filename
    func_name = co.co_name

    # Try reading source line from linecache
    code_context = linecache.getline(filename, lineno).strip() or None

    # Inspect function arguments if applicable
    args_dict: Dict[str, VariableInfo] = {}
    try:
        argvalues = inspect.getargvalues(frame)
        for arg in argvalues.args:
            if arg in frame.f_locals:
                args_dict[arg] = introspect_variable(arg, frame.f_locals[arg])
        if argvalues.varargs and argvalues.varargs in frame.f_locals:
            args_dict[f"*{argvalues.varargs}"] = introspect_variable(argvalues.varargs, frame.f_locals[argvalues.varargs])
        if argvalues.keywords and argvalues.keywords in frame.f_locals:
            args_dict[f"**{argvalues.keywords}"] = introspect_variable(argvalues.keywords, frame.f_locals[argvalues.keywords])
    except Exception:
        pass

    # Extract clean local variables
    locals_dict: Dict[str, VariableInfo] = {}
    for k, v in frame.f_locals.items():
        if not k.startswith("__") and k not in ("__repro_assert__", "__repro_assert_truthy__"):
            locals_dict[k] = introspect_variable(k, v)

    return StackFrameInfo(
        filename=filename,
        lineno=lineno,
        function_name=func_name,
        code_context=code_context,
        arguments=args_dict,
        local_variables=locals_dict,
    )


def extract_call_stack(exc: BaseException) -> List[StackFrameInfo]:
    """Walk an exception's traceback and introspect all stack frames."""
    frames: List[StackFrameInfo] = []
    tb = exc.__traceback__
    this_file = str(pathlib.Path(__file__).resolve())
    while tb is not None:
        frame = tb.tb_frame
        lineno = tb.tb_lineno
        # Filter out internal runner harness frames
        if frame.f_code.co_name == "run_harness" or frame.f_code.co_filename == this_file:
            tb = tb.tb_next
            continue
        frames.append(extract_frame_info(frame, lineno))
        tb = tb.tb_next

    # Fallback to all frames if all were filtered out
    if not frames and exc.__traceback__ is not None:
        tb = exc.__traceback__
        while tb is not None:
            frames.append(extract_frame_info(tb.tb_frame, tb.tb_lineno))
            tb = tb.tb_next

    return frames


# =============================================================================
# ANSI & Control Sequence Decoding
# =============================================================================

ANSI_CSI_RE = re.compile(r"\x1b\[([0-9;]*)([a-zA-Z])")
ANSI_OSC_RE = re.compile(r"\x1b\]([^\x07\x1b]*)(?:\x07|\x1b\\)")
ANSI_ESCAPE_RE = re.compile(
    r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[@-Z\\-_]"
)

SGR_CODES: Dict[str, str] = {
    "0": "Reset / Normal",
    "1": "Bold",
    "2": "Dim / Faint",
    "3": "Italic",
    "4": "Underline",
    "5": "Slow Blink",
    "6": "Rapid Blink",
    "7": "Invert / Reverse video",
    "8": "Concealed / Hidden",
    "9": "Strikethrough / Crossed-out",
    "22": "Normal intensity",
    "23": "Not italic",
    "24": "Not underlined",
    "27": "Not inverted",
    "28": "Reveal (not concealed)",
    "29": "Not crossed out",
    "30": "Black text",
    "31": "Red text",
    "32": "Green text",
    "33": "Yellow text",
    "34": "Blue text",
    "35": "Magenta text",
    "36": "Cyan text",
    "37": "White text",
    "39": "Default text color",
    "40": "Black background",
    "41": "Red background",
    "42": "Green background",
    "43": "Yellow background",
    "44": "Blue background",
    "45": "Magenta background",
    "46": "Cyan background",
    "47": "White background",
    "49": "Default background color",
    "90": "Bright Black / Dark Gray text",
    "91": "Bright Red text",
    "92": "Bright Green text",
    "93": "Bright Yellow text",
    "94": "Bright Blue text",
    "95": "Bright Magenta text",
    "96": "Bright Cyan text",
    "97": "Bright White text",
    "100": "Bright Black background",
    "101": "Bright Red background",
    "102": "Bright Green background",
    "103": "Bright Yellow background",
    "104": "Bright Blue background",
    "105": "Bright Magenta background",
    "106": "Bright Cyan background",
    "107": "Bright White background",
}

CONTROL_CHAR_NAMES: Dict[int, str] = {
    0x00: "NUL (null byte)",
    0x01: "SOH (start of heading)",
    0x02: "STX (start of text)",
    0x03: "ETX (end of text)",
    0x04: "EOT (end of transmission)",
    0x05: "ENQ (enquiry)",
    0x06: "ACK (acknowledge)",
    0x07: "BEL (bell / alert)",
    0x08: "BS (backspace)",
    0x09: "HT (horizontal tab)",
    0x0A: "LF (line feed / newline)",
    0x0B: "VT (vertical tab)",
    0x0C: "FF (form feed)",
    0x0D: "CR (carriage return)",
    0x0E: "SO (shift out)",
    0x0F: "SI (shift in)",
    0x10: "DLE (data link escape)",
    0x11: "DC1 (device control 1)",
    0x12: "DC2 (device control 2)",
    0x13: "DC3 (device control 3)",
    0x14: "DC4 (device control 4)",
    0x15: "NAK (negative acknowledge)",
    0x16: "SYN (synchronous idle)",
    0x17: "ETB (end of trans block)",
    0x18: "CAN (cancel)",
    0x19: "EM (end of medium)",
    0x1A: "SUB (substitute)",
    0x1B: "ESC (escape)",
    0x1C: "FS (file separator)",
    0x1D: "GS (group separator)",
    0x1E: "RS (record separator)",
    0x1F: "US (unit separator)",
    0x7F: "DEL (delete)",
    0x200B: "Zero-Width Space",
    0x200C: "Zero-Width Non-Joiner",
    0x200D: "Zero-Width Joiner",
    0x200E: "Left-to-Right Mark",
    0x200F: "Right-to-Left Mark",
    0xFEFF: "Zero-Width No-Break Space / BOM",
    0x00A0: "Non-Breaking Space",
    0x2028: "Line Separator",
    0x2029: "Paragraph Separator",
}


def decode_ansi_sequence(seq: str) -> str:
    """Decode an ANSI escape sequence into a human-readable description."""
    m_csi = ANSI_CSI_RE.fullmatch(seq)
    if m_csi:
        params, cmd = m_csi.group(1), m_csi.group(2)
        if cmd == "m":
            if not params or params == "0":
                return f"ANSI CSI SGR {seq[2:]}: Reset / Normal"
            param_list = params.split(";")
            meanings = []
            skip_next = 0
            for i, p in enumerate(param_list):
                if skip_next > 0:
                    skip_next -= 1
                    continue
                if p in ("38", "48") and i + 1 < len(param_list):
                    mode = param_list[i + 1]
                    target = "text" if p == "38" else "background"
                    if mode == "5" and i + 2 < len(param_list):
                        color_idx = param_list[i + 2]
                        meanings.append(f"256-color {target} #{color_idx}")
                        skip_next = 2
                        continue
                    elif mode == "2" and i + 4 < len(param_list):
                        r, g, b = param_list[i + 2 : i + 5]
                        meanings.append(f"RGB {target} ({r},{g},{b})")
                        skip_next = 4
                        continue
                desc = SGR_CODES.get(p, f"code {p}")
                meanings.append(desc)
            return f"ANSI CSI SGR {seq[2:]}: {', '.join(meanings)}"
        elif cmd == "K":
            mode = params or "0"
            k_map = {
                "0": "Clear line from cursor to end",
                "1": "Clear line from cursor to start",
                "2": "Clear entire line",
            }
            return f"ANSI CSI {seq[2:]}: {k_map.get(mode, 'Clear line')}"
        elif cmd == "J":
            mode = params or "0"
            j_map = {
                "0": "Clear screen from cursor to end",
                "1": "Clear screen from cursor to start",
                "2": "Clear entire screen",
            }
            return f"ANSI CSI {seq[2:]}: {j_map.get(mode, 'Clear display')}"
        elif cmd in ("H", "f"):
            pos = params or "1;1"
            return f"ANSI CSI {seq[2:]}: Move cursor to row;col {pos}"
        elif cmd == "A":
            return f"ANSI CSI {seq[2:]}: Move cursor up {params or 1} lines"
        elif cmd == "B":
            return f"ANSI CSI {seq[2:]}: Move cursor down {params or 1} lines"
        elif cmd == "C":
            return f"ANSI CSI {seq[2:]}: Move cursor right {params or 1} cols"
        elif cmd == "D":
            return f"ANSI CSI {seq[2:]}: Move cursor left {params or 1} cols"
        else:
            return f"ANSI CSI command '{cmd}' (params: {params or 'none'})"

    m_osc = ANSI_OSC_RE.fullmatch(seq)
    if m_osc:
        content = m_osc.group(1)
        if content.startswith("0;"):
            return f"ANSI OSC 0: Set window title '{content[2:]}'"
        elif content.startswith("8;;"):
            return f"ANSI OSC 8: Hyperlink '{content[3:]}'"
        return f"ANSI OSC: '{content}'"

    return f"ANSI escape sequence: {repr(seq)}"


def scan_escape_and_control_codes(s: str) -> List[Tuple[int, str, str]]:
    """Scan string for ANSI escape sequences and control characters.

    Returns list of (char_index, raw_repr, description).
    """
    results: List[Tuple[int, str, str]] = []
    covered_spans: List[Tuple[int, int]] = []

    # 1. Match ANSI sequences
    for m in ANSI_ESCAPE_RE.finditer(s):
        start, end = m.span()
        seq = m.group(0)
        desc = decode_ansi_sequence(seq)
        results.append((start, repr(seq), desc))
        covered_spans.append((start, end))

    # 2. Match control characters outside covered spans
    for i, c in enumerate(s):
        in_span = any(start <= i < end for start, end in covered_spans)
        if in_span:
            continue
        cp = ord(c)
        if cp in CONTROL_CHAR_NAMES:
            name = CONTROL_CHAR_NAMES[cp]
            results.append((i, repr(c), f"Control char 0x{cp:02x}: {name}"))
        elif cp < 32 and c not in ("\n", "\t"):
            results.append((i, repr(c), f"Control char 0x{cp:02x}: non-printable"))
        elif 127 <= cp <= 159:
            results.append((i, repr(c), f"Control char 0x{cp:02x}: C1 control code"))

    results.sort(key=lambda x: x[0])
    return results


def format_escape_breakdown(actual: str, expected: str) -> Optional[str]:
    """Generate human-readable escape and control sequence breakdown."""
    act_codes = scan_escape_and_control_codes(actual)
    exp_codes = scan_escape_and_control_codes(expected)

    if not act_codes and not exp_codes:
        return None

    lines = ["📟 ANSI & CONTROL ESCAPE BREAKDOWN:"]

    lines.append(f"  Actual ({len(act_codes)} code(s) detected):")
    if act_codes:
        for idx, raw_rep, desc in act_codes:
            lines.append(f"    - Index {idx:3d}: {raw_rep} -> {desc}")
    else:
        lines.append("    (None - plain text, no escape or control sequences)")

    lines.append(f"  Expected ({len(exp_codes)} code(s) detected):")
    if exp_codes:
        for idx, raw_rep, desc in exp_codes:
            lines.append(f"    - Index {idx:3d}: {raw_rep} -> {desc}")
    else:
        lines.append("    (None - plain text, no escape or control sequences)")

    return "\n".join(lines)


def compute_string_divergence(actual: str, expected: str) -> Tuple[Optional[int], str]:
    """Find character index of first divergence and format exact diagnostic."""
    min_len = min(len(actual), len(expected))
    for i in range(min_len):
        if actual[i] != expected[i]:
            c_a = actual[i]
            c_e = expected[i]
            diff_msg = (
                f"Diff at index {i}: actual={c_a!r} (hex: {hex(ord(c_a))}) vs expected={c_e!r} (hex: {hex(ord(c_e))})"
            )
            return i, diff_msg

    if len(actual) < len(expected):
        first_diff = len(actual)
        c_e = expected[first_diff]
        diff_msg = (
            f"Diff at index {first_diff}: actual string ended (length {len(actual)}) vs expected={c_e!r} (hex: {hex(ord(c_e))})"
        )
        return first_diff, diff_msg
    elif len(actual) > len(expected):
        first_diff = len(expected)
        c_a = actual[first_diff]
        diff_msg = (
            f"Diff at index {first_diff}: actual={c_a!r} (hex: {hex(ord(c_a))}) vs expected string ended (length {len(expected)})"
        )
        return first_diff, diff_msg

    return None, "Strings are identical"


def get_string_remediation_hint(actual: Any, expected: Any) -> Optional[str]:
    """Generate targeted remediation hint for common string and boundary defects."""
    if not isinstance(actual, str) or not isinstance(expected, str):
        return None

    if actual == expected:
        return None

    # Degenerate boundary mismatch (empty string vs newline)
    if (actual == "" and expected in ("\n", "\r\n")) or (actual in ("\n", "\r\n") and expected == ""):
        return (
            "💡 HINT: Boundary value mismatch detected. Verify edge-case handling for empty or boundary inputs."
        )

    # Suffix / trailing mismatch (difference is at or near the end, e.g. missing trailing \n, \r\n, or extra trailing whitespace)
    if actual.rstrip() == expected.rstrip():
        return (
            "💡 HINT: Trailing character or newline mismatch. Actual string differs in suffix from expected."
        )

    # Line count mismatch (empty line suppression or newline preservation issue)
    if ("\n" in actual or "\n" in expected) and actual.count("\n") != expected.count("\n"):
        return f"💡 HINT: Line count mismatch detected. Expected {expected.count('\n')} newlines, got {actual.count('\n')}. Check for dropped empty lines or delimiter parsing differences."

    return None


compute_assertion_remediation_hint = get_string_remediation_hint


def generate_root_cause_hint(
    actual: Any,
    op: str,
    expected: Any,
    first_diff_idx: Optional[int] = None,
) -> str:
    """Generate clear, actionable root cause hint for the LLM."""
    if isinstance(actual, str) and isinstance(expected, str):
        act_has_ansi = bool(ANSI_ESCAPE_RE.search(actual))
        exp_has_ansi = bool(ANSI_ESCAPE_RE.search(expected))

        if act_has_ansi and not exp_has_ansi:
            return (
                "Actual string contains ANSI styling/escape codes that are absent from expected. "
                "If plain text was expected, strip ANSI escapes (e.g. using strip_ansi(), Text.plain, "
                "or re.sub(r'\\x1b\\[[0-9;]*[a-zA-Z]', '', text)). "
                "If styled output was expected, update the assertion or expected string with matching ANSI codes."
            )
        elif exp_has_ansi and not act_has_ansi:
            return (
                "Expected string contains ANSI styling/escape codes that are missing from actual output. "
                "Ensure terminal styling, color formatting, or highlighter is enabled and invoked."
            )
        elif act_has_ansi and exp_has_ansi:
            idx_str = f" at index {first_diff_idx}" if first_diff_idx is not None else ""
            return (
                f"ANSI escape sequences differ{idx_str}. "
                "Check the exact style tags, color parameter numbers, or reset codes in the formatting pipeline."
            )

        # Check line ending / CRLF vs LF differences
        if ("\r" in actual and "\r" not in expected) or ("\r" in expected and "\r" not in actual):
            return (
                "Line ending mismatch detected (CRLF '\\r\\n' vs LF '\\n' or carriage return '\\r'). "
                "Normalize line endings using .replace('\\r\\n', '\\n') or str.splitlines()."
            )

        # Check tab vs space indentation
        if ("\t" in actual or "\t" in expected) and actual.expandtabs() == expected.expandtabs():
            return (
                "Tab vs space indentation mismatch detected. "
                "Verify tab expansion or replace tabs with spaces using .expandtabs() or 4 spaces."
            )

        # Check trailing whitespace or newline differences
        if actual.rstrip() == expected.rstrip():
            return (
                "String mismatch is caused by trailing newline or whitespace differences. "
                "Verify rstrip(), strip(), or newline emission logic."
            )

        # Line count mismatch
        if actual.count("\n") != expected.count("\n"):
            return (
                f"Line count mismatch (actual has {actual.count('\n')} newlines, "
                f"expected has {expected.count('\n')}). "
                "Check for dropped empty lines, delimiter parsing, or splitlines() handling."
            )

        # Boundary empty string
        if (actual == "" and expected != "") or (actual != "" and expected == ""):
            return (
                "Boundary value mismatch (empty string vs non-empty string). "
                "Verify edge-case handling for empty or boundary inputs."
            )

        # General string difference
        idx_str = f" at index {first_diff_idx}" if first_diff_idx is not None else ""
        c_a = actual[first_diff_idx] if first_diff_idx is not None and first_diff_idx < len(actual) else "ended"
        c_e = expected[first_diff_idx] if first_diff_idx is not None and first_diff_idx < len(expected) else "ended"
        return (
            f"Strings diverge{idx_str} (actual={c_a!r} vs expected={c_e!r}). "
            "Verify character formatting, escaping, or string manipulation around this position."
        )

    if isinstance(actual, dict) and isinstance(expected, dict):
        missing_keys = [k for k in expected if k not in actual]
        extra_keys = [k for k in actual if k not in expected]
        common_keys = [k for k in actual if k in expected]
        val_diff_keys = [k for k in common_keys if actual[k] != expected[k]]

        hints = []
        if missing_keys:
            hints.append(f"missing expected key(s): {missing_keys}")
        if extra_keys:
            hints.append(f"unexpected extra key(s): {extra_keys}")
        if val_diff_keys:
            hints.append(f"differing values for key(s): {val_diff_keys}")

        hint_desc = "; ".join(hints) if hints else "dictionary contents differ"
        return (
            f"Dictionary mismatch ({hint_desc}). "
            "Check dictionary construction, field serialization, or schema mapping logic."
        )

    if isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
        if len(actual) != len(expected):
            return (
                f"Sequence length mismatch: actual has {len(actual)} items, expected has {len(expected)}. "
                "Check loop iteration, filtering conditions, or item appending logic."
            )
        idx_str = f" at index {first_diff_idx}" if first_diff_idx is not None else ""
        return (
            f"Sequence elements differ{idx_str}. "
            "Verify item construction, sorting order, or transformation logic at this position."
        )

    if type(actual) is not type(expected):
        return (
            f"Type mismatch: actual is of type '{type(actual).__name__}' but expected '{type(expected).__name__}'. "
            "Check function return type or explicit type casting."
        )

    if isinstance(actual, (int, float, complex)) and isinstance(expected, (int, float, complex)):
        try:
            diff = actual - expected
            return (
                f"Numeric value mismatch: actual is {actual}, expected is {expected} (difference: {diff:+}). "
                "Verify calculation, rounding, or offset logic."
            )
        except Exception:
            pass

    return (
        f"Assertion condition '{op}' failed between actual and expected values. "
        "Inspect the logic computing the actual value to ensure it matches expected criteria."
    )


def explain_string_diff(actual: str, expected: str) -> Tuple[str, Optional[int]]:
    """Generate exact plain-English mismatch explanation and first differing index for strings."""
    min_len = min(len(actual), len(expected))
    first_diff = None
    for i in range(min_len):
        if actual[i] != expected[i]:
            first_diff = i
            break

    act_short = repr(actual)
    exp_short = repr(expected)

    if first_diff is None:
        if len(actual) < len(expected):
            first_diff = len(actual)
            missing = expected[len(actual):]
            missing_repr = repr(missing)
            summary = (
                f"MISMATCH: Actual string ({act_short}, {len(actual)} chars) is missing trailing "
                f"{missing_repr} present in Expected string ({exp_short}, {len(expected)} chars). "
                f"Difference at index {first_diff}."
            )
            return summary, first_diff
        elif len(actual) > len(expected):
            first_diff = len(expected)
            extra = actual[len(expected):]
            extra_repr = repr(extra)
            summary = (
                f"MISMATCH: Actual string ({act_short}, {len(actual)} chars) has unexpected trailing "
                f"{extra_repr} not present in Expected string ({exp_short}, {len(expected)} chars). "
                f"Difference at index {first_diff}."
            )
            return summary, first_diff
        else:
            return "Strings are identical.", None
    else:
        c_act = actual[first_diff]
        c_exp = expected[first_diff]
        case_note = ""
        if c_act.lower() == c_exp.lower():
            case_note = f" (Casing difference: Actual has '{c_act}', Expected has '{c_exp}')"
        summary = (
            f"MISMATCH: Actual string ({act_short}, {len(actual)} chars) differs from "
            f"Expected string ({exp_short}, {len(expected)} chars) at index {first_diff}. "
            f"Actual has {repr(c_act)} (hex: {hex(ord(c_act))}), Expected has {repr(c_exp)} (hex: {hex(ord(c_exp))}){case_note}."
        )
        return summary, first_diff


def generate_string_char_diff(actual: str, expected: str, first_diff_idx: Optional[int]) -> str:
    """Generate unified and character-by-character diff showing exact differences."""
    diff_lines: List[str] = []
    act_repr = repr(actual)
    exp_repr = repr(expected)
    diff_lines.append(f"- Expected: {exp_repr} (len={len(expected)})")
    diff_lines.append(f"+ Actual:   {act_repr} (len={len(actual)})")

    # Character-level ndiff
    nd = list(difflib.ndiff([exp_repr], [act_repr]))
    if len(nd) > 2:
        diff_lines.append("  ndiff:")
        for line in nd:
            diff_lines.append(f"    {line}")

    # Multiline unified diff if string has newlines
    if "\n" in actual or "\n" in expected:
        exp_lines = [l + "\n" for l in expected.splitlines()] or ["\n"]
        act_lines = [l + "\n" for l in actual.splitlines()] or ["\n"]
        ud = list(difflib.unified_diff(exp_lines, act_lines, fromfile="expected", tofile="actual"))
        if ud:
            diff_lines.append("  unified diff:")
            for line in ud:
                diff_lines.append(f"    {line.rstrip()}")

    # Exact index breakdown
    if first_diff_idx is not None:
        if first_diff_idx < len(actual) and first_diff_idx < len(expected):
            c_act = actual[first_diff_idx]
            c_exp = expected[first_diff_idx]
            diff_lines.append(
                f"  Diff at index {first_diff_idx}: actual={c_act!r} (hex: {hex(ord(c_act))}) vs expected={c_exp!r} (hex: {hex(ord(c_exp))})"
            )
        elif first_diff_idx == len(actual) and len(actual) < len(expected):
            c_exp = expected[first_diff_idx]
            diff_lines.append(
                f"  Diff at index {first_diff_idx}: actual string ended (length {len(actual)}) vs expected={c_exp!r} (hex: {hex(ord(c_exp))})"
            )
        elif first_diff_idx == len(expected) and len(actual) > len(expected):
            c_act = actual[first_diff_idx]
            diff_lines.append(
                f"  Diff at index {first_diff_idx}: actual={c_act!r} (hex: {hex(ord(c_act))}) vs expected string ended (length {len(expected)})"
            )

    return "\n".join(diff_lines)


def format_sequence_mismatch(actual: Any, expected: Any) -> Tuple[str, str, Optional[int]]:
    """Generate detailed sequence comparison showing length differences and first differing element.

    Returns (explanation_summary, detailed_diff_text, first_diff_index).
    """
    seq_name = type(actual).__name__.capitalize()
    len_a = len(actual)
    len_b = len(expected)
    min_len = min(len_a, len_b)

    first_diff_idx = None
    for i in range(min_len):
        if actual[i] != expected[i]:
            first_diff_idx = i
            break

    if first_diff_idx is None and len_a != len_b:
        first_diff_idx = min_len

    summary_parts = []
    if len_a != len_b:
        summary_parts.append(f"length differs (actual has {len_a}, expected has {len_b})")
    if first_diff_idx is not None and first_diff_idx < min_len:
        summary_parts.append(f"first item differs at index {first_diff_idx}")
    elif first_diff_idx is not None:
        summary_parts.append(f"prefix matches through index {first_diff_idx - 1 if first_diff_idx > 0 else 0}")

    explanation = f"{seq_name.upper()} MISMATCH: {'; '.join(summary_parts) if summary_parts else 'items differ'}."

    lines = ["📋 SEQUENCE / LIST MISMATCH:"]
    lines.append("  Length difference:")
    lines.append(f"    Actual length:   {len_a}")
    lines.append(f"    Expected length: {len_b}")
    lines.append(f"    Difference:      {len_a - len_b:+d} item(s)")

    if first_diff_idx is not None:
        lines.append(f"  First differing element at index {first_diff_idx}:")
        if first_diff_idx < len_a:
            lines.append(f"    Actual:   {format_value_repr(actual[first_diff_idx])} ({type(actual[first_diff_idx]).__name__})")
        else:
            lines.append(f"    Actual:   [End of sequence - length {len_a}]")
        if first_diff_idx < len_b:
            lines.append(f"    Expected: {format_value_repr(expected[first_diff_idx])} ({type(expected[first_diff_idx]).__name__})")
        else:
            lines.append(f"    Expected: [End of sequence - length {len_b}]")
    else:
        lines.append("  All corresponding elements match.")

    return explanation, "\n".join(lines), first_diff_idx


def generate_sequence_diff(actual: Any, expected: Any, first_diff_idx: Optional[int]) -> str:
    """Generate unified diff for lists, tuples, or sequences."""
    _, diff_str, _ = format_sequence_mismatch(actual, expected)
    return diff_str


def format_dict_mismatch(actual: dict, expected: dict) -> Tuple[str, str]:
    """Generate detailed dict comparison showing missing, extra, and differing keys.

    Returns (explanation_summary, detailed_diff_text).
    """
    missing_keys = sorted([k for k in expected if k not in actual], key=lambda x: str(x))
    extra_keys = sorted([k for k in actual if k not in expected], key=lambda x: str(x))
    common_keys = sorted([k for k in actual if k in expected], key=lambda x: str(x))
    val_diffs = {k: (actual[k], expected[k]) for k in common_keys if actual[k] != expected[k]}

    summary_parts = []
    if missing_keys:
        summary_parts.append(f"missing {len(missing_keys)} key(s): {missing_keys}")
    if extra_keys:
        summary_parts.append(f"extra {len(extra_keys)} key(s): {extra_keys}")
    if val_diffs:
        summary_parts.append(f"{len(val_diffs)} value difference(s) in shared keys")

    explanation = f"DICT MISMATCH: {'; '.join(summary_parts) if summary_parts else 'contents differ'}."

    lines = ["📋 DICTIONARY / JSON MISMATCH:"]
    lines.append("  Missing keys (in expected but not actual):")
    if missing_keys:
        for k in missing_keys:
            lines.append(f"    - {k!r}: expected value {expected[k]!r}")
    else:
        lines.append("    (None)")

    lines.append("  Extra keys (in actual but not expected):")
    if extra_keys:
        for k in extra_keys:
            lines.append(f"    + {k!r}: actual value {actual[k]!r}")
    else:
        lines.append("    (None)")

    lines.append("  Value differences for shared keys:")
    if val_diffs:
        for k, (a_v, e_v) in val_diffs.items():
            lines.append(f"    * Key {k!r}:")
            lines.append(f"        Actual:   {format_value_repr(a_v)} ({type(a_v).__name__})")
            lines.append(f"        Expected: {format_value_repr(e_v)} ({type(e_v).__name__})")
    else:
        lines.append("    (None)")

    return explanation, "\n".join(lines)


def generate_dict_diff(actual: dict, expected: dict) -> str:
    """Generate key and value diff for mappings."""
    _, diff_str = format_dict_mismatch(actual, expected)
    return diff_str


def build_assertion_diagnostic(
    actual: Any,
    expected: Any,
    op_str: str,
    code_str: str,
    msg: Optional[str] = None,
) -> AssertionDiagnostic:
    """Build a comprehensive, structured AssertionDiagnostic with deep diffs."""
    actual_type = type(actual).__name__ if actual is not None else "unknown"
    actual_repr = format_value_repr(actual)
    actual_len = get_length(actual)

    expected_type = type(expected).__name__ if expected is not None else "unknown"
    expected_repr = format_value_repr(expected)
    expected_len = get_length(expected)

    explanation, diff_str, first_diff_idx = explain_assertion_failure(
        actual, op_str, expected, msg or ""
    )

    divergence_detail = None
    escape_breakdown = None
    dict_diff_summary = None
    sequence_diff_summary = None

    if isinstance(actual, str) and isinstance(expected, str):
        first_diff_idx, divergence_detail = compute_string_divergence(actual, expected)
        escape_breakdown = format_escape_breakdown(actual, expected)
    elif isinstance(actual, dict) and isinstance(expected, dict):
        _, dict_diff_summary = format_dict_mismatch(actual, expected)
    elif isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
        _, sequence_diff_summary, first_diff_idx = format_sequence_mismatch(actual, expected)

    root_hint = generate_root_cause_hint(actual, op_str, expected, first_diff_idx)

    return AssertionDiagnostic(
        assertion_code=code_str,
        op=op_str,
        actual_type=actual_type,
        actual_repr=actual_repr,
        actual_length=actual_len,
        expected_type=expected_type,
        expected_repr=expected_repr,
        expected_length=expected_len,
        char_diff=diff_str,
        first_diff_index=first_diff_idx,
        divergence_detail=divergence_detail,
        escape_breakdown=escape_breakdown,
        dict_diff_summary=dict_diff_summary,
        sequence_diff_summary=sequence_diff_summary,
        root_cause_hint=root_hint,
        message=msg if msg else None,
        explanation=explanation,
        remediation_hint=root_hint,
    )


def explain_assertion_failure(
    actual: Any, op: str, expected: Any, msg: str = ""
) -> Tuple[str, Optional[str], Optional[int]]:
    """Compute plain-English diagnostic summary, detailed diff, and difference index."""
    first_diff_idx = None
    diff_str = None

    # Handle membership operators first (operands naturally have different types)
    if op == "in":
        explanation = f"MEMBERSHIP FAILED: {format_value_repr(actual)} was not found inside {format_value_repr(expected)}."
        diff_str = f"Target {format_value_repr(actual)} not in container {format_value_repr(expected)}"
        return explanation, diff_str, None
    elif op == "not in":
        explanation = f"FORBIDDEN MEMBERSHIP: {format_value_repr(actual)} was unexpectedly found inside {format_value_repr(expected)}."
        diff_str = f"Target {format_value_repr(actual)} unexpectedly present in {format_value_repr(expected)}"
        return explanation, diff_str, None
    elif op in ("<", "<=", ">", ">="):
        explanation = f"COMPARISON FAILED: Condition '{format_value_repr(actual)} {op} {format_value_repr(expected)}' evaluated to False."
        diff_str = f"- Expected condition: actual {op} expected\n  Actual:   {format_value_repr(actual)}\n  Expected: {format_value_repr(expected)}"
        return explanation, diff_str, None
    elif op == "is":
        explanation = f"IDENTITY MISMATCH: Expected {format_value_repr(actual)} is {format_value_repr(expected)} (id(actual)={id(actual)}, id(expected)={id(expected)})."
        return explanation, None, None
    elif op == "is not":
        explanation = f"IDENTITY MATCH: Expected objects not to be identical, but id(actual) == id(expected) == {id(actual)}."
        return explanation, None, None

    # Case 1: Types differ for equality checks
    if type(actual) is not type(expected):
        act_t = type(actual).__name__
        exp_t = type(expected).__name__
        act_r = format_value_repr(actual)
        exp_r = format_value_repr(expected)
        explanation = f"TYPE MISMATCH: Actual is of type '{act_t}' ({act_r}), Expected is of type '{exp_t}' ({exp_r})."
        diff_str = f"- Expected ({exp_t}): {exp_r}\n+ Actual   ({act_t}): {act_r}"
        return explanation, diff_str, None

    # Case 2: Both are strings
    if isinstance(actual, str) and isinstance(expected, str):
        explanation, first_diff_idx = explain_string_diff(actual, expected)
        diff_str = generate_string_char_diff(actual, expected, first_diff_idx)
        return explanation, diff_str, first_diff_idx

    # Case 3: Both are lists or tuples
    if isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
        explanation, diff_str, first_diff_idx = format_sequence_mismatch(actual, expected)
        return explanation, diff_str, first_diff_idx

    # Case 4: Both are dicts
    if isinstance(actual, dict) and isinstance(expected, dict):
        explanation, diff_str = format_dict_mismatch(actual, expected)
        return explanation, diff_str, None

    # Case 5: Both are sets
    if isinstance(actual, (set, frozenset)) and isinstance(expected, (set, frozenset)):
        missing = set(expected) - set(actual)
        extra = set(actual) - set(expected)
        parts = []
        if missing:
            parts.append(f"missing elements {list(missing)}")
        if extra:
            parts.append(f"unexpected elements {list(extra)}")
        explanation = f"SET MISMATCH: {'; '.join(parts)}."
        diff_str = f"- Missing from actual: {list(missing)}\n+ Extra in actual: {list(extra)}"
        return explanation, diff_str, None

    # Case 6: Numbers
    if isinstance(actual, (int, float, complex)) and isinstance(expected, (int, float, complex)):
        try:
            diff = actual - expected
            explanation = f"VALUE MISMATCH: Actual value {actual} does not equal Expected value {expected} (difference: {diff:+})."
        except Exception:
            explanation = f"VALUE MISMATCH: Actual value {actual} does not equal Expected value {expected}."
        diff_str = f"- Expected: {expected}\n+ Actual:   {actual}"
        return explanation, diff_str, None

    # Default fallback
    explanation = f"VALUE MISMATCH: Expected {format_value_repr(expected)}, but got {format_value_repr(actual)}."
    diff_str = f"- Expected: {format_value_repr(expected)}\n+ Actual:   {format_value_repr(actual)}"
    return explanation, diff_str, None


def explain_exception_operation(
    exc: BaseException,
    line_code: str,
    failing_frame: Optional[StackFrameInfo],
) -> str:
    """Generate clear, plain-English explanation of what operation triggered the exception."""
    exc_type = type(exc).__name__
    exc_msg = str(exc)

    if exc_type == "AttributeError":
        m = re.search(r"'(.*?)' object has no attribute '(.*?)'", exc_msg)
        if m:
            obj_type, attr = m.group(1), m.group(2)
            return (
                f"Attribute access '.{attr}' failed: Target object is of type '{obj_type}' "
                f"which does not possess this attribute."
            )
        return f"Attribute lookup failed: {exc_msg}"

    elif exc_type == "TypeError":
        if "unsupported operand type" in exc_msg:
            return f"Incompatible types for operator: {exc_msg}."
        elif "missing" in exc_msg and "required positional argument" in exc_msg:
            return f"Function call missing argument(s): {exc_msg}."
        elif "takes" in exc_msg and "positional argument" in exc_msg:
            return f"Function call argument count mismatch: {exc_msg}."
        elif "unexpected keyword argument" in exc_msg:
            return f"Function received unexpected keyword argument: {exc_msg}."
        elif "'NoneType' object is not" in exc_msg:
            return f"Operation on None value: {exc_msg}."
        return f"Type mismatch or invalid operation: {exc_msg}"

    elif exc_type == "KeyError":
        return f"Dictionary key lookup failed: Key {exc_msg} does not exist in mapping."

    elif exc_type == "IndexError":
        return f"Sequence index out of bounds: {exc_msg}."

    elif exc_type == "ZeroDivisionError":
        return "Division or modulo operation failed: Denominator evaluated to zero."

    elif exc_type == "ValueError":
        return f"Invalid value supplied to function or operation: {exc_msg}."

    elif exc_type == "FileNotFoundError":
        return f"Filesystem path does not exist: {exc_msg}."

    elif exc_type in ("ModuleNotFoundError", "ImportError"):
        return f"Module import failed: {exc_msg}."

    elif exc_type == "NameError":
        return f"Name reference failed: {exc_msg}. Variable or symbol is not defined in current scope."

    elif exc_type == "UnboundLocalError":
        return f"Local variable referenced before assignment: {exc_msg}."

    return f"Operation failed with {exc_type}: {exc_msg}"


def matches_expected_exception(exc: BaseException, expect_str: Optional[str]) -> bool:
    """Check if the raised exception matches the expected exception specification.

    Supports:
    - Exception class name: 'ValueError', 'KeyError', 'AssertionError'
    - Fully-qualified name: 'pydantic.ValidationError', 'builtins.ValueError'
    - Comma-separated list: 'ValueError, TypeError'
    - Class inheritance / MRO matching: subclass matches parent type name
    - Case-insensitive fallback
    """
    if not expect_str:
        return False

    targets = [t.strip() for t in expect_str.split(",") if t.strip()]
    exc_type = type(exc)
    exc_type_name = exc_type.__name__
    exc_full_name = f"{exc_type.__module__}.{exc_type_name}"
    mro_names = {cls.__name__ for cls in inspect.getmro(exc_type)}

    for target in targets:
        # Direct class name match
        if target == exc_type_name:
            return True
        # Full module.class match or suffix match
        if target == exc_full_name or exc_full_name.endswith(f".{target}"):
            return True
        # MRO / inheritance match (e.g. target is 'Exception', 'ValueError', etc.)
        if target in mro_names:
            return True
        # Special case: ReproAssertionError is an AssertionError
        if isinstance(exc, ReproAssertionError) and target in ("AssertionError", "ReproAssertionError"):
            return True
        # Case-insensitive comparison
        if target.lower() == exc_type_name.lower() or any(target.lower() == m.lower() for m in mro_names):
            return True

    return False


# =============================================================================
# Runtime Assertion Interceptors
# =============================================================================

def _evaluate_op(left: Any, op_str: str, right: Any) -> bool:
    """Evaluate comparison operator safely."""
    if op_str == "==":
        return bool(left == right)
    elif op_str == "!=":
        return bool(left != right)
    elif op_str == "<":
        return bool(left < right)
    elif op_str == "<=":
        return bool(left <= right)
    elif op_str == ">":
        return bool(left > right)
    elif op_str == ">=":
        return bool(left >= right)
    elif op_str == "is":
        return left is right
    elif op_str == "is not":
        return left is not right
    elif op_str == "in":
        return bool(left in right)
    elif op_str == "not in":
        return bool(left not in right)
    return False


def __repro_assert__(left: Any, op_str: str, right: Any, msg: Any, code_str: str, lineno: int) -> None:
    """Injected runtime helper that intercepts assert statements and captures frames."""
    passed = _evaluate_op(left, op_str, right)
    if not passed:
        frame = inspect.currentframe().f_back if inspect.currentframe() else None
        raise ReproAssertionError(
            actual=left,
            expected=right,
            op=op_str,
            code_str=code_str,
            lineno=lineno,
            msg=str(msg) if msg else "",
            frame=frame,
        )


def __repro_assert_truthy__(val: Any, msg: Any, code_str: str, lineno: int) -> None:
    """Injected runtime helper that intercepts boolean assertions."""
    if not bool(val):
        frame = inspect.currentframe().f_back if inspect.currentframe() else None
        raise ReproAssertionError(
            actual=val,
            expected=True,
            op="truthy",
            code_str=code_str,
            lineno=lineno,
            msg=str(msg) if msg else "",
            frame=frame,
        )


# =============================================================================
# Code Healing and Normalization
# =============================================================================

def auto_heal_unterminated_strings(code: str) -> str:
    """Scan and heal unterminated single-line string literals that contain raw unescaped newlines."""
    out: List[str] = []
    state = "NORMAL"
    i = 0
    n = len(code)

    while i < n:
        c = code[i]

        if state == "NORMAL":
            if c == "#":
                end_comment = code.find("\n", i)
                if end_comment == -1:
                    out.append(code[i:])
                    break
                else:
                    out.append(code[i:end_comment])
                    i = end_comment
                    continue

            if code.startswith("'''", i):
                state = "TRIPLE_SINGLE"
                out.append("'''")
                i += 3
            elif code.startswith('"""', i):
                state = "TRIPLE_DOUBLE"
                out.append('"""')
                i += 3
            elif c == "'":
                state = "SINGLE_SINGLE"
                out.append("'")
                i += 1
            elif c == '"':
                state = "SINGLE_DOUBLE"
                out.append('"')
                i += 1
            else:
                out.append(c)
                i += 1

        elif state == "TRIPLE_SINGLE":
            if c == "\\":
                out.append(c)
                i += 1
                if i < n:
                    out.append(code[i])
                    i += 1
            elif code.startswith("'''", i):
                state = "NORMAL"
                out.append("'''")
                i += 3
            else:
                out.append(c)
                i += 1

        elif state == "TRIPLE_DOUBLE":
            if c == "\\":
                out.append(c)
                i += 1
                if i < n:
                    out.append(code[i])
                    i += 1
            elif code.startswith('"""', i):
                state = "NORMAL"
                out.append('"""')
                i += 3
            else:
                out.append(c)
                i += 1

        elif state == "SINGLE_SINGLE":
            if c == "\\":
                out.append(c)
                i += 1
                if i < n:
                    out.append(code[i])
                    i += 1
            elif c == "'":
                out.append(c)
                state = "NORMAL"
                i += 1
            elif c == "\r":
                if i + 1 < n and code[i + 1] == "\n":
                    out.append("\\r\\n")
                    i += 2
                else:
                    out.append("\\r")
                    i += 1
            elif c == "\n":
                out.append("\\n")
                i += 1
            else:
                out.append(c)
                i += 1

        elif state == "SINGLE_DOUBLE":
            if c == "\\":
                out.append(c)
                i += 1
                if i < n:
                    out.append(code[i])
                    i += 1
            elif c == '"':
                out.append(c)
                state = "NORMAL"
                i += 1
            elif c == "\r":
                if i + 1 < n and code[i + 1] == "\n":
                    out.append("\\r\\n")
                    i += 2
                else:
                    out.append("\\r")
                    i += 1
            elif c == "\n":
                out.append("\\n")
                i += 1
            else:
                out.append(c)
                i += 1

    return "".join(out)


def sanitize_assertion_code(raw: str) -> str:
    """Sanitize assertion input string against outer quoting artifacts, markdown fences, and JSON escaped quotes."""
    code = raw.strip()

    # Step 1: Strip markdown code blocks and outer redundant quotes iteratively
    for _ in range(10):
        prev = code
        code = code.strip()

        # Check markdown fences: ```python ... ``` or ```py ... ``` or ``` ... ```
        fence_match = re.match(r"^```[a-zA-Z0-9_\-\+]*\s*\n?(.*?)\n?```$", code, re.DOTALL)
        if fence_match:
            code = fence_match.group(1).strip()
            continue

        # Check escaped outer quotes: \"...\" or \'...\'
        if len(code) >= 4:
            if (code.startswith('\\"') and code.endswith('\\"')) or (code.startswith("\\'") and code.endswith("\\'")):
                code = code[2:-2].strip()
                continue

        # Check triple quotes: """...""" or '''...'''
        if len(code) >= 6:
            if (code.startswith('"""') and code.endswith('"""')) or (code.startswith("'''") and code.endswith("'''")):
                code = code[3:-3].strip()
                continue

        # Check single outer quotes: "..." or '...'
        if len(code) >= 2:
            for q in ('"', "'"):
                if code.startswith(q) and code.endswith(q):
                    candidate = code[1:-1].strip()
                    should_strip = False
                    try:
                        tree = ast.parse(code)
                        # If parsed as a single string literal constant, outer quotes are a redundant wrapper
                        if len(tree.body) == 1 and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
                            if isinstance(tree.body[0].value.value, str):
                                should_strip = True
                    except SyntaxError:
                        should_strip = True

                    if should_strip:
                        code = candidate
                        break

        if code == prev:
            break

    # Step 2: Normalize escaped quotes if passed literally due to double-escaping in JSON
    if '\\"' in code or "\\'" in code:
        needs_norm = False
        try:
            tree = ast.parse(code)
            # If it parsed as a single string constant, it's wrapped in quotes
            if (
                len(tree.body) == 1
                and isinstance(tree.body[0], ast.Expr)
                and isinstance(tree.body[0].value, ast.Constant)
                and isinstance(tree.body[0].value.value, str)
            ):
                needs_norm = True
        except SyntaxError:
            needs_norm = True

        if needs_norm:
            code = code.replace('\\"', '"').replace("\\'", "'")

    # Step 3: Check if code is a string literal containing python code (e.g. wrapped in quotes that parsed as string)
    try:
        tree = ast.parse(code)
        if len(tree.body) == 1 and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
            if isinstance(tree.body[0].value.value, str):
                inner_str = tree.body[0].value.value.strip()
                try:
                    inner_tree = ast.parse(inner_str)
                    if inner_tree.body and not (
                        len(inner_tree.body) == 1
                        and isinstance(inner_tree.body[0], ast.Expr)
                        and isinstance(inner_tree.body[0].value, ast.Constant)
                    ):
                        code = inner_str
                except SyntaxError:
                    pass
    except SyntaxError:
        pass

    # Normalize newlines if literal \n was passed improperly
    if "\\n" in code and "\n" not in code:
        code = code.replace("\\n", "\n")

    code = textwrap.dedent(code).strip()
    return code


def clean_and_normalize_code(raw_args: Union[List[str], str]) -> str:
    """Extract code from arbitrary CLI arguments or string, stripping fences, outer quotes, and normalizing indentation."""
    if isinstance(raw_args, str):
        code = raw_args.strip()
    else:
        if any("\n" in t for t in raw_args):
            code = "\n".join(raw_args).strip()
        else:
            code = " ".join(raw_args).strip()

    code = sanitize_assertion_code(code)
    return auto_heal_unterminated_strings(code)


# =============================================================================
# Omnivorous AST Transformer with Assertion Rewriting
# =============================================================================

class OmnivorousCodeTransformer(ast.NodeTransformer):
    """AST Transformer that converts bare comparisons and asserts into introspectable calls."""

    def __init__(self) -> None:
        super().__init__()
        self.transformed_comparisons = 0
        self.explicit_asserts = 0
        self.defined_test_funcs: Set[str] = set()
        self.called_funcs: Set[str] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        name = node.name.lower()
        if name.startswith("test_") or name.endswith("_test") or name == "test":
            self.defined_test_funcs.add(node.name)
        return self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        name = node.name.lower()
        if name.startswith("test_") or name.endswith("_test") or name == "test":
            self.defined_test_funcs.add(node.name)
        return self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> ast.AST:
        if isinstance(node.func, ast.Name):
            self.called_funcs.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            self.called_funcs.add(node.func.attr)
        return self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> ast.AST:
        self.explicit_asserts += 1
        lineno = getattr(node, "lineno", 1)
        code_str = ast.unparse(node) if hasattr(ast, "unparse") else "assert"
        msg_node = node.msg if node.msg is not None else ast.Constant(value="")

        # Rewrite single-comparison asserts to capture operands directly
        if isinstance(node.test, ast.Compare) and len(node.test.ops) == 1:
            op_cls = type(node.test.ops[0])
            op_str = OP_MAP.get(op_cls, "==")
            call = ast.Call(
                func=ast.Name(id="__repro_assert__", ctx=ast.Load()),
                args=[
                    node.test.left,
                    ast.Constant(value=op_str),
                    node.test.comparators[0],
                    msg_node,
                    ast.Constant(value=code_str),
                    ast.Constant(value=lineno),
                ],
                keywords=[],
            )
            return ast.copy_location(ast.Expr(value=call), node)

        # Other asserts (calls, boolean values, multi-comparisons)
        call = ast.Call(
            func=ast.Name(id="__repro_assert_truthy__", ctx=ast.Load()),
            args=[
                node.test,
                msg_node,
                ast.Constant(value=code_str),
                ast.Constant(value=lineno),
            ],
            keywords=[],
        )
        return ast.copy_location(ast.Expr(value=call), node)

    def visit_Expr(self, node: ast.Expr) -> ast.AST:
        # If the statement is a standalone comparison expression: `a == b` or `x in y`
        # Auto-transform it into an introspected assertion
        if isinstance(node.value, ast.Compare) and len(node.value.ops) == 1:
            self.transformed_comparisons += 1
            lineno = getattr(node, "lineno", 1)
            op_cls = type(node.value.ops[0])
            op_str = OP_MAP.get(op_cls, "==")
            code_str = ast.unparse(node.value) if hasattr(ast, "unparse") else "comparison"
            msg = f"Check failed (auto-asserted): {code_str}"
            call = ast.Call(
                func=ast.Name(id="__repro_assert__", ctx=ast.Load()),
                args=[
                    node.value.left,
                    ast.Constant(value=op_str),
                    node.value.comparators[0],
                    ast.Constant(value=msg),
                    ast.Constant(value=f"assert {code_str}"),
                    ast.Constant(value=lineno),
                ],
                keywords=[],
            )
            return ast.copy_location(ast.Expr(value=call), node)

        return self.generic_visit(node)


def prepare_executable_code(code: str) -> Tuple[str, bool, int]:
    """Parse, transform, and auto-wire code for deterministic execution."""
    code = auto_heal_unterminated_strings(code)

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code, False, 0

    transformer = OmnivorousCodeTransformer()
    tree = transformer.visit(tree)
    ast.fix_missing_locations(tree)

    has_checks = (transformer.explicit_asserts > 0) or (transformer.transformed_comparisons > 0)
    check_count = transformer.explicit_asserts + transformer.transformed_comparisons

    # Auto-invoke uncalled test functions
    uncalled_tests = transformer.defined_test_funcs - transformer.called_funcs
    if uncalled_tests:
        has_checks = True
        runner_lines = ["\n# --- Auto-generated Test Invocations by repro-check ---"]
        for test_fn in sorted(uncalled_tests):
            runner_lines.append(f"{test_fn}()")
        transformed_code = ast.unparse(tree) + "\n" + "\n".join(runner_lines)
    else:
        transformed_code = ast.unparse(tree)

    return transformed_code, has_checks, check_count


# =============================================================================
# Workspace and Probe Circuit Breaker Management
# =============================================================================

def get_workspace_dir() -> pathlib.Path:
    """Deterministically locate the active repository workspace."""
    try:
        f = sys._getframe()
        while f:
            if "_orig_cwd" in f.f_locals:
                p = pathlib.Path(f.f_locals["_orig_cwd"])
                if p.is_dir() and (
                    (p / ".git").exists()
                    or (p / "pyproject.toml").exists()
                    or (p / "setup.py").exists()
                ):
                    return p.resolve()
            f = f.f_back
    except Exception:
        pass

    for env_var in ("SWEGEMMA_WORKSPACE", "WORKSPACE_DIR"):
        val = os.environ.get(env_var)
        if val:
            p = pathlib.Path(val)
            if p.is_dir():
                return p.resolve()

    ws_standard = pathlib.Path("/workspace")
    if ws_standard.is_dir():
        return ws_standard.resolve()

    return pathlib.Path.cwd().resolve()


def is_workspace_path(path_str: str, ws: pathlib.Path) -> bool:
    """Check if a file path belongs to the active target workspace."""
    if not path_str:
        return False
    try:
        p = pathlib.Path(path_str).resolve()
        ws_res = ws.resolve()
        return ws_res in p.parents or p == ws_res
    except Exception:
        return False


def get_probe_count() -> int:
    """Retrieve the current exploratory probe count."""
    try:
        if PROBE_COUNT_FILE.exists():
            return int(PROBE_COUNT_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        pass
    return 0


def increment_probe_count() -> int:
    """Increment exploratory probe count atomically."""
    cnt = get_probe_count() + 1
    try:
        PROBE_COUNT_FILE.write_text(str(cnt), encoding="utf-8")
    except Exception:
        pass
    return cnt


def reset_probe_count() -> None:
    """Reset exploratory probe count to 0."""
    try:
        if PROBE_COUNT_FILE.exists():
            PROBE_COUNT_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def check_and_record_probe_payload(code: str, expect_exception: bool) -> Tuple[bool, int]:
    """Check if this exact probe payload has been executed before.

    Returns:
        (is_duplicate, current_execution_count)
    """
    import hashlib
    import json

    payload_normalized = f"{code.strip()}::expect_exception={expect_exception}"
    payload_hash = hashlib.md5(payload_normalized.encode("utf-8")).hexdigest()

    history: Dict[str, int] = {}
    try:
        if PROBE_HISTORY_FILE.exists():
            history = json.loads(PROBE_HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        history = {}

    count = history.get(payload_hash, 0)
    history[payload_hash] = count + 1

    try:
        PROBE_HISTORY_FILE.write_text(json.dumps(history), encoding="utf-8")
    except Exception:
        pass

    return (count > 0, count + 1)


def reset_probe_history() -> None:
    """Reset probe history cache."""
    try:
        if PROBE_HISTORY_FILE.exists():
            PROBE_HISTORY_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def workspace_has_modifications(ws: pathlib.Path) -> bool:
    """Check if the workspace currently has uncommitted modified files."""
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0 and res.stdout.strip():
            return True
    except Exception:
        pass
    return False


def is_probe_circuit_breaker_active(ws: pathlib.Path) -> bool:
    """Check if the 2-probe circuit breaker is tripped."""
    if workspace_has_modifications(ws):
        return False
    return get_probe_count() >= 2


# =============================================================================
# Path Containment Guard (Strict /tmp Isolation)
# =============================================================================

class PathContainmentGuard:
    """Active containment guard ensuring all scratch files remain strictly in /tmp.

    Prevents and cleans up any accidental /workspace/tmp/... file creation
    that could pollute git status.
    """

    def __init__(self, ws: pathlib.Path):
        self.ws = ws.resolve()
        self.ws_tmp = self.ws / "tmp"
        self.pre_existing_files: Set[pathlib.Path] = set()
        if self.ws_tmp.exists():
            try:
                self.pre_existing_files = {p.resolve() for p in self.ws_tmp.rglob("*")}
            except Exception:
                pass

    def cleanup_pollution(self) -> List[str]:
        """Purge any scratch files or directories created inside /workspace/tmp."""
        cleaned: List[str] = []
        if not self.ws_tmp.exists():
            return cleaned

        try:
            current_files = {p.resolve() for p in self.ws_tmp.rglob("*")}
            new_files = current_files - self.pre_existing_files
            for p in sorted(new_files, key=lambda x: len(str(x)), reverse=True):
                try:
                    if p.is_file() or p.is_symlink():
                        p.unlink(missing_ok=True)
                        cleaned.append(str(p))
                    elif p.is_dir() and not any(p.iterdir()):
                        p.rmdir()
                        cleaned.append(str(p))
                except Exception:
                    pass

            if (
                self.ws_tmp.is_dir()
                and not any(self.ws_tmp.iterdir())
                and self.ws_tmp.resolve() not in self.pre_existing_files
            ):
                self.ws_tmp.rmdir()
                cleaned.append(str(self.ws_tmp))
        except Exception:
            pass

        return cleaned


def assert_scratch_path_contained(path: pathlib.Path, ws: pathlib.Path) -> None:
    """Guard that scratch files/directories are strictly outside the workspace."""
    resolved = path.resolve()
    ws_resolved = ws.resolve()
    if resolved == ws_resolved or ws_resolved in resolved.parents:
        raise RuntimeError(
            f"[repro-check] Path containment violation: Scratch path {resolved} is inside workspace {ws_resolved}!"
        )


# =============================================================================
# In-Harness Process Execution
# =============================================================================

def run_harness(
    script_path: pathlib.Path,
    report_path: pathlib.Path,
    expect_exception: Optional[str] = None,
) -> None:
    """Internal runner executed inside isolated subprocess with diagnostic recording."""
    # Defensive Sandboxing: Fast-fail socket timeouts to prevent network hanging
    try:
        import socket
        socket.setdefaulttimeout(3.0)
    except Exception:
        pass

    # Memory runaway guard (prevents infinite while True append loops from crashing container)
    try:
        import resource
        curr_soft, curr_hard = resource.getrlimit(resource.RLIMIT_AS)
        limit_1g = 1024 * 1024 * 1024
        if curr_hard == resource.RLIM_INFINITY or curr_hard >= limit_1g:
            resource.setrlimit(resource.RLIMIT_AS, (min(limit_1g, curr_hard), curr_hard))
    except Exception:
        pass

    source_code = script_path.read_text(encoding="utf-8")

    global_ns: Dict[str, Any] = {
        "__name__": "__main__",
        "__file__": str(script_path),
        "__doc__": None,
        "__builtins__": __builtins__,
        "__repro_assert__": __repro_assert__,
        "__repro_assert_truthy__": __repro_assert_truthy__,
    }

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    report: Optional[DiagnosticReport] = None

    try:
        compiled = compile(source_code, str(script_path), "exec")
        with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
            exec(compiled, global_ns)

        if expect_exception:
            report = DiagnosticReport(
                status="missing_exception",
                exit_code=1,
                summary=f"Expected exception '{expect_exception}' was NOT raised. Execution completed normally.",
                raw_stdout=stdout_capture.getvalue(),
                raw_stderr=stderr_capture.getvalue(),
            )
        else:
            report = DiagnosticReport(
                status="passed",
                exit_code=0,
                summary="All assertions and checks passed with 0 errors.",
                raw_stdout=stdout_capture.getvalue(),
                raw_stderr=stderr_capture.getvalue(),
            )

    except ReproAssertionError as exc:
        stdout_val = stdout_capture.getvalue()
        stderr_val = stderr_capture.getvalue()

        if expect_exception and matches_expected_exception(exc, expect_exception):
            report = DiagnosticReport(
                status="PASSED",
                exit_code=0,
                summary=f"Expected exception '{type(exc).__name__}' was raised as expected: {exc}",
                raw_stdout=stdout_val,
                raw_stderr=stderr_val,
            )
        else:
            locals_dict: Dict[str, VariableInfo] = {}
            if exc.frame:
                for k, v in exc.frame.f_locals.items():
                    if not k.startswith("__") and k not in ("__repro_assert__", "__repro_assert_truthy__"):
                        locals_dict[k] = introspect_variable(k, v)

            assertion_diag = build_assertion_diagnostic(
                actual=exc.actual,
                expected=exc.expected,
                op_str=exc.op,
                code_str=exc.code_str,
                msg=exc.msg,
            )

            report = DiagnosticReport(
                status="assertion_error",
                exit_code=1,
                summary=assertion_diag.explanation,
                assertion_diagnostic=assertion_diag,
                local_variables=locals_dict,
                raw_stdout=stdout_val,
                raw_stderr=stderr_val,
            )

    except AssertionError as exc:
        stdout_val = stdout_capture.getvalue()
        stderr_val = stderr_capture.getvalue()

        if expect_exception and matches_expected_exception(exc, expect_exception):
            report = DiagnosticReport(
                status="PASSED",
                exit_code=0,
                summary=f"Expected exception '{type(exc).__name__}' was raised as expected: {exc}",
                raw_stdout=stdout_val,
                raw_stderr=stderr_val,
            )
        else:
            tb = exc.__traceback__
            last_tb = tb
            while last_tb and last_tb.tb_next:
                last_tb = last_tb.tb_next

            failing_frame = last_tb.tb_frame if last_tb else None
            failing_lineno = last_tb.tb_lineno if last_tb else 1
            failing_file = failing_frame.f_code.co_filename if failing_frame else str(script_path)

            code_line = linecache.getline(failing_file, failing_lineno).strip()

            locals_dict = {}
            if failing_frame:
                for k, v in failing_frame.f_locals.items():
                    if not k.startswith("__"):
                        locals_dict[k] = introspect_variable(k, v)

            actual_val = None
            expected_val = None
            op_str = "=="

            if code_line:
                try:
                    tree = ast.parse(code_line)
                    if tree.body and isinstance(tree.body[0], ast.Assert):
                        assert_node = tree.body[0]
                        if isinstance(assert_node.test, ast.Compare) and len(assert_node.test.ops) == 1:
                            op_cls = type(assert_node.test.ops[0])
                            op_str = OP_MAP.get(op_cls, "==")
                            if failing_frame:
                                try:
                                    actual_val = eval(compile(ast.Expression(assert_node.test.left), "<eval>", "eval"), failing_frame.f_globals, failing_frame.f_locals)
                                    expected_val = eval(compile(ast.Expression(assert_node.test.comparators[0]), "<eval>", "eval"), failing_frame.f_globals, failing_frame.f_locals)
                                except Exception:
                                    pass
                except Exception:
                    pass

            assertion_diag = build_assertion_diagnostic(
                actual=actual_val,
                expected=expected_val,
                op_str=op_str,
                code_str=code_line or f"assert {str(exc)}",
                msg=str(exc) if str(exc) else None,
            )

            report = DiagnosticReport(
                status="assertion_error",
                exit_code=1,
                summary=assertion_diag.explanation,
                assertion_diagnostic=assertion_diag,
                local_variables=locals_dict,
                raw_stdout=stdout_val,
                raw_stderr=stderr_val,
            )

    except SystemExit as exc:
        stdout_val = stdout_capture.getvalue()
        stderr_val = stderr_capture.getvalue()
        exit_code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        if exit_code == 0:
            if expect_exception:
                report = DiagnosticReport(
                    status="missing_exception",
                    exit_code=1,
                    summary=f"Expected exception '{expect_exception}' was NOT raised. Process exited cleanly with code 0.",
                    raw_stdout=stdout_val,
                    raw_stderr=stderr_val,
                )
            else:
                report = DiagnosticReport(
                    status="passed",
                    exit_code=0,
                    summary="Process exited cleanly with code 0.",
                    raw_stdout=stdout_val,
                    raw_stderr=stderr_val,
                )
        else:
            report = DiagnosticReport(
                status="runtime_exception",
                exit_code=exit_code,
                summary=f"Process exited prematurely with code {exit_code}.",
                raw_stdout=stdout_val,
                raw_stderr=stderr_val,
            )

    except SyntaxError as exc:
        stdout_val = stdout_capture.getvalue()
        stderr_val = stderr_capture.getvalue()
        if expect_exception and matches_expected_exception(exc, expect_exception):
            report = DiagnosticReport(
                status="PASSED",
                exit_code=0,
                summary=f"Expected exception '{type(exc).__name__}' was raised as expected: {exc}",
                raw_stdout=stdout_val,
                raw_stderr=stderr_val,
            )
        else:
            caret_line = f"{' ' * (exc.offset - 1 if exc.offset else 0)}^"
            report = DiagnosticReport(
                status="syntax_error",
                exit_code=1,
                summary=f"SyntaxError: {exc.msg} at line {exc.lineno}",
                raw_stdout=stdout_val,
                raw_stderr=f"  File \"{exc.filename}\", line {exc.lineno}\n    {exc.text.strip() if exc.text else ''}\n    {caret_line}\nSyntaxError: {exc.msg}",
            )

    except BaseException as exc:
        stdout_val = stdout_capture.getvalue()
        stderr_val = stderr_capture.getvalue()

        if expect_exception and matches_expected_exception(exc, expect_exception):
            report = DiagnosticReport(
                status="PASSED",
                exit_code=0,
                summary=f"Expected exception '{type(exc).__name__}' was raised as expected: {exc}",
                raw_stdout=stdout_val,
                raw_stderr=stderr_val,
            )
        else:
            call_stack = extract_call_stack(exc)
            failing_frame_info = call_stack[-1] if call_stack else None

            failing_file = failing_frame_info.filename if failing_frame_info else str(script_path)
            failing_line = failing_frame_info.lineno if failing_frame_info else 1
            failing_code = failing_frame_info.code_context if failing_frame_info else ""
            failing_locals = failing_frame_info.local_variables if failing_frame_info else {}

            operation_desc = explain_exception_operation(exc, failing_code, failing_frame_info)

            exc_diag = ExceptionDiagnostic(
                exception_type=type(exc).__name__,
                exception_message=str(exc),
                failing_file=failing_file,
                failing_line=failing_line,
                failing_code=failing_code,
                operation_description=operation_desc,
                call_stack=call_stack,
            )

            summary_text = (
                f"{type(exc).__name__}: {exc} (Expected: {expect_exception})"
                if expect_exception
                else f"{type(exc).__name__}: {exc}"
            )

            report = DiagnosticReport(
                status="runtime_exception",
                exit_code=1,
                summary=summary_text,
                exception_diagnostic=exc_diag,
                local_variables=failing_locals,
                raw_stdout=stdout_val,
                raw_stderr=stderr_val,
            )

    if report is not None:
        report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")


# =============================================================================
# Execution and Reporting Engine
# =============================================================================

def execute_script(
    code: str,
    ws: pathlib.Path,
    timeout_secs: int = 15,
    expect_exception: Optional[str] = None,
) -> Tuple[int, str, str, DiagnosticReport]:
    """Execute transformed reproduction code inside an isolated /tmp process."""
    tmp_base = "/tmp" if os.path.isdir("/tmp") else None
    guard = PathContainmentGuard(ws)
    try:
        with tempfile.TemporaryDirectory(dir=tmp_base, prefix="swegemma_repro_") as temp_dir:
            temp_dir_path = pathlib.Path(temp_dir).resolve()
            assert_scratch_path_contained(temp_dir_path, ws)

            script_file = temp_dir_path / "repro_test.py"
            script_file.write_text(code, encoding="utf-8")
            report_file = temp_dir_path / "diagnostic_report.json"

            check_py = pathlib.Path(__file__).resolve()

            cmd = [
                sys.executable,
                str(check_py),
                "--runner",
                str(script_file),
                str(report_file),
            ]
            if expect_exception:
                cmd.extend(["--expect-exception", expect_exception])

            env = os.environ.copy()
            python_paths = []
            if (ws / "src").is_dir():
                python_paths.append(str((ws / "src").resolve()))
            if ws.is_dir():
                python_paths.append(str(ws.resolve()))
            for p in ["/workspace", "/workspace/src"]:
                if p not in python_paths:
                    python_paths.append(p)
            existing_pp = env.get("PYTHONPATH", "")
            if existing_pp:
                for p in existing_pp.split(":"):
                    if p and p not in python_paths:
                        python_paths.append(p)

            env["PYTHONPATH"] = ":".join(python_paths)
            env["SWEGEMMA_WORKSPACE"] = str(ws.resolve())
            env["WORKSPACE_DIR"] = str(ws.resolve())
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            if os.path.isdir("/tmp"):
                env["TMPDIR"] = "/tmp"
                env["TEMP"] = "/tmp"
                env["TMP"] = "/tmp"

            proc = None
            try:
                proc = subprocess.Popen(
                    cmd,
                    cwd=temp_dir_path,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    start_new_session=True,  # Distinct process group (setsid)
                )
                stdout_out, stderr_out = proc.communicate(timeout=timeout_secs)
                exit_code = proc.returncode
                stdout_out = stdout_out.strip() if stdout_out else ""
                stderr_out = stderr_out.strip() if stderr_out else ""

                if report_file.exists():
                    try:
                        report_data = json.loads(report_file.read_text(encoding="utf-8"))
                        report = DiagnosticReport.model_validate(report_data)
                        return exit_code, stdout_out, stderr_out, report
                    except Exception:
                        pass

                combined_err = f"{stderr_out}\n{stdout_out}".strip()
                status = "error"
                if expect_exception and expect_exception in combined_err:
                    status = "PASSED"
                elif "AssertionError" in combined_err:
                    status = "assertion_error"
                elif "SyntaxError" in combined_err:
                    status = "syntax_error"
                elif exit_code == 0:
                    status = "passed"
                else:
                    status = "runtime_exception"

                fallback_report = DiagnosticReport(
                    status=status,
                    exit_code=exit_code,
                    summary=combined_err.splitlines()[-1] if combined_err else "Execution finished",
                    raw_stdout=stdout_out,
                    raw_stderr=stderr_out,
                )
                return exit_code, stdout_out, stderr_out, fallback_report

            except subprocess.TimeoutExpired:
                # Terminate entire process group cleanly via SIGKILL
                if proc is not None:
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    except Exception:
                        try:
                            proc.kill()
                        except Exception:
                            pass
                    try:
                        proc.communicate(timeout=2)
                    except Exception:
                        pass

                timeout_summary = f"⏱️ Execution timed out after {timeout_secs}s (possible infinite loop in repro script)"
                timeout_report = DiagnosticReport(
                    status="timeout",
                    exit_code=124,
                    summary=timeout_summary,
                    raw_stderr=f"Timeout expired ({timeout_secs}s)",
                )
                return 124, "", timeout_summary, timeout_report
            except Exception as e:
                err_report = DiagnosticReport(
                    status="error",
                    exit_code=1,
                    summary=f"Failed to execute process: {e}",
                    raw_stderr=str(e),
                )
                return 1, "", f"Failed to execute process: {e}", err_report
    finally:
        guard.cleanup_pollution()


def _format_assertion_failure(
    diag_or_actual: Union[AssertionDiagnostic, Any],
    locals_or_expected: Any = None,
) -> Union[List[str], str]:
    """Format assertion failure details, deep diffs, and root cause hints.

    When called with (AssertionDiagnostic, Optional[Dict[str, VariableInfo]]):
        Returns List[str] formatted lines with assertion details and remediation hints.
    When called with (str, str):
        Returns str remediation hint for trailing newlines or boundary mismatches.
    """
    if isinstance(diag_or_actual, str) and isinstance(locals_or_expected, str):
        hint = get_string_remediation_hint(diag_or_actual, locals_or_expected)
        return hint or ""

    if not isinstance(diag_or_actual, AssertionDiagnostic):
        return []

    diag = diag_or_actual
    locals_vars = locals_or_expected if isinstance(locals_or_expected, dict) else None

    lines: List[str] = [
        "[repro-check] 🎯 DEFECT CONFIRMED (Assertion Failed):"
    ]
    if diag.assertion_code:
        lines.append(f"  Failing Statement: {diag.assertion_code}")
    if diag.divergence_detail:
        lines.append(f"  {diag.divergence_detail}")
    elif diag.first_diff_index is not None:
        lines.append(f"  Difference at index: {diag.first_diff_index}")

    lines.append("")
    lines.append("  🔍 DIAGNOSTIC SUMMARY:")
    lines.append(f"    {diag.explanation}")

    # Actionable Diagnostics: Section 💡 ROOT CAUSE HINT FOR LLM:
    root_hint = diag.root_cause_hint or diag.remediation_hint
    if not root_hint and diag.actual_repr and diag.expected_repr:
        try:
            act_val = ast.literal_eval(diag.actual_repr)
            exp_val = ast.literal_eval(diag.expected_repr)
            root_hint = generate_root_cause_hint(act_val, diag.op, exp_val, diag.first_diff_index)
        except Exception:
            pass

    if root_hint:
        lines.append("")
        lines.append("  💡 ROOT CAUSE HINT FOR LLM:")
        for hl in root_hint.splitlines():
            clean_hl = hl.lstrip("💡 HINT: ")
            lines.append(f"    {clean_hl}")

    lines.append("")
    lines.append("  📊 VALUE COMPARISON:")
    if diag.actual_type == "str" and diag.expected_type == "str":
        lines.append(f"    Actual:   {diag.actual_repr} (length {diag.actual_length})")
        lines.append(f"    Expected: {diag.expected_repr} (length {diag.expected_length})")
    else:
        act_len_str = f" (length {diag.actual_length})" if diag.actual_length is not None else ""
        exp_len_str = f" (length {diag.expected_length})" if diag.expected_length is not None else ""
        lines.append(f"    Actual:   {diag.actual_repr}{act_len_str}")
        lines.append(f"    Expected: {diag.expected_repr}{exp_len_str}")

    # Decoded ANSI escape breakdown
    if diag.escape_breakdown:
        lines.append("")
        for el in diag.escape_breakdown.splitlines():
            lines.append(f"  {el}")

    # Dictionary / JSON mismatch
    if diag.dict_diff_summary:
        lines.append("")
        for dl in diag.dict_diff_summary.splitlines():
            lines.append(f"  {dl}")

    # Sequence / List mismatch
    if diag.sequence_diff_summary:
        lines.append("")
        for sl in diag.sequence_diff_summary.splitlines():
            lines.append(f"  {sl}")

    # Character diff (for strings and general comparisons)
    if diag.char_diff and not diag.dict_diff_summary and not diag.sequence_diff_summary:
        lines.append("")
        lines.append("  🔀 CHARACTER DIFF:")
        for dl in diag.char_diff.splitlines():
            lines.append(f"    {dl}")

    if locals_vars:
        lines.append("")
        lines.append("  📦 LOCAL VARIABLES IN FAILING FRAME:")
        for vname, vinfo in locals_vars.items():
            vlen_str = f", len={vinfo.length}" if vinfo.length is not None else ""
            lines.append(f"    {vname} ({vinfo.type_name}{vlen_str}): {vinfo.value_repr}")

    return lines


format_assertion_diagnostic = _format_assertion_failure


def _truncate_output(text: Optional[str], max_chars: int = 2000) -> str:
    """Cap output stream to max_chars characters.

    If output exceeds max_chars, truncate and append banner.
    """
    if not text or len(text) <= max_chars:
        return text or ""
    total_chars = len(text)
    capped = text[:max_chars]
    sep = "" if capped.endswith("\n") else "\n"
    return f"{capped}{sep}... [TRUNCATED: Output exceeded 2,000 chars (total: {total_chars} chars)]"


def render_report_output(report: DiagnosticReport, has_checks: bool, ws: pathlib.Path) -> str:
    """Render structured report into deterministic human and LLM-friendly diagnostic output."""
    if report.raw_stdout:
        report.raw_stdout = _truncate_output(report.raw_stdout, 2000)
    if report.raw_stderr:
        report.raw_stderr = _truncate_output(report.raw_stderr, 2000)

    lines: List[str] = []

    if report.status == "duplicate_probe":
        lines.append(f"[repro-check] 🛑 REPETITION CIRCUIT BREAKER: {report.summary}")
        lines.append("  You have submitted this exact byte-identical reproduction script before!")
        lines.append("  Repeating identical probes wastes your 40-call budget without generating new information.")
        lines.append("  Stop running duplicate scripts! Modify your probe assertions or proceed directly to edit_file.")
        return "\n".join(lines)

    if report.status.lower() == "passed":
        if "Expected exception" in report.summary:
            lines.append(f"[repro-check] ✅ PASSED: {report.summary}")
            if report.raw_stdout:
                lines.append(report.raw_stdout)
            return "\n".join(lines)
        if has_checks:
            lines.append("[repro-check] ✅ PASSED: All assertions and checks passed with 0 errors.")
            if report.raw_stdout:
                lines.append(report.raw_stdout)
        else:
            probe_cnt = get_probe_count()
            if is_probe_circuit_breaker_active(ws):
                lines.append(
                    "[repro-check] ⚠️ PROBE BUDGET REACHED (2/2 probes used): "
                    "You have executed 2 exploratory probes without reproducing a defect or failing an assertion. "
                    "Stop probing! Formulate your defect hypothesis, locate candidate source lines, and call edit_file immediately."
                )
            else:
                lines.append(
                    f"[repro-check] ❌ FAILED (Missing Assertion) [{probe_cnt}/2 probes used]: "
                    "Code executed with returncode 0, but verified NOTHING because it contained NO assertions (assert) or checks! "
                    "In SWE-bench, print statements do NOT reproduce defects or verify fixes. "
                    "You MUST add assert statements (e.g. `assert actual == expected, 'mismatch'`) or pass expect_exception=True to verify behavior."
                )
                if report.raw_stdout:
                    lines.append(report.raw_stdout)
        return "\n".join(lines)

    if report.status == "missing_exception":
        lines.append("[repro-check] 🎯 DEFECT CONFIRMED (Expected Exception Not Raised):")
        lines.append(f"  {report.summary}")
        lines.append("")
        lines.append("  🔍 DIAGNOSTIC SUMMARY:")
        lines.append("    The target code executed silently without raising the expected exception.")
        lines.append("    This confirms a missing validation or unhandled condition defect.")
        if report.raw_stdout:
            lines.append("")
            lines.append(f"  Standard Output:\n    {report.raw_stdout.strip()}")
        return "\n".join(lines)

    if report.status == "assertion_error":
        if report.assertion_diagnostic:
            formatted_lines = _format_assertion_failure(report.assertion_diagnostic, report.local_variables)
            return "\n".join(formatted_lines)
        lines.append("[repro-check] 🎯 DEFECT CONFIRMED (Assertion Failed):")
        lines.append(f"  {report.summary}")
        return "\n".join(lines)

    if report.status == "runtime_exception":
        diag = report.exception_diagnostic
        failing_file = diag.failing_file if diag else ""
        is_ws = is_workspace_path(failing_file, ws) or (str(ws) in (report.raw_stderr + report.raw_stdout))

        if is_ws:
            lines.append("[repro-check] 💥 DEFECT REPRODUCED (Workspace Runtime Exception):")
        else:
            lines.append("[repro-check] 💥 DEFECT REPRODUCED (Runtime Exception):")

        if diag:
            lines.append(f"  Exception: {diag.exception_type}: {diag.exception_message}")
            rel_path = diag.failing_file
            try:
                rel_path = str(pathlib.Path(diag.failing_file).relative_to(ws))
            except Exception:
                pass
            lines.append(f"  Location: line {diag.failing_line} in {rel_path}")

            lines.append("")
            lines.append("  🔍 DIAGNOSTIC SUMMARY:")
            lines.append(f"    {diag.operation_description}")

            if diag.failing_code:
                lines.append("")
                lines.append("  📍 FAILING LINE:")
                lines.append(f"    {diag.failing_code}")

            if diag.call_stack:
                lines.append("")
                lines.append("  📚 CALL STACK:")
                for i, frame in enumerate(diag.call_stack, 1):
                    try:
                        frame_rel = str(pathlib.Path(frame.filename).relative_to(ws))
                    except Exception:
                        frame_rel = pathlib.Path(frame.filename).name
                    lines.append(f"    [{i}] {frame_rel}:{frame.lineno} in {frame.function_name}()")
                    if frame.code_context:
                        lines.append(f"        Line: {frame.code_context}")
                    if frame.arguments:
                        arg_strs = [f"{k}={v.value_repr}" for k, v in frame.arguments.items()]
                        lines.append(f"        Arguments: {', '.join(arg_strs)}")

        if report.local_variables:
            lines.append("")
            lines.append("  📦 LOCAL VARIABLES IN FAILING FRAME:")
            for vname, vinfo in report.local_variables.items():
                vlen_str = f", len={vinfo.length}" if vinfo.length is not None else ""
                lines.append(f"    {vname} ({vinfo.type_name}{vlen_str}): {vinfo.value_repr}")

        return "\n".join(lines)

    if report.status == "syntax_error":
        lines.append("[repro-check] ⚠️ TEST SCRIPT SYNTAX ERROR:")
        lines.append(f"  {report.summary}")
        if report.raw_stderr:
            for l in report.raw_stderr.splitlines()[-6:]:
                lines.append(f"    {l}")
        return "\n".join(lines)

    if report.status == "timeout":
        lines.append(f"[repro-check] {report.summary}")
        return "\n".join(lines)

    lines.append(f"[repro-check] ❌ EXECUTION FAILED (Exit code {report.exit_code}):")
    lines.append(f"  {report.summary}")
    if report.raw_stderr:
        for l in report.raw_stderr.splitlines()[-10:]:
            lines.append(f"    {l}")
    return "\n".join(lines)


# =============================================================================
# Main CLI Entrypoint
# =============================================================================

def print_help() -> None:
    """Print comprehensive help and usage guide."""
    help_text = """repro-check: Omnivorous Defect Reproduction & Verification Engine.

Usage via run_skill_script:
  skill_name: "repro-check", file_path: "check.py"
  args: ["--code", "assert 1 == 1"]
  args: ["--b64", "<base64_code>"]
  args: ["--file", "/tmp/repro.py"]
  args: ["--expect-exception", "ValueError", "--code", "assert ..."]

Options:
  --code, -c <CODE>             Python code snippet to execute (alternative to positional argument).
  --expect-exception, -e <EXC>  Expect a specific exception type (e.g. ValueError, KeyError, AssertionError).
                                If baseline code fails to raise it, defect_confirmed=True.
                                When the fix causes the exception to be raised, status=PASSED.
  --timeout, -t <SECS>          Execution timeout in seconds (default: 15s). Terminated cleanly via os.killpg.
  --b64, --base64 <B64>         Execute base64-encoded Python assertion code (avoids shell/JSON quote escaping).
  --file, -f <FILE>             Execute raw Python script from the specified file path.
  --stdin, -                    Execute raw Python script read from standard input.
  --help, -h                    Show this help message and exit (exit code 0).

Positional Arguments:
  code                          Python reproduction code snippet to execute.
                                If a single argument is an existing file, it is executed as a script.
                                Multiple positional tokens are joined automatically with spaces.

Guarantees:
  - Omnivorous: auto-asserts comparisons, auto-invokes uncalled test functions, strips fences and redundant outer quotes.
  - Quote sanitization: automatically strips outer quotes and normalizes escaped quotes from JSON.
  - AST pre-parse: validates syntax before writing to /tmp or executing, cleanly reporting SYNTAX_ERROR.
  - Zero git pollution: strictly executes inside isolated /tmp process with Path Containment Guard.
  - Workspace import priority: PYTHONPATH=/workspace:/workspace/src.
  - Deterministic AST diagnostics: plain-English explanations and char diffs.
  - Probe budget limiter: 2-probe cap on exploratory runs; auto-resets on defect or fix.
  - Exit code: exits 0 on pass, exits 1 on fail or syntax error.
"""
    print(help_text.strip())


def main() -> int:
    """Main execution function. Exits 0 on pass, exits 1 on fail/syntax error."""
    try:
        raw_args = sys.argv[1:]

        # Check for help flag
        if any(arg in ("--help", "-h") for arg in raw_args):
            print_help()
            return 0

        # Internal runner mode invoked by execute_script
        if len(raw_args) >= 3 and raw_args[0] == "--runner":
            script_path = pathlib.Path(raw_args[1])
            report_path = pathlib.Path(raw_args[2])
            expect_exc = None
            i = 3
            while i < len(raw_args):
                arg = raw_args[i]
                if arg in ("--expect-exception", "-e") and i + 1 < len(raw_args):
                    expect_exc = raw_args[i + 1]
                    i += 2
                elif arg.startswith(("--expect-exception=", "-e=")):
                    expect_exc = arg.split("=", 1)[1]
                    i += 1
                else:
                    i += 1
            run_harness(script_path, report_path, expect_exception=expect_exc)
            return 0

        # Parse general arguments
        expect_exception: Optional[str] = None
        file_path: Optional[pathlib.Path] = None
        code_arg: Optional[str] = None
        timeout_secs: int = 15
        use_stdin = False
        use_b64 = False
        b64_arg: Optional[str] = None
        code_tokens: List[str] = []

        i = 0
        while i < len(raw_args):
            arg = raw_args[i]
            if arg in ("--expect-exception", "-e") and i + 1 < len(raw_args):
                expect_exception = raw_args[i + 1]
                i += 2
            elif arg.startswith(("--expect-exception=", "-e=")):
                expect_exception = arg.split("=", 1)[1]
                i += 1
            elif arg in ("--timeout", "-t") and i + 1 < len(raw_args):
                try:
                    timeout_secs = int(raw_args[i + 1])
                except ValueError:
                    pass
                i += 2
            elif arg.startswith(("--timeout=", "-t=")):
                try:
                    timeout_secs = int(arg.split("=", 1)[1])
                except ValueError:
                    pass
                i += 1
            elif arg in ("--code", "-c") and i + 1 < len(raw_args):
                code_arg = raw_args[i + 1]
                i += 2
            elif arg.startswith(("--code=", "-c=")):
                code_arg = arg.split("=", 1)[1]
                i += 1
            elif arg in ("--file", "-f") and i + 1 < len(raw_args):
                file_path = pathlib.Path(raw_args[i + 1])
                i += 2
            elif arg.startswith(("--file=", "-f=")):
                file_path = pathlib.Path(arg.split("=", 1)[1])
                i += 1
            elif arg in ("--stdin", "-"):
                use_stdin = True
                i += 1
            elif arg in ("--b64", "--base64"):
                use_b64 = True
                if i + 1 < len(raw_args) and not raw_args[i + 1].startswith("-"):
                    b64_arg = raw_args[i + 1]
                    i += 2
                else:
                    i += 1
            elif arg.startswith(("--b64=", "--base64=")):
                use_b64 = True
                b64_arg = arg.split("=", 1)[1]
                i += 1
            else:
                code_tokens.append(arg)
                i += 1

        # Determine code source
        code = ""
        if code_arg is not None:
            code = code_arg
        elif use_b64:
            if not b64_arg and code_tokens:
                b64_arg = " ".join(code_tokens).strip()
                code_tokens = []
            elif not b64_arg and (use_stdin or not sys.stdin.isatty()):
                b64_arg = sys.stdin.read().strip()

            if not b64_arg:
                print("[repro-check] ⚠️ TEST SCRIPT SYNTAX_ERROR:\n  SYNTAX_ERROR: No base64 payload provided to --b64")
                return 1

            # Sanitize b64_arg of redundant outer quotes
            b64_clean = b64_arg.strip()
            for _ in range(3):
                if (b64_clean.startswith('"') and b64_clean.endswith('"')) or (b64_clean.startswith("'") and b64_clean.endswith("'")):
                    b64_clean = b64_clean[1:-1].strip()
                elif (b64_clean.startswith('\\"') and b64_clean.endswith('\\"')) or (b64_clean.startswith("\\'") and b64_clean.endswith("\\'")):
                    b64_clean = b64_clean[2:-2].strip()

            try:
                pad = len(b64_clean) % 4
                if pad:
                    b64_clean += "=" * (4 - pad)
                code = base64.b64decode(b64_clean).decode("utf-8")
            except Exception as exc:
                print(f"[repro-check] ⚠️ TEST SCRIPT SYNTAX_ERROR:\n  SYNTAX_ERROR: Invalid base64 payload: {exc}")
                return 1
        elif file_path is not None:
            if not file_path.exists():
                print(f"[repro-check] Error: Script file not found: {file_path}")
                return 1
            code = file_path.read_text(encoding="utf-8")
        elif use_stdin:
            code = sys.stdin.read()
        elif code_tokens:
            # Check if single token is a path to an existing .py file
            if len(code_tokens) == 1 and (code_tokens[0].endswith(".py") or "\n" not in code_tokens[0]):
                candidate_path = pathlib.Path(code_tokens[0])
                if candidate_path.is_file():
                    code = candidate_path.read_text(encoding="utf-8")
                else:
                    code = code_tokens[0]
            else:
                if any("\n" in t for t in code_tokens):
                    code = "\n".join(code_tokens)
                else:
                    code = " ".join(code_tokens)
        elif not sys.stdin.isatty():
            piped = sys.stdin.read()
            if piped.strip():
                code = piped

        code = clean_and_normalize_code(code)

        if not code or not code.strip():
            print("[repro-check] No code provided. Usage: check.py [options] [<code>]")
            return 1

        # AST pre-parse syntax validation before writing to /tmp and executing
        try:
            ast.parse(code)
        except SyntaxError as exc:
            if expect_exception and matches_expected_exception(exc, expect_exception):
                report = DiagnosticReport(
                    status="PASSED",
                    exit_code=0,
                    summary=f"Expected exception '{type(exc).__name__}' was raised as expected: {exc}",
                )
                print(f"[repro-check] ✅ PASSED: {report.summary}")
                return 0

            err_line = exc.text.strip() if exc.text else ""
            if not err_line and exc.lineno and 1 <= exc.lineno <= len(code.splitlines()):
                err_line = code.splitlines()[exc.lineno - 1].strip()
            offset = exc.offset or 1
            caret_line = f"{' ' * max(0, offset - 1)}^"
            summary = f"SYNTAX_ERROR: {exc.msg} at line {exc.lineno}"
            raw_err = f"  File \"<assertion>\", line {exc.lineno}\n    {err_line}\n    {caret_line}\nSyntaxError: {exc.msg}"
            report = DiagnosticReport(
                status="syntax_error",
                exit_code=1,
                summary=summary,
                raw_stderr=raw_err,
            )
            print(
                f"[repro-check] ⚠️ TEST SCRIPT SYNTAX_ERROR:\n"
                f"  {summary}\n"
                f"    {err_line}\n"
                f"    {caret_line}\n"
                f"  SyntaxError: {exc.msg}"
            )
            return 1

        ws = get_workspace_dir()

        # If workspace modified, reset probe count and deduplication history
        if workspace_has_modifications(ws):
            reset_probe_count()
            reset_probe_history()
        else:
            # Check for duplicate identical payload on unmodified workspace
            is_dup, seen_count = check_and_record_probe_payload(code, expect_exception)
            if is_dup:
                rendered = (
                    f"[repro-check] 🛑 REPETITION CIRCUIT BREAKER (Duplicate Payload #{seen_count}): "
                    "You have submitted this exact byte-identical reproduction script before on an unmodified workspace! "
                    "Repeating identical probes wastes your 40-call budget without generating new information. "
                    "Stop running duplicate scripts! Modify your probe assertions or proceed directly to edit_file."
                )
                output = ReproCheckOutput(
                    success=False,
                    defect_confirmed=False,
                    category="duplicate_probe",
                    report=DiagnosticReport(
                        status="duplicate_probe",
                        exit_code=1,
                        summary=f"Duplicate probe payload detected (seen {seen_count} times)",
                    ),
                    rendered_output=rendered,
                )
                print(output.rendered_output)
                return 1

        transformed_code, has_checks, check_count = prepare_executable_code(code)

        # If expecting exception, it is an active check
        if expect_exception:
            has_checks = True

        # Check circuit breaker before running pure probes
        if not has_checks and is_probe_circuit_breaker_active(ws):
            rendered = (
                "[repro-check] ⚠️ PROBE BUDGET REACHED (2/2 probes used): "
                "You have executed 2 exploratory probes without reproducing a defect or failing an assertion. "
                "Stop probing! Formulate your defect hypothesis, locate candidate source lines, and call edit_file immediately."
            )
            output = ReproCheckOutput(
                success=False,
                defect_confirmed=False,
                category="probe_budget_reached",
                report=DiagnosticReport(
                    status="probe_budget_reached",
                    exit_code=1,
                    summary="Probe budget reached",
                ),
                rendered_output=rendered,
            )
            print(output.rendered_output)
            return 1

        exit_code, stdout, stderr, report = execute_script(
            transformed_code, ws, timeout_secs=timeout_secs, expect_exception=expect_exception
        )

        # Handle probe count updates
        if report.status.lower() == "passed":
            if has_checks or expect_exception:
                reset_probe_count()
                category = "passed"
                defect_confirmed = False
                success = True
            else:
                increment_probe_count()
                if is_probe_circuit_breaker_active(ws):
                    category = "probe_budget_reached"
                    defect_confirmed = False
                    success = False
                else:
                    category = "missing_assertion"
                    defect_confirmed = False
                    success = False  # HARD FAIL on empty assertion probe
        elif report.status == "missing_exception":
            reset_probe_count()
            category = "missing_exception"
            defect_confirmed = True
            success = False
        elif report.status == "assertion_error":
            reset_probe_count()
            category = "assertion_failure"
            defect_confirmed = True
            success = False
        elif report.status == "runtime_exception":
            reset_probe_count()
            failing_file = report.exception_diagnostic.failing_file if report.exception_diagnostic else ""
            category = "workspace_exception" if is_workspace_path(failing_file, ws) else "runtime_exception"
            defect_confirmed = True
            success = False
        elif report.status == "syntax_error":
            category = "syntax_error"
            defect_confirmed = False
            success = False
        elif report.status == "timeout":
            reset_probe_count()
            category = "timeout"
            defect_confirmed = False
            success = False
        else:
            category = "general_failure"
            defect_confirmed = False
            success = False

        rendered = render_report_output(report, has_checks, ws)

        final_output = ReproCheckOutput(
            success=success,
            defect_confirmed=defect_confirmed,
            category=category,
            report=report,
            rendered_output=rendered,
        )

        print(final_output.rendered_output)
        return 0 if success else 1

    except Exception as e:
        print(f"[repro-check] Runner error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
