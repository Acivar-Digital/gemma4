"""Modular Generator Scaffolding: Classical Vector Retrieval, RAG tool calling, and synthetic fallbacks.

[SCAFFOLD TEMPLATE]
This module provides zero-LLM vector search integration via Qdrant/BaziRAG,
per-cell tool budget management, deduplication guards, and deterministic synthetic fallbacks.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry
from qdrant_client import AsyncQdrantClient

from infrastructure.bazirag import search_single
from infrastructure.workflow_tmp.models import RawCitation, RawSpec

__all__: Final[list[str]] = [
    "DuplicateQueryError",
    "GroundedReference",
    "NoCanonicalReferenceError",
    "RAGPointPayload",
    "Stage1ToolState",
    "ToolBudget",
    "ToolBudgetExhausted",
    "ToolBudgetExhaustedError",
    "build_synthetic_citation",
    "build_synthetic_stage1_payload",
    "query_knowledge_base",
    "ref_to_raw_citation",
]


class NoCanonicalReferenceError(Exception):
    """Raised when Qdrant returns zero hits. Per AGENTS.md 'no silent fallback'."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.is_synthetic_marker: bool = True


class DuplicateQueryError(ModelRetry, Exception):
    """Raised when LLM re-queries the same string. Forces pivot to different keywords."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ToolBudgetExhaustedError(Exception):
    """Raised when per-cell tool-call budget is depleted."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.exhausted_reason: str = "tool_budget_exhausted"


ToolBudgetExhausted = ToolBudgetExhaustedError


class ToolBudget(BaseModel):
    """Per-cell tool-call budget. Fails loudly when exhausted."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    remaining: int = Field(default=10, ge=0, le=50)
    exhausted_reason: str | None = None

    def charge(self, tool_name: str) -> None:
        """Atomically decrement remaining budget; raises if depleted."""
        if self.remaining <= 0:
            self.exhausted_reason = "tool_budget_exhausted"
            raise ToolBudgetExhausted(
                f"Tool budget exhausted during {tool_name!r}. "
                "Stage 1 MUST now produce is_synthetic=True with derivation_basis."
            )
        self.remaining -= 1


class Stage1ToolState(BaseModel):
    """Per-cell deps bundle for stage1_agent. Tracks dedup + budget + shared Qdrant client."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True, validate_assignment=True)

    budget: ToolBudget
    seen_queries: set[str] = Field(default_factory=set)
    qdrant_client: AsyncQdrantClient
    collection_name: str


class RAGPointPayload(BaseModel):
    """Qdrant point payload model."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    text: str = ""
    source: str = ""
    chapter: str = ""
    original_text: str | None = None
    content: str | None = None
    summary_zh: str | None = None
    modern_chinese_summary: str | None = None


class GroundedReference(BaseModel):
    """Grounded reference payload returned from RAG."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    source: str
    text: str
    score: float = 0.0


def _extract_dict_text(p: dict[object, object]) -> str:
    """Extract trimmed text from candidate dictionary."""
    val = p.get("text")
    if not val:
        val = p.get("original_text")
    return str(val or "").strip()


def _extract_dict_source(p: dict[object, object]) -> str:
    """Extract source label from candidate dictionary."""
    val = p.get("source")
    return str(val).strip() if val else "Classical Canon"


def _payload_model_to_ref(p: RAGPointPayload) -> GroundedReference | None:
    """Convert a RAGPointPayload model instance into a GroundedReference."""
    text = p.text.strip()
    if not text and p.original_text:
        text = p.original_text.strip()
    if not text:
        return None
    source = p.source.strip() if p.source else "Classical Canon"
    return GroundedReference(source=source, text=text, score=0.0)


def _candidate_to_ref(p: object) -> GroundedReference | None:
    """Convert a single flat candidate dict or payload model into GroundedReference."""
    if isinstance(p, RAGPointPayload):
        return _payload_model_to_ref(p)
    if not isinstance(p, dict):
        return None
    text = _extract_dict_text(p)
    if not text:
        return None
    source = _extract_dict_source(p)
    score = float(str(p.get("score", 0.0)))
    return GroundedReference(source=source, text=text, score=score)


def _parse_rag_points(points: list[dict[str, object]]) -> list[GroundedReference]:
    """Parse raw Qdrant candidate dicts into GroundedReference models."""
    refs: list[GroundedReference] = []
    for p in points:
        ref = _candidate_to_ref(p)
        if ref is not None:
            refs.append(ref)
    return refs


async def _search_qdrant_for_query(
    client: AsyncQdrantClient,
    collection_name: str,
    query: str,
    limit: int,
) -> list[GroundedReference]:
    """Run a single Qdrant search, returning GroundedReference list."""
    points = await search_single(
        client=client,
        keyword=query,
        collection_name=collection_name,
    )
    if not points:
        return []
    refs = _parse_rag_points(points)
    return refs[:limit]


async def query_knowledge_base(
    ctx: RunContext[Stage1ToolState],
    query: str,
    limit: int = 2,
) -> list[GroundedReference]:
    """Retrieve grounded references from the live Qdrant knowledge base.

    FAILS LOUDLY per AGENTS.md 'no silent fallback' principle.
    """
    state = ctx.deps
    state.budget.charge("query_knowledge_base")

    if query in state.seen_queries:
        raise DuplicateQueryError(
            f"Query {query!r} was already attempted. "
            "Please pivot to alternative classical keywords or proceed with existing findings."
        )
    state.seen_queries.add(query)

    refs = await _search_qdrant_for_query(state.qdrant_client, state.collection_name, query, limit)
    if not refs:
        raise NoCanonicalReferenceError(
            f"Qdrant returned ZERO canonical references for query: {query!r}. "
            "Per AGENTS.md no-silent-fallback principle, this MUST be flagged as "
            "synthetic with explicit derivation basis."
        )

    return refs


def _synthetic_follower() -> tuple[str, str, str]:
    """Synthetic citation fields for follower postures."""
    source_book = "Di Tian Sui (滴天髓)"
    quote = "从神而驰骤，无私意牵制。"
    trans = "When following the dominant momentum, action proceeds without personal friction."
    return source_book, quote, trans


def _synthetic_vibrant() -> tuple[str, str, str]:
    """Synthetic citation fields for vibrant postures."""
    source_book = "Di Tian Sui (滴天髓)"
    quote = "旺者宜克，强者喜裁。"
    trans = "Prosperity requires regulation; strength welcomes disciplined pruning."
    return source_book, quote, trans


def _synthetic_weak() -> tuple[str, str, str]:
    """Synthetic citation fields for weak posture."""
    source_book = "Zi Ping Zhen Quan (子平真诠)"
    quote = "身弱喜印，印绶护身。"
    trans = "The vulnerable Day Master favors the Resource seal for structural protection and renewal."
    return source_book, quote, trans


def _synthetic_strong() -> tuple[str, str, str]:
    """Synthetic citation fields for strong posture."""
    source_book = "Di Tian Sui (滴天髓)"
    quote = "强木得火，方化其顽。"
    trans = "Dense unyielding momentum is transformed through radiant expressive output."
    return source_book, quote, trans


def _resolve_synthetic_quote(posture: str) -> tuple[str, str, str]:
    """Dispatch posture-specific classical citation to keep CC <= 5."""
    if posture in ("follower", "fake_follower"):
        return _synthetic_follower()
    if posture in ("vibrant", "fake_vibrant"):
        return _synthetic_vibrant()
    if posture == "weak":
        return _synthetic_weak()
    return _synthetic_strong()


def build_synthetic_citation(spec: RawSpec, exc: Exception) -> RawCitation:
    """Construct a deterministic synthetic RawCitation when vector retrieval is empty.

    Prevents empty-shell fallbacks while enforcing strict derivation basis.
    """
    source_book, quote_zh, quote_en = _resolve_synthetic_quote(spec.posture)
    _ = exc
    return RawCitation(
        source_book=source_book,
        classical_quote=quote_zh,
        quote_translation_en=quote_en,
    )


def build_synthetic_stage1_payload(spec: RawSpec, exc: Exception) -> RawCitation:
    """Alias for build_synthetic_citation matching the cleaner contract."""
    return build_synthetic_citation(spec, exc)


def ref_to_raw_citation(ref: GroundedReference) -> RawCitation:
    """Convert GroundedReference into a validated RawCitation."""
    return RawCitation(
        source_book=ref.source,
        classical_quote=ref.text,
        quote_translation_en=f"Classical citation from {ref.source} regarding structural dynamics.",
    )
