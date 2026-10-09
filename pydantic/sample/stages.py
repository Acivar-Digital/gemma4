"""Pydantic-AI Cleaning Agent for Modular Workflow Scaffolding - USER-PROMPT-ONLY gate."""

from __future__ import annotations

import json
import time
from typing import Final

import httpx
from openai import AsyncOpenAI
from pydantic import ValidationError
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from infrastructure.workflow_tmp.config import STREAM, generator_model, logger
from infrastructure.workflow_tmp.models import CleanStagePayload, RawSpec
from infrastructure.workflow_tmp.storage import load_cached_stage, save_stage_cache_atomically

__all__: Final[list[str]] = [
    "EXEMPLARS_BLOCK",
    "RETRYABLE_EXCEPTIONS",
    "RUBRIC_QUESTION_CUBE",
    "SIFU_CLEANING_USER_PREFIX",
    "build_cleaning_prompt",
    "build_stage1_user_prompt",
    "cleaner_agent",
    "execute_stage1",
    "run_clean_stage1",
    "run_cleaning_stage",
]

SIFU_CLEANING_USER_PREFIX: Final[str] = (
    "You are the Master Sifu Bazi Counselor, Lineage Scholar, and Psychological Astrologer.\n"
    "Your mission is to clean, polish, de-fatalize, and elevate the domain catalog entry into a "
    "psychologically empowering, authentic, modern masterwork.\n\n"
    "CRITICAL DIRECTIVES:\n"
    "1. MODERN DE-FATALIZATION:\n"
    "   - Transform ancient fatalistic curses into modern psychological diagnostics and empowering behavioral "
    "antidotes that restore agency and choice.\n"
    "2. BRACKETED HANZI RULE (Latin-first):\n"
    "   - All Chinese technical terms, stem names, Ten-God names, and element references inside English narrative "
    "fields MUST be bracketed LATIN-FIRST, e.g., 'Jia Wood (甲木)', 'Direct Officer (正官)', 'Seven Killings (七杀)', "
    "'Eating God (食神)', 'Indirect Resource (偏印)', 'Bing Fire (丙火)', 'Water (水)', 'Fire (火)'. "
    "Never output raw unbracketed Hanzi in English sentences.\n"
    "3. QUOTE FIDELITY & CLASSICAL GROUNDING:\n"
    "   - citation.classical_quote MUST preserve the exact authentic classical Chinese text provided in the draft verbatim.\n"
    "   - citation.source_book MUST be LATIN-FIRST: 'San Ming Tong Hui (三命通会)', 'Di Tian Sui (滴天髓)', "
    "'Zi Ping Zhen Quan (子平真诠)' — NEVER Hanzi-first and NEVER double-parenthesized.\n"
    "   - citation.quote_translation_en MUST provide a faithful, polished, clause-complete English rendering.\n"
    "4. NO CONVERSATIONAL SLOP OR THINKING LEAKS:\n"
    "   - Strictly NO conversational retry preambles, meta-commentary, or chain-of-thought artifacts "
    "(e.g., 'Wait, let me rewrite', 'Actually...', 'Let us restart').\n"
    "5. ANTI-DUPLICATION RULE:\n"
    "   - NEVER duplicate consecutive words or phrases. Write each sentence cleanly once.\n"
    "6. BILINGUAL INTEGRITY:\n"
    "   - zh fields remain authentic Chinese; en fields are polished English with bracketed Hanzi glosses.\n"
    "7. OUTPUT STRUCTURE:\n"
    "   - Produce a CleanStagePayload JSON containing: citation {source_book, classical_quote, quote_translation_en}, "
    "sifu_diagnostic {en, zh}, behavioral_antidote {en, zh}, sifu_advisory {en, zh}, actionable_behaviors (2-4 strings), "
    "pitfall_traps (1-3 strings). All en fields must pass clean English validation.\n"
)

RUBRIC_QUESTION_CUBE: Final[str] = """\
BEFORE YOU OUTPUT, SELF-AUDIT EACH FIELD WITH THESE 7 QUESTIONS (ALL MUST BE YES):

[D1 Bilingual Sanitization / Fidelity] Did you preserve citation.classical_quote verbatim and emit source_book Latin-first 'San Ming Tong Hui (三命通会)' / 'Di Tian Sui (滴天髓)' / 'Zi Ping Zhen Quan (子平真诠)' — not Hanzi-first and not '((...))' double-parens — with zero unbracketed Hanzi in English fields? (D1=0 -> FAIL)

[D2 Posture-Aware Medicine / De-fatalization] Did you reframe every doom cue into a pattern/risk with agency, with zero fatalistic predictions outside classical_quote? (D2=0 -> FAIL)

[D3 Diagnostic Fidelity / Sifu Voice] Is sifu_diagnostic specific, sensory, and tenure-grounded, encoding posture-aware dynamics and distinct interactions for this entry?

[D4 Antidote Behavioral Grounding / Actionability] Does behavioral_antidote translate the medicine into concrete behavioral guidance with mechanisms restoring choice?

[D5 Advisory Non-Determinism / Linguistic] Is sifu_advisory empowering and non-deterministic (agency restored, no doom), and in every English field is all Hanzi Latin-first bracketed with zero COT leaks and zero duplicated words?

[D6 Actionable Behaviors (2-4) / Consistency] Do actionable_behaviors contain 2-4 distinct items each naming cadence, cap, or if-then guard?

[D7 Pitfall Traps (1-3) / Translation] Do pitfall_traps contain 1-3 distinct relational traps, and does quote_translation_en cover every clause of classical_quote faithfully? (D7=0 -> FAIL)

CRITICAL OVERRIDE: If any of D1 / D2 / D7 would be 0, output is FAIL regardless of other dimensions.
"""

EXEMPLARS_BLOCK: Final[str] = """\
Study this PASS exemplar — emulate its bracketing, posture-correct medicine, and doom-free psychology:

# Exemplar 1 — SCAF_primary_male_strong_Alpha_One — PASS
```json
{
  "citation": {
    "source_book": "Di Tian Sui (滴天髓)",
    "classical_quote": "强木得火，方化其顽。",
    "quote_translation_en": "When dense, unyielding wood meets illuminating fire, its rigid obstinacy is transformed into radiant expression."
  },
  "sifu_diagnostic": {
    "en": "When a strong Jia Wood (甲木) Day Master encounters surplus assertive pressure, the energetic field becomes congested with excessive pride and defensive boundaries. In interpersonal dynamics, this manifests as an instinct to defend psychological territory rather than collaborate.",
    "zh": "身强甲木再遇重叠，木气过旺而郁结，极易在亲密与人际互动中激化边界争端与隐性竞争心理。"
  },
  "behavioral_antidote": {
    "en": "Activate the Fire (火) element through radical emotional transparency, vocal appreciation, and creative outward expression. Shift from self-defense to proactive warmth; channel surplus stamina into shared endeavors.",
    "zh": "以火为用，取‘木火通明、泄秀生辉’之意。主动放下防御性姿态，将过剩的意志力转化为温暖的表达与真诚的赞赏。"
  },
  "sifu_advisory": {
    "en": "Your surplus Wood (木) finds liberation through Fire (火) expression — use voice, warmth, and creative leadership to convert stubborn pride into radiant service. Collaboration flourishes with agency restored.",
    "zh": "木旺宜泄以火，主动表达与温暖引领可化顽为明，转竞争为协作，令意志之力成众人之光。"
  },
  "actionable_behaviors": [
    "Practice verbal appreciation daily: articulate one specific quality you admire in your partner before discussing sensitive topics.",
    "Channel surplus assertive energy into a vigorous creative outlet prior to emotionally charged dialogues."
  ],
  "pitfall_traps": [
    "Engaging in silent emotional scorekeeping and misinterpreting healthy compromise as personal defeat."
  ]
}
```
"""

cleaner_agent: Agent[None, CleanStagePayload] = Agent(
    generator_model,
    output_type=CleanStagePayload,
    retries=3,
)

RETRYABLE_EXCEPTIONS: Final[tuple[type[Exception], ...]] = (
    ModelHTTPError,
    ModelAPIError,
    UnexpectedModelBehavior,
    ValidationError,
    OSError,
    httpx.HTTPError,
    httpx.TimeoutException,
    TimeoutError,
)


def _resolve_worker_model(
    client: httpx.AsyncClient | None,
    base_model: OpenAIChatModel | None = None,
) -> OpenAIChatModel | None:
    """Clone generator model with isolated HTTP client and strictly disabled SDK micro-retries."""
    model_to_use = base_model if isinstance(base_model, OpenAIChatModel) else generator_model
    orig_provider = model_to_use.provider
    if not isinstance(orig_provider, OpenAIProvider):
        return None

    if client is None:
        orig_provider.client.max_retries = 0
        return None

    openai_client = AsyncOpenAI(
        base_url=orig_provider.base_url,
        api_key=orig_provider.client.api_key,
        http_client=client,
        max_retries=0,
    )
    new_provider = OpenAIProvider(openai_client=openai_client)
    return OpenAIChatModel(
        model_name=model_to_use.model_name,
        provider=new_provider,
        settings=model_to_use.settings,
        profile=model_to_use.profile,
    )


def _extract_json_block(text: str) -> str:
    """Extract outermost JSON object substring, ignoring outer think tags or commentary."""
    stripped = text.strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return stripped[start : end + 1]
    return stripped


def _strip_json_fences(text: str) -> str:
    """Strip leading json fences and trailing fences from LLM string output."""
    t = text.strip()
    if t.startswith("```"):
        nl = t.find("\n")
        t = t[nl + 1 :] if nl != -1 else t.lstrip("`").lstrip("json").strip()
        if t.endswith("```"):
            t = t.removesuffix("```").strip()
    return t.strip()


def _parse_output_dict(d: dict[str, object]) -> CleanStagePayload:
    """Filter extra metadata fields if model echoed them."""
    allowed = {
        "citation",
        "sifu_diagnostic",
        "behavioral_antidote",
        "sifu_advisory",
        "actionable_behaviors",
        "pitfall_traps",
    }
    filtered = {k: v for k, v in d.items() if k in allowed}
    return CleanStagePayload.model_validate(filtered)


def _parse_output_str(raw: str) -> CleanStagePayload:
    """Extract JSON block and coerce string into CleanStagePayload."""
    cleaned = _extract_json_block(_strip_json_fences(raw))
    try:
        return CleanStagePayload.model_validate_json(cleaned)
    except ValidationError:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return _parse_output_dict(parsed)
        raise


def _parse_output(raw: object) -> CleanStagePayload:
    """Coerce raw agent output into CleanStagePayload handling string fences."""
    if isinstance(raw, CleanStagePayload):
        return raw
    if isinstance(raw, str):
        return _parse_output_str(raw)
    if isinstance(raw, dict):
        return _parse_output_dict(raw)
    return CleanStagePayload.model_validate(raw)


def build_stage1_user_prompt(draft: RawSpec) -> str:
    """Compose single user turn: Persona + Directives + Rubric + Exemplar + Draft block."""
    draft_block = (
        f"\n\n--- DRAFT TO CLEAN (cell_id={draft.cell_id}) ---\n"
        f"{json.dumps(draft.model_dump(), ensure_ascii=False, indent=2)}\n"
        "--- END DRAFT ---\n"
    )
    return SIFU_CLEANING_USER_PREFIX + "\n\n" + RUBRIC_QUESTION_CUBE + "\n\n" + EXEMPLARS_BLOCK + draft_block


build_cleaning_prompt = build_stage1_user_prompt


async def _run_stream_with_fallback(
    agent: Agent[None, CleanStagePayload],
    prompt: str,
    model: OpenAIChatModel | None,
) -> CleanStagePayload:
    """Run agent streaming with fallback to direct run on validation error."""
    try:
        async with agent.run_stream(prompt, model=model) as stream_result:
            raw_output = await stream_result.get_output()
            return _parse_output(raw_output)
    except UnexpectedModelBehavior as exc:
        logger.warning("Streaming validation failed (%s); falling back to direct run...", exc)
        result = await agent.run(prompt, model=model)
        raw = getattr(result, "output", getattr(result, "data", result))
        return _parse_output(raw)


async def _execute_stage_with_retry(
    entry: RawSpec,
    target_agent: Agent[None, CleanStagePayload],
    client: httpx.AsyncClient | None = None,
    *,
    stream: bool = STREAM,
) -> CleanStagePayload:
    """Run agent against entry prompt with model resolution and bubble exceptions to runner."""
    prompt = build_stage1_user_prompt(entry)
    base_model = target_agent.model if isinstance(target_agent.model, OpenAIChatModel) else generator_model
    model = _resolve_worker_model(client, base_model)
    if stream:
        return await _run_stream_with_fallback(target_agent, prompt, model)
    result = await target_agent.run(prompt, model=model)
    raw = getattr(result, "output", getattr(result, "data", result))
    return _parse_output(raw)


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1.5, min=3.0, max=30.0),
    retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
    reraise=True,
)
async def run_clean_stage1(
    source: RawSpec,
    client: httpx.AsyncClient | None = None,
    *,
    force_refresh: bool = False,
    agent: Agent[None, CleanStagePayload] | None = None,
    stream: bool = STREAM,
) -> CleanStagePayload:
    """Run Stage 1 cleaning with staging cache, single user turn, and atomic persistence."""
    cached = load_cached_stage(source.cell_id, 1, CleanStagePayload, force_refresh=force_refresh)
    if cached is not None:
        return cached
    logger.info("[%s] Calling Stage 1 Language Cleaner...", source.cell_id)
    t0 = time.perf_counter()
    target_agent = agent or cleaner_agent
    payload = await _execute_stage_with_retry(source, target_agent, client, stream=stream)
    elapsed = time.perf_counter() - t0
    save_stage_cache_atomically(source.cell_id, 1, payload)
    logger.info(
        "[%s] Stage 1 Cleaned in %.1fs (source_book: %s)",
        source.cell_id,
        elapsed,
        payload.citation.source_book,
    )
    return payload


execute_stage1 = run_clean_stage1


async def run_cleaning_stage(
    entry: RawSpec,
    agent: Agent[None, CleanStagePayload] | None = None,
    *,
    stream: bool = STREAM,
) -> CleanStagePayload:
    """Run cleaning stage directly with optional agent override."""
    target_agent = agent or cleaner_agent
    return await _execute_stage_with_retry(entry, target_agent, None, stream=stream)
