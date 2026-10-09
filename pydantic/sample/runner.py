"""Async FIFO worker pool runner for Modular Cleaner / Generator Scaffolding.

Mirrors ``infrastructure/generators/archetypes/clean/runner.py`` verbatim:
per-worker HTTP/2 socket isolation, FIFO queue with sentinel None termination,
jittered exponential backoff, 429 key-hopping, and priority filters:
retry_failed > target (cell_id or index) > force > unprocessed.
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import random
import sys
from pathlib import Path
from typing import Final, cast

import httpx
from pydantic import ValidationError
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from infrastructure.workflow_tmp.config import (
    BACKOFF_FACTOR,
    BACKOFF_FACTOR_429,
    BACKOFF_INITIAL,
    BACKOFF_INITIAL_429,
    BACKOFF_MAX_ATTEMPTS,
    CELLS_DIR,
    CONCURRENCY,
    FAILED_JSONL,
    FAST_429_RETRY_DELAY,
    HTTP_CONNECT_TIMEOUT,
    HTTP_POOL_TIMEOUT,
    HTTP_WRITE_TIMEOUT,
    LIMIT,
    MAX_429_KEY_HOPS,
    SAMPLE_CATEGORIES,
    SAMPLE_GENDERS,
    SAMPLE_POSTURES,
    START_INDEX,
    STREAM,
    TAKEOFF_SPACING,
    TARGET_ID,
    WORK_DIR,
    WORKER_TIMEOUT,
    SampleCategory,
    SampleGender,
    SamplePosture,
    logger,
)
from infrastructure.workflow_tmp.models import (
    CleanStagePayload,
    RawCitation,
    RawSpec,
    VerifiedCatalogEntry,
)
from infrastructure.workflow_tmp.stages import (
    run_clean_stage1,
    run_cleaning_stage,
)
from infrastructure.workflow_tmp.storage import (
    append_checkpoint,
    assemble_cleaned_entry,
    cleanup_stage_cache,
    get_completed_indices,
    is_cell_completed,
    load_source_catalog,
    log_failure,
    save_cell_atomically,
)

__all__: Final[list[str]] = [
    "clean_single_entry",
    "clone_model_with_client",
    "compute_jittered_backoff",
    "create_isolated_worker_client",
    "generate_combinatorial_specs",
    "get_pending_specs",
    "main",
    "parse_args",
    "process_single_item",
    "resolve_specs_catalog",
    "run_pipeline",
]

BACKUP_ZIP_PATH: Final[Path] = WORK_DIR / "cells_backup.zip"

type WorkQueue = asyncio.Queue[RawSpec | None]

_WORKER_EXCEPTIONS: Final[tuple[type[Exception], ...]] = (
    ModelHTTPError,
    ModelAPIError,
    UnexpectedModelBehavior,
    ValidationError,
    OSError,
    httpx.HTTPError,
    httpx.TimeoutException,
    TimeoutError,
)


# ── HTTP/2 socket isolation helpers ─────────────────────────────────────────


def create_isolated_worker_client(
    worker_timeout: float = WORKER_TIMEOUT,
    connect_timeout: float = HTTP_CONNECT_TIMEOUT,
    write_timeout: float = HTTP_WRITE_TIMEOUT,
    pool_timeout: float = HTTP_POOL_TIMEOUT,
) -> httpx.AsyncClient:
    """Create a dedicated HTTP/2 AsyncClient with bounded socket timeouts."""
    timeout = httpx.Timeout(
        worker_timeout,
        connect=connect_timeout,
        read=worker_timeout,
        write=write_timeout,
        pool=pool_timeout,
    )
    return httpx.AsyncClient(http2=True, timeout=timeout)


def clone_model_with_client(
    model: OpenAIChatModel,
    client: httpx.AsyncClient,
) -> OpenAIChatModel:
    """Clone OpenAIChatModel with isolated httpx AsyncClient (http2 isolation)."""
    orig_provider = model.provider
    if not isinstance(orig_provider, OpenAIProvider):
        raise TypeError(f"Expected OpenAIProvider, got {type(orig_provider).__name__}")
    new_provider = OpenAIProvider(
        base_url=orig_provider.base_url,
        api_key=orig_provider.client.api_key,
        http_client=client,
    )
    return OpenAIChatModel(
        model_name=model.model_name,
        provider=new_provider,
        settings=model.settings,
        profile=model.profile,
    )


# ── Backup assertion ─────────────────────────────────────────────────────────


def _assert_backup_exists() -> None:
    """Fail-fast assertion: verify cells_backup.zip exists before destructive overwrite."""
    if not BACKUP_ZIP_PATH.exists():
        raise FileNotFoundError(
            f"Mandatory backup archive not found: {BACKUP_ZIP_PATH}. Execute backup before executing with force=True."
        )


# ── Per-item processing helpers (CC < 6 each) ───────────────────────────────


def _should_skip(source: RawSpec, force: bool) -> bool:
    """Return True if this cell already exists and --force is not set."""
    return not force and is_cell_completed(source.cell_id, source.index)


def _save_and_checkpoint_cell(
    source: RawSpec,
    payload: CleanStagePayload,
) -> None:
    """Assemble final entry, save to disk, append checkpoint, and clean staging cache."""
    cleaned: VerifiedCatalogEntry = assemble_cleaned_entry(source, payload)
    save_cell_atomically(cleaned)
    append_checkpoint(cleaned)
    cleanup_stage_cache(source.cell_id)
    short_hash = cleaned.content_hash[:8] if hasattr(cleaned, "content_hash") else "ok"
    logger.info("✅ [%04d] [%s] Saved (hash: %s...).", source.index, source.cell_id, short_hash)


async def _execute_single_attempt(
    source: RawSpec,
    client: httpx.AsyncClient | None,
    force: bool,
    timeout: float,
    stream: bool = STREAM,
) -> bool:
    """Run stage 1 cleaning with execution timeout and persist on success."""
    async with asyncio.timeout(timeout):
        payload = await run_clean_stage1(source, client=client, force_refresh=force, stream=stream)
        _save_and_checkpoint_cell(source, payload)
        return True


def _is_rate_limit_error(exc: Exception) -> bool:
    """Check if exception is an HTTP 429 rate limit error."""
    if isinstance(exc, ModelHTTPError) and getattr(exc, "status_code", None) == 429:
        return True
    if getattr(exc, "status_code", None) == 429:
        return True
    return "429" in str(exc)


def compute_jittered_backoff(attempt: int, initial_delay: float, backoff_factor: float) -> float:
    """Calculate exponential backoff delay with decorrelated uniform jitter in [0.75, 1.25]."""
    base_delay = initial_delay * (backoff_factor ** (attempt - 1))
    return base_delay * random.uniform(0.75, 1.25)


def _select_backoff_params(
    exc: Exception,
    backoff_initial: float,
    backoff_factor: float,
    backoff_initial_429: float,
    backoff_factor_429: float,
) -> tuple[float, float]:
    """Select initial delay and factor based on whether exception is 429."""
    if _is_rate_limit_error(exc):
        return backoff_initial_429, backoff_factor_429
    return backoff_initial, backoff_factor


async def _handle_rate_limit_hop(
    key_hop_count: int,
    max_key_hops: int = MAX_429_KEY_HOPS,
    delay: float = FAST_429_RETRY_DELAY,
) -> bool:
    """Log fast key-hop message and sleep to advance LiteRouter round-robin pointer."""
    if key_hop_count >= max_key_hops:
        return False
    logger.info(
        "⚡ [429 Key-Hop %d/%d] Advancing LiteRouter round-robin pointer in %.1fs...",
        key_hop_count,
        max_key_hops,
        delay,
    )
    await asyncio.sleep(delay)
    return True


async def _handle_worker_rate_limit(
    source: RawSpec,
    exc: Exception,
    key_hop_count: int,
) -> bool:
    """Handle 429 rate limit hop; return True if hopped, False if hops exhausted."""
    if not _is_rate_limit_error(exc):
        return False
    if key_hop_count < MAX_429_KEY_HOPS:
        await _handle_rate_limit_hop(key_hop_count + 1)
        return True
    logger.warning(
        "🛑 [%04d] [%s] 429 key-hops exhausted (%d/%d). Entering quota cooldown...",
        source.index,
        source.cell_id,
        key_hop_count,
        MAX_429_KEY_HOPS,
    )
    return False


def _handle_attempt_failure(
    source: RawSpec,
    exc: Exception,
    attempt: int,
    max_attempts: int,
    initial_delay: float,
    backoff_factor: float,
    initial_delay_429: float = BACKOFF_INITIAL_429,
    backoff_factor_429: float = BACKOFF_FACTOR_429,
) -> float | None:
    """Log failure and return backoff delay, or None if attempts exhausted."""
    if attempt >= max_attempts:
        log_failure(source, exc, retry_count=attempt)
        logger.error(
            "❌ [%04d] [%s] All %d attempts failed: %s: %s 🚨",
            source.index,
            source.cell_id,
            max_attempts,
            type(exc).__name__,
            exc,
        )
        return None
    init_delay, factor = _select_backoff_params(
        exc, initial_delay, backoff_factor, initial_delay_429, backoff_factor_429
    )
    delay = compute_jittered_backoff(attempt, init_delay, factor)
    logger.warning(
        "⚠️ [%04d] [%s] Attempt %d/%d failed: %s: %s. Retrying in %.1fs... 🔄",
        source.index,
        source.cell_id,
        attempt,
        max_attempts,
        type(exc).__name__,
        exc,
        delay,
    )
    return delay


async def _handle_worker_exception(
    source: RawSpec,
    exc: Exception,
    attempt: int,
    max_attempts: int,
    backoff_initial: float,
    backoff_factor: float,
    backoff_initial_429: float = BACKOFF_INITIAL_429,
    backoff_factor_429: float = BACKOFF_FACTOR_429,
) -> None:
    """Handle attempt failure by logging and sleeping for jittered backoff delay."""
    delay = _handle_attempt_failure(
        source,
        exc,
        attempt,
        max_attempts,
        backoff_initial,
        backoff_factor,
        initial_delay_429=backoff_initial_429,
        backoff_factor_429=backoff_factor_429,
    )
    if delay is not None:
        await asyncio.sleep(delay)


async def _process_item_with_retries(
    source: RawSpec,
    client: httpx.AsyncClient | None,
    force: bool,
    timeout: float,
    backoff_initial: float,
    backoff_factor: float,
    max_attempts: int,
    stream: bool = STREAM,
    backoff_initial_429: float = BACKOFF_INITIAL_429,
    backoff_factor_429: float = BACKOFF_FACTOR_429,
) -> bool:
    """Execute cleaning for a single item with 429 key-hopping and backoff retries."""
    attempt = 1
    key_hop_count = 0
    while attempt <= max_attempts:
        try:
            return await _execute_single_attempt(source, client, force, timeout, stream=stream)
        except _WORKER_EXCEPTIONS as exc:
            if await _handle_worker_rate_limit(source, exc, key_hop_count):
                key_hop_count += 1
                continue
            await _handle_worker_exception(
                source,
                exc,
                attempt,
                max_attempts,
                backoff_initial,
                backoff_factor,
                backoff_initial_429,
                backoff_factor_429,
            )
            attempt += 1
            key_hop_count = 0
    return False


async def _process_single_item_unlocked(
    source: RawSpec,
    client: httpx.AsyncClient | None,
    force: bool,
    timeout: float,
    backoff_initial: float,
    backoff_factor: float,
    backoff_max_attempts: int,
    stream: bool = STREAM,
    backoff_initial_429: float = BACKOFF_INITIAL_429,
    backoff_factor_429: float = BACKOFF_FACTOR_429,
) -> bool:
    """Check skip condition or delegate to retry loop."""
    if _should_skip(source, force):
        logger.info("⏩ [%04d] [%s] Already completed — skipping.", source.index, source.cell_id)
        return True
    return await _process_item_with_retries(
        source,
        client=client,
        force=force,
        timeout=timeout,
        backoff_initial=backoff_initial,
        backoff_factor=backoff_factor,
        max_attempts=backoff_max_attempts,
        stream=stream,
        backoff_initial_429=backoff_initial_429,
        backoff_factor_429=backoff_factor_429,
    )


async def process_single_item(
    source: RawSpec,
    client: httpx.AsyncClient | None = None,
    *,
    force: bool = False,
    semaphore: asyncio.Semaphore | None = None,
    timeout: float = WORKER_TIMEOUT,
    backoff_initial: float = BACKOFF_INITIAL,
    backoff_factor: float = BACKOFF_FACTOR,
    backoff_max_attempts: int = BACKOFF_MAX_ATTEMPTS,
    stream: bool = STREAM,
    backoff_initial_429: float = BACKOFF_INITIAL_429,
    backoff_factor_429: float = BACKOFF_FACTOR_429,
) -> bool:
    """Process a single raw spec with optional semaphore, timeout, and retries."""
    if semaphore is not None:
        async with semaphore:
            return await _process_single_item_unlocked(
                source,
                client=client,
                force=force,
                timeout=timeout,
                backoff_initial=backoff_initial,
                backoff_factor=backoff_factor,
                backoff_max_attempts=backoff_max_attempts,
                stream=stream,
                backoff_initial_429=backoff_initial_429,
                backoff_factor_429=backoff_factor_429,
            )
    return await _process_single_item_unlocked(
        source,
        client=client,
        force=force,
        timeout=timeout,
        backoff_initial=backoff_initial,
        backoff_factor=backoff_factor,
        backoff_max_attempts=backoff_max_attempts,
        stream=stream,
        backoff_initial_429=backoff_initial_429,
        backoff_factor_429=backoff_factor_429,
    )


async def clean_single_entry(
    entry: RawSpec,
    *,
    stream: bool = STREAM,
) -> CleanStagePayload:
    """Clean a single spec directly via run_cleaning_stage with stream flag."""
    return await run_cleaning_stage(entry, stream=stream)


async def _worker_loop(
    worker_id: int,
    queue: WorkQueue,
    force: bool,
    *,
    semaphore: asyncio.Semaphore,
    worker_timeout: float = WORKER_TIMEOUT,
    connect_timeout: float = HTTP_CONNECT_TIMEOUT,
    write_timeout: float = HTTP_WRITE_TIMEOUT,
    pool_timeout: float = HTTP_POOL_TIMEOUT,
    stream: bool = STREAM,
    backoff_initial: float = BACKOFF_INITIAL,
    backoff_factor: float = BACKOFF_FACTOR,
    backoff_max_attempts: int = BACKOFF_MAX_ATTEMPTS,
    backoff_initial_429: float = BACKOFF_INITIAL_429,
    backoff_factor_429: float = BACKOFF_FACTOR_429,
) -> None:
    """Long-lived FIFO worker: pull items from queue until sentinel None received."""
    async with create_isolated_worker_client(
        worker_timeout=worker_timeout,
        connect_timeout=connect_timeout,
        write_timeout=write_timeout,
        pool_timeout=pool_timeout,
    ) as worker_client:
        while True:
            source = await queue.get()
            if source is None:
                queue.task_done()
                break
            try:
                await process_single_item(
                    source,
                    client=worker_client,
                    force=force,
                    semaphore=semaphore,
                    timeout=worker_timeout,
                    backoff_initial=backoff_initial,
                    backoff_factor=backoff_factor,
                    backoff_max_attempts=backoff_max_attempts,
                    stream=stream,
                    backoff_initial_429=backoff_initial_429,
                    backoff_factor_429=backoff_factor_429,
                )
            except _WORKER_EXCEPTIONS as exc:
                log_failure(source, exc)
                logger.error(
                    "❌ [%04d] [W%d][%s] Failed: %s: %s 🚨",
                    source.index,
                    worker_id,
                    source.cell_id,
                    type(exc).__name__,
                    exc,
                )
            finally:
                queue.task_done()


# ── Queue and spec filtering helpers ─────────────────────────────────────────


def _build_queue(sources: list[RawSpec]) -> WorkQueue:
    """Populate an asyncio.Queue with filtered source items."""
    queue: WorkQueue = asyncio.Queue()
    for item in sources:
        queue.put_nowait(item)
    return queue


def _extract_cell_id(rec: dict[str, object]) -> str:
    """Extract cell_id from parsed JSONL dict with fallback keys."""
    for key in ("cell_id", "entry_id", "archetype_id"):
        val = rec.get(key)
        if isinstance(val, str) and val:
            return val
    return ""


def _parse_cell_id_from_line(line: str) -> str:
    """Parse a single JSONL line and return its cell_id, or empty string if blank."""
    stripped = line.strip()
    if not stripped:
        return ""
    rec: object = json.loads(stripped)
    if isinstance(rec, dict):
        return _extract_cell_id(cast(dict[str, object], rec))
    return ""


def _read_failed_ids() -> set[str]:
    """Parse failed_items.jsonl and return the set of cell_ids to retry."""
    if not FAILED_JSONL.exists():
        return set()
    lines = FAILED_JSONL.read_text(encoding="utf-8").splitlines()
    return {cid for line in lines if (cid := _parse_cell_id_from_line(line))}


def _apply_index_and_limit(
    catalog: list[RawSpec],
    start: int,
    limit: int,
) -> list[RawSpec]:
    """Apply start index and limit slicing to catalog."""
    items = [s for s in catalog if s.index >= start]
    if limit > 0:
        return items[:limit]
    return items


def _filter_unprocessed(
    catalog: list[RawSpec],
    start: int,
    limit: int,
) -> list[RawSpec]:
    """Return unprocessed entries starting at index, excluding verified cells."""
    completed = get_completed_indices()
    items = [s for s in catalog if s.index >= start and s.index not in completed]
    if limit > 0:
        return items[:limit]
    return items


def _filter_by_failed(
    catalog: list[RawSpec],
) -> list[RawSpec]:
    """Return only entries whose cell_id appears in failed_items.jsonl."""
    failed_ids = _read_failed_ids()
    return [s for s in catalog if s.cell_id in failed_ids]


def _filter_by_target(
    catalog: list[RawSpec],
    target: str,
) -> list[RawSpec]:
    """Return only the entry matching the given cell_id or string index."""
    return [s for s in catalog if s.cell_id == target or str(s.index) == target or target in s.cell_id]


def _filter_sources(
    catalog: list[RawSpec],
    *,
    start: int,
    limit: int,
    target: str | None,
    retry_failed: bool,
    force: bool = False,
) -> list[RawSpec]:
    """Apply priority filter: retry_failed > target (cell_id or index) > force > unprocessed."""
    if retry_failed:
        return _filter_by_failed(catalog)
    if target:
        return _filter_by_target(catalog, target)
    if force:
        return _apply_index_and_limit(catalog, start, limit)
    return _filter_unprocessed(catalog, start, limit)


async def _stagger_task_launch(
    wid: int,
    concurrency: int,
    takeoff_spacing: float,
) -> None:
    """Sleep takeoff_spacing if not the final worker lane."""
    if wid < concurrency - 1 and takeoff_spacing > 0.0:
        await asyncio.sleep(takeoff_spacing)


async def _launch_workers(
    queue: WorkQueue,
    concurrency: int,
    takeoff_spacing: float,
    force: bool,
    *,
    semaphore: asyncio.Semaphore,
    worker_timeout: float = WORKER_TIMEOUT,
    connect_timeout: float = HTTP_CONNECT_TIMEOUT,
    write_timeout: float = HTTP_WRITE_TIMEOUT,
    pool_timeout: float = HTTP_POOL_TIMEOUT,
    stream: bool = STREAM,
    backoff_initial: float = BACKOFF_INITIAL,
    backoff_factor: float = BACKOFF_FACTOR,
    backoff_max_attempts: int = BACKOFF_MAX_ATTEMPTS,
    backoff_initial_429: float = BACKOFF_INITIAL_429,
    backoff_factor_429: float = BACKOFF_FACTOR_429,
) -> None:
    """Spawn N staggered worker coroutines, inject sentinels, then await completion."""
    actual_concurrency = min(concurrency, queue.qsize()) if not queue.empty() else concurrency
    tasks: list[asyncio.Task[None]] = []
    logger.info("🚀 Launching %d worker lanes (spacing: %.1fs)...", actual_concurrency, takeoff_spacing)
    for wid in range(actual_concurrency):
        task = asyncio.create_task(
            _worker_loop(
                wid,
                queue,
                force,
                semaphore=semaphore,
                worker_timeout=worker_timeout,
                connect_timeout=connect_timeout,
                write_timeout=write_timeout,
                pool_timeout=pool_timeout,
                stream=stream,
                backoff_initial=backoff_initial,
                backoff_factor=backoff_factor,
                backoff_max_attempts=backoff_max_attempts,
                backoff_initial_429=backoff_initial_429,
                backoff_factor_429=backoff_factor_429,
            )
        )
        tasks.append(task)
        logger.info("  🛫 Worker lane #%02d spawned.", wid + 1)
        await _stagger_task_launch(wid, actual_concurrency, takeoff_spacing)
    for _ in range(actual_concurrency):
        await queue.put(None)
    await queue.join()
    await asyncio.gather(*tasks)


# ── Combinatorial Generation Helpers ─────────────────────────────────────────


def build_raw_spec(
    index: int,
    category: SampleCategory,
    gender: SampleGender,
    posture: SamplePosture,
    primary_entity: str,
    secondary_entity: str,
) -> RawSpec:
    """Build pure Python Stage 0 deterministic spec (0 LLM tokens)."""
    cell_id = f"SCAF_{category}_{gender}_{posture}_{primary_entity}_{secondary_entity}"
    sample_abstract = f"[{gender.capitalize()} {posture} {category}] - {primary_entity} & {secondary_entity}"
    citation = RawCitation(
        source_book="Di Tian Sui (滴天髓)",
        classical_quote="从神而驰骤，无私意牵制。",
        quote_translation_en="When riding the core momentum, action proceeds without private friction.",
    )
    return RawSpec(
        index=index,
        cell_id=cell_id,
        category=category,
        gender=gender,
        posture=posture,
        primary_entity=primary_entity,
        secondary_entity=secondary_entity,
        sample_abstract=sample_abstract,
        citation=citation,
    )


def generate_combinatorial_specs() -> list[RawSpec]:
    """Generate sample specs across combinatorial space.

    [DOMAIN CUSTOMIZATION]: Replace with your domain's combinatorial generation logic.
    """
    specs: list[RawSpec] = []
    idx = 1
    sample_primary_entities = ("Alpha", "Beta")
    sample_secondary_entities = ("One", "Two")

    for cat, gen, pos in itertools.product(SAMPLE_CATEGORIES, SAMPLE_GENDERS, SAMPLE_POSTURES):
        for p_ent, s_ent in itertools.product(sample_primary_entities, sample_secondary_entities):
            specs.append(build_raw_spec(idx, cat, gen, pos, p_ent, s_ent))
            idx += 1
    return specs


def resolve_specs_catalog() -> list[RawSpec]:
    """Load from source catalog file if exists, or generate combinatorial specs."""
    if CELLS_DIR.parent.joinpath("catalog_verified.json").exists():
        try:
            return load_source_catalog()
        except (FileNotFoundError, json.JSONDecodeError, ValidationError):
            pass
    return generate_combinatorial_specs()


def get_pending_specs(
    start_idx: int = START_INDEX,
    limit: int = LIMIT,
    target_id: str = TARGET_ID,
    retry_failed: bool = False,
    force: bool = False,
) -> list[RawSpec]:
    """Resolve list of pending specs to process based on priority filters."""
    all_specs = resolve_specs_catalog()
    target_val = target_id if target_id else None
    return _filter_sources(
        all_specs,
        start=start_idx,
        limit=limit,
        target=target_val,
        retry_failed=retry_failed,
        force=force,
    )


# ── CLI argument parser ──────────────────────────────────────────────────────


def _build_arg_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser for the runner."""
    parser = argparse.ArgumentParser(
        description="Modular Cleaner / Generator Async FIFO Worker Pool Runner",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=CONCURRENCY,
        help=f"Number of parallel worker lanes (default: {CONCURRENCY})",
    )
    parser.add_argument(
        "--takeoff-spacing",
        type=float,
        default=TAKEOFF_SPACING,
        help=f"Spacing delay between task launches (default: {TAKEOFF_SPACING}s)",
    )
    parser.add_argument(
        "--start",
        "--start-index",
        dest="start",
        type=int,
        default=START_INDEX,
        help=f"1-based catalog index to start from (default: {START_INDEX})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=LIMIT,
        help="Max items to process (default: 0 = all pending)",
    )
    parser.add_argument(
        "--target",
        type=str,
        default="",
        help="Specific cell_id or index to process",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        default=False,
        help="Reprocess only entries listed in failed_items.jsonl",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Bypass existing cell checks and staging cache",
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
        help=f"Initial retry backoff delay in seconds on 429 rate limit (default: {BACKOFF_INITIAL_429}s)",
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
        help=f"Per-worker item processing & read timeout in seconds (default: {WORKER_TIMEOUT}s)",
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
        help=f"Enable streaming token responses to prevent socket timeouts (default: {STREAM})",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments (wrapper for _build_arg_parser)."""
    return _build_arg_parser().parse_args(argv)


async def run_pipeline(
    start_index: int = START_INDEX,
    limit: int = LIMIT,
    concurrency: int = CONCURRENCY,
    takeoff_spacing: float = TAKEOFF_SPACING,
    target: str | None = None,
    retry_failed: bool = False,
    force: bool = False,
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
    """Load catalog, apply priority filters, build FIFO queue, and launch worker pool."""
    if force:
        _assert_backup_exists()
    catalog = resolve_specs_catalog()
    logger.info("📦 Loaded %d source specs from catalog.", len(catalog))
    sources = _filter_sources(
        catalog,
        start=start_index,
        limit=limit,
        target=target,
        retry_failed=retry_failed,
        force=force,
    )
    logger.info(
        "🎯 Work slice: %d item(s) to process across %d worker lane(s).",
        len(sources),
        concurrency,
    )
    if not sources:
        logger.info("✨ No items to process — all targeted cells already completed! 🎉")
        return
    queue = _build_queue(sources)
    semaphore = asyncio.Semaphore(concurrency)
    await _launch_workers(
        queue,
        concurrency,
        takeoff_spacing,
        force,
        semaphore=semaphore,
        worker_timeout=worker_timeout,
        connect_timeout=connect_timeout,
        write_timeout=write_timeout,
        pool_timeout=pool_timeout,
        stream=stream,
        backoff_initial=backoff_initial,
        backoff_factor=backoff_factor,
        backoff_max_attempts=backoff_max_attempts,
        backoff_initial_429=backoff_initial_429,
        backoff_factor_429=backoff_factor_429,
    )
    logger.info("🏁 All worker lanes completed successfully. 🎉")


async def main(argv: list[str] | None = None) -> None:
    """Parse CLI args, filter catalog, and run the async FIFO worker pool."""
    args = parse_args(argv)
    target_val = args.target if args.target else None
    await run_pipeline(
        start_index=args.start,
        limit=args.limit,
        concurrency=args.concurrency,
        takeoff_spacing=args.takeoff_spacing,
        target=target_val,
        retry_failed=args.retry_failed,
        force=args.force,
        backoff_initial=args.backoff_initial,
        backoff_factor=args.backoff_factor,
        backoff_max_attempts=args.backoff_max_attempts,
        worker_timeout=args.worker_timeout,
        connect_timeout=args.http_connect_timeout,
        write_timeout=args.http_write_timeout,
        pool_timeout=args.http_pool_timeout,
        stream=args.stream,
        backoff_initial_429=args.backoff_initial_429,
        backoff_factor_429=args.backoff_factor_429,
    )


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
