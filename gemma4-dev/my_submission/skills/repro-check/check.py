#!/usr/bin/env python3
"""repro-check: Omnivorous Defect Reproduction & Verification Engine.

Upgraded with deterministic AST assertion introspection, character-level diffs,
and plain-English failure explanations.

Eats ANY input format:
- Auto-asserts bare comparison expressions: `a == b` -> `assert a == b`
- Auto-invokes uncalled test functions: `def test_...():`
- Auto-heals unterminated string literals with raw unescaped newlines in `'...'` and `"..."`
- Omnivorous assert acceptance: executions without explicit `assert` that exit 0 are accepted as valid passes
- Bypasses 2-probe circuit breaker when workspace contains modified files (post-edit verification)
- Strips markdown fences (```py, ```python, etc.) and auto-dedents
- Guarantees zero workspace git pollution (executes inside isolated /tmp cwd)
- Prioritizes /workspace and /workspace/src in PYTHONPATH
- Deterministic failure explanations: introspects failing frame, local variables, actual/expected values, char diffs
- Structured 100% Pydantic v2 models for all diagnostic outputs
- Always exits 0 and never crashes.
"""

from __future__ import annotations

import ast
import contextlib
import difflib
import inspect
import io
import json
import linecache
import os
import pathlib
import re
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
import textwrap
import types
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field

PROBE_COUNT_FILE = pathlib.Path("/tmp/.swegemma_repro_probe_count")

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

    status: str = Field(..., description="Status: passed, assertion_error, runtime_exception, syntax_error, probe_budget_reached, probe_run, timeout, error")
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
    timeout_secs: int = Field(default=35, description="Timeout in seconds")
    workspace_dir: Optional[str] = Field(default=None, description="Path to active workspace")


class ReproCheckOutput(BaseModel):
    """Top-level structured output of repro-check."""

    model_config = ConfigDict(extra="ignore")

    success: bool = Field(..., description="True if verification passed cleanly")
    defect_confirmed: bool = Field(..., description="True if defect was reproduced via assertion or exception")
    category: str = Field(..., description="Category: passed, assertion_failure, workspace_exception, runtime_exception, syntax_error, probe_budget_reached, probe_run, general_failure")
    report: DiagnosticReport = Field(..., description="Structured diagnostic report")
    rendered_output: str = Field(..., description="Rendered human/agent readable text")


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


def get_string_remediation_hint(actual: Any, expected: Any) -> Optional[str]:
    """Generate targeted remediation hint for common string and boundary defects."""
    if not isinstance(actual, str) or not isinstance(expected, str):
        return None

    if actual == expected:
        return None

    # Degenerate boundary mismatch (empty string vs newline)
    if (actual == "" and expected in ("\n", "\r\n")) or (actual in ("\n", "\r\n") and expected == ""):
        return (
            "💡 HINT: Degenerate boundary mismatch (empty string vs newline). "
            "Ensure string splitting/joining does not collapse single-newline inputs."
        )

    # Trailing newline / whitespace mismatch (difference is at or near the end, e.g. missing trailing \n, \r\n, or extra trailing whitespace)
    if actual.rstrip() == expected.rstrip():
        return (
            '💡 HINT: Trailing newline mismatch detected. In Python, str.splitlines() '
            'and str.splitlines(True) drop the trailing empty token after a terminal newline! '
            'If your code needs to preserve all lines and trailing newlines, use re.split(r"(?<=\\n)", text).'
        )

    return None


compute_assertion_remediation_hint = get_string_remediation_hint


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
            f"Actual has {repr(c_act)} (ASCII {ord(c_act)}), Expected has {repr(c_exp)} (ASCII {ord(c_exp)}){case_note}."
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
                f"  index {first_diff_idx}: Actual has {repr(c_act)} (ASCII {ord(c_act)}), "
                f"Expected has {repr(c_exp)} (ASCII {ord(c_exp)})"
            )
        elif first_diff_idx == len(actual) and len(actual) < len(expected):
            missing_part = expected[len(actual):]
            diff_lines.append(
                f"  index {first_diff_idx}: Actual string ends early; "
                f"Expected continues with {repr(missing_part)}"
            )
        elif first_diff_idx == len(expected) and len(actual) > len(expected):
            extra_part = actual[len(expected):]
            diff_lines.append(
                f"  index {first_diff_idx}: Expected string ends early; "
                f"Actual has extra {repr(extra_part)}"
            )

    return "\n".join(diff_lines)


def generate_sequence_diff(actual: Any, expected: Any, first_diff_idx: Optional[int]) -> str:
    """Generate unified diff for lists, tuples, or sequences."""
    diff_lines: List[str] = []
    act_lines = [repr(item) + "\n" for item in actual]
    exp_lines = [repr(item) + "\n" for item in expected]
    ud = list(difflib.unified_diff(exp_lines, act_lines, fromfile="expected", tofile="actual"))
    if ud:
        for line in ud:
            diff_lines.append(f"  {line.rstrip()}")
    if first_diff_idx is not None and first_diff_idx < min(len(actual), len(expected)):
        diff_lines.append(
            f"  Index {first_diff_idx}: Actual has {repr(actual[first_diff_idx])}, "
            f"Expected has {repr(expected[first_diff_idx])}"
        )
    return "\n".join(diff_lines)


def generate_dict_diff(actual: dict, expected: dict) -> str:
    """Generate key and value diff for mappings."""
    diff_lines: List[str] = []
    missing_keys = set(expected.keys()) - set(actual.keys())
    extra_keys = set(actual.keys()) - set(expected.keys())
    common_keys = set(actual.keys()) & set(expected.keys())
    val_diffs = {k: (actual[k], expected[k]) for k in common_keys if actual[k] != expected[k]}

    if missing_keys:
        diff_lines.append(f"  - Missing keys: {list(missing_keys)}")
    if extra_keys:
        diff_lines.append(f"  + Extra keys: {list(extra_keys)}")
    if val_diffs:
        diff_lines.append("  Key value differences:")
        for k, (a_v, e_v) in val_diffs.items():
            diff_lines.append(f"    Key '{k}': Actual has {repr(a_v)}, Expected has {repr(e_v)}")
    return "\n".join(diff_lines)


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
        min_len = min(len(actual), len(expected))
        for i in range(min_len):
            if actual[i] != expected[i]:
                first_diff_idx = i
                break
        if first_diff_idx is None and len(actual) != len(expected):
            first_diff_idx = min_len

        seq_type = "List" if isinstance(actual, list) else "Tuple"
        if len(actual) != len(expected):
            explanation = (
                f"SEQUENCE MISMATCH: {seq_type} length differs (Actual has {len(actual)} items, "
                f"Expected has {len(expected)} items)."
            )
            if first_diff_idx is not None and first_diff_idx < min_len:
                explanation += (
                    f" First item difference at index {first_diff_idx}: Actual has "
                    f"{format_value_repr(actual[first_diff_idx])}, Expected has {format_value_repr(expected[first_diff_idx])}."
                )
        elif first_diff_idx is not None:
            explanation = (
                f"SEQUENCE MISMATCH: {seq_type} items differ at index {first_diff_idx}: "
                f"Actual has {format_value_repr(actual[first_diff_idx])}, "
                f"Expected has {format_value_repr(expected[first_diff_idx])}."
            )
        else:
            explanation = f"{seq_type}s appear identical."

        diff_str = generate_sequence_diff(actual, expected, first_diff_idx)
        return explanation, diff_str, first_diff_idx

    # Case 4: Both are dicts
    if isinstance(actual, dict) and isinstance(expected, dict):
        missing_keys = set(expected.keys()) - set(actual.keys())
        extra_keys = set(actual.keys()) - set(expected.keys())
        common_keys = set(actual.keys()) & set(expected.keys())
        val_diffs = {k: (actual[k], expected[k]) for k in common_keys if actual[k] != expected[k]}

        parts = []
        if missing_keys:
            parts.append(f"missing expected key(s) {list(missing_keys)}")
        if extra_keys:
            parts.append(f"unexpected extra key(s) {list(extra_keys)}")
        if val_diffs:
            first_k = next(iter(val_diffs))
            a_v, e_v = val_diffs[first_k]
            parts.append(f"value differs for key '{first_k}' (Actual has {format_value_repr(a_v)}, Expected has {format_value_repr(e_v)})")

        summary_body = "; ".join(parts) if parts else "contents differ"
        explanation = f"DICT MISMATCH: {summary_body}."
        diff_str = generate_dict_diff(actual, expected)
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


def clean_and_normalize_code(raw_args: List[str]) -> str:
    """Extract code from arbitrary CLI arguments, stripping fences and normalizing indentation."""
    code = "\n".join(raw_args).strip()

    # Strip markdown code blocks: ```python ... ``` or ```py ... ``` or ``` ... ```
    code = re.sub(r"^```[a-zA-Z0-9_-]*\s*\n?", "", code)
    code = re.sub(r"\n?```\s*$", "", code)

    # Handle accidental literal escaped newlines if passed improperly
    if "\\n" in code and "\n" not in code:
        code = code.replace("\\n", "\n")

    code = textwrap.dedent(code).strip()
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
# In-Harness Process Execution
# =============================================================================

def run_harness(script_path: pathlib.Path, report_path: pathlib.Path) -> None:
    """Internal runner executed inside isolated subprocess with diagnostic recording."""
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

        locals_dict: Dict[str, VariableInfo] = {}
        if exc.frame:
            for k, v in exc.frame.f_locals.items():
                if not k.startswith("__") and k not in ("__repro_assert__", "__repro_assert_truthy__"):
                    locals_dict[k] = introspect_variable(k, v)

        actual_type = type(exc.actual).__name__
        actual_repr = format_value_repr(exc.actual)
        actual_len = get_length(exc.actual)

        expected_type = type(exc.expected).__name__
        expected_repr = format_value_repr(exc.expected)
        expected_len = get_length(exc.expected)

        explanation, diff_str, first_diff_idx = explain_assertion_failure(
            exc.actual, exc.op, exc.expected, exc.msg
        )
        hint = get_string_remediation_hint(exc.actual, exc.expected)

        assertion_diag = AssertionDiagnostic(
            assertion_code=exc.code_str,
            op=exc.op,
            actual_type=actual_type,
            actual_repr=actual_repr,
            actual_length=actual_len,
            expected_type=expected_type,
            expected_repr=expected_repr,
            expected_length=expected_len,
            char_diff=diff_str,
            first_diff_index=first_diff_idx,
            message=exc.msg if exc.msg else None,
            explanation=explanation,
            remediation_hint=hint,
        )

        report = DiagnosticReport(
            status="assertion_error",
            exit_code=1,
            summary=explanation,
            assertion_diagnostic=assertion_diag,
            local_variables=locals_dict,
            raw_stdout=stdout_val,
            raw_stderr=stderr_val,
        )

    except AssertionError as exc:
        stdout_val = stdout_capture.getvalue()
        stderr_val = stderr_capture.getvalue()

        tb = exc.__traceback__
        last_tb = tb
        while last_tb and last_tb.tb_next:
            last_tb = last_tb.tb_next

        failing_frame = last_tb.tb_frame if last_tb else None
        failing_lineno = last_tb.tb_lineno if last_tb else 1
        failing_file = failing_frame.f_code.co_filename if failing_frame else str(script_path)

        line_text = linecache.getline(failing_file, failing_lineno).strip()

        locals_dict = {}
        if failing_frame:
            for k, v in failing_frame.f_locals.items():
                if not k.startswith("__"):
                    locals_dict[k] = introspect_variable(k, v)

        actual_val = None
        expected_val = None
        op_str = "=="
        explanation = f"Assertion failed: {str(exc) or line_text or 'AssertionError'}"
        first_diff_idx = None
        diff_str = None

        if line_text:
            try:
                tree = ast.parse(line_text)
                if tree.body and isinstance(tree.body[0], ast.Assert):
                    assert_node = tree.body[0]
                    if isinstance(assert_node.test, ast.Compare) and len(assert_node.test.ops) == 1:
                        op_cls = type(assert_node.test.ops[0])
                        op_str = OP_MAP.get(op_cls, "==")
                        if failing_frame:
                            try:
                                actual_val = eval(compile(ast.Expression(assert_node.test.left), "<eval>", "eval"), failing_frame.f_globals, failing_frame.f_locals)
                                expected_val = eval(compile(ast.Expression(assert_node.test.comparators[0]), "<eval>", "eval"), failing_frame.f_globals, failing_frame.f_locals)
                                explanation, diff_str, first_diff_idx = explain_assertion_failure(actual_val, op_str, expected_val, str(exc))
                            except Exception:
                                pass
            except Exception:
                pass

        act_type = type(actual_val).__name__ if actual_val is not None else "unknown"
        act_repr = format_value_repr(actual_val) if actual_val is not None else "unknown"
        exp_type = type(expected_val).__name__ if expected_val is not None else "unknown"
        exp_repr = format_value_repr(expected_val) if expected_val is not None else "unknown"

        hint = (
            get_string_remediation_hint(actual_val, expected_val)
            if actual_val is not None and expected_val is not None
            else None
        )

        assertion_diag = AssertionDiagnostic(
            assertion_code=line_text or f"assert {str(exc)}",
            op=op_str,
            actual_type=act_type,
            actual_repr=act_repr,
            actual_length=get_length(actual_val) if actual_val is not None else None,
            expected_type=exp_type,
            expected_repr=exp_repr,
            expected_length=get_length(expected_val) if expected_val is not None else None,
            char_diff=diff_str,
            first_diff_index=first_diff_idx,
            message=str(exc) if str(exc) else None,
            explanation=explanation,
            remediation_hint=hint,
        )

        report = DiagnosticReport(
            status="assertion_error",
            exit_code=1,
            summary=explanation,
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

        report = DiagnosticReport(
            status="runtime_exception",
            exit_code=1,
            summary=f"{type(exc).__name__}: {exc}",
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
    timeout_secs: int = 35,
) -> Tuple[int, str, str, DiagnosticReport]:
    """Execute transformed reproduction code inside an isolated /tmp process."""
    with tempfile.TemporaryDirectory(prefix="swegemma_repro_") as temp_dir:
        temp_dir_path = pathlib.Path(temp_dir)
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

        env = os.environ.copy()
        python_paths = []
        if (ws / "src").is_dir():
            python_paths.append(str(ws / "src"))
        if ws.is_dir():
            python_paths.append(str(ws))
        existing_pp = env.get("PYTHONPATH", "")
        if existing_pp:
            python_paths.append(existing_pp)

        env["PYTHONPATH"] = ":".join(python_paths)
        env["SWEGEMMA_WORKSPACE"] = str(ws)
        env["WORKSPACE_DIR"] = str(ws)
        env["PYTHONUNBUFFERED"] = "1"

        try:
            res = subprocess.run(
                cmd,
                cwd=temp_dir_path,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_secs,
            )
            exit_code = res.returncode
            stdout_out = res.stdout.strip()
            stderr_out = res.stderr.strip()

            if report_file.exists():
                try:
                    report_data = json.loads(report_file.read_text(encoding="utf-8"))
                    report = DiagnosticReport.model_validate(report_data)
                    return exit_code, stdout_out, stderr_out, report
                except Exception:
                    pass

            combined_err = f"{stderr_out}\n{stdout_out}".strip()
            status = "error"
            if "AssertionError" in combined_err:
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
            timeout_report = DiagnosticReport(
                status="timeout",
                exit_code=124,
                summary=f"Execution timed out after {timeout_secs} seconds.",
                raw_stderr=f"Timeout expired ({timeout_secs}s)",
            )
            return 124, "", f"Execution timed out after {timeout_secs} seconds.", timeout_report
        except Exception as e:
            err_report = DiagnosticReport(
                status="error",
                exit_code=1,
                summary=f"Failed to execute process: {e}",
                raw_stderr=str(e),
            )
            return 1, "", f"Failed to execute process: {e}", err_report


def _format_assertion_failure(
    diag_or_actual: Union[AssertionDiagnostic, Any],
    locals_or_expected: Any = None,
) -> Union[List[str], str]:
    """Format assertion failure details and diagnostic remediation hints.

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
    if diag.first_diff_index is not None:
        lines.append(f"  Difference at index: {diag.first_diff_index}")

    lines.append("")
    lines.append("  🔍 DIAGNOSTIC SUMMARY:")
    lines.append(f"    {diag.explanation}")

    hint = diag.remediation_hint
    if not hint and diag.actual_repr and diag.expected_repr:
        try:
            act_val = ast.literal_eval(diag.actual_repr)
            exp_val = ast.literal_eval(diag.expected_repr)
            hint = get_string_remediation_hint(act_val, exp_val)
        except Exception:
            pass

    if hint:
        lines.append("")
        if not hint.startswith("💡"):
            lines.append(f"  💡 HINT: {hint}")
        else:
            lines.append(f"  {hint}")

    lines.append("")
    lines.append("  📊 VALUE COMPARISON:")
    act_len_str = f", len={diag.actual_length}" if diag.actual_length is not None else ""
    exp_len_str = f", len={diag.expected_length}" if diag.expected_length is not None else ""
    lines.append(f"    Actual   ({diag.actual_type}{act_len_str}): {diag.actual_repr}")
    lines.append(f"    Expected ({diag.expected_type}{exp_len_str}): {diag.expected_repr}")

    if diag.char_diff:
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


def render_report_output(report: DiagnosticReport, has_checks: bool, ws: pathlib.Path) -> str:
    """Render structured report into deterministic human and LLM-friendly diagnostic output."""
    lines: List[str] = []

    if report.status == "passed":
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
                    f"[repro-check] ℹ️ PROBE RUN ({probe_cnt}/2 probes used): "
                    f"Code executed cleanly (exit code 0), but contained NO assertions or test functions."
                )
                if report.raw_stdout:
                    lines.append(report.raw_stdout)
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

    lines.append(f"[repro-check] ❌ EXECUTION FAILED (Exit code {report.exit_code}):")
    lines.append(f"  {report.summary}")
    if report.raw_stderr:
        for l in report.raw_stderr.splitlines()[-10:]:
            lines.append(f"    {l}")
    return "\n".join(lines)


# =============================================================================
# Main CLI Entrypoint
# =============================================================================

def main() -> int:
    """Main execution function. Always exits with code 0."""
    try:
        raw_args = sys.argv[1:]

        # Internal runner mode invoked by execute_script
        if len(raw_args) == 3 and raw_args[0] == "--runner":
            script_path = pathlib.Path(raw_args[1])
            report_path = pathlib.Path(raw_args[2])
            run_harness(script_path, report_path)
            return 0

        # Normal Agent / CLI mode
        if not raw_args:
            print("[repro-check] No code provided. Usage: run_skill_script('repro-check', 'check.py', args=['<code>'])")
            return 0

        code = clean_and_normalize_code(raw_args)
        if not code:
            print("[repro-check] Empty code provided.")
            return 0

        ws = get_workspace_dir()

        # If workspace modified, reset probe count immediately
        if workspace_has_modifications(ws):
            reset_probe_count()

        transformed_code, has_checks, check_count = prepare_executable_code(code)

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
                    exit_code=0,
                    summary="Probe budget reached",
                ),
                rendered_output=rendered,
            )
            print(output.rendered_output)
            return 0

        exit_code, stdout, stderr, report = execute_script(transformed_code, ws)

        # Handle probe count updates
        if report.status == "passed":
            if has_checks:
                reset_probe_count()
                category = "passed"
                defect_confirmed = False
                success = True
            else:
                increment_probe_count()
                if is_probe_circuit_breaker_active(ws):
                    category = "probe_budget_reached"
                else:
                    category = "probe_run"
                defect_confirmed = False
                success = True
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
        return 0

    except Exception as e:
        print(f"[repro-check] Runner error: {e}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
