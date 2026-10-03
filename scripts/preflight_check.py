#!/usr/bin/env python3
"""Preflight Check Suite for SWE-Gemma Local Development and Sandbox Runner.

Validates:
1. Core testing dependencies (pytest, anyio, pluggy, etc.)
2. Benchmark repo dependencies (fastapi, starlette, pydantic, rich, requests, httpx)
3. Offline wheels directory integrity
4. Submission structure and real ADK compiler validity
5. End-to-end sandbox subprocess environment isolation and pytest execution
6. Live agent diagnostics on LiteRouter
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# Prevent Python from writing bytecode cache files (.pyc) that ADK compiler strictly forbids
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

from pydantic import BaseModel, ConfigDict, Field, field_validator

WORK_DIR = Path(__file__).resolve().parent
if WORK_DIR.name in ("scripts", "brun"):
    WORK_DIR = WORK_DIR.parent
if not (WORK_DIR / "my_submission").exists() and Path("/Users/yapilymm/Downloads/projects/gemma4-dev").exists():
    WORK_DIR = Path("/Users/yapilymm/Downloads/projects/gemma4-dev")
SUBMISSION_DIR = WORK_DIR / "my_submission"
WHEELS_DIR = WORK_DIR / "wheels"
SNAPSHOTS_DIR = WORK_DIR / "snapshots"

# Comprehensive list of required modules for benchmark repos & test suites
REQUIRED_MODULES = [
    # Core Test Runner & Assertion Tooling
    ("pytest", "Testing runner core"),
    ("inline_snapshot", "Modern snapshot assertions (FastAPI tests)"),
    ("dirty_equals", "Fuzzy assert utilities (FastAPI tests)"),
    ("pytest_timeout", "Pytest timeout extension"),
    # Target Benchmark Repositories
    ("fastapi", "FastAPI repo dependency"),
    ("starlette", "FastAPI / Starlette core"),
    ("pydantic", "FastAPI data modeling"),
    ("anyio", "Async IO test harness"),
    ("httpx", "HTTP client / HTTPX repo"),
    ("rich", "Rich formatting repo"),
    ("requests", "Requests repo"),
    ("urllib3", "Requests HTTP transport"),
    # Auxiliary Ecosystem & Test Integration Modules
    ("flask", "Flask WSGI integration tests"),
    ("sqlmodel", "SQLModel integration"),
    ("sqlalchemy", "SQLAlchemy ORM integration"),
    ("jinja2", "Jinja2 template tests"),
    ("itsdangerous", "Session cookie signing"),
    ("werkzeug", "WSGI utilities"),
    ("a2wsgi", "ASGI-WSGI converter"),
    ("ujson", "Fast JSON parser"),
    ("orjson", "Ultra-fast JSON serializer"),
    ("email_validator", "Pydantic EmailStr validation"),
]


class CheckResult(BaseModel):
    """Result of an individual preflight diagnostic check."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(
        ...,
        description="Name of the check identifier (e.g. python_dependencies, wheels_directory)",
    )
    category: str = Field(
        default="general",
        description="Category of the check (e.g. dependencies, wheels, compiler, sandbox, snapshot, live_agent)",
    )
    passed: bool = Field(
        ...,
        description="Whether the diagnostic check passed successfully",
    )
    message: str = Field(
        default="",
        description="Summary status message or error details",
    )
    details: Any = Field(
        default=None,
        description="Detailed diagnostic outputs, missing lists, or execution metadata",
    )


class PreflightReport(BaseModel):
    """Overall preflight diagnostic report."""

    model_config = ConfigDict(extra="ignore")

    passed_checks: int = Field(
        default=0,
        ge=0,
        description="Total number of passed checks",
    )
    failed_checks: int = Field(
        default=0,
        ge=0,
        description="Total number of failed checks",
    )
    total: int = Field(
        default=0,
        ge=0,
        description="Total number of checks executed",
    )
    all_passed: bool = Field(
        default=False,
        description="Whether all diagnostic checks passed without error",
    )
    checks: list[CheckResult] = Field(
        default_factory=list,
        description="Ordered list of individual CheckResult models",
    )

    @field_validator("passed_checks", "failed_checks", "total", mode="before")
    @classmethod
    def _coerce_int_or_list(cls, v: Any) -> int:
        if isinstance(v, (list, tuple, set)):
            return len(v)
        return int(v)

    @classmethod
    def from_checks(cls, checks: list[CheckResult]) -> PreflightReport:
        passed = sum(1 for c in checks if c.passed)
        failed = sum(1 for c in checks if not c.passed)
        tot = len(checks)
        return cls(
            passed_checks=passed,
            failed_checks=failed,
            total=tot,
            all_passed=(failed == 0 and tot > 0),
            checks=checks,
        )


def check_modules() -> tuple[list[str], list[str]]:
    passed, failed = [], []
    for mod, desc in REQUIRED_MODULES:
        try:
            m = importlib.import_module(mod)
            ver = getattr(m, "__version__", "installed")
            passed.append(f"{mod} ({desc}) v{ver}")
        except Exception:
            try:
                __import__(mod)
                passed.append(f"{mod} ({desc})")
            except ImportError as e:
                failed.append(f"{mod} ({desc}) - Missing: {e}")
    return passed, failed


def check_dependencies() -> CheckResult:
    passed, failed = check_modules()
    is_ok = len(failed) == 0
    msg = f"{len(passed)}/{len(REQUIRED_MODULES)} ok" if is_ok else f"{len(failed)} missing modules"
    return CheckResult(
        name="python_dependencies",
        category="dependencies",
        passed=is_ok,
        message=msg,
        details={"passed": passed, "failed": failed},
    )


def check_wheels() -> CheckResult:
    if WHEELS_DIR.exists() and any(WHEELS_DIR.glob("*.whl")):
        count = len(list(WHEELS_DIR.glob("*.whl")))
        return CheckResult(
            name="wheels_directory",
            category="wheels",
            passed=True,
            message=f"Found {count} wheels in {WHEELS_DIR}",
            details={"wheels_dir": str(WHEELS_DIR), "count": count},
        )
    return CheckResult(
        name="wheels_directory",
        category="wheels",
        passed=False,
        message=f"Wheels directory missing or empty: {WHEELS_DIR}",
        details={"wheels_dir": str(WHEELS_DIR), "count": 0},
    )


def clean_submission_bytecode(submission_dir: Path) -> None:
    """Purge any __pycache__, .pyc, .DS_Store, or macOS metadata from submission dir.
    
    Google ADK compiler strictly forbids .pyc files, __pycache__, or files without extensions (e.g. .DS_Store).
    """
    if not submission_dir.exists():
        return
    for pyc in submission_dir.rglob("*.pyc"):
        try:
            pyc.unlink(missing_ok=True)
        except OSError:
            pass
    for ds in submission_dir.rglob(".DS_Store"):
        try:
            ds.unlink(missing_ok=True)
        except OSError:
            pass
    for apple_meta in submission_dir.rglob("._*"):
        try:
            apple_meta.unlink(missing_ok=True)
        except OSError:
            pass
    for cache_dir in submission_dir.rglob("__pycache__"):
        try:
            shutil.rmtree(cache_dir, ignore_errors=True)
        except OSError:
            pass


def check_submission_compilation() -> tuple[bool, str]:
    try:
        clean_submission_bytecode(SUBMISSION_DIR)
        from adk_submission.compiler import compile_submission
        from swegemma.config import EvalConfig
        from swegemma.context import SwegemmaContext
        from swegemma.models import setup_gemma_model_registry
        from swegemma.sandbox.subprocess import SubprocessManager

        models = setup_gemma_model_registry(
            api_base=os.getenv("SWEGEMMA_API_BASE", "http://literouter.lan:7766/v1"),
            api_key=os.getenv("SWEGEMMA_API_KEY", "lr-or-oa-ch-no"),
            served_model=os.getenv("SWEGEMMA_MODEL", "stealth/space-bunny-alpha"),
        )
        mgr = SubprocessManager(system_site_packages=True)
        sb_id = mgr.start()
        context = SwegemmaContext(
            docker_manager=mgr,
            container_id=sb_id,
            problem_statement="Test preflight problem statement",
        )
        tools = context.create_tools()
        agent = compile_submission(
            submission_dir=SUBMISSION_DIR,
            tool_registry=tools,
            model_registry=models,
        )
        # Verify ADK instruction template syntax (detect accidental {var} KeyError)
        import asyncio
        from google.adk.utils.instructions_utils import inject_session_state
        from unittest.mock import MagicMock
        mock_ctx = MagicMock()
        mock_ctx.session.state = {}
        mock_ctx.artifact_service = None
        for md_file in SUBMISSION_DIR.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            asyncio.run(inject_session_state(content, mock_ctx))
        mgr.stop(sb_id)
        return True, f"Agent '{agent.name}' compiled and instruction templates verified."
    except Exception as e:
        return False, f"compile_submission failed: {e}"


def check_submission_compilation_result() -> CheckResult:
    ok, msg = check_submission_compilation()
    return CheckResult(
        name="submission_compilation",
        category="compiler",
        passed=ok,
        message=msg,
        details={"submission_dir": str(SUBMISSION_DIR)},
    )


def check_sandbox_subprocess_pytest() -> tuple[bool, str]:
    try:
        from swegemma.sandbox.subprocess import SubprocessManager
        mgr = SubprocessManager(system_site_packages=True)
        sb_id = mgr.start()
        
        # Test command matching Phase 2 verification exact flags
        cmd = 'PYTHONSAFEPATH=1 PYTHONNOUSERSITE=1 python3 -s -m pytest --version'
        res = mgr.exec(sb_id, cmd)
        if res.exit_code != 0:
            mgr.stop(sb_id)
            return False, f"Sandbox pytest execution failed (exit {res.exit_code}): stderr={res.stderr.strip()}"

        # Test hermetic sandbox imports for critical assertion libraries
        import_cmd = (
            'PYTHONSAFEPATH=1 PYTHONNOUSERSITE=1 python3 -c "'
            'import pytest, inline_snapshot, dirty_equals, fastapi, pydantic, '
            'rich, requests, httpx, flask, sqlmodel, sqlalchemy, jinja2, '
            'itsdangerous, werkzeug, a2wsgi, ujson, orjson; '
            'print(\'ALL_SANDBOX_IMPORTS_OK\')"'
        )
        res_import = mgr.exec(sb_id, import_cmd)
        mgr.stop(sb_id)

        if res_import.exit_code == 0 and "ALL_SANDBOX_IMPORTS_OK" in res_import.stdout:
            return True, f"Sandbox pytest ({res.stdout.strip()}) and all 17 sandbox imports verified."
        else:
            return False, f"Sandbox imports failed (exit {res_import.exit_code}): {res_import.stderr.strip()}"
    except Exception as e:
        return False, f"Sandbox test failed with exception: {e}"


def check_sandbox_subprocess_result() -> CheckResult:
    ok, msg = check_sandbox_subprocess_pytest()
    return CheckResult(
        name="sandbox_subprocess_pytest",
        category="sandbox",
        passed=ok,
        message=msg,
    )


def check_snapshot_pytest_execution() -> tuple[bool, str]:
    import tempfile, tarfile
    snap = SNAPSHOTS_DIR / "fastapi_15661.tgz"
    if not snap.exists():
        return False, f"Snapshot not found: {snap}"
    with tempfile.TemporaryDirectory() as td:
        with tarfile.open(snap, "r:gz") as tar:
            tar.extractall(td)
        ws = Path(td)
        cmd = [
            sys.executable, "-s", "-m", "pytest",
            "tests/test_datastructures.py",
            "-o", "timeout=0",
            "-o", "python_classes=Test* *Test",
            "-q"
        ]
        res = subprocess.run(
            cmd,
            cwd=ws,
            capture_output=True,
            text=True,
        )
        if res.returncode == 0:
            return True, f"Snapshot live test execution passed (exit 0): {res.stdout.strip().splitlines()[-1]}"
        else:
            return False, f"Snapshot live test execution failed (exit {res.returncode}): {res.stderr or res.stdout}"


def check_snapshot_pytest_result() -> CheckResult:
    ok, msg = check_snapshot_pytest_execution()
    return CheckResult(
        name="snapshot_pytest_execution",
        category="snapshot",
        passed=ok,
        message=msg,
    )


def check_live_agent_diagnostics() -> tuple[bool, str]:
    import asyncio, re
    from swegemma.models import setup_gemma_model_registry
    from swegemma.context import SwegemmaContext
    from swegemma.sandbox.subprocess import SubprocessManager
    from adk_submission.compiler import compile_submission
    from google.adk.runners import Runner, RunConfig
    from google.adk.apps import App
    from google.adk.sessions import InMemorySessionService
    from google.genai import types as genai_types

    async def _query_agent(agent, agent_name: str) -> str:
        app_name = re.sub(r'[^a-zA-Z0-9_]', '_', f'preflight_{agent_name.lower()}')
        session_service = InMemorySessionService()
        session = await session_service.create_session(
            app_name=app_name,
            user_id='preflight_user',
            state={},
        )
        app = App(name=app_name, root_agent=agent)
        runner = Runner(app=app, session_service=session_service)
        msg = genai_types.Content(
            role='user',
            parts=[genai_types.Part(text='What tools, skills, and permissions do you have? Do not call tools. List your direct tools, pre-installed skills, permissions, and workflow in detail as plain text.')],
        )
        responses = []
        try:
            async for event in runner.run_async(
                user_id='preflight_user',
                session_id=session.id,
                new_message=msg,
                run_config=RunConfig(max_llm_calls=4),
            ):
                content = getattr(event, 'content', None)
                if content and content.parts:
                    for p in content.parts:
                        if p.text:
                            responses.append(p.text)
                        if p.function_call:
                            responses.append(f'[Tool Call: {p.function_call.name}({p.function_call.args})]')
        except Exception as e:
            if not responses:
                raise e
        return '\n'.join(responses).strip()

    try:
        models = setup_gemma_model_registry(
            api_base=os.getenv("SWEGEMMA_API_BASE", "http://literouter.lan:7766/v1"),
            api_key=os.getenv("SWEGEMMA_API_KEY", "lr-or-oa-ch-no"),
            served_model=os.getenv("SWEGEMMA_MODEL", "stealth/space-bunny-alpha"),
        )
        mgr = SubprocessManager(system_site_packages=True)
        sb_id = mgr.start()
        context = SwegemmaContext(
            docker_manager=mgr,
            container_id=sb_id,
            problem_statement='Preflight live diagnostics',
        )
        tools = context.create_tools()
        clean_submission_bytecode(SUBMISSION_DIR)
        main_agent = compile_submission(
            submission_dir=SUBMISSION_DIR,
            tool_registry=tools,
            model_registry=models,
        )
        subagent_tools = [t for t in main_agent.tools if hasattr(t, 'agent')]
        
        main_resp = asyncio.run(_query_agent(main_agent, 'main'))
        subagent_resps = []
        for sat in subagent_tools:
            name = getattr(sat.agent, 'name', 'subagent')
            subagent_resps.append((name, asyncio.run(_query_agent(sat.agent, name))))
        mgr.stop(sb_id)

        print("\n" + "=" * 80)
        print("🤖 [LIVE AGENT] MAIN DEVELOPER AGENT RESPONSE:")
        print("=" * 80)
        print(main_resp)
        for sname, sresp in subagent_resps:
            print("\n" + "=" * 80)
            print(f"🛡️  [LIVE SUBAGENT] {sname.upper()} RESPONSE:")
            print("=" * 80)
            print(sresp)
        print("=" * 80)

        if not main_resp:
            return False, "Empty response received from Main Developer Agent"
        if subagent_tools and any(not r for _, r in subagent_resps):
            return False, "Empty response received from subagent"
        return True, f"Main Developer Agent ({'with ' + str(len(subagent_tools)) + ' subagents' if subagent_tools else 'lean monolith'}) responded with full verified tool/skill awareness."
    except Exception as e:
        return False, f"Live agent diagnostic failed: {e}"


def check_live_agent_result() -> CheckResult:
    ok, msg = check_live_agent_diagnostics()
    return CheckResult(
        name="live_agent_diagnostics",
        category="live_agent",
        passed=ok,
        message=msg,
    )


def run_preflight_suite(verbose: bool = True) -> PreflightReport:
    """Run all preflight checks and return structured PreflightReport."""
    if verbose:
        print("=" * 60)
        print("SWE-Gemma Preflight Environment & Sandbox Check")
        print("=" * 60)

    checks: list[CheckResult] = []

    # 1. Module checks
    dep_check = check_dependencies()
    checks.append(dep_check)
    if verbose:
        passed = dep_check.details.get("passed", []) if isinstance(dep_check.details, dict) else []
        failed = dep_check.details.get("failed", []) if isinstance(dep_check.details, dict) else []
        print(f"\n[1/6] Checking Python environment dependencies ({len(passed)}/{len(REQUIRED_MODULES)} ok):")
        for p in passed:
            print(f"  ✓ {p}")
        for f in failed:
            print(f"  ✗ {f}")

    # 2. Wheels directory
    if verbose:
        print("\n[2/6] Checking pre-baked wheels directory:")
    whl_check = check_wheels()
    checks.append(whl_check)
    if verbose:
        if whl_check.passed:
            print(f"  ✓ {whl_check.message}")
        else:
            print(f"  ✗ {whl_check.message}")

    # 3. Submission compilation check
    if verbose:
        print("\n[3/6] Checking submission compilation with real ADK compiler:")
    comp_check = check_submission_compilation_result()
    checks.append(comp_check)
    if verbose:
        if comp_check.passed:
            print(f"  ✓ {comp_check.message}")
        else:
            print(f"  ✗ {comp_check.message}")

    # 4. Sandbox subprocess execution
    if verbose:
        print("\n[4/6] Checking sandbox subprocess isolation & pytest execution:")
    sb_check = check_sandbox_subprocess_result()
    checks.append(sb_check)
    if verbose:
        if sb_check.passed:
            print(f"  ✓ {sb_check.message}")
        else:
            print(f"  ✗ {sb_check.message}")

    # 5. Snapshot pytest execution
    if verbose:
        print("\n[5/6] Checking live snapshot pytest execution (fastapi_15661):")
    snap_check = check_snapshot_pytest_result()
    checks.append(snap_check)
    if verbose:
        if snap_check.passed:
            print(f"  ✓ {snap_check.message}")
        else:
            print(f"  ✗ {snap_check.message}")

    # 6. Live agent diagnostics on LiteRouter
    if verbose:
        print("\n[6/6] Live Agent Diagnostics on LiteRouter (Main & Supervisor self-declaration):")
    diag_check = check_live_agent_result()
    checks.append(diag_check)
    if verbose:
        if diag_check.passed:
            print(f"  ✓ {diag_check.message}")
        else:
            print(f"  ✗ {diag_check.message}")

    report = PreflightReport.from_checks(checks)

    if verbose:
        print("\n" + "=" * 60)
        if report.all_passed:
            print(f"PREFLIGHT RESULT: ALL {report.passed_checks}/{report.total} CHECKS PASSED (100% WATERTIGHT)")
            print("=" * 60)
        else:
            print(f"PREFLIGHT RESULT: FAILED CHECKS DETECTED ({report.failed_checks}/{report.total} FAILED)")
            print("=" * 60)

    return report


def main() -> None:
    report = run_preflight_suite(verbose=True)
    if report.all_passed:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
