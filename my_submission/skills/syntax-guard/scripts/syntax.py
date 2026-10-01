#!/usr/bin/env python3
"""syntax-guard: Immediate post-edit AST syntax and regex verification.

Lightweight, robust Python AST syntax verification skill designed to run
immediately after file edits (edit_file / write_file). Catches syntax defects,
unterminated strings, indentation errors, and unescaped regex lookbehinds
before wasting tool calls on failed test runners or submitting bad patches.

Features:
- Validates Python syntax using standard library ast.parse().
- Detects SyntaxError, IndentationError, TabError, and unterminated strings.
- Inspects regex patterns in re.* calls and string literals to catch
  unescaped regex lookbehinds, non-fixed-width lookbehinds, and malformed groups.
- Inspects git status -s / --porcelain if no file paths are specified on CLI.
- Emits clean, actionable output: file, line, column, offending snippet with
  visual caret pointer, and exact error message.
- Optional --json output mode.
- Exits with code 0 if all clean, exit code 1 if syntax errors exist.
- 100% standard library only (zero external dependencies).
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

sys.dont_write_bytecode = True


class SyntaxIssue:
    """Represents a diagnosed syntax or regex error in a target file."""

    def __init__(
        self,
        file_path: str,
        line_number: int,
        column: int,
        error_type: str,
        message: str,
        snippet: str,
        raw_line: str = "",
    ):
        self.file_path = file_path
        self.line_number = line_number
        self.column = column
        self.error_type = error_type
        self.message = message
        self.snippet = snippet
        self.raw_line = raw_line

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file_path,
            "line": self.line_number,
            "column": self.column,
            "error_type": self.error_type,
            "message": self.message,
            "snippet": self.snippet,
        }


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
    # Check if current directory has workspace / competition markers
    if (
        (cur / "tasks.jsonl").exists()
        or (cur / "my_submission").exists()
        or (cur / "sample_submission").exists()
    ):
        return cur

    for parent in [cur] + list(cur.parents):
        if (
            (parent / ".git").exists()
            or (parent / "pyproject.toml").exists()
            or (parent / "setup.py").exists()
            or (parent / "setup.cfg").exists()
        ):
            return parent

    return cur


def find_modified_python_files(ws: pathlib.Path) -> List[pathlib.Path]:
    """Inspect git status -s / --porcelain to find modified or untracked .py files."""
    git_bin = shutil.which("git") or "git"
    try:
        res = subprocess.run(
            [git_bin, "status", "--porcelain", "-uall"],
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if res.returncode != 0:
            res = subprocess.run(
                [git_bin, "status", "-s"],
                cwd=ws,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode != 0:
                return []
    except Exception:
        return []

    # Get git top level if possible to resolve relative porcelain paths accurately
    git_root = ws
    try:
        root_res = subprocess.run(
            [git_bin, "rev-parse", "--show-toplevel"],
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if root_res.returncode == 0 and root_res.stdout.strip():
            git_root = pathlib.Path(root_res.stdout.strip()).resolve()
    except Exception:
        pass

    found_files: List[pathlib.Path] = []
    for line in res.stdout.splitlines():
        line = line.rstrip()
        if not line or len(line) < 3:
            continue
        status_code = line[:2]
        rel_path = line[3:].strip().strip('"')
        if " -> " in rel_path:
            rel_path = rel_path.split(" -> ")[-1].strip().strip('"')

        # Skip deleted files
        if "D" in status_code:
            continue

        if not rel_path.endswith(".py"):
            continue

        file_path = (git_root / rel_path).resolve()
        if file_path.is_file():
            found_files.append(file_path)

    # Sort and deduplicate
    unique_files: List[pathlib.Path] = []
    seen: Set[pathlib.Path] = set()
    for f in found_files:
        if f not in seen:
            seen.add(f)
            unique_files.append(f)

    return sorted(unique_files)


def generate_snippet(
    source_lines: Sequence[str],
    lineno: int,
    column: int,
    context_lines: int = 1,
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
            # Highlight offending line with '>'
            line_display = line_content.expandtabs(4)
            output_lines.append(f"> {num_str} | {line_display}")

            # Align caret with expandtabs(4)
            col = max(1, column)
            prefix = line_content[: col - 1].expandtabs(4)
            caret_indent = " " * len(prefix)
            output_lines.append(f"  {blank_gutter} | {caret_indent}^")
        else:
            line_display = line_content.expandtabs(4)
            output_lines.append(f"  {num_str} | {line_display}")

    return "\n".join(output_lines)


class RegexSyntaxChecker(ast.NodeVisitor):
    """AST visitor that validates regular expression syntax and lookbehind patterns."""

    def __init__(self, file_path: str, source_lines: Sequence[str]):
        self.file_path = file_path
        self.source_lines = source_lines
        self.issues: List[SyntaxIssue] = []
        self.re_aliases: Set[str] = {"re"}
        self.re_func_imports: Dict[str, str] = {}
        self.docstring_node_ids: Set[int] = set()
        self.checked_node_ids: Set[int] = set()

    def visit(self, node: ast.AST):
        self._find_docstrings(node)
        super().visit(node)

    def _find_docstrings(self, root: ast.AST):
        """Identify docstring constant nodes to prevent false positives in markdown/docs."""
        for n in ast.walk(root):
            if isinstance(
                n,
                (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                if n.body and isinstance(n.body[0], ast.Expr):
                    val = n.body[0].value
                    if isinstance(val, ast.Constant) and isinstance(val.value, str):
                        self.docstring_node_ids.add(id(val))

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            if alias.name in ("re", "regex"):
                self.re_aliases.add(alias.asname or alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module in ("re", "regex"):
            for alias in node.names:
                self.re_func_imports[alias.asname or alias.name] = alias.name
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        re_func_name = None

        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id in self.re_aliases:
                re_func_name = node.func.attr
        elif isinstance(node.func, ast.Name):
            if node.func.id in self.re_func_imports:
                re_func_name = self.re_func_imports[node.func.id]

        if re_func_name in (
            "compile",
            "search",
            "match",
            "fullmatch",
            "split",
            "findall",
            "finditer",
            "sub",
            "subn",
        ):
            pattern_node = None
            if node.args:
                pattern_node = node.args[0]
            else:
                for kw in node.keywords:
                    if kw.arg == "pattern":
                        pattern_node = kw.value
                        break

            if pattern_node and isinstance(pattern_node, ast.Constant) and isinstance(pattern_node.value, str):
                self.checked_node_ids.add(id(pattern_node))
                self._verify_regex_pattern(
                    pattern=pattern_node.value,
                    node=pattern_node,
                    context=f"re.{re_func_name}()",
                )
        else:
            # Check for keyword arguments like pattern=... in any function call
            for kw in node.keywords:
                if (
                    kw.arg in ("pattern", "regex")
                    and isinstance(kw.value, ast.Constant)
                    and isinstance(kw.value.value, str)
                ):
                    self.checked_node_ids.add(id(kw.value))
                    self._verify_regex_pattern(
                        pattern=kw.value.value,
                        node=kw.value,
                        context=f"call keyword {kw.arg}=",
                    )

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        # Check if variable name indicates a regex pattern (e.g. PATTERN, *_RE, *_REGEX)
        is_regex_var = False
        target_name = ""
        for target in node.targets:
            if isinstance(target, ast.Name):
                name_lower = target.id.lower()
                if (
                    name_lower in ("pattern", "regex", "pat")
                    or name_lower.endswith(("_regex", "_re", "_pattern", "_pat"))
                    or name_lower.startswith(("re_", "regex_", "pat_"))
                ):
                    is_regex_var = True
                    target_name = target.id
                    break

        if (
            is_regex_var
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            val = node.value.value
            if (
                id(node.value) not in self.checked_node_ids
                and id(node.value) not in self.docstring_node_ids
            ):
                self.checked_node_ids.add(id(node.value))
                self._verify_regex_pattern(
                    pattern=val,
                    node=node.value,
                    context=f"assignment to {target_name}",
                )

        self.generic_visit(node)

    def _verify_regex_pattern(
        self,
        pattern: str,
        node: ast.AST,
        context: str,
    ):
        try:
            re.compile(pattern)
        except re.error as e:
            lineno = getattr(node, "lineno", 1)
            raw_line = (
                self.source_lines[lineno - 1]
                if 0 < lineno <= len(self.source_lines)
                else ""
            )

            # Determine column pointer
            col = getattr(node, "col_offset", 0) + 1
            if pattern in raw_line:
                idx = raw_line.find(pattern)
                offset = e.pos or 0
                col = max(1, idx + 1 + offset)

            snippet = generate_snippet(self.source_lines, lineno, col)
            error_type = (
                "UnescapedRegexLookbehind"
                if ("look-behind" in e.msg.lower() or "(?<=" in pattern or "(?<!" in pattern)
                else "RegexSyntaxError"
            )
            msg = f"{error_type}: {e.msg} (in {context})"

            self.issues.append(
                SyntaxIssue(
                    file_path=self.file_path,
                    line_number=lineno,
                    column=col,
                    error_type=error_type,
                    message=msg,
                    snippet=snippet,
                    raw_line=raw_line,
                )
            )


def check_python_file(file_path: pathlib.Path) -> List[SyntaxIssue]:
    """Check a single Python file for AST syntax errors and regex errors."""
    issues: List[SyntaxIssue] = []

    if not file_path.exists():
        snippet = "> 1 | (file does not exist on disk)"
        issues.append(
            SyntaxIssue(
                file_path=str(file_path),
                line_number=1,
                column=1,
                error_type="FileNotFoundError",
                message=f"File does not exist: {file_path}",
                snippet=snippet,
            )
        )
        return issues

    try:
        raw_bytes = file_path.read_bytes()
    except Exception as e:
        issues.append(
            SyntaxIssue(
                file_path=str(file_path),
                line_number=1,
                column=1,
                error_type="FileReadError",
                message=f"Could not read file: {e}",
                snippet="> 1 | (unreadable file)",
            )
        )
        return issues

    # Decode source lines for snippet generation
    try:
        source_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        source_text = raw_bytes.decode("latin-1", errors="replace")

    source_lines = source_text.splitlines()

    # Step 1: ast.parse()
    try:
        tree = ast.parse(raw_bytes, filename=str(file_path))
    except SyntaxError as e:
        lineno = e.lineno or 1
        col = e.offset or 1
        error_type = type(e).__name__
        msg = e.msg or "syntax error"

        if (
            "unterminated string literal" in msg.lower()
            or "unterminated triple-quoted string" in msg.lower()
        ):
            error_type = "UnterminatedStringLiteral"

        snippet = generate_snippet(source_lines, lineno, col)
        raw_line = (
            source_lines[lineno - 1]
            if 0 < lineno <= len(source_lines)
            else (e.text or "")
        )

        issues.append(
            SyntaxIssue(
                file_path=str(file_path),
                line_number=lineno,
                column=col,
                error_type=error_type,
                message=msg,
                snippet=snippet,
                raw_line=raw_line,
            )
        )
        return issues

    # Step 2: AST Regex & Lookbehind Verification
    regex_checker = RegexSyntaxChecker(str(file_path), source_lines)
    regex_checker.visit(tree)
    issues.extend(regex_checker.issues)

    return issues


def format_report(
    files_checked: Sequence[pathlib.Path],
    all_issues: Sequence[SyntaxIssue],
) -> str:
    """Format human-readable verification report."""
    total_files = len(files_checked)
    total_issues = len(all_issues)

    if total_issues == 0:
        if total_files == 0:
            return "✓ [syntax-guard] No modified or untracked Python files found to verify (clean working tree)."
        return f"✓ [syntax-guard] All {total_files} Python file(s) passed AST syntax verification."

    # Group issues by file
    failed_files = {issue.file_path for issue in all_issues}
    lines = [
        f"✗ [syntax-guard] Syntax error(s) detected in {len(failed_files)} of {total_files} file(s):",
        "",
    ]

    for idx, issue in enumerate(all_issues, 1):
        lines.append("=" * 80)
        lines.append(
            f"[{issue.error_type}] {issue.file_path}:{issue.line_number}:{issue.column}"
        )
        lines.append(f"Type:    {issue.error_type}")
        lines.append(f"Message: {issue.message}")
        lines.append("Snippet:")
        lines.append(issue.snippet)
        lines.append("=" * 80)
        lines.append("")

    lines.append(
        f"Fix: Correct syntax error(s) before running tests or calling submit_patch()."
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AST Syntax Guard: Fast, zero-dependency Python syntax and regex verification.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Python file(s) to verify. If omitted, checks modified/untracked .py files from git status.",
    )
    parser.add_argument(
        "--workspace",
        "-w",
        default=None,
        help="Workspace directory (default: SWEGEMMA_WORKSPACE, /workspace, or repo root).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit results in structured JSON format.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output (lists all checked files).",
    )

    args = parser.parse_args()
    ws = get_workspace_dir(args.workspace)

    # Determine files to inspect
    target_files: List[pathlib.Path] = []
    if args.files:
        for f_arg in args.files:
            p = pathlib.Path(f_arg)
            if p.is_file() or p.exists():
                target_files.append(p.resolve())
            elif not p.is_absolute() and (ws / p).exists():
                target_files.append((ws / p).resolve())
            elif not p.is_absolute():
                target_files.append((ws / p).resolve())
            else:
                target_files.append(p.resolve())
    else:
        target_files = find_modified_python_files(ws)

    # Run check
    all_issues: List[SyntaxIssue] = []
    for file_path in target_files:
        issues = check_python_file(file_path)
        all_issues.extend(issues)

    has_errors = len(all_issues) > 0

    if args.json:
        result_dict = {
            "status": "FAILED" if has_errors else "PASSED",
            "files_checked": [str(p) for p in target_files],
            "total_checked": len(target_files),
            "total_errors": len(all_issues),
            "errors": [issue.to_dict() for issue in all_issues],
        }
        print(json.dumps(result_dict, indent=2))
    else:
        report = format_report(target_files, all_issues)
        print(report)

    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
