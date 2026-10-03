#!/usr/bin/env python3
"""Configurable SWE-Gemma evaluation runner for local and full benchmark runs."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import litellm
from pydantic import BaseModel, ConfigDict, Field, model_validator

litellm.drop_params = True

from swegemma.config import EvalConfig
from swegemma.evaluate import Evaluator
from swegemma.models import setup_gemma_model_registry

ROOT_DIR = Path(__file__).resolve().parent.parent


class EvalRunConfig(BaseModel):
    """Configuration and CLI arguments for SWE-Gemma evaluation run."""

    model_config = ConfigDict(extra="ignore")

    model: str = Field(
        default_factory=lambda: os.getenv("SWEGEMMA_MODEL", "stealth/space-bunny-alpha"),
        description="Model identifier on LiteRouter (default: stealth/space-bunny-alpha)",
    )
    api_base: str = Field(
        default_factory=lambda: os.getenv("SWEGEMMA_API_BASE", "http://literouter.lan:7766/v1"),
        description="API Base URL (default: http://literouter.lan:7766/v1)",
    )
    api_key: str = Field(
        default_factory=lambda: os.getenv("SWEGEMMA_API_KEY", "lr-or-oa-ch-no"),
        description="API Key (default: lr-or-oa-ch-no or SWEGEMMA_API_KEY env var)",
    )
    concurrency: int = Field(
        default_factory=lambda: int(os.getenv("SWEGEMMA_CONCURRENCY", "15")),
        ge=1,
        description="Parallel task evaluations (default: 15)",
    )
    max_tool_calls: int = Field(
        default=50,
        ge=1,
        description="Max tool calls per task (default: 50)",
    )
    max_time_minutes: int = Field(
        default=30,
        ge=1,
        description="Max minutes per task (default: 30)",
    )
    display: str = Field(
        default="dashboard",
        description="Display mode: dashboard, single, auto, quiet (default: dashboard)",
    )
    all: bool = Field(
        default=False,
        description="Run all tasks in tasks.jsonl (bypasses test.txt)",
    )
    task_ids: list[str] | None = Field(
        default=None,
        description="Specific task ID(s) to evaluate (e.g. fastapi_15588)",
    )
    pilot: bool = Field(
        default=False,
        description="Run 2-task pilot (fastapi_15661 and fastapi_15588)",
    )
    tasks_file: str = Field(
        default="test.txt",
        description="Path to file listing tasks to run (default: test.txt)",
    )
    run_name: str | None = Field(
        default=None,
        description="Explicit run name (e.g. run_B05). If not set, auto-increments run_Bxx",
    )


class TaskEvalResult(BaseModel):
    """Structured evaluation outcome for a single task."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    instance_id: str = Field(
        ...,
        description="Unique task / problem instance identifier (e.g. fastapi_15661)",
    )
    repo: str = Field(
        default="",
        description="Repository identifier (e.g. fastapi/fastapi)",
    )
    resolved: bool = Field(
        default=False,
        description="Whether the task was successfully resolved according to benchmark criteria",
    )
    agent_patch_size: int = Field(
        default=0,
        ge=0,
        description="Size of generated patch in bytes / characters",
    )
    test_exit_code: int = Field(
        default=0,
        description="Process exit code from running pytest",
    )
    duration_seconds: float = Field(
        default=0.0,
        ge=0.0,
        description="Total task execution wall-clock time in seconds",
    )
    error: str | None = Field(
        default=None,
        description="Failure details or traceback if execution faulted",
    )
    tool_calls: int = Field(
        default=0,
        ge=0,
        description="Total number of tool calls executed",
    )
    total_llm_calls: int = Field(
        default=0,
        ge=0,
        description="Total number of LLM calls executed",
    )
    task_index: int | None = Field(
        default=None,
        description="Original 1-based task index",
    )

    @model_validator(mode="before")
    @classmethod
    def _remap_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "instance_id" not in data and "task_id" in data:
                data["instance_id"] = data["task_id"]
            if "agent_patch_size" not in data and "agent_patch" in data:
                patch = data.get("agent_patch") or ""
                data["agent_patch_size"] = len(patch.encode("utf-8") if isinstance(patch, str) else patch)
            if "error" not in data and "error_message" in data:
                data["error"] = data["error_message"]
        return data

    @classmethod
    def from_task_result(cls, r: Any) -> "TaskEvalResult":
        patch = getattr(r, "agent_patch", "") or ""
        patch_size = len(patch.encode("utf-8")) if isinstance(patch, str) else len(patch)
        return cls(
            instance_id=getattr(r, "instance_id", None) or getattr(r, "task_id", "") or "unknown",
            repo=getattr(r, "repo", "") or "",
            resolved=bool(getattr(r, "resolved", False)),
            agent_patch_size=patch_size,
            test_exit_code=int(getattr(r, "test_exit_code", 0) or 0),
            duration_seconds=float(getattr(r, "duration_seconds", 0.0) or 0.0),
            error=getattr(r, "error_message", None) or getattr(r, "error", None),
            tool_calls=int(getattr(r, "tool_calls", 0) or 0),
            total_llm_calls=int(getattr(r, "total_llm_calls", 0) or 0),
            task_index=getattr(r, "task_index", None),
        )


class RunSummary(BaseModel):
    """Structured overall evaluation run summary."""

    model_config = ConfigDict(extra="ignore")

    total_tasks: int = Field(
        default=0,
        ge=0,
        description="Total tasks evaluated",
    )
    resolved: int = Field(
        default=0,
        ge=0,
        description="Total tasks resolved successfully",
    )
    resolution_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Resolution rate fraction between 0.0 and 1.0",
    )
    by_repo: dict[str, Any] = Field(
        default_factory=dict,
        description="Evaluation metrics grouped by repository",
    )
    errors: int = Field(
        default=0,
        ge=0,
        description="Number of tasks that encountered runtime errors",
    )

    @classmethod
    def from_evaluation_result(
        cls, eval_result: Any, task_results: list[TaskEvalResult] | None = None
    ) -> "RunSummary":
        total = int(getattr(eval_result, "total", 0) or 0)
        resolved = int(getattr(eval_result, "resolved", 0) or 0)
        res_rate = float(getattr(eval_result, "resolution_rate", 0.0) or 0.0)
        by_repo = eval_result.by_repo() if hasattr(eval_result, "by_repo") else {}
        if task_results is not None:
            err_count = sum(1 for r in task_results if r.error is not None)
        else:
            raw_trs = getattr(eval_result, "task_results", [])
            err_count = sum(1 for r in raw_trs if getattr(r, "error", None) or getattr(r, "error_message", None))
        return cls(
            total_tasks=total,
            resolved=resolved,
            resolution_rate=round(res_rate, 4),
            by_repo=by_repo,
            errors=err_count,
        )


def get_next_run_dir(results_dir: Path, prefix: str = "run_B") -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    existing = [d.name for d in results_dir.iterdir() if d.is_dir() and d.name.startswith(prefix)]
    max_num = 0
    for name in existing:
        match = re.match(rf"^{re.escape(prefix)}(\d+)$", name)
        if match:
            max_num = max(max_num, int(match.group(1)))
    next_num = max_num + 1
    return results_dir / f"{prefix}{next_num:02d}"


def load_tasks_from_file(file_path: Path) -> list[str]:
    """Load non-empty, non-comment lines from a tasks file."""
    tasks = []
    seen = set()
    if not file_path.exists():
        return tasks
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            task_id = line.split("#", 1)[0].strip()
            if task_id and task_id not in seen:
                seen.add(task_id)
                tasks.append(task_id)
    return tasks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run SWE-Gemma evaluation with live Rich dashboard.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all tasks in tasks.jsonl (bypasses test.txt)",
    )
    parser.add_argument(
        "--task-id",
        "--task-ids",
        dest="task_ids",
        nargs="+",
        help="Specific task ID(s) to evaluate (e.g. fastapi_15588)",
    )
    parser.add_argument(
        "--pilot",
        action="store_true",
        help="Run 2-task pilot (fastapi_15661 and fastapi_15588)",
    )
    parser.add_argument(
        "--tasks-file",
        type=str,
        default="test.txt",
        help="Path to file listing tasks to run (default: test.txt)",
    )
    parser.add_argument(
        "--run-name",
        type=str,
        default=None,
        help="Explicit run name (e.g. run_B05). If not set, auto-increments run_Bxx",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=int(os.getenv("SWEGEMMA_CONCURRENCY", "15")),
        help="Parallel task evaluations (default: 15)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=os.getenv("SWEGEMMA_MODEL", "stealth/space-bunny-alpha"),
        help="Model identifier on LiteRouter (default: stealth/space-bunny-alpha)",
    )
    parser.add_argument(
        "--api-base",
        type=str,
        default=os.getenv("SWEGEMMA_API_BASE", "http://literouter.lan:7766/v1"),
        help="API Base URL (default: http://literouter.lan:7766/v1)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=os.getenv("SWEGEMMA_API_KEY", "lr-or-oa-ch-no"),
        help="API Key (default: lr-or-oa-ch-no or SWEGEMMA_API_KEY env var)",
    )
    parser.add_argument(
        "--max-tool-calls",
        type=int,
        default=50,
        help="Max tool calls per task (default: 50)",
    )
    parser.add_argument(
        "--max-time-minutes",
        type=int,
        default=30,
        help="Max minutes per task (default: 30)",
    )
    parser.add_argument(
        "--display",
        choices=["dashboard", "single", "auto", "quiet"],
        default="dashboard",
        help="Display mode (default: dashboard)",
    )
    return parser.parse_args()


def main() -> int:
    raw_args = parse_args()
    run_config = EvalRunConfig.model_validate(vars(raw_args))

    # Determine tasks
    tasks_file_path = ROOT_DIR / run_config.tasks_file
    if run_config.task_ids:
        selected_tasks = run_config.task_ids
        source_desc = f"CLI args ({len(selected_tasks)} tasks)"
    elif run_config.all:
        selected_tasks = None  # None means all tasks in tasks.jsonl
        source_desc = "all 129 tasks (--all flag)"
    elif run_config.pilot:
        selected_tasks = ["fastapi_15661", "fastapi_15588"]
        source_desc = "2-task pilot (--pilot flag)"
    elif tasks_file_path.exists():
        file_tasks = load_tasks_from_file(tasks_file_path)
        if file_tasks:
            selected_tasks = file_tasks
            source_desc = f"{tasks_file_path.name} ({len(selected_tasks)} active tasks)"
        else:
            print(f"\n[!] Notice: No active tasks found in '{tasks_file_path.name}'.")
            print(f"    All tasks in '{tasks_file_path.name}' are currently commented out with '#'.")
            print(f"    Please uncomment at least one task in '{tasks_file_path.name}' (remove the leading '# '),")
            print(f"    or specify tasks directly using --task-id <TASK_ID> (or use --pilot / --all).\n")
            return 1
    else:
        print(f"\n[!] Error: Tasks file '{tasks_file_path}' does not exist.")
        print(f"    Please ensure '{tasks_file_path.name}' exists or specify tasks using --task-id <TASK_ID> (or --pilot / --all).\n")
        return 1

    # Determine results dir
    results_parent = ROOT_DIR / "results"
    if run_config.run_name:
        run_dir = results_parent / run_config.run_name
    else:
        run_dir = get_next_run_dir(results_parent)

    print(f"\n============================================================")
    print(f" SWE-Gemma Evaluation Runner")
    print(f"============================================================")
    print(f" Target Run Dir : {run_dir}")
    print(f" Model Target   : {run_config.model}")
    print(f" Endpoint       : {run_config.api_base}")
    print(f" Display Mode   : {run_config.display}")
    print(f" Task Source    : {source_desc}")
    if selected_tasks is not None and len(selected_tasks) <= 10:
        print(f" Task List      : {', '.join(selected_tasks)}")
    elif selected_tasks is not None:
        print(f" Task List      : {selected_tasks[0]} ... {selected_tasks[-1]} ({len(selected_tasks)} total)")
    print(f" Concurrency    : {run_config.concurrency}")
    print(f" Budgets        : {run_config.max_tool_calls} tool calls / {run_config.max_time_minutes} mins")
    print(f"============================================================\n")

    models = setup_gemma_model_registry(
        api_base=run_config.api_base,
        api_key=run_config.api_key,
        served_model=run_config.model,
    )

    # Clean any rogue macOS metadata or bytecode before compiling agents
    submission_dir = ROOT_DIR / "my_submission"
    if submission_dir.exists():
        for f in submission_dir.rglob("*.pyc"):
            try:
                f.unlink(missing_ok=True)
            except OSError:
                pass
        for f in submission_dir.rglob(".DS_Store"):
            try:
                f.unlink(missing_ok=True)
            except OSError:
                pass
        for f in submission_dir.rglob("._*"):
            try:
                f.unlink(missing_ok=True)
            except OSError:
                pass
        for d in submission_dir.rglob("__pycache__"):
            try:
                shutil.rmtree(d, ignore_errors=True)
            except OSError:
                pass

    config = EvalConfig(
        tasks_path=ROOT_DIR / "tasks.jsonl",
        snapshots_dir=ROOT_DIR / "snapshots",
        submission_dir=submission_dir,
        results_dir=run_dir,
        models=models,
        sandbox="subprocess",
        task_ids=selected_tasks,
        concurrency=run_config.concurrency,
        max_tool_calls=run_config.max_tool_calls,
        max_time_minutes=run_config.max_time_minutes,
        verbose=True,
        display_mode=run_config.display,
    )

    ev = Evaluator(config)
    result = asyncio.run(ev.run())

    # Structure individual task results through Pydantic v2 TaskEvalResult
    task_eval_results: list[TaskEvalResult] = [
        TaskEvalResult.from_task_result(tr) for tr in getattr(result, "task_results", [])
    ]

    # Validate or construct RunSummary model
    summary_file = run_dir / "summary.json"
    if summary_file.exists():
        try:
            summary = RunSummary.model_validate_json(summary_file.read_text(encoding="utf-8"))
        except Exception:
            summary = RunSummary.from_evaluation_result(result, task_eval_results)
    else:
        summary = RunSummary.from_evaluation_result(result, task_eval_results)
        summary_file.write_text(summary.model_dump_json(indent=2), encoding="utf-8")

    print("\n============================================================")
    print(" EVALUATION FINISHED")
    print("============================================================")
    print(f" Summary: {summary_file}")
    print(f" Run Summary:\n{summary.model_dump_json(indent=2)}")
    print(f" Results: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
