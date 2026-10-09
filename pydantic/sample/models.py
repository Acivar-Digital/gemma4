"""Strict Pydantic v2 contracts and models for Modular Cleaner / Generator Scaffolding.

[SCAFFOLD TEMPLATE]
Design: mirrors ``infrastructure/generators/archetypes/clean/models.py`` with
strict PEP 695 type aliases, validate_assignment=True, and ConfigDict(extra="forbid").
Chinese ``zh`` fields preserve authentic classical text; only ``en`` narrative
fields pass ``validate_clean_english_text``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from infrastructure.workflow_tmp.config import (
    validate_clean_english_text,
)

# ── PEP 695 Type Aliases ────────────────────────────────────────────────────
# [DOMAIN CUSTOMIZATION: Define your domain-specific type aliases here]

type SampleCategory = Literal["primary", "secondary", "tertiary"]

type SamplePosture = Literal[
    "follower",
    "fake_follower",
    "weak",
    "strong",
    "fake_vibrant",
    "vibrant",
]

type SampleGender = Literal["male", "female"]

type CanonicalSourceBook = Literal[
    "San Ming Tong Hui (三命通会)",
    "Di Tian Sui (滴天髓)",
    "Zi Ping Zhen Quan (子平真诠)",
    "Qiong Tong Bao Jian (穷通宝鉴)",
    "Yuan Hai Zi Ping (渊海子平)",
    "Shen Feng Tong Kao (神峰通考)",
]


# ── Raw Source Models (matching catalog/source inputs) ──────────────────────
# [DOMAIN CUSTOMIZATION: Define your raw input spec and cleaned payload]


class RawCitation(BaseModel):
    """Raw citation container loaded from input sources or drafting stages."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    source_book: str = Field(..., min_length=2, description="Classical source title")
    classical_quote: str = Field(..., min_length=4, description="Original classical Chinese quote")
    quote_translation_en: str = Field(..., min_length=10, description="Draft English rendering")

    @field_validator("quote_translation_en")
    @classmethod
    def validate_en(cls, v: str) -> str:
        return validate_clean_english_text(v)


class RawBilingualText(BaseModel):
    """Raw bilingual narrative container holding authentic Chinese and clean English."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    en: str = Field(..., min_length=10, description="English counseling or narrative text")
    zh: str = Field(..., min_length=4, description="Authentic Chinese metaphysical text")

    @field_validator("en")
    @classmethod
    def validate_en(cls, v: str) -> str:
        return validate_clean_english_text(v)


class RawSpec(BaseModel):
    """Stage 0 pure-Python deterministic input spec (0 LLM tokens)."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    index: int = Field(..., ge=1, description="1-based unique combinatorial spec index")
    cell_id: str = Field(..., min_length=3, description="Canonical deterministic identifier")
    category: SampleCategory = Field(..., description="Sample domain category")
    gender: SampleGender = Field(..., description="Sample domain gender")
    posture: SamplePosture = Field(..., description="Sample domain posture")
    primary_entity: str = Field(..., min_length=1, description="Primary domain entity label")
    secondary_entity: str = Field(..., min_length=1, description="Secondary domain entity label")
    sample_abstract: str = Field(..., min_length=5, description="Brief human-readable summary")
    citation: RawCitation = Field(..., description="Raw classical citation spec")


# ── Cleaned Payload Models ──────────────────────────────────────────────────


class CleanedCitation(BaseModel):
    """Polished citation with Latin-first source_book and faithful English translation."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    source_book: str = Field(..., min_length=2, description="Latin-first source e.g. San Ming Tong Hui (三命通会)")
    classical_quote: str = Field(..., min_length=4, description="Verbatim classical quote preserved")
    quote_translation_en: str = Field(..., min_length=10, description="Polished philosophical English rendering")

    @field_validator("source_book", "quote_translation_en")
    @classmethod
    def validate_en(cls, v: str) -> str:
        return validate_clean_english_text(v)


class CleanedBilingualText(BaseModel):
    """Polished bilingual text container; en is clean English, zh is authentic Chinese."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    en: str = Field(..., min_length=10, description="Polished counseling English narrative")
    zh: str = Field(..., min_length=4, description="Polished Chinese, not sanitized")

    @field_validator("en")
    @classmethod
    def validate_en(cls, v: str) -> str:
        return validate_clean_english_text(v)


class CleanStagePayload(BaseModel):
    """Structured LLM output payload from the cleaning/generation agent."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    citation: CleanedCitation
    sifu_diagnostic: CleanedBilingualText
    behavioral_antidote: CleanedBilingualText
    sifu_advisory: CleanedBilingualText
    actionable_behaviors: list[str] = Field(..., min_length=2, max_length=4)
    pitfall_traps: list[str] = Field(..., min_length=1, max_length=3)

    @field_validator("actionable_behaviors")
    @classmethod
    def validate_behaviors(cls, v: list[str]) -> list[str]:
        return [validate_clean_english_text(item) for item in v]

    @field_validator("pitfall_traps")
    @classmethod
    def validate_traps(cls, v: list[str]) -> list[str]:
        return [validate_clean_english_text(item) for item in v]


# ── Storage & Checkpointing Models ──────────────────────────────────────────


class VerifiedCatalogEntry(BaseModel):
    """Fully assembled cellular entry saved to cells/{index:04d}_{cell_id}.json."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    cell_id: str = Field(..., min_length=3, description="Canonical deterministic identifier")
    index: int = Field(..., ge=1, description="1-based unique spec index")
    category: SampleCategory = Field(..., description="Sample domain category")
    gender: SampleGender = Field(..., description="Sample domain gender")
    posture: SamplePosture = Field(..., description="Sample domain posture")
    primary_entity: str = Field(..., min_length=1, description="Primary domain entity label")
    secondary_entity: str = Field(..., min_length=1, description="Secondary domain entity label")
    sample_abstract: str = Field(..., min_length=5, description="Brief human-readable summary")
    citation: CleanedCitation
    sifu_diagnostic: CleanedBilingualText
    behavioral_antidote: CleanedBilingualText
    sifu_advisory: CleanedBilingualText
    actionable_behaviors: list[str] = Field(..., min_length=2, max_length=4)
    pitfall_traps: list[str] = Field(..., min_length=1, max_length=3)
    verified_at: str = Field(..., min_length=10, description="ISO-8601 UTC timestamp")
    content_hash: str = Field(..., min_length=10, description="SHA-256 hex digest")

    @field_validator("actionable_behaviors")
    @classmethod
    def validate_behaviors(cls, v: list[str]) -> list[str]:
        return [validate_clean_english_text(item) for item in v]

    @field_validator("pitfall_traps")
    @classmethod
    def validate_traps(cls, v: list[str]) -> list[str]:
        return [validate_clean_english_text(item) for item in v]


class ReviewCheckpoint(BaseModel):
    """Append-only audit record for review_checkpoints.jsonl."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    cell_id: str = Field(..., min_length=3, description="Canonical deterministic identifier")
    index: int = Field(..., ge=1, description="1-based unique spec index")
    verified_at: str = Field(..., min_length=10, description="ISO-8601 UTC timestamp")
    content_hash: str = Field(..., min_length=10, description="SHA-256 hex digest")
    status: str = Field(default="cleaned", min_length=3, description="Verification status")


class FailedItemRecord(BaseModel):
    """Append-only failure log for failed_items.jsonl."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    cell_id: str = Field(..., min_length=3, description="Canonical deterministic identifier")
    index: int = Field(..., ge=1, description="1-based unique spec index")
    failed_at: str = Field(..., min_length=10, description="ISO-8601 UTC timestamp")
    error_type: str = Field(..., min_length=2, description="Exception class name")
    error_message: str = Field(..., min_length=5, description="Sanitized error details")
    retry_count: int = Field(default=0, ge=0, description="Retry attempt counter")


class GenerationResult(BaseModel):
    """Task outcome schema for pipeline processing."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    success: bool = Field(..., description="Whether cell processing succeeded")
    cell_id: str = Field(..., min_length=3, description="Canonical deterministic identifier")
    error_message: str | None = Field(default=None, description="Error message if failed")
    error_stage: int | None = Field(default=None, description="Stage index where failure occurred")
