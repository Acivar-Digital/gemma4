#!/usr/bin/env python3
"""Live terminal monitor for SWE-Gemma evaluation runs.

Usage:
    python scripts/monitor_eval.py --run-dir results/run_B04
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table


def parse_args():
    parser = argparse.ArgumentParser(description="Live monitor for SWE-Gemma evaluation")
    parser.add_argument("--run-dir", type=str, default="results/run_B04", help="Path to run results dir")
    parser.add_argument("--total-tasks", type=int, default=129, help="Total expected tasks")
    parser.add_argument("--interval", type=float, default=2.0, help="Refresh interval (seconds)")
    return parser.parse_args()


def load_task_results(jsonl_path: Path):
    if not jsonl_path.exists():
        return []
    results = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return results


def build_renderable(run_dir: Path, total_tasks: int):
    jsonl_path = run_dir / "task_results.jsonl"
    results = load_task_results(jsonl_path)
    completed = len(results)
    resolved = sum(1 for r in results if r.get("resolved", False))
    failed = completed - resolved
    rate = (resolved / completed * 100) if completed > 0 else 0.0

    summary_table = Table.grid(padding=(0, 2))
    summary_table.add_row(
        f"[bold cyan]Run Dir:[/bold cyan] {run_dir.name}",
        f"[bold]Completed:[/bold] {completed}/{total_tasks} ({completed/total_tasks*100:.1f}%)" if total_tasks else f"[bold]Completed:[/bold] {completed}",
        f"[bold green]Resolved:[/bold green] {resolved}",
        f"[bold red]Failed:[/bold red] {failed}",
        f"[bold yellow]Resolution Rate:[/bold yellow] {rate:.1f}%",
    )

    task_table = Table(
        box=None,
        expand=True,
        show_header=True,
        header_style="bold magenta",
        padding=(0, 1),
    )
    task_table.add_column("#", justify="right", width=4)
    task_table.add_column("Task ID", style="bold", width=22)
    task_table.add_column("Repo", width=20)
    task_table.add_column("Status", width=12)
    task_table.add_column("Patch (B)", justify="right", width=10)
    task_table.add_column("Tools", justify="right", width=8)
    task_table.add_column("Duration", justify="right", width=10)

    # Show last 15 completed tasks
    recent_results = results[-15:]
    start_idx = max(1, completed - len(recent_results) + 1)
    for idx, r in enumerate(recent_results, start=start_idx):
        status_str = "[bold green]RESOLVED[/bold green]" if r.get("resolved") else "[bold red]FAILED[/bold red]"
        dur = r.get("duration_seconds", 0.0)
        dur_str = f"{int(dur // 60)}m {int(dur % 60):02d}s" if dur >= 60 else f"{dur:.1f}s"
        patch_size = r.get("agent_patch_size", 0)
        tool_calls = r.get("tool_calls", 0)

        task_table.add_row(
            str(idx),
            r.get("instance_id", ""),
            r.get("repo", ""),
            status_str,
            f"{patch_size:,}",
            str(tool_calls),
            dur_str,
        )

    panel_content = Table.grid()
    panel_content.add_row(summary_table)
    panel_content.add_row("\n")
    panel_content.add_row(task_table)

    return Panel(
        panel_content,
        title="[bold green]SWE-Gemma Evaluation Live Progress[/bold green]",
        subtitle="[dim]Press Ctrl+C to exit monitor (eval continues in background)[/dim]",
        border_style="green",
    )


def main():
    args = parse_args()
    run_dir = Path(args.run_dir)
    console = Console()

    with Live(build_renderable(run_dir, args.total_tasks), console=console, refresh_per_second=1.0) as live:
        try:
            while True:
                time.sleep(args.interval)
                live.update(build_renderable(run_dir, args.total_tasks))
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
