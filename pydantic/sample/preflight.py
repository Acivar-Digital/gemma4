"""Modular Generator Scaffolding: Preflight health audit, embedding check, and execution plan reporter.

[SCAFFOLD TEMPLATE]
This module audits storage directories, Qdrant vector database connectivity, LiteRouter/OpenAI
gateway 1-token probe latency, and computes the pending execution plan.
"""

from __future__ import annotations

import argparse
import asyncio
import time
from pathlib import Path

import httpx
from pydantic import BaseModel, ConfigDict
from pydantic_ai import Agent

from infrastructure.bazirag import (
    _embed_keyword,
    _load_qdrant_client,
    _resolve_collection,
)
from infrastructure.workflow_tmp.config import (
    CELLS_DIR,
    CHECKPOINT_JSONL,
    CONCURRENCY,
    FAILED_JSONL,
    FORCE_REFRESH,
    LIMIT,
    LOG_FILE,
    RETRY_FAILED,
    STAGING_DIR,
    START_INDEX,
    TAKEOFF_SPACING,
    TARGET_ID,
    generator_model,
    logger,
)
from infrastructure.workflow_tmp.runner import (
    generate_combinatorial_specs,
    get_pending_specs,
)


class PreflightError(RuntimeError):
    """Raised when one or more mandatory preflight checks fail."""


# ── 1. Audit Data Models ──────────────────────────────────────────────────────
class StorageAuditResult(BaseModel):
    """Filesystem storage, checkpoint integrity, and directory state."""

    model_config = ConfigDict(extra="forbid")

    cells_dir_exists: bool
    cells_count: int
    staging_dir_exists: bool
    staging_orphans_count: int
    logs_dir_exists: bool
    checkpoint_lines: int
    failed_lines: int
    passed: bool
    details: str


class VectorStoreAuditResult(BaseModel):
    """Qdrant connection, collection status, and BGE-M3 embedding latency."""

    model_config = ConfigDict(extra="forbid")

    connected: bool
    collection_name: str
    vector_count: int
    embedding_engine: str
    probe_latency_ms: float
    passed: bool
    details: str


class ModelGatewayAuditResult(BaseModel):
    """LiteRouter / LLM gateway connectivity and 1-token dry probe latency."""

    model_config = ConfigDict(extra="forbid")

    model_name: str
    provider_base_url: str
    probe_latency_ms: float
    passed: bool
    details: str


class GenerationPlanSummary(BaseModel):
    """Execution plan, scope breakdown, target count, and concurrency sanity check."""

    model_config = ConfigDict(extra="forbid")

    total_combinatorial_specs: int
    verified_saved_cells: int
    failed_queue_items: int
    pending_target_count: int
    execution_mode: str
    concurrency: int
    takeoff_spacing: float
    concurrency_warning: str | None
    sample_targets: list[str]


class PreflightReport(BaseModel):
    """Unified preflight report combining all audits and generation plan."""

    model_config = ConfigDict(extra="forbid")

    storage: StorageAuditResult
    vector_store: VectorStoreAuditResult
    model_gateway: ModelGatewayAuditResult
    plan: GenerationPlanSummary
    passed: bool
    summary_text: str


# ── 2. Audit Implementations ──────────────────────────────────────────────────
def _count_valid_jsonl_lines(path: Path) -> int:
    """Safely count non-empty lines in a JSONL file."""
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def audit_storage() -> StorageAuditResult:
    """Verify directories, count verified cells, and audit JSONL checkpoints."""
    CELLS_DIR.mkdir(parents=True, exist_ok=True)
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    cells_count = len(list(CELLS_DIR.glob("*.json")))
    staging_orphans = len(list(STAGING_DIR.glob("*.json")))
    checkpoint_lines = _count_valid_jsonl_lines(CHECKPOINT_JSONL)
    failed_lines = _count_valid_jsonl_lines(FAILED_JSONL)

    details = (
        f"cells: {cells_count} verified, "
        f"staging: {staging_orphans} intermediate, "
        f"checkpoints: {checkpoint_lines}, "
        f"failed_log: {failed_lines}"
    )
    return StorageAuditResult(
        cells_dir_exists=CELLS_DIR.exists(),
        cells_count=cells_count,
        staging_dir_exists=STAGING_DIR.exists(),
        staging_orphans_count=staging_orphans,
        logs_dir_exists=LOG_FILE.parent.exists(),
        checkpoint_lines=checkpoint_lines,
        failed_lines=failed_lines,
        passed=True,
        details=details,
    )


async def audit_vector_store() -> VectorStoreAuditResult:
    """Audit Qdrant connectivity, active collection, and BGE-M3 embedding latency."""
    t0 = time.perf_counter()
    client = _load_qdrant_client()
    try:
        collection_name = await _resolve_collection(client)
        info = await client.get_collection(collection_name)
        vector_count = int(info.points_count or 0)
        vec = await _embed_keyword("甲木生于子月")
        latency_ms = (time.perf_counter() - t0) * 1000.0
        has_vectors = vector_count > 0 and vec is not None and len(vec) > 0
        details = (
            f"collection '{collection_name}' has {vector_count} points, BGE-M3 test query ok in {latency_ms:.1f}ms"
        )
        return VectorStoreAuditResult(
            connected=True,
            collection_name=collection_name,
            vector_count=vector_count,
            embedding_engine="BGE-M3 (dense 1024d)",
            probe_latency_ms=round(latency_ms, 2),
            passed=has_vectors,
            details=details,
        )
    except (httpx.HTTPError, OSError, ConnectionError, ValueError, RuntimeError, TimeoutError) as exc:
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return VectorStoreAuditResult(
            connected=False,
            collection_name="unknown",
            vector_count=0,
            embedding_engine="BGE-M3",
            probe_latency_ms=round(latency_ms, 2),
            passed=False,
            details=f"Vector store connection failed: {exc}",
        )
    finally:
        await client.close()


async def audit_model_gateway() -> ModelGatewayAuditResult:
    """Audit LiteRouter connectivity and perform a live 1-token probe request."""
    t0 = time.perf_counter()
    model_name = getattr(generator_model, "model_name", "unknown")
    provider = getattr(generator_model, "_provider", None)
    base_url = str(getattr(provider, "base_url", "https://localhost:7766/v1"))

    try:
        probe_agent: Agent[None, str] = Agent(
            generator_model,
            system_prompt="You are a health probe. Reply with 'OK'.",
        )
        result = await probe_agent.run("ping")
        latency_ms = (time.perf_counter() - t0) * 1000.0
        is_ok = bool(result.output)
        details = f"Model '{model_name}' on '{base_url}' probe ok in {latency_ms:.1f}ms"
        return ModelGatewayAuditResult(
            model_name=model_name,
            provider_base_url=base_url,
            probe_latency_ms=round(latency_ms, 2),
            passed=is_ok,
            details=details,
        )
    except (httpx.HTTPError, OSError, ConnectionError, ValueError, RuntimeError, TimeoutError) as exc:
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return ModelGatewayAuditResult(
            model_name=model_name,
            provider_base_url=base_url,
            probe_latency_ms=round(latency_ms, 2),
            passed=False,
            details=f"Model probe failed: {exc}",
        )


def compute_generation_plan(
    *,
    concurrency: int,
    takeoff_spacing: float,
    start_idx: int,
    limit: int,
    target_id: str,
    retry_failed: bool,
) -> GenerationPlanSummary:
    """Calculate exact targets, scope breakdown, and concurrency sanity check."""
    all_specs = generate_combinatorial_specs()
    total_specs = len(all_specs)
    verified_count = len(list(CELLS_DIR.glob("*.json")))

    pending = get_pending_specs(
        start_idx=start_idx,
        limit=limit,
        target_id=target_id,
        retry_failed=retry_failed,
    )
    failed_lines = _count_valid_jsonl_lines(FAILED_JSONL)

    mode = "retry-failed" if retry_failed else ("target" if target_id else "batch")
    concurrency_warn: str | None = None
    if concurrency >= 40:
        concurrency_warn = (
            f"High Concurrency ({concurrency} workers): "
            "Ensure LiteRouter rate limits support this throughput without TTFT timeout."
        )

    sample_targets = [s.cell_id for s in pending[:5]]

    return GenerationPlanSummary(
        total_combinatorial_specs=total_specs,
        verified_saved_cells=verified_count,
        failed_queue_items=failed_lines,
        pending_target_count=len(pending),
        execution_mode=mode,
        concurrency=concurrency,
        takeoff_spacing=takeoff_spacing,
        concurrency_warning=concurrency_warn,
        sample_targets=sample_targets,
    )


# ── 3. Report Formatting & Execution ──────────────────────────────────────────
def _format_infra_lines(report: PreflightReport) -> list[str]:
    """Format the infrastructure availability section of the preflight report."""
    storage_icon = "✔" if report.storage.passed else "✖"
    vector_icon = "✔" if report.vector_store.passed else "✖"
    model_icon = "✔" if report.model_gateway.passed else "✖"
    return [
        "[1] Infrastructure Availability:",
        f"    {storage_icon} Storage:       {report.storage.details}",
        f"    {vector_icon} Vector DB:     {report.vector_store.details}",
        f"    {model_icon} Model Gateway: {report.model_gateway.details}",
        "",
    ]


def _format_plan_lines(report: PreflightReport) -> list[str]:
    """Format the generation plan and target scope section of the preflight report."""
    warn = f"\n    ⚠ WARNING: {report.plan.concurrency_warning}" if report.plan.concurrency_warning else ""
    lines = [
        "[2] Generation Plan & Scope:",
        f"    • Combinatorial Space: {report.plan.total_combinatorial_specs:,} total specs",
        f"    • Verified & Saved:    {report.plan.verified_saved_cells:,} cells on disk",
        f"    • Failed Queue:        {report.plan.failed_queue_items:,} items logged",
        f"    • Execution Mode:      {report.plan.execution_mode}",
        f"    • Active Queue Target: {report.plan.pending_target_count:,} cells to generate",
        f"    • Concurrency/Spacing: {report.plan.concurrency} workers (spacing: {report.plan.takeoff_spacing:.1f}s){warn}",
    ]
    if report.plan.sample_targets:
        lines.append(f"    • Sample Targets:      {', '.join(report.plan.sample_targets[:3])}...")
    return lines


def format_preflight_summary(report: PreflightReport) -> str:
    """Format structured CLI output table for preflight audit report."""
    status_str = "ALL CHECKS PASSED (Ready for takeoff)" if report.passed else "PREFLIGHT AUDIT FAILED"
    lines = [
        "============================================================",
        "           Modular Generator Preflight Audit",
        "============================================================",
    ]
    lines.extend(_format_infra_lines(report))
    lines.extend(_format_plan_lines(report))
    lines.extend(
        [
            "",
            f"[3] Overall Preflight Status: {status_str}",
            "============================================================",
        ]
    )
    return "\n".join(lines)


def print_preflight_banner(report: PreflightReport) -> None:
    """Print the preflight report to stdout and logfire."""
    print(report.summary_text)
    if not report.passed:
        logger.error("Preflight audit failed:\n%s", report.summary_text)
    else:
        logger.info("Preflight audit passed:\n%s", report.summary_text)


async def run_preflight_checks(
    *,
    concurrency: int = CONCURRENCY,
    takeoff_spacing: float = TAKEOFF_SPACING,
    start_idx: int = START_INDEX,
    limit: int = LIMIT,
    target_id: str = TARGET_ID,
    retry_failed: bool = RETRY_FAILED,
    force_refresh: bool = FORCE_REFRESH,
) -> PreflightReport:
    """Execute all preflight audits concurrently and build report."""
    storage_res = audit_storage()
    vector_res, model_res = await asyncio.gather(
        audit_vector_store(),
        audit_model_gateway(),
    )
    plan_res = compute_generation_plan(
        concurrency=concurrency,
        takeoff_spacing=takeoff_spacing,
        start_idx=start_idx,
        limit=limit,
        target_id=target_id,
        retry_failed=retry_failed,
    )
    all_passed = storage_res.passed and vector_res.passed and model_res.passed

    report = PreflightReport(
        storage=storage_res,
        vector_store=vector_res,
        model_gateway=model_res,
        plan=plan_res,
        passed=all_passed,
        summary_text="",
    )
    report_text = format_preflight_summary(report)
    return report.model_copy(update={"summary_text": report_text})


# ── 4. CLI Entrypoint ─────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for standalone preflight inspection."""
    parser = argparse.ArgumentParser(description="Modular Generator Preflight Audit")
    parser.add_argument("--concurrency", type=int, default=CONCURRENCY)
    parser.add_argument("--takeoff-spacing", type=float, default=TAKEOFF_SPACING)
    parser.add_argument("--start", type=int, default=START_INDEX)
    parser.add_argument("--limit", type=int, default=LIMIT)
    parser.add_argument("--target", type=str, default=TARGET_ID)
    parser.add_argument(
        "--retry-failed",
        action=argparse.BooleanOptionalAction,
        default=RETRY_FAILED,
        help="Inspect retry queue from failed_items.jsonl",
    )
    parser.add_argument(
        "--force-refresh",
        action=argparse.BooleanOptionalAction,
        default=FORCE_REFRESH,
        help="Bypass intermediate stage cache files and recompute from scratch",
    )
    return parser.parse_args()


def main() -> None:
    """Run preflight audit from CLI and exit with appropriate status code."""
    args = parse_args()
    report = asyncio.run(
        run_preflight_checks(
            concurrency=args.concurrency,
            takeoff_spacing=args.takeoff_spacing,
            start_idx=args.start,
            limit=args.limit,
            target_id=args.target,
            retry_failed=args.retry_failed,
        )
    )
    print_preflight_banner(report)
    if not report.passed:
        raise PreflightError("Preflight audit failed. Review errors above before running.")


if __name__ == "__main__":
    main()
