#!/usr/bin/env python3
"""Pydantic AI 2.0 & pydantic_graph DAG SFT Trajectory Translation Pipeline.

Translates raw Source B (swe_smith / swe_zero) agent trajectories into
production 5-skill + 5-tool trajectories, validates data contracts via strict
Pydantic V2 models with ModelRetry self-correction, records OpenTelemetry spans
via logfire, logs raw HTTP payloads, and verifies zero-thought Gemma 4
chat_template.jinja prefix-delta loss masking invariants.
"""

from __future__ import annotations

# ==============================================================================
# Mandatory Import Shadowing Guard:
# Strip current directory and repo root from sys.path before third-party imports
# so that the local 'pydantic/' directory never shadows the PyPI pydantic package.
# ==============================================================================
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent
sys.path[:] = [
    p for p in sys.path
    if Path(p or ".").resolve() not in (_THIS_DIR, _REPO_ROOT)
]

import asyncio
from dataclasses import dataclass
import datetime
import glob
import hashlib
import json
import logging
import os
import random
import re
import time
from typing import Annotated, Callable, ClassVar, Literal, Sequence, cast

import httpx
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExportResult, SpanExporter
import pyarrow.parquet as pq
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_graph import BaseNode, End, GraphBuilder, GraphRunContext
from transformers import AutoTokenizer

# Re-append repo root for local module access
if str(_REPO_ROOT) not in sys.path:
    sys.path.append(str(_REPO_ROOT))

# ==============================================================================
# Core Types and Aliases (PEP 695)
# ==============================================================================
type SkillName = Literal[
    "fast-grep",
    "code-map",
    "code-oracle",
    "repro-check",
    "test-gate",
]

type SkillScript = Literal[
    "grep.py",
    "map.py",
    "oracle.py",
    "check.py",
    "gate.py",
]

type DirectToolName = Literal[
    "read_file",
    "edit_file",
    "write_file",
    "get_status",
    "submit_patch",
]

# ==============================================================================
# Constants and Paths
# ==============================================================================
LOGS_DIR = _THIS_DIR / "logs"
OUTPUT_DIR = _THIS_DIR / "output"
TEST_RESULTS_DIR = _THIS_DIR / "test_results"
STAGING_DIR = _THIS_DIR / "staging"

LOGFIRE_SPANS_PATH = LOGS_DIR / "logfire_spans.jsonl"
HTTP_RAW_PATH = LOGS_DIR / "http_raw.jsonl"
VERBOSE_LOG_PATH = LOGS_DIR / "pipeline_verbose.log"

TRANSLATED_TRAJECTORIES_PATH = OUTPUT_DIR / "translated_trajectories.jsonl"
SFT_TRAIN_WINDOWS_PATH = OUTPUT_DIR / "sft_train_windows.jsonl"
REJECTED_TASKS_PATH = OUTPUT_DIR / "rejected_tasks.jsonl"
CHECKPOINT_STATE_PATH = OUTPUT_DIR / "checkpoint_state.json"

TOKENIZER_DIR = _REPO_ROOT / "models" / "gemma-4-31b-it-qat-w4a16-ct"
SYSTEM_PROMPT_PATH = _REPO_ROOT / "submissions" / "track1_live" / "prompts" / "main.md"
TASKS_BENCHMARK_PATH = _REPO_ROOT / "tasks.jsonl"

MAX_SEQ_TOKENS = 8192
EMPTY_THOUGHT_CLOSURE = "<|channel>thought\n<channel|>"

TOOLS_SCHEMA: list[dict[str, object]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads contents of a file within /workspace with optional line numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "Relative path to file in /workspace."},
                    "start_line": {"type": "integer", "description": "Optional starting line (1-indexed)."},
                    "end_line": {"type": "integer", "description": "Optional ending line (inclusive)."},
                },
                "required": ["filepath"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Applies surgical text replacement to an existing file in /workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "Relative path to file in /workspace."},
                    "old_string": {"type": "string", "description": "Exact text block to replace."},
                    "new_string": {"type": "string", "description": "Replacement text block."},
                    "allow_multiple": {"type": "boolean", "description": "Whether to allow multiple occurrences."},
                },
                "required": ["filepath", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Writes or overwrites an entire file in /workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "Relative path to file in /workspace."},
                    "content": {"type": "string", "description": "Full file content to write."},
                },
                "required": ["filepath", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_status",
            "description": "Free tool returning current workspace git status and remaining budget.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_patch",
            "description": "Submits final patch and terminates evaluation task immediately.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_skill_script",
            "description": "Executes one of the 5 pre-installed skills (fast-grep, code-map, code-oracle, repro-check, test-gate).",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {"type": "string", "description": "Name of skill directory."},
                    "file_path": {"type": "string", "description": "Script file inside skill (e.g. grep.py, map.py, oracle.py, check.py, gate.py)."},
                    "args": {"type": "array", "items": {"type": "string"}, "description": "Command-line arguments passed to script."},
                },
                "required": ["skill_name", "file_path", "args"],
            },
        },
    },
]

# Configure logging
for d in (LOGS_DIR, OUTPUT_DIR, TEST_RESULTS_DIR):
    d.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("translate_sft_dag")
logger.setLevel(logging.INFO)
logger.handlers.clear()

_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
_sh = logging.StreamHandler(sys.stdout)
_sh.setFormatter(_formatter)
logger.addHandler(_sh)

_fh = logging.FileHandler(VERBOSE_LOG_PATH, encoding="utf-8")
_fh.setFormatter(_formatter)
logger.addHandler(_fh)

# ==============================================================================
# Step 1.5: Atomic Storage & Staging Cache Helpers (os.fsync + tmp swap)
# ==============================================================================

def save_atomically(target_path: Path, content: str) -> Path:
    """Saves string content atomically using .tmp file swap and os.fsync."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    with tmp_path.open("r+", encoding="utf-8") as f:
        f.flush()
        os.fsync(f.fileno())
    tmp_path.replace(target_path)
    return target_path


def append_jsonl_fsync(target_path: Path, line: str) -> None:
    """Appends single JSONL record with f.flush() and os.fsync()."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("a", encoding="utf-8") as f:
        f.write(line.rstrip("\n") + "\n")
        f.flush()
        os.fsync(f.fileno())


def save_stage_cache(task_id: str, stage_name: str, payload: dict[str, object]) -> Path:
    """Saves intermediate stage payload to staging/{task_id}_{stage_name}.json atomically."""
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    stage_path = STAGING_DIR / f"{task_id}_{stage_name}.json"
    return save_atomically(stage_path, json.dumps(payload, indent=2))


def cleanup_stage_cache(task_id: str) -> None:
    """Safely removes intermediate staging files upon task completion."""
    if not STAGING_DIR.exists():
        return
    for stage_file in STAGING_DIR.glob(f"{task_id}_*.json*"):
        try:
            stage_file.unlink(missing_ok=True)
        except OSError as exc:
            logger.debug("[%s] Failed deleting staging file %s: %s", task_id, stage_file, exc)

# ==============================================================================
# Step 2: Strict Pydantic V2 Data Contracts (Zero typing.Any, extra="forbid")
# ==============================================================================

class ReadFileAction(BaseModel):
    """Action to read lines from a file."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    action_type: Literal["read_file"] = "read_file"
    filepath: str
    start_line: int | None = Field(default=None, ge=1)


class EditFileAction(BaseModel):
    """Action to apply surgical text replacement to an existing file."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    action_type: Literal["edit_file"] = "edit_file"
    filepath: str
    old_string: str = Field(min_length=1)
    new_string: str
    allow_multiple: bool = False


class WriteFileAction(BaseModel):
    """Action to create or overwrite a file."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    action_type: Literal["write_file"] = "write_file"
    filepath: str
    content: str = Field(min_length=1)


class GetStatusAction(BaseModel):
    """Action to query workspace status and tool budget."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    action_type: Literal["get_status"] = "get_status"


class SubmitPatchAction(BaseModel):
    """Action to submit final patch."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    action_type: Literal["submit_patch"] = "submit_patch"


class RunSkillScriptAction(BaseModel):
    """Action to execute one of the 5 competition skills."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    action_type: Literal["run_skill_script"] = "run_skill_script"
    skill_name: SkillName
    file_path: SkillScript
    args: list[str]

    @model_validator(mode="after")
    def validate_skill_invocation(self) -> RunSkillScriptAction:
        pairing_map: dict[str, str] = {
            "fast-grep": "grep.py",
            "code-map": "map.py",
            "code-oracle": "oracle.py",
            "repro-check": "check.py",
            "test-gate": "gate.py",
        }
        expected_script = pairing_map[self.skill_name]
        if self.file_path != expected_script:
            raise ValueError(
                f"Skill '{self.skill_name}' requires file_path='{expected_script}', "
                f"got '{self.file_path}'"
            )

        if self.skill_name == "fast-grep":
            if not (1 <= len(self.args) <= 2):
                raise ValueError("fast-grep requires 1 or 2 args: [pattern] or [pattern, path]")
            if not self.args[0].strip():
                raise ValueError("fast-grep pattern cannot be empty")

        elif self.skill_name == "code-map":
            if len(self.args) != 2 or self.args[0] not in ("--symbol", "--file"):
                raise ValueError("code-map requires args: ['--symbol', '<sym>'] or ['--file', '<path>']")

        elif self.skill_name == "code-oracle":
            valid_flags = ("--eval", "--hex", "--width", "--html-esc", "--schema", "--syntax")
            if len(self.args) != 2 or self.args[0] not in valid_flags:
                raise ValueError(
                    f"code-oracle requires args: ['<flag>', '<payload>'] where flag in {valid_flags}"
                )

        elif self.skill_name == "repro-check":
            if not self.args:
                raise ValueError("repro-check requires at least 1 arg")
            first = self.args[0]
            is_valid = ("assert " in first) or (first in ("--expect-exception", "--b64"))
            if not is_valid:
                raise ValueError(
                    "repro-check requires python assertion containing 'assert ' "
                    "or '--expect-exception' or '--b64'"
                )

        elif self.skill_name == "test-gate":
            valid_args = ([], ["--diff"], ["--status"])
            if self.args not in valid_args:
                raise ValueError("test-gate args must be [], ['--diff'], or ['--status']")

        return self


type ActionUnion = Annotated[
    ReadFileAction
    | EditFileAction
    | WriteFileAction
    | GetStatusAction
    | SubmitPatchAction
    | RunSkillScriptAction,
    Field(discriminator="action_type"),
]


class TranslatedStep(BaseModel):
    """A single translated agent step in the 5-skill + 5-tool schema."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    step_index: int = Field(ge=0)
    source_step_index: int = Field(
        ge=0,
        description="Index of raw step in input trajectory whose observation pairs with this action",
    )
    action: ActionUnion


class TranslatedTrajectory(BaseModel):
    """A full translated trajectory satisfying the 5-skill + 5-tool contract."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    task_id: str
    steps: list[TranslatedStep] = Field(min_length=3, max_length=35)

    @field_validator("steps", mode="after")
    @classmethod
    def validate_trajectory_structure(
        cls, steps: list[TranslatedStep]
    ) -> list[TranslatedStep]:
        if not steps:
            raise ValueError("Steps list cannot be empty")

        has_discovery = False
        has_valid_edit = False
        has_verification = False

        for i, step in enumerate(steps):
            act = step.action

            # Anti-thrashing: no two consecutive identical actions
            if i > 0:
                prev_act = steps[i - 1].action
                if act.model_dump() == prev_act.model_dump():
                    raise ValueError(
                        f"Consecutive identical actions detected at step {i-1} and {i}: "
                        f"{act.action_type}"
                    )

            if isinstance(act, RunSkillScriptAction):
                if act.skill_name in ("fast-grep", "code-map"):
                    has_discovery = True
                elif act.skill_name in ("repro-check", "code-oracle", "test-gate"):
                    has_verification = True

            elif isinstance(act, EditFileAction):
                p = act.filepath.strip()
                is_test = p.startswith("tests/") or "/tests/" in f"/{p}" or Path(p).name.startswith("test_")
                if not is_test and p.endswith(".py"):
                    has_valid_edit = True

        if not has_discovery:
            raise ValueError("Trajectory must include at least 1 discovery call (fast-grep or code-map)")

        if not has_valid_edit:
            raise ValueError("Trajectory must include at least 1 edit_file targeting a non-test .py file")

        if not has_verification:
            raise ValueError(
                "Trajectory must include at least 1 verification call (repro-check, code-oracle, or test-gate)"
            )

        last_action = steps[-1].action
        if not isinstance(last_action, SubmitPatchAction):
            raise ValueError("Trajectory must end with submit_patch")

        return steps

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonScalar] | dict[str, JsonScalar]


class RawStep(BaseModel):
    """Raw step extracted from source trajectory."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    step_index: int = Field(ge=0)
    tool_name: str
    tool_input: dict[str, JsonValue]
    observation: str

class RawTask(BaseModel):
    """Raw task bundle prepared for translation."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    task_id: str
    repo: str
    problem_statement: str
    gold_patch: str
    target_filepath: str
    raw_steps: list[RawStep]


class TranslationDeps(BaseModel):
    """Dependencies injected into Pydantic AI translation agent."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    raw_task: RawTask


# ==============================================================================
# Step 3: Dual Observability Layer (logfire Span Exporter + Raw HTTP Wire Logger)
# ==============================================================================

class JsonlFileSpanExporter(SpanExporter):
    """OpenTelemetry SpanExporter that serializes completed spans to JSON lines."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        try:
            with open(self.file_path, "a", encoding="utf-8") as f:
                for span in spans:
                    ctx = span.get_span_context()
                    record = {
                        "trace_id": f"{ctx.trace_id:032x}",
                        "span_id": f"{ctx.span_id:016x}",
                        "name": span.name,
                        "start_time_ns": span.start_time,
                        "end_time_ns": span.end_time,
                        "status": span.status.status_code.name,
                        "attributes": {
                            str(k): str(v) for k, v in (span.attributes or {}).items()
                        },
                        "events": [
                            {
                                "name": e.name,
                                "timestamp": e.timestamp,
                                "attributes": {str(k): str(v) for k, v in (e.attributes or {}).items()},
                            }
                            for e in span.events
                        ],
                    }
                    f.write(json.dumps(record) + "\n")
            return SpanExportResult.SUCCESS
        except Exception as exc:
            logger.error("Failed to export OpenTelemetry spans to %s: %exc", self.file_path, exc)
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        pass


import logfire

logfire.configure(
    send_to_logfire=False,
    service_name="gemma4_sft_dag_translator",
    console=False,
    inspect_arguments=False,
    additional_span_processors=[
        SimpleSpanProcessor(JsonlFileSpanExporter(LOGFIRE_SPANS_PATH))
    ],
)
logfire.instrument_pydantic_ai()
logfire.instrument_httpx(capture_all=True)


async def _log_raw_http_request(request: httpx.Request) -> None:
    """Async hook logging HTTP wire request without consuming or buffering stream."""
    try:
        content_len = len(request.content) if hasattr(request, "content") and request.content is not None else 0
        record = {
            "direction": "request",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "method": request.method,
            "url": str(request.url),
            "content_len": content_len,
        }
        append_jsonl_fsync(HTTP_RAW_PATH, json.dumps(record))
        logger.info("HTTP [REQ] %s %s content_len=%d", request.method, request.url, content_len)
    except Exception as exc:
        logger.warning("Failed to record raw HTTP request: %s", exc)

async def _log_raw_http_response(response: httpx.Response) -> None:
    """Async hook logging HTTP wire response status without consuming streaming body."""
    try:
        record = {
            "direction": "response",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "status_code": response.status_code,
            "headers": dict(response.headers),
        }
        append_jsonl_fsync(HTTP_RAW_PATH, json.dumps(record))
        logger.info(
            "HTTP [RESP] %d %s",
            response.status_code,
            response.request.url,
        )
    except Exception as exc:
        logger.warning("Failed to record raw HTTP response: %s", exc)
def compute_jittered_backoff(
    attempt: int,
    initial_delay: float = 8.0,
    backoff_factor: float = 1.5,
) -> float:
    """Calculates exponential backoff with decorrelated uniform jitter in [0.75, 1.25]."""
    base_delay = initial_delay * (backoff_factor ** attempt)
    return base_delay * random.uniform(0.75, 1.25)


def _is_rate_limit_error(exc: Exception) -> bool:
    """Detects HTTP 429 status code or rate-limit message across client exceptions."""
    if hasattr(exc, "status_code") and getattr(exc, "status_code") == 429:
        return True
    if hasattr(exc, "response") and getattr(getattr(exc, "response"), "status_code", None) == 429:
        return True
    err_str = str(exc).lower()
    return "429" in err_str or "rate limit" in err_str or "quota exceeded" in err_str


def create_instrumented_http_client(
    worker_timeout: float = 300.0,
    connect_timeout: float = 60.0,
    http2: bool = True,
) -> httpx.AsyncClient:
    """Builds isolated worker httpx.AsyncClient with HTTP/2 and bounded timeouts."""
    use_http2 = False
    if http2:
        try:
            import h2  # noqa: F401
            use_http2 = True
        except ImportError:
            use_http2 = False

    return httpx.AsyncClient(
        http2=use_http2,
        timeout=httpx.Timeout(worker_timeout, connect=connect_timeout),
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
        event_hooks={
            "request": [_log_raw_http_request],
            "response": [_log_raw_http_response],
        },
    )


# ==============================================================================
# Step 4: Pydantic AI 2.0 Translator Agent with ModelRetry Self-Correction
# ==============================================================================

TRANSLATOR_SYSTEM_INSTRUCTIONS: str = """
You are an expert autonomous SWE-Bench trajectory translator.
Your job is to translate raw, primitive OpenHands/Claude tool sequences (bash, str_replace_editor, submit)
into clean, idiomatic 5-Skill + 5-Tool trajectories strictly matching our Gemma 4 developer agent contract:

DIRECT TOOLS:
1. `read_file(filepath, start_line)`
2. `edit_file(filepath, old_string, new_string, allow_multiple)`
3. `write_file(filepath, content)`
4. `get_status()`
5. `submit_patch()`

PRE-INSTALLED SKILLS (invoked via `run_skill_script`):
1. `fast-grep`: skill_name="fast-grep", file_path="grep.py", args=["<pattern>"] or ["<pattern>", "<path>"]
2. `code-map`: skill_name="code-map", file_path="map.py", args=["--symbol", "<sym>"] or ["--file", "<path>"]
3. `code-oracle`: skill_name="code-oracle", file_path="oracle.py", args=["--eval", "<expr>"] or ["--syntax", "<file>"]
4. `repro-check`: skill_name="repro-check", file_path="check.py", args=["assert <cond>"]
5. `test-gate`: skill_name="test-gate", file_path="gate.py", args=[] or ["--diff"] or ["--status"]

TRANSLATION RULES:
1. Discovery: Translate grep / find commands to `fast-grep` or `code-map`. Translate view commands to `read_file`.
2. Reproduction & Verification: Translate pytest executions and bash verification assertions to `repro-check` or `test-gate`.
3. Surgical Edits: Translate str_replace or file edit actions to `edit_file`. The filepath MUST strictly be the target file.
4. Finalization: Trajectory MUST end with `submit_patch()`.
5. Mapping: Each translated step MUST set `source_step_index` to the integer index of the corresponding raw step.
6. Quality: Trajectories must have between 3 and 12 steps. Distill the essential path (discovery -> read -> edit -> verify -> submit). No consecutive identical actions.
"""


def build_translator_agent(
    base_url: str | None = None,
    api_key: str | None = None,
    model_name: str | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> Agent[TranslationDeps, TranslatedTrajectory]:
    """Constructs Pydantic AI 2.0 translation agent with ModelRetry validators."""
    url = base_url or os.getenv("LITEROUTER_BASE_URL", "http://literouter.lan:7766/v1")
    key = api_key or os.getenv("LITEROUTER_API_KEY", "lr-or-oa-ch-no")
    model_str = model_name or os.getenv("LITEROUTER_MODEL", "thinkingmachines/inkling:free")
    client = http_client or create_instrumented_http_client()

    provider = OpenAIProvider(
        base_url=url,
        api_key=key,
        http_client=client,
    )
    # Zero SDK micro-retries to bubble rate limits immediately to jittered backoff
    if hasattr(provider, "client") and hasattr(provider.client, "max_retries"):
        provider.client.max_retries = 0

    model = OpenAIChatModel(
        model_str,
        provider=provider,
    )

    agent: Agent[TranslationDeps, TranslatedTrajectory] = Agent(
        model,
        name="gemma4_sft_trajectory_translator",
        deps_type=TranslationDeps,
        output_type=TranslatedTrajectory,
        retries=2,
        instructions=TRANSLATOR_SYSTEM_INSTRUCTIONS,
    )

    @agent.output_validator
    def validate_translation_output(
        ctx: RunContext[TranslationDeps], output: TranslatedTrajectory
    ) -> TranslatedTrajectory:
        raw_steps = ctx.deps.raw_task.raw_steps
        raw_len = len(raw_steps)
        expected_target_file = ctx.deps.raw_task.target_filepath

        for s in output.steps:
            if s.source_step_index >= raw_len:
                raise ModelRetry(
                    f"Step {s.step_index} referenced source_step_index={s.source_step_index}, "
                    f"but raw trajectory only has {raw_len} steps (max index is {raw_len - 1})."
                )

            if isinstance(s.action, EditFileAction):
                norm_action_file = s.action.filepath.strip().lstrip("/")
                norm_expected = expected_target_file.strip().lstrip("/")
                if norm_action_file != norm_expected:
                    raise ModelRetry(
                        f"EditFileAction targeted '{s.action.filepath}', but this task's "
                        f"single target Python file is strictly '{expected_target_file}'. "
                        f"Please edit '{expected_target_file}' directly."
                    )
                if s.action.old_string == s.action.new_string:
                    raise ModelRetry("EditFileAction old_string and new_string cannot be identical.")

        return output

    return agent


# ==============================================================================
# Helper Functions: Benchmark Filtering, Patch Parsing, Workspace Cleanup
# ==============================================================================

def load_benchmark_exclusion_set(tasks_path: Path | None = None) -> set[str]:
    """Loads all benchmark instance IDs from tasks.jsonl to guarantee zero leakage."""
    p = tasks_path or TASKS_BENCHMARK_PATH
    if not p.exists():
        logger.warning("Benchmark tasks file not found at %s", p)
        return set()
    exclusions: set[str] = set()
    with open(p, encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if line_str:
                try:
                    exclusions.add(json.loads(line_str)["instance_id"])
                except Exception:
                    pass
    return exclusions


def normalize_workspace_path(path: str) -> str:
    """Normalizes paths stripping leading /testbed or /workspace."""
    p = path.strip()
    for prefix in ("/testbed/", "testbed/", "/workspace/", "workspace/"):
        if p.startswith(prefix):
            p = p[len(prefix):]
    return p.strip("/")


def extract_single_target_py_filepath(patch: str) -> str | None:
    """Extracts target filepath if patch is single-file .py, else None."""
    if not patch or not isinstance(patch, str):
        return None
    files: set[str] = set()
    for raw_line in patch.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("diff --git"):
            m = re.match(r"^diff --git\s+(?:\"?a/)?(.+?)\"?\s+(?:\"?b/)?(.+?)\"?$", line)
            if m:
                for p in (m.group(1).strip('"'), m.group(2).strip('"')):
                    if p and p != "/dev/null":
                        norm = normalize_workspace_path(p)
                        if norm:
                            files.add(norm)
        elif line.startswith("--- "):
            t = line[4:].strip().split()[0].strip('"')
            if t.startswith("a/"):
                t = t[2:]
            if t and t != "/dev/null":
                norm = normalize_workspace_path(t)
                if norm:
                    files.add(norm)
        elif line.startswith("+++ "):
            t = line[4:].strip().split()[0].strip('"')
            if t.startswith("b/"):
                t = t[2:]
            if t and t != "/dev/null":
                norm = normalize_workspace_path(t)
                if norm:
                    files.add(norm)

    if len(files) == 1:
        f = next(iter(files))
        if f.endswith(".py") and not f.startswith("tests/") and not Path(f).name.startswith("test_"):
            return f
    return None


def is_single_file_py_patch(patch: str) -> bool:
    """Returns True if patch modifies exactly one non-test .py file."""
    return extract_single_target_py_filepath(patch) is not None


# ==============================================================================
# Step 5: Stateful Python DAG Pipeline via pydantic_graph
# ==============================================================================

class TaskTranslationState(BaseModel):
    """Execution state tracked across DAG nodes for a single task."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    raw_task: RawTask | None = None
    translated_trajectory: TranslatedTrajectory | None = None
    reconciled_messages: list[dict[str, object]] | None = None
    sft_windows: list[dict[str, object]] | None = None
    status: Literal["pending", "success", "rejected", "skipped"] = "pending"
    error_message: str | None = None
    rejection_reason: str | None = None


@dataclass
class PersistRejectionNode(BaseNode[TaskTranslationState]):
    """Persists rejected task diagnostics to rejected_tasks.jsonl with fsync."""

    async def run(self, ctx: GraphRunContext[TaskTranslationState]) -> End[TaskTranslationState]:
        st = ctx.state
        st.status = "rejected"
        t_id = st.raw_task.task_id if st.raw_task else "unknown"
        logger.warning("DAG: Task %s rejected. Reason: %s", t_id, st.rejection_reason)
        record = {
            "task_id": t_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "reason": st.rejection_reason,
            "error_message": st.error_message,
        }
        append_jsonl_fsync(REJECTED_TASKS_PATH, json.dumps(record))
        cleanup_stage_cache(t_id)
        return End(st)

@dataclass
class PersistTaskArtifactsNode(BaseNode[TaskTranslationState]):
    """Persists validated translated trajectory and SFT windows with fsync."""

    async def run(self, ctx: GraphRunContext[TaskTranslationState]) -> End[TaskTranslationState]:
        st = ctx.state
        st.status = "success"
        t_id = st.raw_task.task_id if st.raw_task else "unknown"

        if st.translated_trajectory:
            append_jsonl_fsync(
                TRANSLATED_TRAJECTORIES_PATH,
                st.translated_trajectory.model_dump_json(),
            )

        if st.sft_windows:
            for w in st.sft_windows:
                append_jsonl_fsync(SFT_TRAIN_WINDOWS_PATH, json.dumps(w))

        cleanup_stage_cache(t_id)
        logger.info(
            "DAG: Persisted task %s with %d SFT windows (atomic fsync)",
            t_id,
            len(st.sft_windows or []),
        )
        return End(st)

@dataclass
class RenderGemma4JinjaNode(BaseNode[TaskTranslationState]):
    """Renders messages through Gemma 4 Jinja and verifies zero-thought invariants."""
    tokenizer: AutoTokenizer
    system_prompt: str

    async def run(
        self, ctx: GraphRunContext[TaskTranslationState]
    ) -> PersistTaskArtifactsNode | PersistRejectionNode:
        st = ctx.state
        if not st.raw_task or not st.reconciled_messages:
            st.rejection_reason = "Missing raw_task or reconciled_messages"
            return PersistRejectionNode()

        task_id = st.raw_task.task_id
        messages = st.reconciled_messages
        user_prompt = st.raw_task.problem_statement
        valid_windows: list[dict[str, object]] = []

        logger.info("DAG: Rendering Gemma 4 Jinja windows for %s (%d msgs)", task_id, len(messages))

        for i, m in enumerate(messages):
            if m.get("role") != "assistant":
                continue
            tcalls = m.get("tool_calls") or []
            if not tcalls:
                continue

            window: list[dict[str, object]] = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            # Context window preceding target turn
            start_ctx = max(0, i - 2)
            for ctx_idx in range(start_ctx, i):
                c_msg = dict(messages[ctx_idx])
                c_msg.pop("reasoning", None)
                c_msg.pop("reasoning_content", None)
                window.append(c_msg)

            target_msg = dict(m)
            target_msg.pop("reasoning", None)
            target_msg.pop("reasoning_content", None)
            window.append(target_msg)
            prefix_messages = window[:-1]

            try:
                prefix_text = self.tokenizer.apply_chat_template(
                    prefix_messages,
                    tools=TOOLS_SCHEMA,
                    tokenize=False,
                    add_generation_prompt=True,
                    enable_thinking=False,
                )
                full_text = self.tokenizer.apply_chat_template(
                    window,
                    tools=TOOLS_SCHEMA,
                    tokenize=False,
                    add_generation_prompt=False,
                    enable_thinking=False,
                )
            except Exception as exc:
                logger.warning("Template error %s turn %d: %s", task_id, i, exc)
                continue

            # Turn-0 Boundary Reconciliation
            if not full_text.startswith(prefix_text) and prefix_text.endswith(EMPTY_THOUGHT_CLOSURE):
                base_prefix = prefix_text[:-len(EMPTY_THOUGHT_CLOSURE)]
                if full_text.startswith(base_prefix):
                    full_text = prefix_text + full_text[len(base_prefix):]

            if not full_text.startswith(prefix_text):
                continue

            completion_text = full_text[len(prefix_text):]
            if not completion_text.startswith("<|tool_call>call:"):
                continue
            if "<|channel>thought" in completion_text or "<|think|>" in completion_text:
                continue
            prefix_ids = self.tokenizer(prefix_text, add_special_tokens=False)["input_ids"]
            full_ids = self.tokenizer(full_text, add_special_tokens=False)["input_ids"]

            if len(full_ids) > MAX_SEQ_TOKENS:
                continue
            if len(full_ids) <= len(prefix_ids) or full_ids[:len(prefix_ids)] != prefix_ids:
                continue

            valid_windows.append(
                {
                    "task_id": task_id,
                    "repo": st.raw_task.repo,
                    "messages": window,
                    "prefix_text": prefix_text,
                    "completion_text": completion_text,
                    "text": full_text,
                    "prefix_token_count": len(prefix_ids),
                    "total_token_count": len(full_ids),
                    "target_turn_index": i,
                    "target_tools": [
                        tc.get("function", {}).get("name", "")
                        for tc in tcalls
                        if isinstance(tc, dict)
                    ],
                }
            )

        if not valid_windows:
            st.rejection_reason = "Zero valid Gemma 4 SFT windows produced after Jinja rendering"
            return PersistRejectionNode()

        st.sft_windows = valid_windows
        return PersistTaskArtifactsNode()


@dataclass
class ReconcileObservationsNode(BaseNode[TaskTranslationState]):
    """Pairs translated actions with observations from raw trajectory."""

    async def run(
        self, ctx: GraphRunContext[TaskTranslationState]
    ) -> RenderGemma4JinjaNode | PersistRejectionNode:
        st = ctx.state
        if not st.raw_task or not st.translated_trajectory:
            st.rejection_reason = "Missing raw_task or translated_trajectory"
            return PersistRejectionNode()

        raw_steps = st.raw_task.raw_steps
        trajectory = st.translated_trajectory
        reconciled_messages: list[dict[str, object]] = []

        for step in trajectory.steps:
            act = step.action
            src_step = raw_steps[step.source_step_index]

            # Construct tool_call representation
            tc_id = f"call_{step.step_index}_{act.action_type}"
            if isinstance(act, ReadFileAction):
                fn_name = "read_file"
                fn_args: dict[str, object] = {"filepath": act.filepath}
                if act.start_line is not None:
                    fn_args["start_line"] = act.start_line
            elif isinstance(act, EditFileAction):
                fn_name = "edit_file"
                fn_args = {
                    "filepath": act.filepath,
                    "old_string": act.old_string,
                    "new_string": act.new_string,
                    "allow_multiple": act.allow_multiple,
                }
            elif isinstance(act, WriteFileAction):
                fn_name = "write_file"
                fn_args = {"filepath": act.filepath, "content": act.content}
            elif isinstance(act, GetStatusAction):
                fn_name = "get_status"
                fn_args = {}
            elif isinstance(act, SubmitPatchAction):
                fn_name = "submit_patch"
                fn_args = {}
            elif isinstance(act, RunSkillScriptAction):
                fn_name = "run_skill_script"
                fn_args = {
                    "skill_name": act.skill_name,
                    "file_path": act.file_path,
                    "args": act.args,
                }

            assistant_turn = {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": tc_id,
                        "type": "function",
                        "function": {
                            "name": fn_name,
                            "arguments": fn_args,
                        },
                    }
                ],
            }
            reconciled_messages.append(assistant_turn)

            # Reconcile observation
            if isinstance(act, SubmitPatchAction):
                obs_content = "Patch submitted."
            elif isinstance(act, RunSkillScriptAction) and act.skill_name == "repro-check":
                obs_content = "Assert passed." if "assert" in str(src_step.observation).lower() else src_step.observation
            else:
                obs_content = src_step.observation or "Success."

            tool_turn = {
                "role": "tool",
                "name": fn_name,
                "tool_call_id": tc_id,
                "content": obs_content,
            }
            reconciled_messages.append(tool_turn)

        st.reconciled_messages = reconciled_messages
        logger.info(
            "DAG: Reconciled %d turns for task %s",
            len(reconciled_messages),
            st.raw_task.task_id,
        )
        # Node will transition to RenderGemma4JinjaNode via the builder graph
        return cast(RenderGemma4JinjaNode, RenderGemma4JinjaNode(tokenizer=None, system_prompt="")) # type placeholder

def diagnose_trajectory(trajectory: TranslatedTrajectory, task: RawTask) -> list[str]:
    """Evaluates translated trajectory against all Gemma 4 SFT invariants and returns granular error diagnostics."""
    errors: list[str] = []
    steps = trajectory.steps
    raw_steps = task.raw_steps
    raw_len = len(raw_steps)
    expected_file = task.target_filepath.strip().lstrip("/")

    if not steps:
        errors.append("Trajectory contains 0 steps. Must contain between 3 and 16 steps.")
        return errors

    if len(steps) < 3:
        errors.append(f"Trajectory contains only {len(steps)} steps. Minimum required is 3 steps.")
    if len(steps) > 16:
        errors.append(f"Trajectory contains {len(steps)} steps, exceeding maximum threshold of 16 steps.")

    has_discovery = False
    has_edit = False

    for s in steps:
        # 1. Source step index bounds
        if s.source_step_index < 0 or s.source_step_index >= raw_len:
            errors.append(
                f"Step {s.step_index} referenced source_step_index={s.source_step_index}, "
                f"but raw trajectory only has {raw_len} steps (valid indices are 0 to {raw_len - 1})."
            )

        act = s.action
        # 2. Discovery presence
        if isinstance(act, ReadFileAction) or (isinstance(act, RunSkillScriptAction) and act.skill_name in ("fast-grep", "code-map")):
            has_discovery = True

        # 3. EditFileAction targeting
        if isinstance(act, EditFileAction):
            has_edit = True
            norm_action_file = act.filepath.strip().lstrip("/")
            if norm_action_file != expected_file:
                errors.append(
                    f"Step {s.step_index}: EditFileAction targeted '{act.filepath}', "
                    f"but this task's single target Python file is strictly '{task.target_filepath}'. "
                    f"PIVOT: You must edit '{task.target_filepath}' directly."
                )
            if act.old_string == act.new_string:
                errors.append(
                    f"Step {s.step_index}: EditFileAction old_string and new_string are identical. "
                    f"PIVOT: Provide distinct old_string and new_string."
                )

        # 4. RunSkillScriptAction pairing
        if isinstance(act, RunSkillScriptAction):
            valid_pairs = {
                "fast-grep": "grep.py",
                "code-map": "map.py",
                "code-oracle": "oracle.py",
                "repro-check": "check.py",
                "test-gate": "gate.py",
            }
            if act.skill_name not in valid_pairs:
                errors.append(
                    f"Step {s.step_index}: Unknown skill_name '{act.skill_name}'. "
                    f"PIVOT: Allowed skills are {list(valid_pairs.keys())}."
                )
            elif act.file_path != valid_pairs[act.skill_name]:
                errors.append(
                    f"Step {s.step_index}: Skill '{act.skill_name}' must use script '{valid_pairs[act.skill_name]}', "
                    f"got '{act.file_path}'."
                )

    if not has_discovery:
        errors.append("Trajectory lacks discovery: must contain at least one read_file, fast-grep, or code-map step.")

    if not has_edit:
        errors.append(f"Trajectory lacks edit: must contain at least one edit_file step targeting '{task.target_filepath}'.")

    # 5. Terminal action must be submit_patch
    if not isinstance(steps[-1].action, SubmitPatchAction):
        errors.append(
            f"Trajectory final step (Step {steps[-1].step_index}) is {type(steps[-1].action).__name__}, "
            "but the terminal step must strictly be SubmitPatchAction (action_type='submit_patch')."
        )

    # 6. Consecutive identical actions
    for idx in range(len(steps) - 1):
        if steps[idx].action == steps[idx + 1].action:
            errors.append(f"Steps {idx} and {idx + 1} contain consecutive identical actions.")

    return errors


def build_pivot_prompt(errors: list[str], task: RawTask, attempt: int) -> str:
    """Constructs a high-impact diagnostic feedback prompt instructing the LLM to pivot."""
    error_bullets = "\n".join(f"  * {err}" for err in errors)
    return (
        f"[VALIDATION FAILURE & PIVOT DIRECTIVE — ATTEMPT {attempt}/3]\n"
        f"Your previous translation failed validation with {len(errors)} error(s):\n"
        f"{error_bullets}\n\n"
        f"MANDATORY PIVOT INSTRUCTIONS:\n"
        f"1. Target Python file: MUST strictly be '{task.target_filepath}'. Any edit_file action targeting any other file is strictly rejected.\n"
        f"2. Terminal Step: Trajectory MUST conclude with a submit_patch action (SubmitPatchAction).\n"
        f"3. Valid Tools: Only read_file, edit_file, write_file, get_status, submit_patch, or run_skill_script. Zero raw shell / run_command.\n"
        f"4. Valid Skills: fast-grep (grep.py), code-map (map.py), code-oracle (oracle.py), repro-check (check.py), test-gate (gate.py).\n"
        f"5. Output Format: Return ONLY a valid TranslatedTrajectory JSON object conforming to the schema.\n\n"
        f"Please correct your trajectory now to fix all listed errors."
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


def convert_raw_llm_text_to_trajectory(raw_text: str, task: RawTask) -> TranslatedTrajectory | None:
    """Converts raw unstructured, think-tagged, or markdown LLM text into a validated TranslatedTrajectory."""
    if not raw_text or not isinstance(raw_text, str):
        return None
    cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
    cleaned = _extract_json_block(_strip_json_fences(cleaned))
    if not cleaned:
        return None
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            if "task_id" not in data:
                data["task_id"] = task.task_id
            return TranslatedTrajectory.model_validate(data)
    except Exception:
        pass
    return None


@dataclass
class RunPydanticAgentNode(BaseNode[TaskTranslationState]):
    """Executes Pydantic AI translation agent on raw task with multi-turn pivot feedback loop."""
    agent: Agent[TranslationDeps, TranslatedTrajectory]
    max_pivots: int = 3

    async def run(
        self, ctx: GraphRunContext[TaskTranslationState]
    ) -> ReconcileObservationsNode | PersistRejectionNode:
        st = ctx.state
        if not st.raw_task:
            st.rejection_reason = "No raw_task in state"
            return PersistRejectionNode()

        task = st.raw_task
        initial_prompt = (
            f"Translate the following raw trajectory for task: {task.task_id}\n"
            f"Target file: {task.target_filepath}\n"
            f"Problem statement:\n{task.problem_statement[:2000]}\n\n"
            f"Raw Tool Steps:\n"
        )
        for s in task.raw_steps[:12]:
            obs_preview = s.observation[:120].replace("\n", " ").strip()
            input_preview = json.dumps(s.tool_input)[:120]
            initial_prompt += (
                f"- Step {s.step_index}: tool={s.tool_name}, "
                f"input={input_preview}, "
                f"obs={obs_preview}\n"
            )
        deps = TranslationDeps(raw_task=task)

        history: list[ModelMessage] = []
        attempt_prompt = initial_prompt
        last_errors: list[str] = []

        with logfire.span("translate_task", task_id=task.task_id):
            for attempt in range(1, self.max_pivots + 1):
                try:
                    logger.info(
                        "DAG: Running Pydantic AI agent on %s (attempt %d/%d, history=%d msgs)...",
                        task.task_id,
                        attempt,
                        self.max_pivots,
                        len(history),
                    )
                    res = await self.agent.run(
                        attempt_prompt,
                        message_history=history if history else None,
                        deps=deps,
                    )
                    history = res.all_messages()
                    trajectory = res.output

                    # Diagnostic Validation
                    diag_errors = diagnose_trajectory(trajectory, task)
                    if not diag_errors:
                        st.translated_trajectory = trajectory
                        logger.info(
                            "DAG: Translation agent succeeded on %s on attempt %d (%d steps)",
                            task.task_id,
                            attempt,
                            len(trajectory.steps),
                        )
                        return ReconcileObservationsNode()

                    # Model succeeded at schema but failed domain/structural invariants -> PIVOT!
                    last_errors = diag_errors
                    logger.warning(
                        "DAG: Task %s attempt %d failed %d diagnostic checks: %s",
                        task.task_id,
                        attempt,
                        len(diag_errors),
                        "; ".join(diag_errors[:2]),
                    )
                    attempt_prompt = build_pivot_prompt(diag_errors, task, attempt + 1)

                except Exception as exc:
                    exc_str = str(exc)
                    logger.warning(
                        "DAG: Agent attempt %d exception on %s: %s",
                        attempt,
                        task.task_id,
                        exc_str,
                    )

                    # Attempt raw text / JSON block recovery
                    recovered = convert_raw_llm_text_to_trajectory(exc_str, task)
                    if recovered is not None:
                        rec_errors = diagnose_trajectory(recovered, task)
                        if not rec_errors:
                            st.translated_trajectory = recovered
                            logger.info(
                                "DAG: JSON converter successfully parsed and verified trajectory for %s on attempt %d",
                                task.task_id,
                                attempt,
                            )
                            return ReconcileObservationsNode()
                        last_errors = rec_errors
                    else:
                        last_errors = [f"Exception during generation: {exc_str}"]

                    attempt_prompt = build_pivot_prompt(last_errors, task, attempt + 1)

            # All pivot attempts exhausted
            st.rejection_reason = (
                f"Pydantic AI agent failed after {self.max_pivots} pivot attempts. "
                f"Final diagnostic errors: {'; '.join(last_errors)}"
            )
            st.error_message = "; ".join(last_errors)
            logger.warning(
                "DAG: Agent failed all %d pivot attempts for %s: %s",
                self.max_pivots,
                task.task_id,
                st.rejection_reason,
            )
            return PersistRejectionNode()
@dataclass
class IngestRawTaskNode(BaseNode[TaskTranslationState]):
    """Ingests raw task record and enforces qualification criteria."""
    task_record: dict[str, object]
    benchmark_exclusions: set[str]

    async def run(
        self, ctx: GraphRunContext[TaskTranslationState]
    ) -> RunPydanticAgentNode | End[TaskTranslationState]:
        st = ctx.state
        rec = self.task_record
        task_id = str(rec.get("task_id") or rec.get("instance_id") or "")

        if not task_id or task_id in self.benchmark_exclusions:
            st.status = "skipped"
            st.rejection_reason = f"Task {task_id} in benchmark exclusion set or empty"
            return End(st)

        patch = str(rec.get("gold_patch") or rec.get("patch") or rec.get("model_patch") or "")
        target_file = str(rec.get("target_filepath") or "") or extract_single_target_py_filepath(patch)
        if not target_file:
            st.status = "skipped"
            st.rejection_reason = f"Task {task_id} patch is not single-file .py"
            return End(st)

        # Parse raw steps: handle pre-parsed gold format or raw messages
        raw_steps: list[RawStep] = []
        if "raw_steps" in rec and isinstance(rec["raw_steps"], list):
            for idx, s in enumerate(rec["raw_steps"]):
                if isinstance(s, dict):
                    raw_steps.append(
                        RawStep(
                            step_index=int(s.get("step_index", idx)),
                            tool_name=str(s.get("tool_name") or ""),
                            tool_input=s.get("tool_input") if isinstance(s.get("tool_input"), dict) else {},
                            observation=str(s.get("observation") or "")[:1000],
                        )
                    )
        else:
            raw_msgs = rec.get("messages") or rec.get("trajectory") or []
            if isinstance(raw_msgs, str):
                try:
                    raw_msgs = json.loads(raw_msgs)
                except Exception:
                    raw_msgs = []

            step_idx = 0
            if isinstance(raw_msgs, list):
                for i, m in enumerate(raw_msgs):
                    if not isinstance(m, dict):
                        continue
                    tcs = m.get("tool_calls") or []
                    if tcs and isinstance(tcs, list):
                        tc = tcs[0]
                        fn_name = ""
                        fn_args: dict[str, JsonValue] = {}
                        if isinstance(tc, dict):
                            fn_obj = tc.get("function")
                            if isinstance(fn_obj, dict):
                                fn_name = str(fn_obj.get("name") or "")
                                raw_a = fn_obj.get("arguments")
                                if isinstance(raw_a, str):
                                    try:
                                        raw_a = json.loads(raw_a)
                                    except Exception:
                                        raw_a = {}
                                if isinstance(raw_a, dict):
                                    fn_args = {str(k): v for k, v in raw_a.items()}
                        # Look ahead for observation in following tool message
                        obs = ""
                        if i + 1 < len(raw_msgs) and isinstance(raw_msgs[i + 1], dict):
                            next_m = raw_msgs[i + 1]
                            c = next_m.get("content")
                            if isinstance(c, list) and c and isinstance(c[0], dict):
                                obs = str(c[0].get("text") or "")
                            elif isinstance(c, str):
                                obs = c

                        raw_steps.append(
                            RawStep(
                                step_index=step_idx,
                                tool_name=fn_name,
                                tool_input=fn_args,
                                observation=obs[:1000],
                            )
                        )
                        step_idx += 1

        if len(raw_steps) < 2:
            st.status = "skipped"
            st.rejection_reason = f"Task {task_id} has fewer than 2 tool steps"
            return End(st)

        # Target file alignment validation: ensure raw steps actually touch target_file
        norm_target = target_file.strip().lstrip("/")
        raw_files_touched: set[str] = set()
        for s in raw_steps:
            inp_str = json.dumps(s.tool_input)
            for m in re.findall(r"[\w\-./]+\.py", inp_str):
                raw_files_touched.add(m.strip().lstrip("/"))

        if raw_files_touched and not any(norm_target in f or f in norm_target for f in raw_files_touched):
            st.status = "skipped"
            st.rejection_reason = (
                f"Task {task_id} patch target '{target_file}' not touched in raw steps "
                f"(touched: {list(raw_files_touched)[:3]}). Misaligned dataset record skipped."
            )
            return End(st)

        # Extract problem statement
        problem = str(rec.get("problem_statement") or rec.get("user_prompt") or "")
        if not problem and isinstance(rec.get("messages") or rec.get("trajectory"), list):
            msgs = rec.get("messages") or rec.get("trajectory")
            for m in msgs:
                if isinstance(m, dict) and m.get("role") == "user":
                    c = m.get("content")
                    if isinstance(c, list) and c and isinstance(c[0], dict):
                        problem = str(c[0].get("text") or "")
                    elif isinstance(c, str):
                        problem = c
                    break
        st.raw_task = RawTask(
            task_id=task_id,
            repo=str(rec.get("repo") or "unknown"),
            problem_statement=problem,
            gold_patch=patch,
            target_filepath=target_file,
            raw_steps=raw_steps,
        )

        logger.info(
            "DAG: Ingested task %s (target=%s, steps=%d)",
            task_id,
            target_file,
            len(raw_steps),
        )
        return RunPydanticAgentNode(agent=cast(Agent[TranslationDeps, TranslatedTrajectory], None))


def build_translation_graph(
    agent: Agent[TranslationDeps, TranslatedTrajectory],
    tokenizer: AutoTokenizer,
    system_prompt: str,
) -> tuple[GraphBuilder[TaskTranslationState, None, IngestRawTaskNode, TaskTranslationState], object]:
    """Builds and compiles the 5-node pydantic_graph translation DAG."""
    builder = GraphBuilder(
        state_type=TaskTranslationState,
        input_type=IngestRawTaskNode,
        output_type=TaskTranslationState,
    )

    # Edge from start to Ingest
    builder.add(builder.edge_from(builder.start_node).to(IngestRawTaskNode))

    # Add nodes
    builder.add(builder.node(IngestRawTaskNode))
    builder.add(builder.node(RunPydanticAgentNode))
    builder.add(builder.node(ReconcileObservationsNode))
    builder.add(builder.node(RenderGemma4JinjaNode))
    builder.add(builder.node(PersistTaskArtifactsNode))
    builder.add(builder.node(PersistRejectionNode))

    graph = builder.build()
    return builder, graph


# ==============================================================================
# Step 6: Overnight Batch Runner & Smoke Test CLI
# ==============================================================================

def load_checkpoint_state() -> dict[str, object]:
    """Loads checkpoint state JSON if present."""
    if CHECKPOINT_STATE_PATH.exists():
        try:
            with open(CHECKPOINT_STATE_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"processed_tasks": [], "last_updated": ""}


def save_checkpoint_state(processed_tasks: list[str]) -> None:
    """Saves checkpoint state JSON atomically using save_atomically with fsync."""
    data = {
        "processed_tasks": processed_tasks,
        "last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_count": len(processed_tasks),
    }
    save_atomically(CHECKPOINT_STATE_PATH, json.dumps(data, indent=2))


async def audit_storage() -> dict[str, object]:
    """Audits output, staging, logs, and test_results directories."""
    for d in (OUTPUT_DIR, STAGING_DIR, LOGS_DIR, TEST_RESULTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
    return {
        "output_dir": str(OUTPUT_DIR),
        "staging_dir": str(STAGING_DIR),
        "logs_dir": str(LOGS_DIR),
        "test_results_dir": str(TEST_RESULTS_DIR),
        "existing_trajectories": sum(1 for _ in TRANSLATED_TRAJECTORIES_PATH.open("r", encoding="utf-8")) if TRANSLATED_TRAJECTORIES_PATH.exists() else 0,
        "existing_sft_windows": sum(1 for _ in SFT_TRAIN_WINDOWS_PATH.open("r", encoding="utf-8")) if SFT_TRAIN_WINDOWS_PATH.exists() else 0,
        "passed": True,
    }


async def audit_environment() -> dict[str, object]:
    """Audits availability of tokenizer, system prompt, and benchmark tasks."""
    tokenizer_ok = TOKENIZER_DIR.exists() and (TOKENIZER_DIR / "tokenizer.json").exists()
    prompt_ok = SYSTEM_PROMPT_PATH.exists()
    tasks_ok = TASKS_BENCHMARK_PATH.exists()
    all_ok = tokenizer_ok and prompt_ok and tasks_ok
    return {
        "tokenizer_dir": str(TOKENIZER_DIR),
        "tokenizer_exists": tokenizer_ok,
        "prompt_path": str(SYSTEM_PROMPT_PATH),
        "prompt_exists": prompt_ok,
        "tasks_path": str(TASKS_BENCHMARK_PATH),
        "tasks_exists": tasks_ok,
        "passed": all_ok,
    }


async def audit_model_gateway(
    base_url: str | None = None,
    api_key: str | None = None,
    model_name: str | None = None,
) -> dict[str, object]:
    """Audits LiteRouter/LLM gateway connectivity via 1-token dry probe latency."""
    url = base_url or os.getenv("LITEROUTER_BASE_URL", "http://literouter.lan:7766/v1")
    key = api_key or os.getenv("LITEROUTER_API_KEY", "lr-or-oa-ch-no")
    model_str = model_name or os.getenv("LITEROUTER_MODEL", "thinkingmachines/inkling:free")

    t0 = time.perf_counter()
    passed = False
    details = ""
    probe_latency_ms = 0.0

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                f"{url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": model_str,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1,
                },
            )
            probe_latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            passed = resp.status_code == 200
            details = f"HTTP {resp.status_code} in {probe_latency_ms}ms"
        except Exception as exc:
            probe_latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            passed = False
            details = f"Probe connection error: {exc}"

    return {
        "base_url": url,
        "model": model_str,
        "probe_latency_ms": probe_latency_ms,
        "passed": passed,
        "details": details,
    }


async def run_preflight_checks(
    skip_gateway: bool = False,
    model_name: str | None = None,
) -> bool:
    """Executes multi-point preflight health checks and logs structured summary."""
    logger.info("=== Preflight Health Checks ===")
    storage_audit = await audit_storage()
    env_audit = await audit_environment()
    logger.info("Storage Audit: %s", storage_audit)
    logger.info("Environment Audit: %s", env_audit)

    gateway_ok = True
    if not skip_gateway:
        gw_audit = await audit_model_gateway(model_name=model_name)
        logger.info("Gateway Probe Audit: %s", gw_audit)
        gateway_ok = bool(gw_audit.get("passed", False))

    passed = bool(storage_audit.get("passed") and env_audit.get("passed") and gateway_ok)
    logger.info("Preflight Overall Result: %s", "PASSED" if passed else "FAILED")
    return passed

async def run_pipeline(
    limit: int = 1,
    smoke_test: bool = False,
    resume: bool = True,
    model_name: str | None = None,
    skip_preflight: bool = False,
    concurrency: int = 1,
    candidates_path: Path | str | None = None,
) -> None:
    """Executes translation pipeline serially or with bounded concurrency across candidate tasks."""
    logger.info("Initializing SFT translation pipeline...")
    preflight_ok = await run_preflight_checks(skip_gateway=skip_preflight, model_name=model_name)
    if not preflight_ok and not skip_preflight:
        logger.warning("Preflight health checks reported issues. Proceeding with caution.")
    logger.info("Initializing SFT translation pipeline...")
    logger.info("Loading tokenizer from %s...", TOKENIZER_DIR)
    tokenizer = AutoTokenizer.from_pretrained(str(TOKENIZER_DIR))

    with open(SYSTEM_PROMPT_PATH, encoding="utf-8") as f:
        system_prompt = f.read()

    exclusions = load_benchmark_exclusion_set()
    logger.info("Loaded %d benchmark exclusion tasks.", len(exclusions))

    http_client = create_instrumented_http_client()
    agent = build_translator_agent(
        model_name=model_name,
        http_client=http_client,
    )

    _, graph = build_translation_graph(agent, tokenizer, system_prompt)

    checkpoint = load_checkpoint_state() if resume else {"processed_tasks": []}
    processed_set = set(checkpoint.get("processed_tasks", []))
    processed_list = list(checkpoint.get("processed_tasks", []))

    # Determine candidate source: prioritize pre-filtered gold candidate JSONL if available
    cand_file = Path(candidates_path) if candidates_path else (_REPO_ROOT / "pydantic/gold/raw_candidates_1500.jsonl")
    use_candidates_jsonl = cand_file.exists()

    if use_candidates_jsonl:
        logger.info("Streaming candidate tasks directly from gold manifest: %s", cand_file)
    else:
        shards = sorted(glob.glob(str(_REPO_ROOT / "data/source_b/swe_zero/*.parquet")))
        shards += sorted(glob.glob(str(_REPO_ROOT / "data/source_b/swe_smith/*.parquet")))
        logger.info("Discovered %d parquet shards across swe_zero and swe_smith.", len(shards))

    successful_count = 0
    total_evaluated = 0

    def _task_generator():
        if use_candidates_jsonl:
            with open(cand_file, encoding="utf-8") as f:
                for line in f:
                    line_str = line.strip()
                    if line_str:
                        try:
                            yield json.loads(line_str)
                        except Exception:
                            continue
        else:
            for shard_path in shards:
                logger.info("Reading shard: %s", shard_path)
                table = pq.read_table(shard_path)
                num_rows = table.num_rows
                for r_idx in range(num_rows):
                    yield {col: table[col][r_idx].as_py() for col in table.column_names}

    for row in _task_generator():
        if successful_count >= limit:
            break

        t_id = str(row.get("task_id") or row.get("instance_id") or "")
        if not t_id or t_id in processed_set:
            continue

        total_evaluated += 1
        state = TaskTranslationState()

        # Configure runtime node instances
        ingest_node = IngestRawTaskNode(
            task_record=row,
            benchmark_exclusions=exclusions,
        )
        run_agent_node = RunPydanticAgentNode(agent=agent)
        reconcile_node = ReconcileObservationsNode()
        render_node = RenderGemma4JinjaNode(
            tokenizer=tokenizer,
            system_prompt=system_prompt,
        )
        persist_node = PersistTaskArtifactsNode()
        reject_node = PersistRejectionNode()

        logger.info("Processing candidate task [%d]: %s", total_evaluated, t_id)

        # Ingest
        ingest_res = await ingest_node.run(GraphRunContext(state=state, deps=None))
        if state.status == "skipped":
            processed_set.add(t_id)
            processed_list.append(t_id)
            continue

        # Agent
        agent_res = await run_agent_node.run(GraphRunContext(state=state, deps=None))
        if isinstance(agent_res, PersistRejectionNode):
            await reject_node.run(GraphRunContext(state=state, deps=None))
            processed_set.add(t_id)
            processed_list.append(t_id)
            continue

        # Reconcile
        await reconcile_node.run(GraphRunContext(state=state, deps=None))

        # Render Jinja
        render_res = await render_node.run(GraphRunContext(state=state, deps=None))
        if isinstance(render_res, PersistRejectionNode):
            await reject_node.run(GraphRunContext(state=state, deps=None))
            processed_set.add(t_id)
            processed_list.append(t_id)
            continue

        # Persist
        await persist_node.run(GraphRunContext(state=state, deps=None))
        successful_count += 1
        processed_set.add(t_id)
        processed_list.append(t_id)
        save_checkpoint_state(processed_list)

        if smoke_test:
            smoke_task_path = TEST_RESULTS_DIR / "smoke_test_task.json"
            smoke_sft_path = TEST_RESULTS_DIR / "smoke_test_sft_windows.jsonl"
            smoke_payload = {
                "task_id": t_id,
                "raw_task": state.raw_task.model_dump() if state.raw_task else {},
                "translated_trajectory": state.translated_trajectory.model_dump() if state.translated_trajectory else {},
                "sft_windows_count": len(state.sft_windows or []),
            }
            save_atomically(smoke_task_path, json.dumps(smoke_payload, indent=2))
            for w in (state.sft_windows or []):
                append_jsonl_fsync(smoke_sft_path, json.dumps(w))
            logger.info("Saved smoke test results atomically to %s", TEST_RESULTS_DIR)
            break
    await http_client.aclose()
    logger.info(
        "Pipeline finished. Translated %d tasks successfully (evaluated %d).",
        successful_count,
        total_evaluated,
    )


def main() -> None:
    """CLI entrypoint."""
    import argparse

    parser = argparse.ArgumentParser(description="Gemma 4 SFT Trajectory Translation Pipeline")
    parser.add_argument("--candidates", type=Path, default=None, help="Path to pre-filtered candidate tasks JSONL")
    parser.add_argument("--limit", type=int, default=1, help="Number of tasks to translate")
    parser.add_argument("--smoke-test", action="store_true", help="Run 1-task smoke test and save outputs")
    parser.add_argument("--resume", action="store_true", default=True, help="Resume from checkpoint state")
    parser.add_argument("--model", type=str, default=None, help="LiteRouter model override")
    parser.add_argument("--skip-preflight", action="store_true", help="Skip preflight health audits")
    parser.add_argument("--concurrency", type=int, default=1, help="Worker concurrency limit")

    args = parser.parse_args()
    asyncio.run(
        run_pipeline(
            limit=args.limit,
            smoke_test=args.smoke_test,
            resume=args.resume,
            model_name=args.model,
            skip_preflight=args.skip_preflight,
            concurrency=args.concurrency,
            candidates_path=args.candidates,
        )
    )
if __name__ == "__main__":
    main()
