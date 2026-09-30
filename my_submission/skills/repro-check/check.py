#!/usr/bin/env python3
"""repro-check: Omnivorous Defect Reproduction & Verification Engine.

Eats ANY input format:
- Auto-asserts bare comparison expressions: `a == b` -> `assert a == b`
- Auto-invokes uncalled test functions: `def test_...():`
- Strips markdown fences (```py, ```python, etc.) and auto-dedents
- Guarantees zero workspace git pollution (executes inside isolated /tmp cwd)
- Prioritizes /workspace and /workspace/src in PYTHONPATH
- Distinguishes between Assertion Failures, Workspace Exceptions, and Probes
- Active probe budget limiter: circuit breaker after 2 exploratory probes
- Always exits 0 and never crashes.
"""

import ast
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import textwrap
from typing import List, Optional, Set, Tuple

PROBE_COUNT_FILE = pathlib.Path("/tmp/.swegemma_repro_probe_count")


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

    ws = pathlib.Path("/workspace")
    if ws.is_dir():
        return ws.resolve()

    return pathlib.Path.cwd().resolve()


def clean_and_normalize_code(raw_args: List[str]) -> str:
    """Extract code from arbitrary CLI arguments, stripping fences and normalizing indentation."""
    # If passed as multiple arguments, join with newlines
    code = "\n".join(raw_args).strip()

    # Strip markdown code blocks: ```python ... ``` or ```py ... ``` or ``` ... ```
    code = re.sub(r"^```[a-zA-Z0-9_-]*\s*\n?", "", code)
    code = re.sub(r"\n?```\s*$", "", code)

    # Handle accidental literal escaped newlines (e.g. "\\n" instead of "\n" if passed improperly)
    if "\\n" in code and "\n" not in code:
        code = code.replace("\\n", "\n")

    return textwrap.dedent(code).strip()


class OmnivorousCodeTransformer(ast.NodeTransformer):
    """AST Transformer that converts bare comparison expressions into assertions and tracks tests."""

    def __init__(self) -> None:
        super().__init__()
        self.transformed_comparisons = 0
        self.explicit_asserts = 0
        self.defined_test_funcs: Set[str] = set()
        self.called_funcs: Set[str] = set()

    def visit_Assert(self, node: ast.Assert) -> ast.AST:
        self.explicit_asserts += 1
        return self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        name = node.name.lower()
        if name.startswith(("test_", "check_", "verify_")):
            self.defined_test_funcs.add(node.name)
        return self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        name = node.name.lower()
        if name.startswith(("test_", "check_", "verify_")):
            self.defined_test_funcs.add(node.name)
        return self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> ast.AST:
        if isinstance(node.func, ast.Name):
            self.called_funcs.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            self.called_funcs.add(node.func.attr)
        return self.generic_visit(node)

    def visit_Expr(self, node: ast.Expr) -> ast.AST:
        # If the statement is a standalone comparison expression: `a == b` or `x in y`
        # Auto-transform it into `assert <expr>`
        if isinstance(node.value, ast.Compare):
            self.transformed_comparisons += 1
            msg = f"Check failed (auto-asserted): {ast.unparse(node.value) if hasattr(ast, 'unparse') else 'comparison'}"
            new_assert = ast.Assert(
                test=node.value,
                msg=ast.Constant(value=msg),
            )
            return ast.copy_location(new_assert, node)
        return self.generic_visit(node)


def prepare_executable_code(code: str) -> Tuple[str, bool, int]:
    """Parse, transform, and auto-wire code for flawless execution."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        # If AST parsing fails, return raw code so python interpreter gives the exact traceback
        return code, False, 0

    transformer = OmnivorousCodeTransformer()
    new_tree = transformer.visit(tree)
    ast.fix_missing_locations(new_tree)

    # Check uncalled test functions
    uncalled = transformer.defined_test_funcs - transformer.called_funcs
    has_checks = (
        transformer.explicit_asserts > 0
        or transformer.transformed_comparisons > 0
        or len(transformer.defined_test_funcs) > 0
        or "pytest.raises" in code
        or "unittest" in code
    )

    total_checks = transformer.explicit_asserts + transformer.transformed_comparisons

    # Auto-generate runner calls for any uncalled test functions
    new_code = ast.unparse(new_tree) if hasattr(ast, "unparse") else code
    if uncalled:
        runner_lines = ["\n# --- Auto-generated Test Invocations by repro-check ---"]
        for fn in sorted(uncalled):
            runner_lines.append(f"{fn}()")
        new_code += "\n".join(runner_lines) + "\n"

    return new_code, has_checks, total_checks


def execute_script(
    code_to_run: str, ws: pathlib.Path, timeout_secs: int = 45
) -> Tuple[int, str, str]:
    """Execute code in an isolated /tmp sandbox with /workspace imports."""
    with tempfile.TemporaryDirectory(prefix="swegemma_repro_") as temp_dir:
        temp_dir_path = pathlib.Path(temp_dir)
        script_file = temp_dir_path / "repro_test.py"
        script_file.write_text(code_to_run, encoding="utf-8")

        # Build clean, robust environment
        env = dict(os.environ)
        # Prioritize workspace/src and workspace
        src_path = str(ws / "src")
        ws_path = str(ws)
        current_py_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{src_path}:{ws_path}:{current_py_path}".strip(":")
        env["PYTHONSAFEPATH"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        cmd = [sys.executable, "-s", str(script_file)]

        try:
            res = subprocess.run(
                cmd,
                cwd=temp_dir_path,  # Crucial: runs in /tmp, NEVER in /workspace!
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_secs,
            )
            return res.returncode, res.stdout.strip(), res.stderr.strip()
        except subprocess.TimeoutExpired:
            return 124, "", f"Execution timed out after {timeout_secs} seconds."
        except Exception as e:
            return 1, "", f"Failed to execute process: {e}"


def get_probe_count() -> int:
    """Retrieve the current exploratory probe count."""
    try:
        if PROBE_COUNT_FILE.exists():
            return int(PROBE_COUNT_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        pass
    return 0


def increment_probe_count() -> int:
    """Increment and persist the exploratory probe count."""
    count = get_probe_count() + 1
    try:
        PROBE_COUNT_FILE.write_text(str(count), encoding="utf-8")
    except Exception:
        pass
    return count


def reset_probe_count() -> None:
    """Reset the exploratory probe count to 0."""
    try:
        PROBE_COUNT_FILE.write_text("0", encoding="utf-8")
    except Exception:
        pass


def main() -> int:
    try:
        raw_args = sys.argv[1:]
        if not raw_args:
            print("[repro-check] No code provided. Usage: run_skill_script('repro-check', 'check.py', args=['<code>'])")
            return 0

        code = clean_and_normalize_code(raw_args)
        if not code:
            print("[repro-check] Empty code provided.")
            return 0

        ws = get_workspace_dir()
        transformed_code, has_checks, check_count = prepare_executable_code(code)

        exit_code, stdout, stderr = execute_script(transformed_code, ws)

        # -------------------------------------------------------------
        # Classification & Reporting
        # -------------------------------------------------------------
        if exit_code == 0:
            if has_checks:
                reset_probe_count()
                print("[repro-check] ✅ PASSED: All assertions and checks passed with 0 errors.")
                if stdout:
                    print(stdout)
                return 0
            else:
                count = increment_probe_count()
                print("[repro-check] 📋 PROBE EXECUTION (Exit code 0):")
                if stdout:
                    print(stdout)
                if count >= 2:
                    print(
                        "[repro-check] ⚠️ PROBE BUDGET REACHED (2/2 probes used): "
                        "You have executed 2 exploratory probes without reproducing a defect or failing an assertion. "
                        "Stop probing! Formulate your defect hypothesis, locate candidate source lines, and call edit_file immediately."
                    )
                return 0

        # Non-zero exit code: Analyze failure
        combined_err = f"{stderr}\n{stdout}".strip()

        # Case A: Defect confirmed via AssertionError
        if "AssertionError" in combined_err:
            reset_probe_count()
            print("[repro-check] 🎯 DEFECT CONFIRMED (Assertion Failed):")
            lines = [l for l in combined_err.splitlines() if l.strip()][-10:]
            for l in lines:
                print(f"  {l}")
            return 0

        # Case B: Defect confirmed via Workspace Runtime Exception (e.g. AttributeError, KeyError in repo code)
        ws_str = str(ws)
        if ws_str in combined_err:
            reset_probe_count()
            print("[repro-check] 💥 DEFECT REPRODUCED (Workspace Runtime Exception):")
            lines = [l for l in combined_err.splitlines() if l.strip()][-12:]
            for l in lines:
                print(f"  {l}")
            return 0

        # Case C: SyntaxError in the test script itself
        if "SyntaxError" in combined_err:
            print("[repro-check] ⚠️ TEST SCRIPT SYNTAX ERROR:")
            lines = [l for l in combined_err.splitlines() if l.strip()][-6:]
            for l in lines:
                print(f"  {l}")
            return 0

        # Case D: General Execution Failure
        print(f"[repro-check] ❌ EXECUTION FAILED (Exit code {exit_code}):")
        lines = [l for l in combined_err.splitlines() if l.strip()][-10:]
        for l in lines:
            print(f"  {l}")

        return 0
    except Exception as e:
        print(f"[repro-check] Runner error: {e}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
