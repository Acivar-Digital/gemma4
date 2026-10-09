"""Atomic storage, staging cache, checkpoint logging, and catalog compilation.

[SCAFFOLD TEMPLATE]
Design: mirrors ``infrastructure/generators/archetypes/clean/storage.py`` pattern.
Atomic writes via .tmp + replace() with os.fsync().
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ValidationError

from infrastructure.workflow_tmp.config import (
    CATALOG_JSON,
    CELLS_DIR,
    CHECKPOINT_JSONL,
    FAILED_JSONL,
    STAGING_DIR,
    logger,
    sanitize_bracketed_hanzi,
    validate_clean_english_text,
)
from infrastructure.workflow_tmp.models import (
    CleanedBilingualText,
    CleanedCitation,
    CleanStagePayload,
    FailedItemRecord,
    RawCitation,
    RawSpec,
    ReviewCheckpoint,
    VerifiedCatalogEntry,
)

__all__: Final[list[str]] = [
    "append_checkpoint",
    "append_failure",
    "assemble_cleaned_entry",
    "assemble_record",
    "cleanup_stage_cache",
    "compile_catalog",
    "create_raw_citation",
    "get_completed_indices",
    "is_cell_completed",
    "load_cached_stage",
    "load_source_catalog",
    "log_failure",
    "normalize_source_book",
    "save_cell_atomically",
    "save_stage_cache_atomically",
]

_HANZI_ALTS: Final[str] = "三命通会|滴天髓|子平真诠|穷通宝鉴|渊海子平|神峰通考"
_LATIN_ALTS: Final[str] = (
    "San Ming Tong Hui|Di Tian Sui|Zi Ping Zhen Quan|Qiong Tong Bao Jian|Yuan Hai Zi Ping|Shen Feng Tong Kao"
)
_SOURCE_BOOK_DOUBLE_PAREN_RE: Final[re.Pattern[str]] = re.compile(rf"\(({_HANZI_ALTS})\)\s*\(({_LATIN_ALTS})\)")
_SOURCE_BOOK_HANZI_FIRST_RE: Final[re.Pattern[str]] = re.compile(rf"({_HANZI_ALTS})\s*\(({_LATIN_ALTS})\)")
_DUP_PERIOD_WORD_RE: Final[re.Pattern[str]] = re.compile(r"\b(\w+)\.\s+\1\.")
_DUP_WORD_RE: Final[re.Pattern[str]] = re.compile(r"\b(\w+)\s+\1\b")


def normalize_source_book(text: str) -> str:
    """Normalize inverted source_book to Latin-first form for canonical books."""
    cleaned = text.strip()
    if _SOURCE_BOOK_DOUBLE_PAREN_RE.search(cleaned):
        cleaned = _SOURCE_BOOK_DOUBLE_PAREN_RE.sub(lambda m: f"{m.group(2)} ({m.group(1)})", cleaned)
    if _SOURCE_BOOK_HANZI_FIRST_RE.search(cleaned):
        cleaned = _SOURCE_BOOK_HANZI_FIRST_RE.sub(lambda m: f"{m.group(2)} ({m.group(1)})", cleaned)
    return cleaned


def _deduplicate_translation(text: str) -> str:
    """Collapse duplicated consecutive words like 'scholar. scholar.'."""
    deduped = _DUP_PERIOD_WORD_RE.sub(r"\1.", text)
    return _DUP_WORD_RE.sub(r"\1", deduped)


def create_raw_citation(source_book: str, classical_quote: str, quote_translation_en: str) -> RawCitation:
    """Instantiate a validated RawCitation model container."""
    return RawCitation(
        source_book=source_book,
        classical_quote=classical_quote,
        quote_translation_en=quote_translation_en,
    )


def load_source_catalog() -> list[RawSpec]:
    """Load and validate all raw source spec items from verified catalog."""
    if not CATALOG_JSON.exists():
        raise FileNotFoundError(f"Source catalog not found at {CATALOG_JSON}")
    raw_text = CATALOG_JSON.read_text(encoding="utf-8")
    raw_data: list[object] = json.loads(raw_text)
    return [RawSpec.model_validate(item) for item in raw_data]


def _get_stage_file_path(cell_id: str, stage_num: int) -> Path:
    """Resolve target path for intermediate stage cache."""
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    return STAGING_DIR / f"{cell_id}_stage{stage_num}.json"


def save_stage_cache_atomically(
    cell_id: str,
    stage_num: int,
    payload: BaseModel,
) -> Path:
    """Save intermediate stage output to staging cache using atomic file replacement with fsync."""
    target_path = _get_stage_file_path(cell_id, stage_num)
    tmp_path = target_path.with_suffix(".json.tmp")
    tmp_path.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
    with tmp_path.open("r+", encoding="utf-8") as f:
        f.flush()
        os.fsync(f.fileno())
    tmp_path.replace(target_path)
    return target_path


def load_cached_stage[T: BaseModel](
    cell_id: str,
    stage_num: int,
    model_cls: type[T],
    force_refresh: bool = False,
) -> T | None:
    """Load intermediate stage from staging cache with auto-purge on corrupted data."""
    if force_refresh:
        return None
    target_path = _get_stage_file_path(cell_id, stage_num)
    if not target_path.exists():
        return None
    cached: T | None = None
    try:
        cached_text = target_path.read_text(encoding="utf-8")
        cached = model_cls.model_validate_json(cached_text)
        logger.info("[%s] 📦 Loaded Stage %d from staging cache", cell_id, stage_num)
    except (ValidationError, json.JSONDecodeError, OSError) as exc:
        logger.warning("[%s] Corrupt Stage %d cache (%s). Purging.", cell_id, stage_num, exc)
        target_path.unlink(missing_ok=True)
    return cached


def _unlink_stage_file(stage_file: Path, cell_id: str) -> None:
    """Safely unlink a single stage cache file."""
    try:
        stage_file.unlink(missing_ok=True)
    except OSError as exc:
        logger.debug("[%s] Failed deleting staging file %s: %s", cell_id, stage_file, exc)


def cleanup_stage_cache(cell_id: str) -> None:
    """Remove intermediate staging files for the specified entry upon completion."""
    if not STAGING_DIR.exists():
        return
    for stage_file in STAGING_DIR.glob(f"{cell_id}_stage*.json*"):
        _unlink_stage_file(stage_file, cell_id)


def is_cell_completed(cell_id: str, index: int) -> bool:
    """Verify if a cell file exists and contains valid JSON."""
    cell_path = CELLS_DIR / f"{index:04d}_{cell_id}.json"
    if not cell_path.exists():
        return False
    is_valid = False
    try:
        json.loads(cell_path.read_text(encoding="utf-8"))
        is_valid = True
    except (json.JSONDecodeError, OSError) as exc:
        logger.debug("[%s] Invalid cell JSON for index %d: %s", cell_id, index, exc)
    return is_valid


def _extract_cell_file_index(file_path: Path) -> int:
    """Extract numeric index prefix from a cell filename like '0001_SCAF_...json'."""
    prefix = file_path.stem.split("_")[0]
    return int(prefix) if prefix.isdigit() else 0


def _append_cell_file_index(indices: set[int], cell_file: Path) -> None:
    """Extract and add valid index from cell file path."""
    idx = _extract_cell_file_index(cell_file)
    if idx > 0:
        indices.add(idx)


def _collect_indices_from_cells_dir() -> set[int]:
    """Collect completed indices by scanning valid JSON files in CELLS_DIR."""
    indices: set[int] = set()
    if not CELLS_DIR.exists():
        return indices
    for cell_file in CELLS_DIR.glob("*.json"):
        _append_cell_file_index(indices, cell_file)
    return indices


def _parse_checkpoint_line(line: str) -> int | None:
    """Parse single JSON line into a verified checkpoint index."""
    stripped = line.strip()
    if not stripped:
        return None
    chk = ReviewCheckpoint.model_validate_json(stripped)
    return chk.index


def _append_checkpoint_index(indices: set[int], line: str) -> None:
    """Parse single line and add index to set if valid."""
    idx = _parse_checkpoint_line(line)
    if idx is not None:
        indices.add(idx)


def _collect_indices_from_checkpoints() -> set[int]:
    """Collect completed indices recorded in CHECKPOINT_JSONL."""
    indices: set[int] = set()
    if not CHECKPOINT_JSONL.exists():
        return indices
    try:
        lines = CHECKPOINT_JSONL.read_text(encoding="utf-8").splitlines()
        for line in lines:
            _append_checkpoint_index(indices, line)
    except (ValidationError, json.JSONDecodeError, OSError) as exc:
        logger.warning("Error reading checkpoints for completed indices: %s", exc)
    return indices


def get_completed_indices() -> set[int]:
    """Scan CELLS_DIR and CHECKPOINT_JSONL for already processed indices."""
    cell_indices = _collect_indices_from_cells_dir()
    chk_indices = _collect_indices_from_checkpoints()
    return cell_indices.union(chk_indices)


def _sanitize_cleaned_bilingual(bt: CleanedBilingualText) -> CleanedBilingualText:
    """Sanitize English field via bracketed Hanzi; preserve Chinese verbatim."""
    return CleanedBilingualText(
        en=sanitize_bracketed_hanzi(bt.en),
        zh=bt.zh,
    )


def _sanitize_cleaned_citation(
    cit: CleanedCitation,
    original_quote: str,
) -> CleanedCitation:
    """Sanitize citation translation while preserving authentic original quote."""
    normalized_book = normalize_source_book(cit.source_book)
    deduped_translation = _deduplicate_translation(cit.quote_translation_en)
    return CleanedCitation(
        source_book=sanitize_bracketed_hanzi(normalized_book),
        classical_quote=original_quote,
        quote_translation_en=sanitize_bracketed_hanzi(deduped_translation),
    )


def _sanitize_behavior_list(items: list[str]) -> list[str]:
    """Map sanitize_bracketed_hanzi + validate over each behavior/trap string."""
    return [validate_clean_english_text(sanitize_bracketed_hanzi(item)) for item in items]


def _compute_entry_content_hash(
    cell_id: str,
    citation: CleanedCitation,
    diagnostic: CleanedBilingualText,
    antidote: CleanedBilingualText,
    advisory: CleanedBilingualText,
    behaviors: list[str],
    traps: list[str],
) -> str:
    """Compute SHA-256 integrity hash for assembled cleaned entry."""
    content_raw = (
        f"{cell_id}|"
        f"{citation.model_dump_json()}|"
        f"{diagnostic.model_dump_json()}|"
        f"{antidote.model_dump_json()}|"
        f"{advisory.model_dump_json()}|"
        f"{json.dumps(behaviors, ensure_ascii=False)}|"
        f"{json.dumps(traps, ensure_ascii=False)}"
    )
    return hashlib.sha256(content_raw.encode("utf-8")).hexdigest()


def assemble_cleaned_entry(
    spec: RawSpec,
    payload: CleanStagePayload,
) -> VerifiedCatalogEntry:
    """Assemble final VerifiedCatalogEntry with sanitized narratives and source coordinates."""
    diagnostic = _sanitize_cleaned_bilingual(payload.sifu_diagnostic)
    antidote = _sanitize_cleaned_bilingual(payload.behavioral_antidote)
    advisory = _sanitize_cleaned_bilingual(payload.sifu_advisory)
    cit = _sanitize_cleaned_citation(payload.citation, spec.citation.classical_quote)
    behaviors = _sanitize_behavior_list(payload.actionable_behaviors)
    traps = _sanitize_behavior_list(payload.pitfall_traps)
    now_iso = datetime.datetime.now(datetime.UTC).isoformat()
    content_hash = _compute_entry_content_hash(spec.cell_id, cit, diagnostic, antidote, advisory, behaviors, traps)
    return VerifiedCatalogEntry(
        cell_id=spec.cell_id,
        index=spec.index,
        category=spec.category,
        gender=spec.gender,
        posture=spec.posture,
        primary_entity=spec.primary_entity,
        secondary_entity=spec.secondary_entity,
        sample_abstract=spec.sample_abstract,
        citation=cit,
        sifu_diagnostic=diagnostic,
        behavioral_antidote=antidote,
        sifu_advisory=advisory,
        actionable_behaviors=behaviors,
        pitfall_traps=traps,
        verified_at=now_iso,
        content_hash=content_hash,
    )


def assemble_record(
    spec: RawSpec,
    payload: CleanStagePayload,
) -> VerifiedCatalogEntry:
    """Assemble final VerifiedCatalogEntry (alias for assemble_cleaned_entry)."""
    return assemble_cleaned_entry(spec, payload)


def save_cell_atomically(entry: VerifiedCatalogEntry) -> Path:
    """Save cleaned cell JSON to cells/ using atomic file swap with fsync."""
    CELLS_DIR.mkdir(parents=True, exist_ok=True)
    fname = f"{entry.index:04d}_{entry.cell_id}.json"
    target_path = CELLS_DIR / fname
    tmp_path = CELLS_DIR / f"{fname}.tmp"
    tmp_path.write_text(entry.model_dump_json(indent=2), encoding="utf-8")
    with tmp_path.open("r+", encoding="utf-8") as f:
        f.flush()
        os.fsync(f.fileno())
    tmp_path.replace(target_path)
    return target_path


def append_checkpoint(checkpoint: ReviewCheckpoint | VerifiedCatalogEntry) -> None:
    """Append checkpoint audit record to review_checkpoints.jsonl."""
    CHECKPOINT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    record = (
        checkpoint
        if isinstance(checkpoint, ReviewCheckpoint)
        else ReviewCheckpoint(
            cell_id=checkpoint.cell_id,
            index=checkpoint.index,
            verified_at=checkpoint.verified_at,
            content_hash=checkpoint.content_hash,
            status="cleaned",
        )
    )
    with CHECKPOINT_JSONL.open("a", encoding="utf-8") as f:
        f.write(record.model_dump_json() + "\n")


def append_failure(failure: FailedItemRecord) -> None:
    """Append single failure JSON line to FAILED_JSONL."""
    FAILED_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with FAILED_JSONL.open("a", encoding="utf-8") as f:
        f.write(failure.model_dump_json() + "\n")


def _format_error_message(exc: Exception) -> str:
    """Format safe error message string with minimum length of 5 chars."""
    raw_msg = str(exc).strip() or repr(exc) or type(exc).__name__
    if len(raw_msg) >= 5:
        return raw_msg
    return f"{type(exc).__name__}: {raw_msg}".strip(": ")


def log_failure(
    spec: RawSpec,
    exc: Exception,
    retry_count: int = 0,
) -> None:
    """Append failed item record to failed_items.jsonl via append_failure."""
    now_iso = datetime.datetime.now(datetime.UTC).isoformat()
    record = FailedItemRecord(
        cell_id=spec.cell_id,
        index=spec.index,
        failed_at=now_iso,
        error_type=type(exc).__name__,
        error_message=_format_error_message(exc),
        retry_count=retry_count,
    )
    append_failure(record)


def _write_entries_stream(cell_files: list[Path], tmp_path: Path, now_iso: str) -> None:
    """Stream cell JSON contents into destination temporary file with O(1) memory."""
    with tmp_path.open("w", encoding="utf-8") as out:
        out.write('{\n  "version": "1.0.0",\n')
        out.write(f'  "compiled_at": "{now_iso}",\n')
        out.write(f'  "total_cells": {len(cell_files)},\n')
        out.write('  "cells": [\n')
        for i, p in enumerate(cell_files):
            if i > 0:
                out.write(",\n")
            out.write(p.read_text(encoding="utf-8"))
        out.write("\n  ]\n}\n")


def _write_in_memory_entries(entries: list[VerifiedCatalogEntry], tmp_path: Path, now_iso: str) -> None:
    """Stream provided in-memory VerifiedCatalogEntry objects to catalog file."""
    with tmp_path.open("w", encoding="utf-8") as out:
        out.write('{\n  "version": "1.0.0",\n')
        out.write(f'  "compiled_at": "{now_iso}",\n')
        out.write(f'  "total_cells": {len(entries)},\n')
        out.write('  "cells": [\n')
        for i, entry in enumerate(entries):
            if i > 0:
                out.write(",\n")
            out.write(entry.model_dump_json(indent=2))
        out.write("\n  ]\n}\n")


def _commit_catalog_file(tmp_path: Path) -> None:
    """Flush and atomic replace temporary catalog file with fsync."""
    with tmp_path.open("r+", encoding="utf-8") as f:
        f.flush()
        os.fsync(f.fileno())
    tmp_path.replace(CATALOG_JSON)


def compile_catalog(entries: list[VerifiedCatalogEntry] | None = None) -> int:
    """Compile VerifiedCatalogEntry objects or on-disk cell JSONs into master catalog_verified.json."""
    now_iso = datetime.datetime.now(datetime.UTC).isoformat()
    tmp_path = CATALOG_JSON.with_suffix(".json.tmp")
    CATALOG_JSON.parent.mkdir(parents=True, exist_ok=True)

    if entries is not None:
        if not entries:
            return 0
        _write_in_memory_entries(entries, tmp_path, now_iso)
        _commit_catalog_file(tmp_path)
        return len(entries)

    if not CELLS_DIR.exists():
        return 0
    cell_files = sorted(CELLS_DIR.glob("*.json"))
    if not cell_files:
        return 0

    _write_entries_stream(cell_files, tmp_path, now_iso)
    _commit_catalog_file(tmp_path)
    return len(cell_files)
