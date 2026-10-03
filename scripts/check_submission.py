#!/usr/bin/env python3
"""Ironclad submission gates for the Gemma 4 Developer Agent competition.

Every threshold lives in ``scripts/gate_policy.yaml`` (single source of truth,
decision D13). This module is both an importable library and a runnable CLI:

    python3 scripts/check_submission.py            # human-readable summary
    python3 scripts/check_submission.py --json     # machine-readable JSON
    python3 scripts/check_submission.py --only g_zip_root_layout

Exit code is ``0`` when no gate FAILs, ``1`` when any gate FAILs. WARN never
affects the exit code; only FAIL does (a false-negative gate can burn the
single daily submission slot, so WARNs are informational, FAILs are blocking).

Layout (decision D14): all gate checks are plain functions returning the SAME
result shape (:class:`GateResult`). Pre-submission gates operate on the
*working tree* + the packed zip; post-run gates operate on *completed-run*
artifacts (``cloud_results/``) and are a clearly separate section (decision D2).

Standard library only, plus ``yaml`` when importable (with a stdlib fallback
parser). No third-party dependencies.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import sys
import zipfile
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Paths — resolved relative to THIS FILE, never the CWD, so the script runs
# correctly from the repo root OR when imported from anywhere.
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(_HERE)

POLICY_PATH = os.path.join(_HERE, "gate_policy.yaml")
SUBMISSION_DIR = os.path.join(REPO_ROOT, "my_submission")
SUBMISSION_ZIP = os.path.join(REPO_ROOT, "submission.zip")
ADAPTERS_STAGING = os.path.join(REPO_ROOT, "adapters_staging")
TASK_RESULTS = os.path.join(REPO_ROOT, "cloud_results", "results", "task_results.jsonl")
TRACES_DIR = os.path.join(REPO_ROOT, "cloud_results", "results", "traces")
DOCS_DIR = os.path.join(REPO_ROOT, "docs")

# The harness allowlist (HARNESS_README.md allowed_file_extensions). This is a
# fixed format allowlist from the competition, not a tunable threshold, so it
# is a module constant rather than policy — but it is verified against the
# policy note in the gate. Kept here so the reader sees its provenance.
ALLOWED_SUBMISSION_EXTENSIONS = {
    ".yaml", ".yml",  # agent / eval configs
    ".md", ".txt",    # prompts & SKILL.md
    ".py",            # ADK skill scripts
    ".json",          # adapter_config.json
    ".safetensors",   # adapter_model.safetensors
}

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"


# ---------------------------------------------------------------------------
# Shared result shape
# ---------------------------------------------------------------------------
@dataclass
class GateResult:
    """The uniform result every gate returns.

    Attributes:
        name: stable gate identifier (e.g. ``g_adapter_base_model``).
        status: one of PASS / FAIL / WARN.
        message: one-line human summary of the verdict.
        evidence: the file:line references or concrete values justifying it.
        remediation: what a human should do if the gate did not pass.
    """

    name: str
    status: str
    message: str
    evidence: str = ""
    remediation: str = ""


# ---------------------------------------------------------------------------
# Policy loading (decision D13 — single source of truth)
# ---------------------------------------------------------------------------
def _coerce_scalar(raw: str) -> Any:
    """Coerce a YAML scalar to a native Python type.

    The policy file is deliberately FLAT, so every value arrives as a string.
    We explicitly coerce numerics and booleans here so gate code can compare
    against real types (ints/bools), not strings. This is the ONLY place a
    policy value's type is decided; gates read already-typed values.
    """
    text = raw.strip()
    low = text.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    # integer
    try:
        return int(text)
    except ValueError:
        pass
    # float
    try:
        return float(text)
    except ValueError:
        pass
    return text


def _stdlib_parse_policy(text: str) -> Dict[str, Dict[str, Any]]:
    """Parse the flat gate policy with the standard library only.

    Format contract: ``section:`` headers at column 0, then two-space indented
    ``key: value`` scalars. Values may contain internal colons (e.g. the
    ``source:`` lines cite ``HARNESS_README.md:177/185``), so we split on the
    FIRST colon with :meth:`str.partition` — never bare ``line.split(':')``,
    which would raise ValueError when a value carries colons.
    """
    policy: Dict[str, Dict[str, Any]] = {}
    current: Optional[str] = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and ":" in line:
            # section header at column 0
            key, _, _val = line.partition(":")
            current = key.strip()
            policy[current] = {}
        elif current is not None:
            stripped = line.strip()
            if ":" not in stripped:
                continue
            key, _, value = stripped.partition(":")
            policy[current][key.strip()] = _coerce_scalar(value)
    return policy


def load_policy(path: str = POLICY_PATH) -> Dict[str, Dict[str, Any]]:
    """Load the gate policy. Prefer PyYAML; fall back to a stdlib parser.

    Raises:
        FileNotFoundError: if the policy file is absent.
    """
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    try:
        import yaml  # type: ignore
    except ImportError:
        return _stdlib_parse_policy(text)
    loaded = yaml.safe_load(text)
    # Normalize: ensure a dict-of-dicts even if the file is ever changed, and
    # coerce values consistently with the fallback path.
    normalized: Dict[str, Dict[str, Any]] = {}
    if isinstance(loaded, dict):
        for section, body in loaded.items():
            if isinstance(body, dict):
                normalized[str(section)] = {str(k): _coerce_scalar(str(v)) for k, v in body.items()}
    return normalized


def _policy_get(policy: Dict[str, Dict[str, Any]], section: str, key: str) -> Any:
    """Fetch ``policy[section][key]`` with a clear error when missing."""
    sec = policy.get(section)
    if sec is None:
        raise KeyError(f"policy section missing: {section!r}")
    if key not in sec:
        raise KeyError(f"policy key missing: {section}.{key}")
    return sec[key]


def _resolve_serve_model_name(policy) -> str:
    return str(_policy_get(policy, "served_model", "name"))


# ===========================================================================
# PRE-SUBMISSION GATES (operating on the working tree + packed zip)
# ===========================================================================

# --- 1. required files -----------------------------------------------------

def g_required_files(policy: Dict[str, Dict[str, Any]]) -> GateResult:
    """Core submission files are present and every skill has SKILL.md+script."""
    required = [
        os.path.join(SUBMISSION_DIR, "agent.yaml"),
        os.path.join(SUBMISSION_DIR, "eval_config.yaml"),
        os.path.join(SUBMISSION_DIR, "configs", "sampling.yaml"),
        os.path.join(SUBMISSION_DIR, "prompts", "main.md"),
    ]
    missing = [os.path.relpath(p, SUBMISSION_DIR) for p in required if not os.path.isfile(p)]
    problems = []
    if missing:
        problems.append("missing core files: " + ", ".join(missing))

    skills_root = os.path.join(SUBMISSION_DIR, "skills")
    skills_detail = []
    if not os.path.isdir(skills_root):
        problems.append("skills/ directory missing")
    else:
        for entry in sorted(os.listdir(skills_root)):
            sdir = os.path.join(skills_root, entry)
            if not os.path.isdir(sdir):
                continue
            if not os.path.isfile(os.path.join(sdir, "SKILL.md")):
                problems.append(f"skills/{entry} missing SKILL.md")
                continue
            scripts_dir = os.path.join(sdir, "scripts")
            pys = []
            if os.path.isdir(scripts_dir):
                pys = [f for f in os.listdir(scripts_dir) if f.endswith(".py")]
            if not pys:
                problems.append(f"skills/{entry} has no scripts/*.py")
            else:
                skills_detail.append(f"skills/{entry}: SKILL.md + {len(pys)} script(s)")

    evidence = "required=agent.yaml,eval_config.yaml,configs/sampling.yaml,prompts/main.md; " + (
        "; ".join(skills_detail) if skills_detail else "no skills enumerated"
    )
    if problems:
        return GateResult(
            "g_required_files", FAIL,
            "required submission files/skills incomplete",
            evidence, "Add the missing files; every skills/*/ needs SKILL.md and scripts/*.py.",
        )
    return GateResult(
        "g_required_files", PASS,
        f"all required files present ({len(skills_detail)} skills verified)",
        evidence, "",
    )


# --- 2. adapter declared in agent.yaml -------------------------------------

def g_adapter_declared(policy: Dict[str, Dict[str, Any]]) -> GateResult:
    """agent.yaml declares the policy ``declared_name`` adapter."""
    declared_name = str(_policy_get(policy, "adapter", "declared_name"))
    agent_yaml = os.path.join(SUBMISSION_DIR, "agent.yaml")
    if not os.path.isfile(agent_yaml):
        return GateResult("g_adapter_declared", FAIL, "agent.yaml missing",
                          f"expected {os.path.relpath(agent_yaml, REPO_ROOT)}", "Create agent.yaml.")
    found_line = None
    with open(agent_yaml, "r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            stripped = line.strip()
            if stripped.startswith("adapter:"):
                value = stripped.partition(":")[2].strip()
                if value == declared_name:
                    found_line = (lineno, value)
                else:
                    return GateResult(
                        "g_adapter_declared", FAIL,
                        f"agent.yaml adapter: value != required declared_name",
                        f"agent.yaml:{lineno} 'adapter: {value}' != policy declared_name '{declared_name}'",
                        f"Set 'adapter: {declared_name}' in agent.yaml (decision D9).",
                    )
    if found_line is None:
        return GateResult(
            "g_adapter_declared", FAIL,
            "agent.yaml does not declare the required adapter",
            f"no 'adapter: {declared_name}' line found in agent.yaml; policy requires '{declared_name}'",
            f"Add 'adapter: {declared_name}' to agent.yaml (decision D9).",
        )
    lineno, value = found_line
    return GateResult("g_adapter_declared", PASS,
                      f"agent.yaml declares adapter '{value}'",
                      f"agent.yaml:{lineno} 'adapter: {value}'", "")


# --- 3. adapter present ----------------------------------------------------

def g_adapter_present(policy: Dict[str, Dict[str, Any]]) -> GateResult:
    """The adapters/ dir inside the submission is populated."""
    adapters_subdir = str(_policy_get(policy, "adapter", "dir"))
    adir = os.path.join(SUBMISSION_DIR, adapters_subdir)
    if not os.path.isdir(adir):
        return GateResult("g_adapter_present", FAIL, f"{adapters_subdir}/ missing in submission",
                          f"{adapters_subdir}/ not found under my_submission/",
                          f"Populate my_submission/{adapters_subdir}/ with the trained adapter (D9).")
    files = []
    for root, _dirs, names in os.walk(adir):
        for n in names:
            files.append(os.path.relpath(os.path.join(root, n), adir))
    if not files:
        return GateResult("g_adapter_present", FAIL, f"{adapters_subdir}/ is empty",
                          f"{adapters_subdir}/ exists but contains no files",
                          f"Install the adapter files into my_submission/{adapters_subdir}/.")
    weight = [f for f in files if f.endswith("adapter_model.safetensors")]
    detail = f"{len(files)} file(s); weights={'yes' if weight else 'NO'}"
    if not weight:
        return GateResult("g_adapter_present", FAIL,
                          f"{adapters_subdir}/ has no adapter_model.safetensors",
                          detail, "Include adapter_model.safetensors (the harness requires it).")
    return GateResult("g_adapter_present", PASS, f"{adapters_subdir}/ populated with adapter",
                      detail, "")


# --- 4. adapter base model == served model EXACTLY -------------------------

def _find_adapter_config() -> Optional[str]:
    """Locate an adapter_config.json, preferring the submission, then staging."""
    candidates = [
        os.path.join(SUBMISSION_DIR, "adapters", "main_lora", "adapter_config.json"),
        os.path.join(ADAPTERS_STAGING, "main_lora", "adapter_config.json"),
        os.path.join(ADAPTERS_STAGING, "adapters", "main_lora", "adapter_config.json"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def g_adapter_base_model(policy: Dict[str, Dict[str, Any]]) -> GateResult:
    """adapter_config base_model_name_or_path == served model, EXACTLY.

    String equality only: no allowlist, no prefix matching, no normalization
    (decision D10). This currently FAILS on purpose — the staged adapter base
    is a 4-bit bnb quantization that mismatches the QAT w4a16 served model.
    Failing honestly is correct.
    """
    required_base = str(_policy_get(policy, "adapter", "required_base_model"))
    cfg = _find_adapter_config()
    if cfg is None:
        return GateResult("g_adapter_base_model", FAIL,
                          "no adapter_config.json found to validate",
                          "searched my_submission/adapters/ and adapters_staging/",
                          "Stage a real adapter with adapter_config.json.")
    try:
        with open(cfg, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        return GateResult("g_adapter_base_model", FAIL,
                          "adapter_config.json unreadable/invalid JSON",
                          f"{os.path.relpath(cfg, REPO_ROOT)}: {exc}",
                          "Fix the adapter_config.json JSON.")
    base = data.get("base_model_name_or_path")
    rel = os.path.relpath(cfg, REPO_ROOT)
    if base is None:
        return GateResult("g_adapter_base_model", FAIL,
                          "adapter_config.json has no base_model_name_or_path",
                          f"{rel}: key absent", "Set base_model_name_or_path to the served model.")
    if base != required_base:
        return GateResult(
            "g_adapter_base_model", FAIL,
            "adapter base model does not exactly match served model",
            f"{rel}: base_model_name_or_path={base!r} != required {required_base!r}",
            "Retrain/retarget the LoRA so its base is the served model exactly (D10); "
            "do NOT widen with an allowlist.",
        )
    return GateResult("g_adapter_base_model", PASS,
                      "adapter base model exactly matches served model",
                      f"{rel}: base_model_name_or_path={base!r}", "")


# --- 5. tool budget parity (prompt vs eval_config) -------------------------

_TC_RE = None


def _parse_tool_calls_from_prompt(text: str) -> List[Tuple[int, int]]:
    """Extract (line_no, budget) pairs from prompt prose like 'budget of 40 tool calls'."""
    import re
    global _TC_RE
    if _TC_RE is None:
        _TC_RE = re.compile(r"budget of\s+(\d+)\s+tool calls", re.IGNORECASE)
    out: List[Tuple[int, int]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        m = _TC_RE.search(line)
        if m:
            out.append((lineno, int(m.group(1))))
    return out


def _read_eval_max_tool_calls(policy) -> Tuple[Optional[int], str]:
    """Read evaluation.max_tool_calls from eval_config.yaml, flat, no yaml dep."""
    import re
    path = os.path.join(SUBMISSION_DIR, "eval_config.yaml")
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.readlines()
    in_eval = False
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("evaluation:"):
            in_eval = True
            continue
        if in_eval:
            m = re.match(r"^(\s*)max_tool_calls:\s*(\d+)", line)
            if m:
                return int(m.group(2)), f"eval_config.yaml:{lineno} evaluation.max_tool_calls"
            if line and not line.startswith((" ", "\t")):
                in_eval = False
    return None, "eval_config.yaml: no evaluation.max_tool_calls found"


def g_tool_budget_parity(policy: Dict[str, Dict[str, Any]]) -> GateResult:
    """The tool-call budget in prompts/main.md == evaluation.max_tool_calls."""
    prompt_path = os.path.join(SUBMISSION_DIR, "prompts", "main.md")
    if not os.path.isfile(prompt_path):
        return GateResult("g_tool_budget_parity", FAIL, "prompts/main.md missing",
                          os.path.relpath(prompt_path, REPO_ROOT), "Create prompts/main.md.")
    with open(prompt_path, "r", encoding="utf-8") as fh:
        text = fh.read()
    prompt_budgets = _parse_tool_calls_from_prompt(text)
    if not prompt_budgets:
        return GateResult("g_tool_budget_parity", FAIL,
                          "no 'budget of N tool calls' statement found in main.md",
                          "main.md contains no parseable budget line",
                          "State the total tool-call budget explicitly in main.md.")
    eval_path = os.path.join(SUBMISSION_DIR, "eval_config.yaml")
    if not os.path.isfile(eval_path):
        return GateResult("g_tool_budget_parity", FAIL, "eval_config.yaml missing",
                          os.path.relpath(eval_path, REPO_ROOT), "Create eval_config.yaml.")
    try:
        eval_budget, eval_ev = _read_eval_max_tool_calls(policy)
    except OSError as exc:
        return GateResult("g_tool_budget_parity", FAIL, "eval_config.yaml unreadable", str(exc),
                          "Fix eval_config.yaml readability.")
    if eval_budget is None:
        return GateResult("g_tool_budget_parity", FAIL,
                          "evaluation.max_tool_calls not found in eval_config.yaml", eval_ev,
                          "Declare evaluation.max_tool_calls.")

    distinct = {b for _ln, b in prompt_budgets}
    lines_repr = ", ".join(f"main.md:{ln}->{b}" for ln, b in prompt_budgets)
    if len(distinct) > 1:
        return GateResult("g_tool_budget_parity", FAIL,
                          "main.md states multiple different tool-call budgets",
                          f"{lines_repr}; eval {eval_budget} ({eval_ev})",
                          "Make main.md state exactly one budget equal to eval_config.")
    prompt_budget = prompt_budgets[0][1]
    if prompt_budget != eval_budget:
        return GateResult("g_tool_budget_parity", FAIL,
                          "prompt tool-call budget != eval_config max_tool_calls",
                          f"main.md:{prompt_budgets[0][0]}->{prompt_budget} != eval {eval_budget} ({eval_ev})",
                          f"Correct main.md to state {eval_budget} tool calls (D3).")
    return GateResult("g_tool_budget_parity", PASS,
                      f"prompt budget == eval_config max_tool_calls ({prompt_budget})",
                      f"{lines_repr}; {eval_ev}={eval_budget}", "")


# --- 6. prompt ladder consistency ------------------------------------------

def g_prompt_ladder_consistency(policy: Dict[str, Dict[str, Any]]) -> GateResult:
    """All turn-calibration references in main.md must be internally consistent.

    There was a real defect: the Section-6 ladder said Turns 1–10 / Turn 11
    while the Phase headers still said Turns 1–12 / Turn 13, giving the model
    two contradictory deadlines. We detect that *contradiction class* precisely:

      1. Two different ranges that both start at the SAME turn but end at
         different turns are contradictory (a phase claimed to end at 10 and
         another claimed to end at 12, both from Turn 1).
      2. The mandatory-initial-edit deadline must be stated identically
         everywhere it appears.
      3. The mandatory-edit deadline must be contiguous with the end of the
         discovery window (deadline == discovery_end + 1).

    A legitimate multi-phase ladder (1–10 discovery, 12–32 verify, 33–36
    polish) is NOT a contradiction: its ranges have different starts and do not
    overlap. We therefore assert the ranges form a non-overlapping monotone
    partition, not that all starts are equal.
    """
    import re
    prompt_path = os.path.join(SUBMISSION_DIR, "prompts", "main.md")
    if not os.path.isfile(prompt_path):
        return GateResult("g_prompt_ladder_consistency", FAIL, "prompts/main.md missing",
                          os.path.relpath(prompt_path, REPO_ROOT), "Create prompts/main.md.")
    with open(prompt_path, "r", encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    range_re = re.compile(r"Turns?\s+(\d+)\s*[–\-—]\s*(\d+)")
    turn_re = re.compile(r"\bTurn\s+(\d+)\b")

    spans: List[Tuple[int, int, int]] = []  # (line, start, end)
    for lineno, line in enumerate(lines, 1):
        for m in range_re.finditer(line):
            spans.append((lineno, int(m.group(1)), int(m.group(2))))

    # The mandatory-initial-edit deadline: a single Turn N tied to the first
    # required edit (a line naming an initial fix/edit AND exactly one Turn N).
    deadline_re = re.compile(r"initial\s+(?:surgical\s+)?fix|initial\s+edit", re.IGNORECASE)
    deadlines: List[Tuple[int, int]] = []  # (line, turn)
    for lineno, line in enumerate(lines, 1):
        if not deadline_re.search(line):
            continue
        singles = [int(x) for x in turn_re.findall(line)]
        if len(singles) == 1:
            deadlines.append((lineno, singles[0]))

    problems: List[str] = []

    # (1) Same start, different end => contradiction.
    by_start: Dict[int, set] = {}
    for _ln, a, b in spans:
        by_start.setdefault(a, set()).add(b)
    for a, ends in sorted(by_start.items()):
        if len(ends) > 1:
            conflicting = sorted(
                (ln, a, b) for ln, sa, b in spans if sa == a and b != min(ends)
            )
            detail = ", ".join(f"main.md:{ln}='Turns {a}–{b}'" for ln, _a, b in conflicting)
            problems.append(
                f"contradictory range end for Turn {a} (claimed ends {sorted(ends)}): {detail}"
            )

    # (2) Deadline stated inconsistently.
    if len({t for _ln, t in deadlines}) > 1:
        detail = ", ".join(f"main.md:{ln}->Turn {t}" for ln, t in sorted(deadlines))
        problems.append(f"mandatory-edit deadline disagrees: {detail}")

    # (3) Overlapping ranges => contradictory coverage of the same turns.
    ordered = sorted({(a, b) for _ln, a, b in spans})
    for (a1, b1), (a2, b2) in zip(ordered, ordered[1:]):
        if a2 <= b1 and (a1, b1) != (a2, b2):
            problems.append(
                f"overlapping turn ranges: 'Turns {a1}–{b1}' and 'Turns {a2}–{b2}' both cover Turn {a2}"
            )

    # (4) Deadline contiguity with the earliest window that ends before it.
    if spans and deadlines:
        deadline_turns = {t for _ln, t in deadlines}
        earliest_start = min(a for _ln, a, _b in spans)
        first_window_end = min(b for _ln, a, b in spans if a == earliest_start)
        if deadline_turns and (first_window_end + 1) not in deadline_turns:
            problems.append(
                f"mandatory-edit deadline Turn(s) {sorted(deadline_turns)} not contiguous with "
                f"the discovery window 'Turns {earliest_start}–{first_window_end}' "
                f"(expected Turn {first_window_end + 1})"
            )

    span_repr = "; ".join(f"main.md:{ln}=Turns{a}–{b}" for ln, a, b in sorted(spans))
    deadline_repr = "; ".join(f"main.md:{ln}=Turn{t}" for ln, t in sorted(deadlines))
    evidence = f"ranges[{span_repr}] deadlines[{deadline_repr}]"
    if problems:
        return GateResult("g_prompt_ladder_consistency", FAIL,
                          "turn ladder in main.md is internally inconsistent",
                          evidence + " || " + " | ".join(problems),
                          "Reconcile the Phase headers and the Section-6 ladder to one turn schedule.")
    return GateResult("g_prompt_ladder_consistency", PASS,
                      "turn ladder in main.md is internally consistent", evidence, "")


# --- 7. forbidden sampling keys absent -------------------------------------

def g_sampling_no_thinking_level(policy: Dict[str, Dict[str, Any]]) -> GateResult:
    """Forbidden sampling keys (currently thinking_level) must be ABSENT."""
    import re
    forbidden = str(_policy_get(policy, "serving", "forbidden_sampling_keys"))
    sampling = os.path.join(SUBMISSION_DIR, "configs", "sampling.yaml")
    if not os.path.isfile(sampling):
        return GateResult("g_sampling_no_thinking_level", FAIL, "configs/sampling.yaml missing",
                          os.path.relpath(sampling, REPO_ROOT), "Create configs/sampling.yaml.")
    with open(sampling, "r", encoding="utf-8") as fh:
        lines = fh.readlines()
    pattern = re.compile(r"^\s*" + re.escape(forbidden) + r"\s*:")
    hits = [(ln, ln_text.strip()) for ln, ln_text in enumerate(lines, 1) if pattern.match(ln_text)]
    if hits:
        detail = ", ".join(f"sampling.yaml:{ln}:{text}" for ln, text in hits)
        return GateResult("g_sampling_no_thinking_level", FAIL,
                          f"forbidden sampling key '{forbidden}' present",
                          detail, f"Delete '{forbidden}' from sampling.yaml (LiteLLM mistranslates it).")
    return GateResult("g_sampling_no_thinking_level", PASS,
                      f"forbidden key '{forbidden}' absent from sampling.yaml",
                      f"scanned {len(lines)} lines; no '{forbidden}:' match", "")


# --- 8. max_output_tokens vs project cap (policy-driven severity) ----------

def g_sampling_output_cap(policy: Dict[str, Dict[str, Any]]) -> GateResult:
    """max_output_tokens vs the project cap; severity is policy-driven.

    The harness only requires max_output_tokens + thinking_budget <= the
    ceiling, which the current larger value passes, but the PROJECT cap derived
    from token_threshold is asserted separately as a WARN (not a FAIL) until a
    real Gemma run settles it. The severity is read from policy so the intent
    is explicit, not hardcoded.
    """
    import re
    project_cap = int(_policy_get(policy, "serving", "max_output_tokens_project_cap"))
    harness_ceiling = int(_policy_get(policy, "submission", "max_output_tokens_ceiling"))
    current_expected = _policy_get(policy, "serving", "max_output_tokens_current")
    sampling = os.path.join(SUBMISSION_DIR, "configs", "sampling.yaml")
    if not os.path.isfile(sampling):
        return GateResult("g_sampling_output_cap", FAIL, "configs/sampling.yaml missing",
                          os.path.relpath(sampling, REPO_ROOT), "Create configs/sampling.yaml.")
    value = None
    vline = None
    with open(sampling, "r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            m = re.match(r"^\s*max_output_tokens\s*:\s*(\d+)", line)
            if m:
                value = int(m.group(1))
                vline = lineno
                break
    if value is None:
        return GateResult("g_sampling_output_cap", FAIL,
                          "max_output_tokens not found in sampling.yaml",
                          os.path.relpath(sampling, REPO_ROOT), "Declare max_output_tokens.")
    thinking_budget = None
    with open(sampling, "r", encoding="utf-8") as fh:
        m = re.search(r"thinking_budget\s*:\s*(\d+)", fh.read())
        if m:
            thinking_budget = int(m.group(1))

    evidence = (f"sampling.yaml:{vline} max_output_tokens={value}; "
                f"project_cap={project_cap}; harness_ceiling={harness_ceiling}; "
                f"thinking_budget={thinking_budget}")

    if value > harness_ceiling:
        return GateResult("g_sampling_output_cap", FAIL,
                          "max_output_tokens exceeds the harness ceiling",
                          evidence, f"Lower max_output_tokens to <= {harness_ceiling}.")
    if value > project_cap:
        # Within the harness limit but above the PROJECT cap -> WARN, not FAIL.
        return GateResult(
            "g_sampling_output_cap", WARN,
            f"max_output_tokens ({value}) above project cap ({project_cap}) but within harness ceiling ({harness_ceiling})",
            evidence + (f"; sum={'%d' % (value + thinking_budget) if thinking_budget is not None else 'n/a'} <= {harness_ceiling} passes harness, "
                        f"but token_threshold crowds context (docs/FINDINGS.md:76)"),
            f"Consider lowering max_output_tokens to the project cap {project_cap}; "
            "documented as a project rule, not a hard harness rule.",
        )
    return GateResult("g_sampling_output_cap", PASS,
                      f"max_output_tokens ({value}) within project cap ({project_cap})",
                      evidence, "")


# --- 9. unpacked submission size (from zip CONTENTS) -----------------------

def g_submission_size_unpacked(policy: Dict[str, Dict[str, Any]]) -> GateResult:
    """Total UNPACKED size of the zip vs policy max_unpacked_mb.

    The known defect is verify_submission.py computing size from the COMPRESSED
    file and printing '< 3 GiB'; HARNESS_README sets the limit on UNPACKED
    total. We compute from the zip's member file_size, not ZIP_PATH.stat().
    If the zip is absent, WARN (nothing to measure yet) rather than crash.
    """
    max_mb = int(_policy_get(policy, "submission", "max_unpacked_mb"))
    if not os.path.isfile(SUBMISSION_ZIP):
        return GateResult("g_submission_size_unpacked", WARN,
                          "submission.zip absent; nothing to measure yet",
                          "submission.zip not found", "Pack submission.zip then re-run the gate.")
    try:
        with zipfile.ZipFile(SUBMISSION_ZIP, "r") as zf:
            unpacked = sum(info.file_size for info in zf.infolist())
            member_count = len(zf.infolist())
    except (zipfile.BadZipFile, OSError) as exc:
        return GateResult("g_submission_size_unpacked", FAIL,
                          "submission.zip unreadable/corrupt", str(exc),
                          "Repack a valid submission.zip.")
    unpacked_mb = unpacked / (1024 * 1024)
    compressed_mb = os.path.getsize(SUBMISSION_ZIP) / (1024 * 1024)
    evidence = (f"unpacked={unpacked_mb:.1f} MB across {member_count} members; "
                f"compressed_on_disk={compressed_mb:.1f} MB; cap={max_mb} MB (unpacked)")
    if unpacked_mb > max_mb:
        return GateResult("g_submission_size_unpacked", FAIL,
                          f"unpacked size {unpacked_mb:.1f} MB exceeds cap {max_mb} MB",
                          evidence, f"Shrink the submission below {max_mb} MB unpacked.")
    return GateResult("g_submission_size_unpacked", PASS,
                      f"unpacked size {unpacked_mb:.1f} MB within cap {max_mb} MB", evidence, "")


# --- 10. zip-vs-directory byte-identity drift ------------------------------

def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _dir_hashes(root: str) -> Dict[str, str]:
    """Map relative path -> sha256 for every file under root (files only)."""
    out: Dict[str, str] = {}
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            try:
                with open(full, "rb") as fh:
                    out[rel] = _sha256_bytes(fh.read())
            except OSError:
                out[rel] = "<unreadable>"
    return out


def _zip_hashes(zf: zipfile.ZipFile) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for info in zf.infolist():
        if info.is_dir():
            continue
        name = info.filename.lstrip("./")
        try:
            with zf.open(info) as fh:
                out[name] = _sha256_bytes(fh.read())
        except (zipfile.BadZipFile, OSError, RuntimeError):
            out[name] = "<unreadable>"
    return out


def g_zip_directory_drift(policy: Dict[str, Dict[str, Any]]) -> GateResult:
    """Byte-identity between the zip's contents and the working directory.

    A directory can be correct while the zip is stale. Walk both, compare
    relative paths and content hashes, report every differing path. Handles the
    case where the zip predates the directory.
    """
    if not os.path.isdir(SUBMISSION_DIR):
        return GateResult("g_zip_directory_drift", FAIL, "submission directory missing",
                          os.path.relpath(SUBMISSION_DIR, REPO_ROOT), "Restore my_submission/.")
    if not os.path.isfile(SUBMISSION_ZIP):
        return GateResult("g_zip_directory_drift", FAIL,
                          "submission.zip absent; cannot verify drift",
                          "submission.zip not found", "Pack submission.zip then re-check drift.")
    try:
        with zipfile.ZipFile(SUBMISSION_ZIP, "r") as zf:
            zh = _zip_hashes(zf)
    except (zipfile.BadZipFile, OSError) as exc:
        return GateResult("g_zip_directory_drift", FAIL, "submission.zip unreadable", str(exc),
                          "Repack a valid submission.zip.")
    dh = _dir_hashes(SUBMISSION_DIR)

    only_zip = sorted(set(zh) - set(dh))
    only_dir = sorted(set(dh) - set(zh))
    differing = sorted(k for k in set(zh) & set(dh) if zh[k] != dh[k])

    if not (only_zip or only_dir or differing):
        return GateResult("g_zip_directory_drift", PASS,
                          f"zip and directory byte-identical ({len(dh)} files)",
                          f"compared {len(dh)} dir files vs {len(zh)} zip members; no diff", "")

    parts = []
    if only_dir:
        parts.append(f"in dir not zip ({len(only_dir)}): " + ", ".join(only_dir[:8]) + (" ..." if len(only_dir) > 8 else ""))
    if only_zip:
        parts.append(f"in zip not dir ({len(only_zip)}): " + ", ".join(only_zip[:8]) + (" ..." if len(only_zip) > 8 else ""))
    if differing:
        parts.append(f"content differs ({len(differing)}): " + ", ".join(differing[:8]) + (" ..." if len(differing) > 8 else ""))
    return GateResult("g_zip_directory_drift", FAIL,
                      "submission.zip is out of sync with my_submission/",
                      " | ".join(parts),
                      "Repack submission.zip from my_submission/ so the zip matches the tree.")


# --- 11. zip root layout ----------------------------------------------------

def g_zip_root_layout(policy: Dict[str, Dict[str, Any]]) -> GateResult:
    """Required files must sit at the archive ROOT, not nested a level deep."""
    required = ["agent.yaml", "eval_config.yaml", "configs/sampling.yaml", "prompts/main.md"]
    if not os.path.isfile(SUBMISSION_ZIP):
        return GateResult("g_zip_root_layout", WARN, "submission.zip absent",
                          "submission.zip not found", "Pack submission.zip then verify root layout.")
    try:
        with zipfile.ZipFile(SUBMISSION_ZIP, "r") as zf:
            names = {n.lstrip("./") for n in zf.namelist() if not n.endswith("/")}
    except (zipfile.BadZipFile, OSError) as exc:
        return GateResult("g_zip_root_layout", FAIL, "submission.zip unreadable", str(exc),
                          "Repack a valid submission.zip.")
    # Detect an extra nesting level: some top dir containing everything.
    top_levels = {n.split("/", 1)[0] for n in names if "/" in n}
    single_root = None
    if names and not any("/" not in n for n in names) and len(top_levels) == 1:
        single_root = next(iter(top_levels))

    missing = [r for r in required if r not in names]
    misplaced = []
    if single_root:
        misplaced = [r for r in required if f"{single_root}/{r}" in names]

    found_root = sorted(n for n in names if "/" not in n)
    evidence = f"root-level files={found_root}; top-level dirs={sorted(top_levels)}"
    if single_root:
        return GateResult("g_zip_root_layout", FAIL,
                          f"archive is nested one level deep under '{single_root}/'",
                          evidence + f"; required found under {single_root}/: {misplaced}",
                          "Zip from INSIDE my_submission/ so agent.yaml sits at the archive root.")
    if missing:
        return GateResult("g_zip_root_layout", FAIL,
                          "required files missing from archive root",
                          evidence + f"; missing={missing}",
                          "Ensure the required files are at the archive root.")
    return GateResult("g_zip_root_layout", PASS,
                      "required files sit at the archive root", evidence, "")


# --- 12. disallowed extensions inside the zip ------------------------------

def g_disallowed_extensions(policy: Dict[str, Dict[str, Any]]) -> GateResult:
    """No file inside the zip uses a disallowed extension (HARNESS_README allowlist)."""
    if not os.path.isfile(SUBMISSION_ZIP):
        return GateResult("g_disallowed_extensions", WARN, "submission.zip absent",
                          "submission.zip not found", "Pack submission.zip then re-check extensions.")
    try:
        with zipfile.ZipFile(SUBMISSION_ZIP, "r") as zf:
            names = [n.lstrip("./") for n in zf.namelist() if not n.endswith("/")]
    except (zipfile.BadZipFile, OSError) as exc:
        return GateResult("g_disallowed_extensions", FAIL, "submission.zip unreadable", str(exc),
                          "Repack a valid submission.zip.")
    bad = []
    for n in names:
        ext = os.path.splitext(n)[1].lower()
        if ext not in ALLOWED_SUBMISSION_EXTENSIONS:
            bad.append(n)
    if bad:
        listed = ", ".join(sorted(bad)[:12]) + (" ..." if len(bad) > 12 else "")
        return GateResult("g_disallowed_extensions", FAIL,
                          f"{len(bad)} disallowed file extension(s) inside zip",
                          f"disallowed: {listed}",
                          "Remove disallowed files (pickle weights .bin/.pt/.pth and binaries are rejected).")
    return GateResult("g_disallowed_extensions", PASS,
                      f"all {len(names)} zip files use allowed extensions",
                      f"allowed={sorted(ALLOWED_SUBMISSION_EXTENSIONS)}", "")


# ===========================================================================
# POST-RUN GATES (decision D2 — operate on COMPLETED-RUN artifacts, kept
# deliberately separate from the pre-submission gates above)
# ===========================================================================

DEGENERATE_MESSAGE = "INFRASTRUCTURE FAILURE, NOT A QUALITY RESULT"


def g_run_health(policy: Dict[str, Dict[str, Any]]) -> GateResult:
    """Detect a degenerate run from task_results.jsonl and traces/*.json.

    Signature (the one real Gemma 4 run): high fraction of traces at zero
    completion tokens AND many empty patches. When matched, this is an
    INFRASTRUCTURE FAILURE, not a quality result. Stdlib json only.
    """
    min_frac = float(_policy_get(policy, "run_health", "zero_completion_token_traces_min_fraction"))
    min_empty = int(_policy_get(policy, "run_health", "empty_patch_min_count"))

    if not os.path.isfile(TASK_RESULTS):
        return GateResult("g_run_health", WARN, "no task_results.jsonl; no completed run to assess",
                          os.path.relpath(TASK_RESULTS, REPO_ROOT),
                          "Produce a completed run before judging run health.")
    rows = []
    try:
        with open(TASK_RESULTS, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError as exc:
        return GateResult("g_run_health", FAIL, "task_results.jsonl unreadable", str(exc),
                          "Fix the run-artifact readability.")

    n_rows = len(rows)
    resolved = sum(1 for r in rows if r.get("resolved"))
    empty_patch = sum(1 for r in rows if not str(r.get("patch") or "").strip())
    exit_hist: Dict[str, int] = {}
    for r in rows:
        k = str(r.get("test_exit_code"))
        exit_hist[k] = exit_hist.get(k, 0) + 1

    # Trace-side: fraction of traces at zero completion tokens.
    n_traces = 0
    zero_completion = 0
    if os.path.isdir(TRACES_DIR):
        for name in sorted(os.listdir(TRACES_DIR)):
            if not name.endswith(".json"):
                continue
            path = os.path.join(TRACES_DIR, name)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    trace = json.load(fh)
            except (OSError, json.JSONDecodeError):
                continue
            n_traces += 1
            fm = trace.get("final_metrics") or {}
            if not fm.get("total_completion_tokens"):
                zero_completion += 1
    zero_frac = (zero_completion / n_traces) if n_traces else 0.0

    evidence = (f"rows={n_rows} resolved={resolved} empty_patch={empty_patch} "
                f"(threshold {min_empty}); test_exit_code histogram={exit_hist}; "
                f"traces={n_traces} zero_completion={zero_completion} "
                f"fraction={zero_frac:.3f} (threshold {min_frac})")

    degenerate = (empty_patch >= min_empty) and (zero_frac >= min_frac)
    if degenerate:
        return GateResult("g_run_health", FAIL, DEGENERATE_MESSAGE, evidence,
                          "Do not read this score as model quality. Fix the inference/health "
                          "infrastructure (endpoint, params, health gate) and re-run.")
    if n_rows == 0:
        return GateResult("g_run_health", WARN, "task_results.jsonl contained no usable rows",
                          evidence, "Regenerate run artifacts.")
    return GateResult("g_run_health", PASS, "run does not match the degenerate signature",
                      evidence, "")


# --- 14. no embedded code literals in docs ----------------------------------

def g_no_embedded_code_in_docs(policy: Dict[str, Dict[str, Any]]) -> GateResult:
    """No docs/*.md may hide a large escaped code literal.

    A working /health + /v1/chat/completions probe was hidden inside a markdown
    string literal, invisible to any grep of .py files, which caused earlier
    research to wrongly conclude no such check existed. We flag any single
    markdown line longer than EMBED_THRESHOLD chars (a large escaped literal).
    Ordinary prose and short fenced snippets are far below this; the real
    offending doc has lines up to ~110k chars.
    """
    EMBED_THRESHOLD = 5000
    if not os.path.isdir(DOCS_DIR):
        return GateResult("g_no_embedded_code_in_docs", WARN, "docs/ directory missing",
                          os.path.relpath(DOCS_DIR, REPO_ROOT), "No docs to scan.")
    offenders = []
    for name in sorted(os.listdir(DOCS_DIR)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(DOCS_DIR, name)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                for lineno, line in enumerate(fh, 1):
                    if len(line.rstrip("\n")) > EMBED_THRESHOLD:
                        offenders.append((name, lineno, len(line.rstrip("\n"))))
        except OSError:
            continue
    if offenders:
        detail = ", ".join(f"docs/{n}:{ln} ({sz} chars)" for n, ln, sz in offenders[:8])
        if len(offenders) > 8:
            detail += f" ... (+{len(offenders) - 8} more)"
        return GateResult("g_no_embedded_code_in_docs", FAIL,
                          f"{len(offenders)} line(s) contain a large escaped code literal",
                          f"threshold={EMBED_THRESHOLD} chars; {detail}",
                          "Extract embedded code literals into real .py files (D20/D21) and "
                          "annotate the doc to point at them.")
    return GateResult("g_no_embedded_code_in_docs", PASS,
                      "no docs/*.md contains a large embedded code literal",
                      f"threshold={EMBED_THRESHOLD} chars; scanned {DOCS_DIR}", "")


# ===========================================================================
# Gate registry — pre-submission, then post-run (D2 separation)
# ===========================================================================

PRE_SUBMISSION_GATES: List[Tuple[str, Callable[[Dict[str, Dict[str, Any]]], GateResult]]] = [
    ("g_required_files", g_required_files),
    ("g_adapter_declared", g_adapter_declared),
    ("g_adapter_present", g_adapter_present),
    ("g_adapter_base_model", g_adapter_base_model),
    ("g_tool_budget_parity", g_tool_budget_parity),
    ("g_prompt_ladder_consistency", g_prompt_ladder_consistency),
    ("g_sampling_no_thinking_level", g_sampling_no_thinking_level),
    ("g_sampling_output_cap", g_sampling_output_cap),
    ("g_submission_size_unpacked", g_submission_size_unpacked),
    ("g_zip_directory_drift", g_zip_directory_drift),
    ("g_zip_root_layout", g_zip_root_layout),
    ("g_disallowed_extensions", g_disallowed_extensions),
]

POST_RUN_GATES: List[Tuple[str, Callable[[Dict[str, Dict[str, Any]]], GateResult]]] = [
    ("g_run_health", g_run_health),
    ("g_no_embedded_code_in_docs", g_no_embedded_code_in_docs),
]

ALL_GATES = PRE_SUBMISSION_GATES + POST_RUN_GATES

# Section labels for output (D2: post-run kept clearly separate).
_SECTION = {}
for _n, _f in PRE_SUBMISSION_GATES:
    _SECTION[_n] = "PRE-SUBMISSION"
for _n, _f in POST_RUN_GATES:
    _SECTION[_n] = "POST-RUN"


def run_all(policy: Optional[Dict[str, Dict[str, Any]]] = None,
            only: Optional[Sequence[str]] = None) -> List[GateResult]:
    """Run every gate (or the subset named in ``only``) and return results.

    A gate that raises is converted into a FAIL result so one broken gate never
    aborts the whole run (robustness requirement).
    """
    if policy is None:
        policy = load_policy()
    wanted = set(only) if only else None
    results: List[GateResult] = []
    for name, fn in ALL_GATES:
        if wanted and name not in wanted:
            continue
        try:
            results.append(fn(policy))
        except Exception as exc:  # noqa: BLE001 - deliberate: never crash the runner
            results.append(GateResult(name, FAIL, f"gate raised an unhandled error: {exc}",
                                     f"{type(exc).__name__}: {exc}",
                                     "Inspect this gate; an exception is a bug, not a verdict."))
    return results


# ---------------------------------------------------------------------------
# Output rendering
# ---------------------------------------------------------------------------
_STATUS_MARK = {PASS: "PASS", FAIL: "FAIL", WARN: "WARN"}


def render_text(results: List[GateResult]) -> str:
    lines: List[str] = []
    last_section = None
    for r in results:
        section = _SECTION.get(r.name, "GATE")
        if section != last_section:
            lines.append("")
            lines.append(f"== {section} ==")
            last_section = section
        mark = _STATUS_MARK.get(r.status, r.status)
        lines.append(f"[{mark}] {r.name}: {r.message}")
    n_pass = sum(1 for r in results if r.status == PASS)
    n_fail = sum(1 for r in results if r.status == FAIL)
    n_warn = sum(1 for r in results if r.status == WARN)
    lines.append("")
    lines.append(f"{n_pass} passed, {n_fail} failed, {n_warn} warnings (of {len(results)} gates)")
    return "\n".join(lines)


def to_json(results: List[GateResult]) -> str:
    payload = {
        "results": [asdict(r) for r in results],
        "summary": {
            "passed": sum(1 for r in results if r.status == PASS),
            "failed": sum(1 for r in results if r.status == FAIL),
            "warnings": sum(1 for r in results if r.status == WARN),
            "total": len(results),
        },
    }
    return json.dumps(payload, indent=2)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Ironclad submission gates (Gemma 4 Kaggle).")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--only", action="append", metavar="GATE",
                        help="run only the named gate (repeatable)")
    args = parser.parse_args(argv)

    try:
        policy = load_policy()
    except (OSError, KeyError) as exc:
        print(f"FATAL: could not load gate policy ({POLICY_PATH}): {exc}", file=sys.stderr)
        return 1

    unknown = [g for g in (args.only or []) if g not in dict(ALL_GATES)]
    if unknown:
        print(f"FATAL: unknown gate(s): {', '.join(unknown)}", file=sys.stderr)
        return 1

    results = run_all(policy, only=args.only)

    if args.json:
        print(to_json(results))
    else:
        print(render_text(results))
        failed = [r for r in results if r.status == FAIL]
        # Exit 1 only when a gate FAILs; WARN never blocks.
        return 1 if failed else 0
    return 1 if any(r.status == FAIL for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
