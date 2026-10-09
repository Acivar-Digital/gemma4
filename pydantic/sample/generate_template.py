#!/usr/bin/env python3
"""Execution & Generation Controls Entrypoint Facade for Modular Generator Scaffolding.

[SCAFFOLD TEMPLATE]
Target: Combinatorial multi-stage cellular generation pipeline.
Configure execution controls directly below, or override via CLI arguments.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from typing import Final

from infrastructure.workflow_tmp.config import (
    CELLS_DIR,
    SOURCE_CATALOG_PATH,
    generator_model,
    logger,
)
from infrastructure.workflow_tmp.preflight import run_preflight_checks
from infrastructure.workflow_tmp.runner import (
    generate_combinatorial_specs,
)
from infrastructure.workflow_tmp.runner import (
    run_pipeline as runner_run_pipeline,
)

# ── Execution & Generation Controls (Top-Level Config) ────────────────────────
# CONCURRENCY: Number of parallel async worker lanes running simultaneously.
#   Each worker has its own isolated HTTP/2 socket so they don't share connections.
#   7 workers = 7 items processed in parallel (optimal half-pool allocation across keys).
CONCURRENCY: int = 7

# TAKEOFF_SPACING: seconds to wait between launching each successive worker.
#   With 7 workers and 3.5s spacing, the last worker starts ~21s after the first.
#   This staggers API calls to avoid thundering-herd on the gateway at startup.
TAKEOFF_SPACING: float = 3.5

# START_INDEX: 1-based catalog position to begin from.
#   Use this to resume from a specific row (e.g. START_INDEX = 501 skips first 500).
START_INDEX: int = 1

# LIMIT: Max number of items to pull from the catalog for this run.
#   0 = no cap — process ALL pending (unfinished) items from START_INDEX onward.
#   N > 0 = stop after queuing exactly N items across ALL workers combined.
#   NOTE: LIMIT and CONCURRENCY are independent — LIMIT=5, CONCURRENCY=5 means
#   5 items total shared across 5 workers (each worker may only process 1 item).
#   Set LIMIT=0 to run the full batch.
LIMIT: int = 0

# TARGET_ID: Pin to a single cell_id for debugging (e.g. "SCAF_primary_male_strong_Alpha_One").
#   When set, overrides START_INDEX and LIMIT — only that one cell is processed.
TARGET_ID: str = ""

# INDEX: Pin to a single numeric index (1..N) for targeted cellular debugging.
#   When set, resolves cell_id automatically and processes only that single cell.
INDEX: int | None = None

# RETRY_FAILED: When True, re-processes only entries listed in failed_items.jsonl.
#   Takes highest priority — overrides TARGET_ID, START_INDEX, and LIMIT.
RETRY_FAILED: bool = False

# FORCE_REFRESH: Bypass the "already completed" cell check and re-run everything.
#   Without this, cells with existing output files are silently skipped.
FORCE_REFRESH: bool = False

# BACKOFF_INITIAL: Initial backoff in seconds on error
BACKOFF_INITIAL: float = 8.0

# BACKOFF_INITIAL_429: Initial backoff in seconds on 429 quota exhaustion (bucket refill)
BACKOFF_INITIAL_429: float = 45.0

# BACKOFF_FACTOR: Multiplier factor for geometric backoff (1.5 = 50% increase per attempt)
BACKOFF_FACTOR: float = 1.5

# BACKOFF_FACTOR_429: Multiplier factor for geometric backoff on 429 rate limit
BACKOFF_FACTOR_429: float = 1.2

# BACKOFF_MAX_ATTEMPTS: Maximum retry attempts before permanent failure logged to failed_items.jsonl
BACKOFF_MAX_ATTEMPTS: int = 5

# WORKER_TIMEOUT: Maximum seconds allowed per worker item processing
WORKER_TIMEOUT: float = 300.0

# HTTP_CONNECT_TIMEOUT: Socket connection timeout in seconds
HTTP_CONNECT_TIMEOUT: float = 60.0

# HTTP_WRITE_TIMEOUT: Socket write timeout in seconds
HTTP_WRITE_TIMEOUT: float = 300.0

# HTTP_POOL_TIMEOUT: Socket pool acquisition timeout in seconds
HTTP_POOL_TIMEOUT: float = 300.0

# SKIP_PREFLIGHT: Skip preflight environment and model readiness audit
SKIP_PREFLIGHT: bool = False

# STREAM: Enable streaming token responses to prevent gateway socket timeouts on heavy batches.
STREAM: bool = True

__all__: Final[list[str]] = [
    "BACKOFF_FACTOR",
    "BACKOFF_FACTOR_429",
    "BACKOFF_INITIAL",
    "BACKOFF_INITIAL_429",
    "BACKOFF_MAX_ATTEMPTS",
    "CONCURRENCY",
    "FORCE_REFRESH",
    "HTTP_CONNECT_TIMEOUT",
    "HTTP_POOL_TIMEOUT",
    "HTTP_WRITE_TIMEOUT",
    "INDEX",
    "LIMIT",
    "RETRY_FAILED",
    "SKIP_PREFLIGHT",
    "START_INDEX",
    "STREAM",
    "TAKEOFF_SPACING",
    "TARGET_ID",
    "WORKER_TIMEOUT",
    "main",
    "parse_args",
    "run_pipeline",
]


def _find_cell_id_by_index(index: int) -> str:
    """Find cell_id corresponding to numeric index in source catalog or combinatorial spec.

    [CUSTOMIZATION]: Replace spec generation with your domain's catalog loader or spec generator.
    """
    specs = generate_combinatorial_specs()
    if not (1 <= index <= len(specs)):
        msg = f"No source spec found for index {index} (valid range 1..{len(specs)})"
        raise ValueError(msg)
    return specs[index - 1].cell_id


def _resolve_target(cell_id: str | None, index: int | None) -> str:
    """Resolve cell_id target from either cell_id or numeric index."""
    if cell_id:
        return cell_id
    if index is not None:
        return _find_cell_id_by_index(index)
    return ""


def _format_target_description(cell_id: str | None, index: int | None) -> str:
    """Format human-readable target string for launch banner."""
    if cell_id:
        return f"Cell ID: {cell_id}"
    if index is not None:
        return f"Index: {index:04d}"
    return "Full Combinatorial Universe"


def _print_launch_banner(
    start_index: int,
    limit: int,
    concurrency: int,
    takeoff_spacing: float,
    cell_id: str | None,
    index: int | None,
    retry_failed: bool,
    force: bool,
    worker_timeout: float,
    stream: bool = STREAM,
) -> None:
    """Print an intuitive launch banner with pipeline configuration and emojis."""
    target_str = _format_target_description(cell_id, index)
    limit_str = f"{limit} items" if limit > 0 else "All Pending"
    model_name = getattr(generator_model, "model_name", "unknown")
    source_path = str(SOURCE_CATALOG_PATH) if SOURCE_CATALOG_PATH.exists() else "Combinatorial Specs Generator"
    sep = "━" * 66
    print(f"\n{sep}")
    print("🏛️ [BaziForecaster] Modular Generation Pipeline [TEMPLATE]")
    print(sep)
    print(f"  🤖 Model Target   : {model_name} (via CONTROL_SHEET.clean_rag)")
    print(f"  ⚡ Worker Lanes   : {concurrency} parallel lanes (takeoff: {takeoff_spacing:.1f}s)")
    print(f"  🎯 Target Filter  : {target_str}")
    print(f"  📊 Processing     : Start Index {start_index:04d} | Limit: {limit_str}")
    print(f"  ⏱️ Timeouts       : Worker {worker_timeout:.0f}s | Socket {HTTP_CONNECT_TIMEOUT:.0f}s")
    print(f"  📡 Streaming      : {'Enabled (stream=True)' if stream else 'Disabled (stream=False)'}")
    print(f"  🔄 Operational    : Retry Failed: {retry_failed} | Force Overwrite: {force}")
    print(f"  📂 Source Path    : {source_path}")
    print(f"  💾 Output Path    : {CELLS_DIR}")
    print(f"{sep}\n")


def _handle_preflight_gate(preflight_only: bool, skip_preflight: bool) -> None:
    """Evaluate preflight requirements and exit if checks fail or preflight-only requested."""
    if preflight_only:
        report = asyncio.run(run_preflight_checks())
        sys.exit(0 if report.passed else 1)
    if not skip_preflight:
        report = asyncio.run(run_preflight_checks())
        if not report.passed:
            logger.error("❌ Preflight checks failed. Aborting pipeline execution.")
            sys.exit(1)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments with fallback to top-level module constants."""
    parser = argparse.ArgumentParser(
        description="Modular Generator Scaffolding CLI Facade",
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        default=False,
        help="Run preflight checks and exit",
    )
    parser.add_argument(
        "--skip-preflight",
        action=argparse.BooleanOptionalAction,
        default=SKIP_PREFLIGHT,
        help="Skip preflight checks before running the pipeline",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=CONCURRENCY,
        help=f"Worker pool size override (default: {CONCURRENCY})",
    )
    parser.add_argument(
        "--takeoff-spacing",
        type=float,
        default=TAKEOFF_SPACING,
        help=f"Spacing delay between task launches (default: {TAKEOFF_SPACING}s)",
    )
    parser.add_argument(
        "--start-index",
        "--start",
        dest="start_index",
        type=int,
        default=START_INDEX,
        help=f"Starting item index (default: {START_INDEX})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=LIMIT,
        help=f"Maximum items to process (default: {LIMIT} = all)",
    )
    parser.add_argument(
        "--cell-id",
        "--target",
        dest="cell_id",
        type=str,
        default=TARGET_ID,
        help="Target specific cell ID",
    )
    parser.add_argument(
        "--index",
        type=int,
        default=INDEX,
        help="Target specific numeric index (1..N)",
    )
    parser.add_argument(
        "--retry-failed",
        action=argparse.BooleanOptionalAction,
        default=RETRY_FAILED,
        help="Re-run items recorded in failed_items.jsonl",
    )
    parser.add_argument(
        "--force",
        "--force-refresh",
        dest="force",
        action=argparse.BooleanOptionalAction,
        default=FORCE_REFRESH,
        help="Force overwrite existing completed cells in cells/",
    )
    parser.add_argument(
        "--backoff-initial",
        type=float,
        default=BACKOFF_INITIAL,
        help=f"Initial retry backoff delay in seconds on error (default: {BACKOFF_INITIAL}s)",
    )
    parser.add_argument(
        "--backoff-initial-429",
        type=float,
        default=BACKOFF_INITIAL_429,
        help=f"Initial retry backoff delay on 429 rate limit (default: {BACKOFF_INITIAL_429}s)",
    )
    parser.add_argument(
        "--backoff-factor",
        type=float,
        default=BACKOFF_FACTOR,
        help=f"Geometric backoff multiplier factor per retry attempt (default: {BACKOFF_FACTOR})",
    )
    parser.add_argument(
        "--backoff-factor-429",
        type=float,
        default=BACKOFF_FACTOR_429,
        help=f"Geometric backoff multiplier for 429 rate limit (default: {BACKOFF_FACTOR_429})",
    )
    parser.add_argument(
        "--backoff-max-attempts",
        type=int,
        default=BACKOFF_MAX_ATTEMPTS,
        help=f"Maximum retry attempts before failing cell (default: {BACKOFF_MAX_ATTEMPTS})",
    )
    parser.add_argument(
        "--worker-timeout",
        type=float,
        default=WORKER_TIMEOUT,
        help=f"Worker execution timeout in seconds (default: {WORKER_TIMEOUT}s)",
    )
    parser.add_argument(
        "--http-connect-timeout",
        type=float,
        default=HTTP_CONNECT_TIMEOUT,
        help=f"Socket connection timeout in seconds (default: {HTTP_CONNECT_TIMEOUT}s)",
    )
    parser.add_argument(
        "--http-write-timeout",
        type=float,
        default=HTTP_WRITE_TIMEOUT,
        help=f"Socket write timeout in seconds (default: {HTTP_WRITE_TIMEOUT}s)",
    )
    parser.add_argument(
        "--http-pool-timeout",
        type=float,
        default=HTTP_POOL_TIMEOUT,
        help=f"Socket pool acquisition timeout in seconds (default: {HTTP_POOL_TIMEOUT}s)",
    )
    parser.add_argument(
        "--stream",
        action=argparse.BooleanOptionalAction,
        default=STREAM,
        help=f"Enable streaming token responses to prevent gateway socket timeouts (default: {STREAM})",
    )
    return parser.parse_args(argv)


async def run_pipeline(
    concurrency: int = CONCURRENCY,
    takeoff_spacing: float = TAKEOFF_SPACING,
    start_index: int = START_INDEX,
    limit: int = LIMIT,
    cell_id: str | None = TARGET_ID,
    index: int | None = INDEX,
    retry_failed: bool = RETRY_FAILED,
    force: bool = FORCE_REFRESH,
    backoff_initial: float = BACKOFF_INITIAL,
    backoff_factor: float = BACKOFF_FACTOR,
    backoff_max_attempts: int = BACKOFF_MAX_ATTEMPTS,
    worker_timeout: float = WORKER_TIMEOUT,
    connect_timeout: float = HTTP_CONNECT_TIMEOUT,
    write_timeout: float = HTTP_WRITE_TIMEOUT,
    pool_timeout: float = HTTP_POOL_TIMEOUT,
    stream: bool = STREAM,
    backoff_initial_429: float = BACKOFF_INITIAL_429,
    backoff_factor_429: float = BACKOFF_FACTOR_429,
) -> None:
    """Execute the generation pipeline via runner."""
    target = _resolve_target(cell_id, index)
    await runner_run_pipeline(
        start_index=start_index,
        limit=limit,
        concurrency=concurrency,
        takeoff_spacing=takeoff_spacing,
        target=target,
        retry_failed=retry_failed,
        force=force,
        backoff_initial=backoff_initial,
        backoff_factor=backoff_factor,
        backoff_max_attempts=backoff_max_attempts,
        worker_timeout=worker_timeout,
        connect_timeout=connect_timeout,
        write_timeout=write_timeout,
        pool_timeout=pool_timeout,
        stream=stream,
        backoff_initial_429=backoff_initial_429,
        backoff_factor_429=backoff_factor_429,
    )


def main(argv: list[str] | None = None) -> None:
    """CLI entry point executing the modular generation pipeline."""
    args = parse_args(argv)
    _handle_preflight_gate(bool(args.preflight), bool(args.skip_preflight))
    start_index: int = int(args.start_index)
    limit: int = int(args.limit)
    concurrency: int = int(args.concurrency)
    takeoff_spacing: float = float(args.takeoff_spacing)
    cell_id: str | None = str(args.cell_id) if args.cell_id else None
    index: int | None = int(args.index) if args.index is not None else None
    retry_failed: bool = bool(args.retry_failed)
    force: bool = bool(args.force)
    backoff_initial: float = float(args.backoff_initial)
    backoff_factor: float = float(args.backoff_factor)
    backoff_max_attempts: int = int(args.backoff_max_attempts)
    worker_timeout: float = float(args.worker_timeout)
    connect_timeout: float = float(args.http_connect_timeout)
    write_timeout: float = float(args.http_write_timeout)
    pool_timeout: float = float(args.http_pool_timeout)
    stream: bool = bool(args.stream)
    backoff_initial_429: float = float(args.backoff_initial_429)
    backoff_factor_429: float = float(args.backoff_factor_429)

    _print_launch_banner(
        start_index=start_index,
        limit=limit,
        concurrency=concurrency,
        takeoff_spacing=takeoff_spacing,
        cell_id=cell_id,
        index=index,
        retry_failed=retry_failed,
        force=force,
        worker_timeout=worker_timeout,
        stream=stream,
    )

    t0 = time.perf_counter()
    asyncio.run(
        run_pipeline(
            concurrency=concurrency,
            takeoff_spacing=takeoff_spacing,
            start_index=start_index,
            limit=limit,
            cell_id=cell_id,
            index=index,
            retry_failed=retry_failed,
            force=force,
            backoff_initial=backoff_initial,
            backoff_factor=backoff_factor,
            backoff_max_attempts=backoff_max_attempts,
            worker_timeout=worker_timeout,
            connect_timeout=connect_timeout,
            write_timeout=write_timeout,
            pool_timeout=pool_timeout,
            stream=stream,
            backoff_initial_429=backoff_initial_429,
            backoff_factor_429=backoff_factor_429,
        )
    )
    elapsed = time.perf_counter() - t0
    print(f"\n✨ [BaziForecaster] Modular generation pipeline sweep finished in {elapsed:.1f}s! 🎉\n")


if __name__ == "__main__":
    main()
