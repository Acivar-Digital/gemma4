"""Modular Generator Scaffolding: Runtime configuration, paths, model binding, and text sanitizers.

[SCAFFOLD TEMPLATE]
This module defines runtime paths, execution controls, centralized model bindings,
and domain constants for multi-stage batch generation pipelines.
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import Final, Literal

import logfire
from dotenv import load_dotenv
from pydantic_ai.models.openai import OpenAIChatModel

from admin.controls.controls import CONTROL_SHEET


# ── 1. Root & Environment Setup & Unified Model ───────────────────────────────
def _find_project_root() -> Path:
    """Deterministically resolve repository root searching upwards for marker files."""
    current = Path(__file__).resolve()
    for parent in [current, *list(current.parents)]:
        if (parent / "pyproject.toml").exists() or (parent / ".git").exists():
            return parent
    return Path.cwd()


PROJECT_ROOT: Final[Path] = _find_project_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

# Model binding: Bound to CONTROL_SHEET.clean_rag (centralized via controls.py)
generator_model: OpenAIChatModel = CONTROL_SHEET.clean_rag

# ── 2. Standard Execution & Generation Controls ───────────────────────────────
CONCURRENCY: int = 7
TAKEOFF_SPACING: float = 3.5
MAX_429_KEY_HOPS: int = 2
FAST_429_RETRY_DELAY: float = 0.5
WORKER_TIMEOUT: float = 300.0  # Maximum seconds allowed per worker item processing
HTTP_CONNECT_TIMEOUT: float = 60.0  # Socket connection timeout in seconds
HTTP_WRITE_TIMEOUT: float = 300.0  # Socket write timeout in seconds
HTTP_POOL_TIMEOUT: float = 300.0  # Socket pool acquisition timeout in seconds
START_INDEX: int = 1
LIMIT: int = 0  # 0 = process all pending
TARGET_ID: str = ""
INDEX: int | None = None
RETRY_FAILED: bool = False
FORCE_REFRESH: bool = False
BACKOFF_INITIAL: float = 8.0
BACKOFF_INITIAL_429: float = 45.0
BACKOFF_FACTOR: float = 1.5
BACKOFF_FACTOR_429: float = 1.2
BACKOFF_MAX_ATTEMPTS: int = 5
SKIP_PREFLIGHT: bool = False
STREAM: Final[bool] = True

# ── 3. Standard Paths & Logging Configuration ─────────────────────────────────
# [CUSTOMIZATION NOTE]: Change "scaffold_output" to your generator's target directory name
BASE_DIR: Final[Path] = PROJECT_ROOT / "infrastructure" / "generators" / "scaffold_output"
WORK_DIR: Final[Path] = BASE_DIR
CELLS_DIR: Final[Path] = BASE_DIR / "cells"
STAGING_DIR: Final[Path] = BASE_DIR / "staging"
CATALOG_PATH: Final[Path] = BASE_DIR / "catalog_verified.json"
CATALOG_JSON: Final[Path] = CATALOG_PATH
SOURCE_CATALOG_PATH: Final[Path] = CATALOG_PATH
CHECKPOINTS_PATH: Final[Path] = BASE_DIR / "review_checkpoints.jsonl"
CHECKPOINT_JSONL: Final[Path] = CHECKPOINTS_PATH
FAILURES_PATH: Final[Path] = BASE_DIR / "failed_items.jsonl"
FAILED_JSONL: Final[Path] = FAILURES_PATH
LOG_PATH: Final[Path] = PROJECT_ROOT / "logs" / "generator_scaffold.log"
LOG_FILE: Final[Path] = LOG_PATH

LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
    ],
)
logger: logging.Logger = logging.getLogger("scaffold_generator")

logfire.configure(
    send_to_logfire="if-token-present",
    console=False,
)
logfire.instrument_pydantic()

# ── 4. Regex Patterns & Sanitization Suite ─────────────────────────────────────
# Note: BANNED_COT_RE is preserved for backwards compatibility; vocabulary crashing is permanently removed.
BANNED_COT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?i)(?:^|[\n\.\?!]\s*)(wait[,:\.\-]+|wait\s+(?:actually|let me|no|hold on|sorry|scratch)|"
    r"let me (?:restart|rewrite|rethink|start over|re-evaluate)|"
    r"let's (?:restart|rewrite|rethink)|i (?:need|should) to (?:restart|rewrite)|oops[,!]|actually, let me|scratch that|thinking process)"
)
XML_THINKING_RE: Final[re.Pattern[str]] = re.compile(
    r"(?is)<(?:think|thought)>.*?</(?:think|thought)>|&lt;(?:think|thought)&gt;.*?&lt;/(?:think|thought)&gt;"
)
STRAY_THINKING_TAGS_RE: Final[re.Pattern[str]] = re.compile(r"(?i)</?(?:think|thought)>|&lt;/?(?:think|thought)&gt;")
PAREN_BLOCK_RE: Final[re.Pattern[str]] = re.compile(r"(\([^\)]*\)|\[[^\]]*\]|【[^】]*】)")
HANZI_RUN_RE: Final[re.Pattern[str]] = re.compile(r"[\u4e00-\u9fff]+")
DOUBLE_PAREN_RE: Final[re.Pattern[str]] = re.compile(r"\(\(([^\(\)]+)\)\)")
MULTI_SPACE_RE: Final[re.Pattern[str]] = re.compile(r"[ ]{2,}")


def _get_boundary_prefix(seg: str, start: int) -> str:
    """Return prefix space if preceding character is alphanumeric."""
    return " " if start > 0 and seg[start - 1].isalnum() else ""


def _get_boundary_suffix(seg: str, end: int) -> str:
    """Return suffix space if following character is alphanumeric."""
    return " " if end < len(seg) and seg[end].isalnum() else ""


def _wrap_unbracketed_hanzi_match(seg: str, match: re.Match[str]) -> str:
    """Format single unbracketed Hanzi match with boundary spacing."""
    hanzi = match.group(0)
    prefix = _get_boundary_prefix(seg, match.start())
    suffix = _get_boundary_suffix(seg, match.end())
    return f"{prefix}({hanzi}){suffix}"


def _sanitize_unbracketed_segment(seg: str) -> str:
    """Bracket standalone Hanzi sequences in text outside parenthetical blocks."""
    if not seg:
        return ""
    return HANZI_RUN_RE.sub(lambda m: _wrap_unbracketed_hanzi_match(seg, m), seg)


def sanitize_bracketed_hanzi(text: str) -> str:
    """Identify unbracketed Hanzi terms in English text and wrap them in standard parentheses."""
    if not text:
        return text
    normalized = text.replace("（", "(").replace("）", ")")
    tokens = PAREN_BLOCK_RE.split(normalized)
    out: list[str] = [t if PAREN_BLOCK_RE.match(t) else _sanitize_unbracketed_segment(t) for t in tokens if t]
    res = DOUBLE_PAREN_RE.sub(r"(\1)", "".join(out))
    return MULTI_SPACE_RE.sub(" ", res).strip()


def _strip_markdown_enclosing(text: str) -> str:
    """Remove outer markdown fences if present."""
    t = text.strip()
    if t.startswith("```"):
        nl = t.find("\n")
        t = t[nl + 1 :] if nl != -1 else t.lstrip("`")
    if t.endswith("```"):
        t = t.removesuffix("```")
    return t.strip()


def strip_markdown_fences(text: str) -> str:
    """Strip markdown code fence wrappers (```markdown ... ``` or ``` ... ```)."""
    t = _strip_markdown_enclosing(text)
    lines = [line for line in t.splitlines() if not line.strip().startswith("```")]
    return "\n".join(lines).strip()


def strip_thinking_tags(text: str) -> str:
    """Strip XML thinking/thought blocks and stray tags."""
    if not text:
        return ""
    without_blocks = XML_THINKING_RE.sub("", text)
    return STRAY_THINKING_TAGS_RE.sub("", without_blocks).strip()


def strip_tags_and_fences(text: str) -> str:
    """Deterministically strip XML thinking tags and markdown fences from LLM output."""
    without_tags = strip_thinking_tags(text)
    return strip_markdown_fences(without_tags)


def validate_clean_english_text(v: str) -> str:
    """Strip tags/fences, format bracketed Hanzi, and verify substantive content."""
    if not isinstance(v, str):
        raise TypeError("Text field must be a string")
    cleaned = strip_tags_and_fences(v)
    cleaned = sanitize_bracketed_hanzi(cleaned)
    if len(cleaned.strip()) < 5:
        raise ValueError("Text field cannot be empty or fewer than 5 characters. Provide full substantive content.")
    return cleaned


# ── 5. Domain Types & Enums (PEP 695) ──────────────────────────────────────────
# [DOMAIN CUSTOMIZATION]: Replace these sample types with your domain entities
type SampleCategory = Literal["primary", "secondary", "tertiary"]
type SamplePosture = Literal["follower", "fake_follower", "weak", "strong", "fake_vibrant", "vibrant"]
type SampleGender = Literal["male", "female"]
type ClassicalSource = Literal[
    "子平真诠",
    "滴天髓",
    "穷通宝鉴",
    "神峰通考",
    "三命通会",
    "三命指迷赋",
    "千里命稿",
    "命理探源",
    "渊海子平",
]

# ── 6. Domain Constants ───────────────────────────────────────────────────────
# [DOMAIN CUSTOMIZATION]: Adjust domain lists/tuples matching your domain entities
SAMPLE_CATEGORIES: Final[tuple[SampleCategory, ...]] = ("primary", "secondary", "tertiary")
SAMPLE_POSTURES: Final[tuple[SamplePosture, ...]] = (
    "follower",
    "fake_follower",
    "weak",
    "strong",
    "fake_vibrant",
    "vibrant",
)
SAMPLE_GENDERS: Final[tuple[SampleGender, ...]] = ("male", "female")
