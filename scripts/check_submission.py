#!/usr/bin/env python3
"""Ironclad submission gates for the Gemma 4 Developer Agent competition.

Every threshold lives in ``scripts/gate_policy.yaml`` (single source of truth,
decision D13). This module is both an importable library and a runnable CLI:

    python3 scripts/check_submission.py            # human-readable summary
    python3 scripts/check_submission.py --json     # machine-readable JSON
    python3 scripts/check_submission.py --only g_zip_root_layout
    python3 scripts/check_submission.py --category submission
    python3 scripts/check_submission.py --pre-pack # skip the zip-dependent gates

Exit code is ``0`` unless a gate in the ``submission`` category FAILs. WARN never
affects the exit code, in any category (a false-negative gate can burn the
single daily submission slot, so WARNs are informational, FAILs are blocking --
but "blocking" means blocking *for the category that owns the verdict*).

TWO-PHASE VALIDATION (``--pre-pack``) -- validating a not-yet-built artifact
-------------------------------------------------------------------------------
Four gates read ``submission.zip``: ``g_submission_size_unpacked``,
``g_zip_directory_drift``, ``g_zip_root_layout`` and ``g_disallowed_extensions``.
Before a pack has run, a verdict from any of them is a verdict about a STALE or
ABSENT artifact -- exactly the same category error as judging last week's run
before this week's exists. Worse, it is a DEADLOCK: drift is only *fixable* by
the pack, so a submission-category FAIL at that point refuses to proceed to the
very step that would resolve the refusal. (This is not hypothetical: a stale zip
made ``submit_safe.sh`` refuse to proceed to its own step 2.)

``--pre-pack`` therefore runs every gate EXCEPT those four, and prints one
explicit ``SKIPPED (pre-pack): <gate>`` line per skipped gate -- never a silent
drop. The summary counts and names them and states that the full check runs
after the pack. Pre-pack mode changes only WHICH gates run, never a verdict: a
genuine pre-pack defect (a missing adapter) still FAILs and still exits non-zero.
It composes with ``--only`` and ``--category`` exactly as they compose with each
other -- a gate must satisfy all applicable filters to run.

The skip set is deliberately expressed as a PHASE, not as a fourth category. A
``pack`` category would answer "may this gate veto?", and the design gives veto
power to the category -- so demoting ``g_zip_directory_drift`` to a non-
submission category would make its FAIL NON-GATING by default and silently
weaken the post-pack check that is the whole point of step 3. Phase membership
and veto power are orthogonal axes, so they are separate mechanisms.

Gate categories -- every gate is EXACTLY ONE of these, and the registry asserts
at load time that none is uncategorized (see ``GATE_CATEGORIES``):

    submission  Asserts a property of the artifact being shipped. A FAIL here is
                a real defect in ``my_submission/`` / ``submission.zip``, so it
                blocks the submission and sets a non-zero exit code.
    post_run    Analyzes COMPLETED-RUN artifacts (``cloud_results/results/``). A
                FAIL is a verdict about a HISTORICAL RUN's health, not about
                whether the artifact being submitted is valid: an old bad run must
                never veto a corrected submission. Still RUNS by default and still
                prints loudly, labelled ``NON-GATING``, but does not set the exit
                code unless the operator explicitly selects ``--category post_run``.
    hygiene     Repository/code hygiene (e.g. a ``docs/*.md`` lint) with no bearing
                on the submitted artifact. Same treatment as ``post_run``: runs,
                reports, labels ``NON-GATING``, does not block by default.

``--category`` and ``--only`` compose: a gate must satisfy both filters to run.
``--pre-pack`` composes with both as a third selection filter (see above).

The gate that reports ``INFRASTRUCTURE FAILURE, NOT A QUALITY RESULT`` is
``g_run_health``, a ``post_run`` gate. That phrase is preserved verbatim precisely
BECAUSE the gate no longer blocks: demoting its veto power must not cost it its
voice.

Submission modes (which obligation the adapter gates enforce):
    submit       (DEFAULT) This tree is what gets uploaded to Kaggle, so an
                 adapter MUST be declared in ``agent.yaml`` (``adapter:`` key
                 present) AND present in ``adapters/`` (populated). Either one
                 missing is a hard FAIL -- if there is no adapter for submission,
                 fail loudly and fail quickly (HARNESS_README.md:202-203).
    local_test   Explicit opt-in for validating the harness locally WITHOUT
                 shipping an adapter. The adapter must be explicitly turned OFF,
                 i.e. the ``adapter:`` key is absent from ``agent.yaml``. A
                 ``local_test`` run that still finds an adapter declared is a
                 hard FAIL: the local path must not pretend to use an adapter it
                 does not have. There is no middle state in which an adapter is
                 silently absent.

``submit`` is the default and is selected by precedence:
``--mode`` CLI flag > ``GATE_SUBMISSION_MODE`` env var > ``adapter.submission_mode``
in the policy file. Example::

    python3 scripts/check_submission.py --mode local_test
    GATE_SUBMISSION_MODE=local_test python3 scripts/check_submission.py
    python3 scripts/check_submission.py --mode submit  # beats the env var

In BOTH modes the adapter's base-model comparison is a WARN, never a FAIL: the
harness imposes no such rule (the adapter's own base string is never consulted
when vLLM picks serving weights), so a mismatch is a numerical-fidelity risk
worth surfacing, not a loading or harness violation.

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
# Gate categories — WHY a gate exists, which decides WHETHER it may veto a
# submission. Exactly one category per gate; the registry is the single source
# of truth and :func:`_assert_gate_categories` proves at load time that none of
# the 14 gates is left uncategorized.
#
#   submission  Asserts a property OF THE ARTIFACT BEING SHIPPED. A FAIL here is
#               a genuine defect in submission.zip / my_submission/, so it MUST
#               block the submission and sets a non-zero exit code.
#   post_run    Analyzes COMPLETED-RUN artifacts (cloud_results/results/).
#               A FAIL here is a verdict about a HISTORICAL RUN's infrastructure
#               health, not about whether the artifact being submitted is valid.
#               It must stay LOUD but must never veto a submission.
#   hygiene     Repository / code hygiene that has no bearing on the submitted
#               artifact at all (e.g. a docs/*.md lint). Must never veto a
#               submission.
#
# post_run and hygiene still RUN by default and still print their FAILs
# prominently -- a silent demotion would hide a real problem. Only their POWER
# over the exit code changes, and only when they are not explicitly selected.
# ---------------------------------------------------------------------------
CAT_SUBMISSION = "submission"
CAT_POST_RUN = "post_run"
CAT_HYGIENE = "hygiene"
GATE_CATEGORIES: Tuple[str, ...] = (CAT_SUBMISSION, CAT_POST_RUN, CAT_HYGIENE)

# The prefix used to label a non-gating FAIL in the rendered output. A reader
# must never see INFRASTRUCTURE FAILURE and be left guessing whether it blocks.
NON_GATING_LABEL = "NON-GATING"

# ---------------------------------------------------------------------------
# Validation PHASES — WHICH gates can produce a meaningful verdict YET.
#
# Deliberately NOT a fourth category. The category axis answers exactly one
# question: "may this gate's FAIL veto a submission?" (see GATE_CATEGORIES
# above). Phase membership answers a different, orthogonal question: "does this
# gate have the artifact it needs to have been built?" Folding the two together
# would demote the four zip gates to a non-submission category, and
# exit_code_for() grants veto power only to CAT_SUBMISSION -- so their FAILs
# would silently become NON-GATING in the default full run, which is precisely
# the check that must stay blocking AFTER the pack. Phase and veto power are
# separate mechanisms, kept separate.
#
# Every gate below opens submission.zip. Before the pack has run, each of them
# is judging an artifact that does not exist yet or is stale, and one of them
# (drift) can only be FIXED by the very step that a drift FAIL would block.
# ---------------------------------------------------------------------------
PRE_PACK_PHASE = "pre-pack"

#: The gates that read submission.zip and are therefore skipped in --pre-pack
#: mode. Asserted at load time below to be a subset of the registry and to
#: name no gate that does not exist.
ZIP_DEPENDENT_GATES: Tuple[str, ...] = (
    "g_submission_size_unpacked",
    "g_zip_directory_drift",
    "g_zip_root_layout",
    "g_disallowed_extensions",
)

#: The reason printed on every SKIPPED line, so no reader mistakes a skipped
#: gate for a passing one.
PRE_PACK_SKIP_REASON = "depends on a zip that has not been built yet"

#: The operator-visible label prefix for a skipped gate. Pinned as a literal for
#: the same reason NON_GATING_LABEL is: operator greps and CI must match it.
PRE_PACK_SKIP_LABEL = "SKIPPED (pre-pack)"

#: Stated in the summary so the skip set can never read as "everything passed".
#: The gate total is filled in by :func:`_pre_pack_phase_hint`, which can see
#: the fully-built registry; this is the template it fills.
PRE_PACK_PHASE_HINT_TEMPLATE = (
    "the full check (all {total} gates, including the {n} zip-dependent ones) "
    "runs AFTER the pack -- e.g. submit_safe.sh step 3"
)


def _pre_pack_phase_hint() -> str:
    """The summary sentence that names where the skipped gates DO get checked."""
    return PRE_PACK_PHASE_HINT_TEMPLATE.format(
        total=len(ALL_GATES), n=len(ZIP_DEPENDENT_GATES)
    )

# ---------------------------------------------------------------------------
# Submission-mode constants (adapter obligations; see the module docstring).
#
# The DEFAULT is 'submit': fail loudly if there is no adapter for submission.
# 'local_test' is the only opt-out, and it inverts the obligation -- the adapter
# must be explicitly turned OFF. These names are the *code-side* vocabulary; the
# effective default is read from policy (adapter.submission_mode) and the
# allowed set from policy (adapter.allowed_modes) so the policy file stays the
# single source of truth. No served-model or other policy literal is hardcoded
# here (a red-test asserts that).
# ---------------------------------------------------------------------------
MODE_SUBMIT = "submit"
MODE_LOCAL_TEST = "local_test"
DEFAULT_MODE = MODE_SUBMIT
ALLOWED_MODES = (MODE_SUBMIT, MODE_LOCAL_TEST)

# The environment variable that may override the policy's submission_mode. The
# --mode CLI flag still wins over this. Deliberately namespaced with GATE_ to
# avoid colliding with anything else in the environment.
MODE_ENV_VAR = "GATE_SUBMISSION_MODE"


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


def resolve_excluded_globs(policy: Dict[str, Dict[str, Any]]) -> Tuple[str, ...]:
    """Packaging exclusion globs, read from ``packaging.excluded_globs``.

    The policy file is FLAT, so this arrives as one comma-separated STRING; we
    split it here. This is the ONLY exclusion vocabulary in the codebase: the
    packer (scripts/submit_safe.sh) MUST consume the same key, and
    :func:`g_zip_directory_drift` MUST honour it, so the gate and the packer can
    never disagree about which files are junk. A second, divergent list would
    reintroduce exactly the drift bug this key exists to fix.
    """
    section = policy.get("packaging") or {}
    raw = section.get("excluded_globs")
    if raw is None:
        return ()
    if isinstance(raw, (list, tuple)):
        parts = [str(p) for p in raw]
    else:
        parts = str(raw).split(",")
    return tuple(p.strip() for p in parts if p.strip())


def _is_excluded(rel_path: str, globs: Sequence[str]) -> bool:
    """True when ``rel_path`` matches ANY exclusion glob (fnmatch semantics).

    ``fnmatch`` is used rather than ``PurePath.match`` because we need ``*`` to
    span ``/`` -- the same way the packer's ``zip -x`` and ``find -name`` filters
    behave for these patterns. The path is normalized to POSIX separators first
    so a Windows-style walk still compares cleanly.
    """
    from fnmatch import fnmatch
    normalized = rel_path.replace(os.sep, "/")
    for pattern in globs:
        if fnmatch(normalized, pattern):
            return True
    return False


def _resolve_allowed_modes(policy: Dict[str, Dict[str, Any]]) -> Tuple[str, ...]:
    """Allowed submission modes, from policy when present, else the constant.

    Every policy scalar reads back as a STRING, so we split the comma-separated
    ``adapter.allowed_modes`` value here. We always keep the two module
    constants in the set so a malformed policy cannot silently permit a mode the
    gate code has no branch for.
    """
    modes = set(ALLOWED_MODES)
    section = policy.get("adapter") or {}
    raw = section.get("allowed_modes")
    if isinstance(raw, str):
        for part in raw.split(","):
            name = part.strip().lower()
            if name:
                modes.add(name)
    return tuple(sorted(modes))


def resolve_submission_mode(policy: Dict[str, Dict[str, Any]],
                            cli_mode: Optional[str] = None,
                            environ: Optional[Dict[str, str]] = None) -> str:
    """Resolve the effective submission mode by precedence.

    Precedence (highest first): explicit ``--mode`` CLI flag > ``MODE_ENV_VAR``
    environment variable > ``adapter.submission_mode`` policy default. The
    policy default itself defaults to ``DEFAULT_MODE`` ('submit') when absent.

    Raises:
        ValueError: if the resolved value is not one of ``_resolve_allowed_modes``.
    """
    env = os.environ if environ is None else environ
    if cli_mode:
        mode = cli_mode.strip().lower()
    else:
        raw_env = env.get(MODE_ENV_VAR, "").strip()
        if raw_env:
            mode = raw_env.lower()
        else:
            section = policy.get("adapter") or {}
            mode = str(section.get("submission_mode", DEFAULT_MODE)).strip().lower()
            if not mode:
                mode = DEFAULT_MODE
    allowed = _resolve_allowed_modes(policy)
    if mode not in allowed:
        raise ValueError(
            f"unknown submission mode {mode!r}; allowed: {', '.join(allowed)}"
        )
    return mode


def _mode_source(cli_mode: Optional[str] = None,
                 policy: Optional[Dict[str, Dict[str, Any]]] = None) -> str:
    """Human-readable provenance of the mode (cli / env / policy), for evidence.

    When ``policy`` carries the private ``_resolved_mode`` stash written by
    ``run_all``, that stash's recorded provenance wins, because it reflects the
    ACTUAL resolution for this run (e.g. an explicit ``--mode`` the process env
    cannot see). Otherwise we report live env/policy provenance.
    """
    if policy is not None:
        stash = policy.get("_resolved_mode") or {}
        recorded = stash.get("source")
        if isinstance(recorded, str) and recorded.strip():
            return recorded.strip()
    env = os.environ
    if cli_mode:
        return "cli:--mode"
    if env.get(MODE_ENV_VAR, "").strip():
        return f"env:{MODE_ENV_VAR}"
    return "policy:adapter.submission_mode"


def _effective_mode(policy: Dict[str, Dict[str, Any]]) -> str:
    """The run-wide mode a gate must honor.

    ``run_all`` resolves the mode once (CLI > env > policy) and stashes it under
    the private ``_resolved_mode`` section so every gate in the run agrees. When a
    gate is called directly (red-tests import the module and call gates by hand,
    with a plain ``load_policy()`` mapping that has no stash), we resolve from the
    policy/env exactly as :func:`resolve_submission_mode` would. The stash
    therefore wins when present, and the default remains 'submit'.
    """
    stash = policy.get("_resolved_mode") or {}
    mode = stash.get("mode")
    if isinstance(mode, str) and mode.strip():
        return mode.strip().lower()
    try:
        return resolve_submission_mode(policy)
    except ValueError:
        return DEFAULT_MODE


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
    """agent.yaml adapter declaration, per the active submission mode.

    Mode semantics (see module docstring / gate_policy adapter.submission_mode):

    * ``submit`` (DEFAULT): agent.yaml MUST carry an ``adapter:`` key and it MUST
      equal the policy ``declared_name``. A missing key is a hard FAIL ("if there
      is no adapter for submission, fail it"); a wrong value is a hard FAIL.
    * ``local_test``: the adapter must be explicitly turned OFF, i.e. NO
      ``adapter:`` key in agent.yaml. If a declaration is still present, that is a
      hard FAIL -- the local path must not pretend to use an adapter it does not
      have. An absent key is the correct PASS for this mode.

    There is deliberately no middle state: in ``local_test`` a silent adapter is a
    FAIL, and in ``submit`` a silent (absent) adapter is a FAIL.
    """
    declared_name = str(_policy_get(policy, "adapter", "declared_name"))
    mode = _effective_mode(policy)
    agent_yaml = os.path.join(SUBMISSION_DIR, "agent.yaml")
    rel_agent = os.path.relpath(agent_yaml, REPO_ROOT)
    if not os.path.isfile(agent_yaml):
        return GateResult("g_adapter_declared", FAIL, "agent.yaml missing",
                          f"expected {rel_agent}", "Create agent.yaml.")
    found_line = None
    declarations = []  # (lineno, value) for every 'adapter:' line we saw
    with open(agent_yaml, "r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            stripped = line.strip()
            if stripped.startswith("adapter:"):
                value = stripped.partition(":")[2].strip()
                declarations.append((lineno, value))
                if value == declared_name:
                    found_line = (lineno, value)

    if mode == MODE_LOCAL_TEST:
        # Adapter must be explicitly OFF. Any 'adapter:' declaration is a FAIL.
        if declarations:
            lineno, value = declarations[0]
            detail = "; ".join(f"agent.yaml:{ln} 'adapter: {v}'" for ln, v in declarations)
            return GateResult(
                "g_adapter_declared", FAIL,
                f"local_test mode: agent.yaml still declares an adapter ('{value}')",
                f"{detail}; local_test requires the adapter be explicitly turned OFF "
                f"(no 'adapter:' key) so the local path does not pretend to use an adapter it lacks",
                f"Remove the 'adapter:' key from agent.yaml for a local_test run "
                f"(mode {mode}, from {_mode_source(None, policy)}), or run in 'submit' mode to ship it.",
            )
        return GateResult(
            "g_adapter_declared", PASS,
            f"local_test mode: agent.yaml declares no adapter (adapter explicitly OFF)",
            f"no 'adapter:' key in agent.yaml; mode={mode} (from {_mode_source(None, policy)})",
            "",
        )

    # submit mode: a declaration is REQUIRED.
    if found_line is None and declarations:
        lineno, value = declarations[0]
        return GateResult(
            "g_adapter_declared", FAIL,
            "agent.yaml adapter: value != required declared_name",
            f"agent.yaml:{lineno} 'adapter: {value}' != policy declared_name '{declared_name}'",
            f"Set 'adapter: {declared_name}' in agent.yaml (decision D9).",
        )
    if found_line is None:
        return GateResult(
            "g_adapter_declared", FAIL,
            "agent.yaml does not declare the required adapter",
            f"no 'adapter: {declared_name}' line found in agent.yaml; policy requires "
            f"'{declared_name}'; mode={mode} (from {_mode_source(None, policy)})",
            f"Add 'adapter: {declared_name}' to agent.yaml, or drop 'adapter' explicitly "
            f"via --mode {MODE_LOCAL_TEST} if this is a local (no-ship) run.",
        )
    lineno, value = found_line
    return GateResult("g_adapter_declared", PASS,
                      f"agent.yaml declares adapter '{value}'",
                      f"agent.yaml:{lineno} 'adapter: {value}'; mode={mode} "
                      f"(from {_mode_source(None, policy)})", "")


# --- 3. adapter present ----------------------------------------------------

def g_adapter_present(policy: Dict[str, Dict[str, Any]]) -> GateResult:
    """The adapters/ dir inside the submission is populated, per submission mode.

    * ``submit`` (DEFAULT): ``adapters/`` must exist AND be populated AND contain
      ``adapter_model.safetensors``. Missing, empty, or weights-absent is a hard
      FAIL -- shipping without an adapter means shipping no adapter.
    * ``local_test``: the adapter is explicitly OFF, so a populated ``adapters/``
      dir is neither required nor a defect. A present-but-empty dir PASSes (this
      mode is for validating the harness without shipping weights). The *declaration*
      inversion (an adapter still declared in agent.yaml) is enforced by
      :func:`g_adapter_declared`, not here.

    SCOPE -- THIS GATE READS THE DIRECTORY ONLY. It deliberately does not open
    ``submission.zip``: the zip is the graded artifact, and a second zip reader
    here would be a second vocabulary that can silently disagree with the packer.

    The zip-vs-directory invariant is not left unasserted -- it is owned by
    :func:`g_zip_directory_drift`, which hashes every file on both sides under the
    SAME ``packaging.excluded_globs``. Verified empirically: with an adapter
    present in ``my_submission/`` but absent from the zip, drift reports
    ``submission.zip is out of sync with my_submission/`` as a blocking
    ``submission``-category FAIL, and the reverse (zip-only adapter) drifts too.
    So a directory-only adapter cannot reach Kaggle undeclared.
    """
    adapters_subdir = str(_policy_get(policy, "adapter", "dir"))
    mode = _effective_mode(policy)
    adir = os.path.join(SUBMISSION_DIR, adapters_subdir)
    rel_dir = os.path.join(adapters_subdir, "")

    if not os.path.isdir(adir):
        if mode == MODE_LOCAL_TEST:
            return GateResult("g_adapter_present", PASS,
                              f"local_test mode: {adapters_subdir}/ absent (adapter explicitly OFF)",
                              f"{rel_dir} not present; mode={mode} (from {_mode_source(None, policy)}); "
                              "presence is not required when no adapter ships", "")
        return GateResult("g_adapter_present", FAIL, f"{adapters_subdir}/ missing in submission",
                          f"{rel_dir} not found under my_submission/; mode={mode} "
                          f"(from {_mode_source(None, policy)})",
                          f"Populate my_submission/{adapters_subdir}/ with the trained adapter "
                          f"(D9), or run in {MODE_LOCAL_TEST} mode if no adapter ships.")
    files = []
    for root, _dirs, names in os.walk(adir):
        for n in names:
            files.append(os.path.relpath(os.path.join(root, n), adir))
    if not files:
        if mode == MODE_LOCAL_TEST:
            return GateResult("g_adapter_present", PASS,
                              f"local_test mode: {adapters_subdir}/ present but empty (adapter OFF)",
                              f"{adapters_subdir}/ exists with 0 files; mode={mode} "
                              f"(from {_mode_source(None, policy)}); empty is fine when no adapter ships", "")
        return GateResult("g_adapter_present", FAIL, f"{adapters_subdir}/ is empty",
                          f"{adapters_subdir}/ exists but contains no files; mode={mode} "
                          f"(from {_mode_source(None, policy)})",
                          f"Install the adapter files into my_submission/{adapters_subdir}/, "
                          f"or run in {MODE_LOCAL_TEST} mode if no adapter ships.")
    weight = [f for f in files if f.endswith("adapter_model.safetensors")]
    detail = f"{len(files)} file(s); weights={'yes' if weight else 'NO'}; mode={mode}"
    if not weight:
        return GateResult("g_adapter_present", FAIL,
                          f"{adapters_subdir}/ has no adapter_model.safetensors",
                          detail, "Include adapter_model.safetensors (the harness requires it).")
    return GateResult("g_adapter_present", PASS, f"{adapters_subdir}/ populated with adapter",
                      detail, "")


# --- 4. adapter base model == served model EXACTLY -------------------------

def _find_adapter_config() -> Optional[str]:
    """Locate the adapter_config.json of the adapter that is actually GRADED.

    Only ``my_submission/adapters/`` counts. Staging directories are not part
    of the submission artifact, so a config there says nothing about what
    Kaggle would load -- warning about one is noise that masks a real signal.
    """
    candidate = os.path.join(SUBMISSION_DIR, "adapters", "main_lora", "adapter_config.json")
    return candidate if os.path.isfile(candidate) else None


def g_adapter_base_model(policy: Dict[str, Dict[str, Any]]) -> GateResult:
    """Advisory check: adapter_config base_model_name_or_path vs served model.

    This is a NUMERICAL-FIDELITY WARN in BOTH submission modes, never a FAIL.
    The harness imposes NO rule that an adapter's base must equal the served
    model: ``discover_adapters()`` (HARNESS_README.md:204) registers adapters as
    ``--lora-modules name=path`` and vLLM applies them to the already-loaded
    base, so the adapter's own base string is never consulted when choosing
    serving weights. ``ALLOWED_MODEL_NAMES`` (HARNESS_README.md:185) constrains
    the ``model:`` field declared in agent.yaml -- a different field.

    A mismatch (e.g. a bnb-4bit-trained adapter onto a QAT w4a16 served base) is
    a real quality risk worth surfacing, so it WARNs -- but it is NOT a loading or
    harness violation and does NOT demand the adapter be retrained. A clean match
    PASSes.
    """
    required_base = str(_policy_get(policy, "adapter", "required_base_model"))
    cfg = _find_adapter_config()
    if cfg is None:
        return GateResult("g_adapter_base_model", PASS,
                          "submission ships no adapter; base-model fidelity not applicable",
                          "no adapters/main_lora/adapter_config.json in my_submission/",
                          "")
    try:
        with open(cfg, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        return GateResult("g_adapter_base_model", WARN,
                          "adapter_config.json unreadable/invalid JSON (fidelity not assessed)",
                          f"{os.path.relpath(cfg, REPO_ROOT)}: {exc}",
                          "Advisory only. Fix the JSON if you want this fidelity signal.")
    base = data.get("base_model_name_or_path")
    rel = os.path.relpath(cfg, REPO_ROOT)
    if base is None:
        return GateResult("g_adapter_base_model", WARN,
                          "adapter_config.json has no base_model_name_or_path (fidelity not assessed)",
                          f"{rel}: key absent",
                          "Advisory only; the harness does not require this key to be set.")
    if base != required_base:
        return GateResult(
            "g_adapter_base_model", WARN,
            "adapter base model differs from served model (numerical-fidelity warning, NOT a harness rule)",
            f"{rel}: base_model_name_or_path={base!r} != served {required_base!r}. "
            "The harness imposes NO requirement that these match (discover_adapters() "
            "registers the adapter against the already-loaded base); this is a "
            "numerical-fidelity signal only, not a loading/harness violation.",
            "Advisory only; not a harness requirement (HARNESS_README.md has no "
            "rule on adapter base). A LoRA fit against a different quantization may "
            "degrade output fidelity — measure before shipping one.",
        )
    return GateResult("g_adapter_base_model", PASS,
                      "adapter base model matches served model",
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


def _dir_hashes(root: str, exclude: Sequence[str] = ()) -> Tuple[Dict[str, str], List[str]]:
    """Map relative path -> sha256 for every file under root (files only).

    Files matching ANY glob in ``exclude`` are SKIPPED and their relative paths
    returned separately, so the drift gate can say what it ignored instead of
    silently dropping the evidence. ``exclude`` comes from
    ``packaging.excluded_globs`` (see :func:`resolve_excluded_globs`) -- the same
    list the packer uses, which is what stops a correctly-excluded .DS_Store
    from being reported as a permanent "in dir not zip" drift.
    """
    out: Dict[str, str] = {}
    skipped: List[str] = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            if exclude and _is_excluded(rel, exclude):
                skipped.append(rel)
                continue
            try:
                with open(full, "rb") as fh:
                    out[rel] = _sha256_bytes(fh.read())
            except OSError:
                out[rel] = "<unreadable>"
    return out, sorted(skipped)


def _zip_hashes(zf: zipfile.ZipFile, exclude: Sequence[str] = ()) -> Tuple[Dict[str, str], List[str]]:
    out: Dict[str, str] = {}
    skipped: List[str] = []
    for info in zf.infolist():
        if info.is_dir():
            continue
        name = info.filename.lstrip("./")
        if exclude and _is_excluded(name, exclude):
            skipped.append(name)
            continue
        try:
            with zf.open(info) as fh:
                out[name] = _sha256_bytes(fh.read())
        except (zipfile.BadZipFile, OSError, RuntimeError):
            out[name] = "<unreadable>"
    return out, sorted(skipped)


def g_zip_directory_drift(policy: Dict[str, Dict[str, Any]]) -> GateResult:
    """Byte-identity between the zip's contents and the working directory.

    A directory can be correct while the zip is stale. Walk both, compare
    relative paths and content hashes, report every differing path. Handles the
    case where the zip predates the directory.

    BOTH sides are filtered through the shared ``packaging.excluded_globs`` list
    -- the same list the packer honours when it builds the zip. Without this,
    a file the packer CORRECTLY omitted (a stray .DS_Store) would be reported as
    "in dir not zip" and the gate would FAIL forever, blocking an otherwise
    valid submission. Files matched by the exclusion list are named in the
    evidence as ignored, so the filter is visible rather than silent.
    """
    exclude = resolve_excluded_globs(policy)
    if not os.path.isdir(SUBMISSION_DIR):
        return GateResult("g_zip_directory_drift", FAIL, "submission directory missing",
                          os.path.relpath(SUBMISSION_DIR, REPO_ROOT), "Restore my_submission/.")
    if not os.path.isfile(SUBMISSION_ZIP):
        return GateResult("g_zip_directory_drift", FAIL,
                          "submission.zip absent; cannot verify drift",
                          "submission.zip not found", "Pack submission.zip then re-check drift.")
    try:
        with zipfile.ZipFile(SUBMISSION_ZIP, "r") as zf:
            zh, zip_skipped = _zip_hashes(zf, exclude)
    except (zipfile.BadZipFile, OSError) as exc:
        return GateResult("g_zip_directory_drift", FAIL, "submission.zip unreadable", str(exc),
                          "Repack a valid submission.zip.")
    dh, dir_skipped = _dir_hashes(SUBMISSION_DIR, exclude)

    only_zip = sorted(set(zh) - set(dh))
    only_dir = sorted(set(dh) - set(zh))
    differing = sorted(k for k in set(zh) & set(dh) if zh[k] != dh[k])

    ignored_note = (
        f"; excluded {len(set(dir_skipped) | set(zip_skipped))} file(s) via "
        f"packaging.excluded_globs ({len(exclude)} globs): "
        + ", ".join(sorted(set(dir_skipped) | set(zip_skipped))[:8])
        + (" ..." if len(set(dir_skipped) | set(zip_skipped)) > 8 else "")
        if (dir_skipped or zip_skipped) else "; excluded 0 files (no junk present)"
    )

    if not (only_zip or only_dir or differing):
        return GateResult("g_zip_directory_drift", PASS,
                          f"zip and directory byte-identical ({len(dh)} files)",
                          f"compared {len(dh)} dir files vs {len(zh)} zip members; no diff"
                          + ignored_note, "")

    parts = []
    if only_dir:
        parts.append(f"in dir not zip ({len(only_dir)}): " + ", ".join(only_dir[:8]) + (" ..." if len(only_dir) > 8 else ""))
    if only_zip:
        parts.append(f"in zip not dir ({len(only_zip)}): " + ", ".join(only_zip[:8]) + (" ..." if len(only_zip) > 8 else ""))
    if differing:
        parts.append(f"content differs ({len(differing)}): " + ", ".join(differing[:8]) + (" ..." if len(differing) > 8 else ""))
    return GateResult("g_zip_directory_drift", FAIL,
                      "submission.zip is out of sync with my_submission/",
                      " | ".join(parts) + ignored_note,
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

def resolve_embedded_code_doc_exemptions(policy: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
    """Map of docs/*.md filename -> recorded exemption reason.

    Read from ``hygiene.embedded_code_doc_exemptions`` (a comma-separated
    filename list) and ``hygiene.embedded_code_doc_exemption_reasons`` (a
    comma-separated ``<filename>=<reason>`` list). The policy file is FLAT, so
    both arrive as single comma-separated STRINGs, exactly like
    ``packaging.excluded_globs`` -- see :func:`resolve_excluded_globs` for the
    same idiom. The REASON TEXT LIVES IN THE POLICY FILE, never in this logic;
    this function only splits it. Removing a filename from the policy
    immediately re-arms the gate for that doc.

    A filename present in the exemption list with no matching reason still gets
    a generic note, so an exemption can never become invisible -- but such an
    entry is under-documented and should be fixed in policy, not here.
    """
    section = policy.get("hygiene") or {}
    names_raw = section.get("embedded_code_doc_exemptions")
    if names_raw is None:
        return {}
    if isinstance(names_raw, (list, tuple)):
        names = [str(n) for n in names_raw]
    else:
        names = str(names_raw).split(",")
    reasons: Dict[str, str] = {}
    reasons_raw = section.get("embedded_code_doc_exemption_reasons")
    if reasons_raw is not None:
        parts = reasons_raw if isinstance(reasons_raw, (list, tuple)) else str(reasons_raw).split(",")
        for part in parts:
            doc, sep, why = str(part).partition("=")
            if sep and doc.strip():
                reasons[doc.strip()] = why.strip()
    out: Dict[str, str] = {}
    for name in names:
        doc = name.strip()
        if doc:
            out[doc] = reasons.get(doc, "recorded policy exemption (no reason recorded)")
    return out


def g_no_embedded_code_in_docs(policy: Dict[str, Dict[str, Any]]) -> GateResult:
    """No docs/*.md may hide a large escaped code literal.

    A working /health + /v1/chat/completions probe was hidden inside a markdown
    string literal, invisible to any grep of .py files, which caused earlier
    research to wrongly conclude no such check existed. We flag any single
    markdown line longer than EMBED_THRESHOLD chars (a large escaped literal).
    Ordinary prose and short fenced snippets are far below this; the real
    offending doc has lines up to ~110k chars.

    A doc named in ``hygiene.embedded_code_doc_exemptions`` is still SCANNED, but
    its long lines are not counted as offenders -- and the exemption is always
    REPORTED (doc name + the reason recorded in policy) so it reads as a
    deliberate decision, never a silent skip.
    """
    EMBED_THRESHOLD = 5000
    if not os.path.isdir(DOCS_DIR):
        return GateResult("g_no_embedded_code_in_docs", WARN, "docs/ directory missing",
                          os.path.relpath(DOCS_DIR, REPO_ROOT), "No docs to scan.")
    exempt = resolve_embedded_code_doc_exemptions(policy)
    offenders = []
    exempt_seen = []
    for name in sorted(os.listdir(DOCS_DIR)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(DOCS_DIR, name)
        is_exempt = name in exempt
        hit = 0
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                for lineno, line in enumerate(fh, 1):
                    if len(line.rstrip("\n")) > EMBED_THRESHOLD:
                        hit += 1
                        if not is_exempt:
                            offenders.append((name, lineno, len(line.rstrip("\n"))))
        except OSError:
            continue
        if is_exempt and hit:
            exempt_seen.append(f"docs/{name}: EXEMPT by hygiene.embedded_code_doc_exemptions "
                               f"({hit} line(s) over threshold) -- {exempt[name]}")
    notes = "; ".join(exempt_seen)
    if offenders:
        detail = ", ".join(f"docs/{n}:{ln} ({sz} chars)" for n, ln, sz in offenders[:8])
        if len(offenders) > 8:
            detail += f" ... (+{len(offenders) - 8} more)"
        evidence = f"threshold={EMBED_THRESHOLD} chars; {detail}"
        if notes:
            evidence = f"{notes}; {evidence}"
        return GateResult("g_no_embedded_code_in_docs", FAIL,
                          f"{len(offenders)} line(s) contain a large escaped code literal",
                          evidence,
                          "Extract embedded code literals into real .py files (D20/D21) and "
                          "annotate the doc to point at them.")
    if notes:
        return GateResult("g_no_embedded_code_in_docs", PASS,
                          "no docs/*.md contains a large embedded code literal "
                          "(policy-exempt doc(s) intentionally embed source)",
                          f"threshold={EMBED_THRESHOLD} chars; scanned {DOCS_DIR}; {notes}", "")
    return GateResult("g_no_embedded_code_in_docs", PASS,
                      "no docs/*.md contains a large embedded code literal",
                      f"threshold={EMBED_THRESHOLD} chars; scanned {DOCS_DIR}", "")


# ===========================================================================
# Gate registry — pre-submission, then post-run (D2 separation)
#
# Each gate carries EXACTLY ONE category (see GATE_CATEGORIES). The category --
# not the list a gate happens to sit in -- decides whether a FAIL may veto a
# submission. That is why g_no_embedded_code_in_docs, which is physically listed
# under POST_RUN_GATES for output-sectioning reasons, is categorized 'hygiene':
# it lints docs/*.md and says nothing about the artifact being shipped.
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

# --- THE classification: gate name -> category ------------------------------
# Exactly one category per gate. Keys here are asserted to be a bijection onto
# the 14 registered gates by _assert_gate_categories() at import time, so
# adding a gate without classifying it is a hard import-time failure rather
# than a silently-uncategorized gate whose FAIL nobody knows how to weigh.
#
# g_adapter_base_model is categorized 'submission' even though it is WARN-only
# by design: it inspects an artifact INSIDE my_submission/, so it is a
# submission-category check. Categorizing it does not grant it veto power --
# WARN never affects the exit code (unchanged semantics).
GATE_CATEGORY: Dict[str, str] = {
    # --- submission: a FAIL is a real defect in the artifact being shipped ---
    "g_required_files": CAT_SUBMISSION,
    "g_adapter_declared": CAT_SUBMISSION,
    "g_adapter_present": CAT_SUBMISSION,
    "g_adapter_base_model": CAT_SUBMISSION,   # WARN-only; category != veto power
    "g_tool_budget_parity": CAT_SUBMISSION,
    "g_prompt_ladder_consistency": CAT_SUBMISSION,
    "g_sampling_no_thinking_level": CAT_SUBMISSION,
    "g_sampling_output_cap": CAT_SUBMISSION,
    "g_submission_size_unpacked": CAT_SUBMISSION,
    "g_zip_directory_drift": CAT_SUBMISSION,
    "g_zip_root_layout": CAT_SUBMISSION,
    "g_disallowed_extensions": CAT_SUBMISSION,
    # --- post_run: a verdict about a HISTORICAL run, not about this artifact ---
    "g_run_health": CAT_POST_RUN,
    # --- hygiene: repository hygiene, irrelevant to the shipped artifact ---
    "g_no_embedded_code_in_docs": CAT_HYGIENE,
}


def _assert_gate_categories(
    registry: Sequence[Tuple[str, Callable[[Dict[str, Dict[str, Any]]], GateResult]]],
    categories: Dict[str, str],
) -> None:
    """Fail loudly at LOAD time if any gate lacks exactly one valid category.

    A gate that is registered but uncategorized would have undefined veto power
    -- exactly the ambiguity this registry exists to remove -- so we raise rather
    than guess. Also catches a category typo and a category naming a gate that
    does not exist.
    """
    names = [n for n, _fn in registry]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise AssertionError(f"duplicate gate(s) in registry: {', '.join(dupes)}")

    uncategorized = [n for n in names if n not in categories]
    if uncategorized:
        raise AssertionError(
            "gate(s) registered without a category: "
            + ", ".join(uncategorized)
            + f"; every gate needs exactly one of {', '.join(GATE_CATEGORIES)}"
        )
    invalid = sorted({c for c in categories.values() if c not in GATE_CATEGORIES})
    if invalid:
        raise AssertionError(
            f"invalid gate categor{'y' if len(invalid) == 1 else 'ies'}: "
            + ", ".join(repr(c) for c in invalid)
            + f"; allowed: {', '.join(GATE_CATEGORIES)}"
        )
    orphans = sorted(c for c in categories if c not in set(names))
    if orphans:
        raise AssertionError(
            f"categor{'y' if len(orphans) == 1 else 'ies'} name gate(s) that are not "
            f"registered: {', '.join(orphans)}"
        )


# Proven at import time. If this raises, the module does not load and no gate
# can run in an undefined state.
_assert_gate_categories(ALL_GATES, GATE_CATEGORY)


def _assert_pre_pack_phase() -> None:
    """Fail loudly at LOAD time if the pre-pack skip set is inconsistent.

    Three ways it could rot silently, each of which would make ``--pre-pack``
    quietly wrong:
      * a name in the skip set that is not a registered gate (the skip would
        never happen, and the gate would run on a missing artifact);
      * a duplicated name (the SKIPPED line would print twice);
      * an EMPTY skip set (the flag would degrade to a no-op that claims to have
        skipped something).
    """
    registered = {n for n, _fn in ALL_GATES}
    unknown = sorted(set(ZIP_DEPENDENT_GATES) - registered)
    if unknown:
        raise AssertionError(
            "pre-pack skip set names gate(s) that are not registered: "
            + ", ".join(unknown)
        )
    dupes = sorted({g for g in ZIP_DEPENDENT_GATES if ZIP_DEPENDENT_GATES.count(g) > 1})
    if dupes:
        raise AssertionError(
            "pre-pack skip set contains duplicate(s): " + ", ".join(dupes)
        )
    if not ZIP_DEPENDENT_GATES:
        raise AssertionError(
            "pre-pack skip set is empty; --pre-pack would silently degrade to a no-op"
        )


_assert_pre_pack_phase()


def skipped_by_phase(gate_name: str, phase: Optional[str] = None) -> bool:
    """True when ``gate_name`` cannot produce a meaningful verdict in ``phase``.

    With no ``phase`` (the default full run) nothing is ever skipped -- the full
    check stays the full check. Only ``PRE_PACK_PHASE`` narrows the set.
    """
    if phase is None or phase != PRE_PACK_PHASE:
        return False
    return gate_name in ZIP_DEPENDENT_GATES


def category_of(gate_name: str) -> str:
    """The category of a gate name (raises if unregistered -- see the assert)."""
    return GATE_CATEGORY[gate_name]


# Section labels for output (D2: post-run kept clearly separate).
_SECTION = {}
for _n, _f in PRE_SUBMISSION_GATES:
    _SECTION[_n] = "PRE-SUBMISSION"
for _n, _f in POST_RUN_GATES:
    _SECTION[_n] = "POST-RUN"


def selected_gates(only: Optional[Sequence[str]] = None,
                   category: Optional[str] = None,
                   phase: Optional[str] = None,
                   ) -> Tuple[List[Tuple[str, Callable[[Dict[str, Dict[str, Any]]], GateResult]]],
                              List[str]]:
    """Split the registry into (gates that WILL run, gates SKIPPED by phase).

    A gate must satisfy all three filters to run: ``--only``, ``--category`` and
    the phase. ``phase`` alone decides the skip, so this function is the single
    place that knows both sets and the two can never disagree.

    A gate excluded by ``only``/``category`` is NOT reported as phase-skipped:
    it was not selected at all, and calling that "skipped" would misattribute an
    operator's own filter choice to the pre-pack phase. Ordering follows
    ``ALL_GATES`` so both lists render in registry order.
    """
    wanted = set(only) if only else None
    will_run: List[Tuple[str, Callable[[Dict[str, Dict[str, Any]]], GateResult]]] = []
    skipped: List[str] = []
    for name, fn in ALL_GATES:
        if wanted and name not in wanted:
            continue
        if category is not None and category_of(name) != category:
            continue
        if skipped_by_phase(name, phase):
            skipped.append(name)
            continue
        will_run.append((name, fn))
    return will_run, skipped


def run_all(policy: Optional[Dict[str, Dict[str, Any]]] = None,
            only: Optional[Sequence[str]] = None,
            cli_mode: Optional[str] = None,
            category: Optional[str] = None,
            phase: Optional[str] = None) -> List[GateResult]:
    """Run every gate (or the subset named in ``only``) and return results.

    The effective submission mode (CLI > env > policy, see
    :func:`resolve_submission_mode`) is resolved once here and stashed into the
    ``policy`` mapping (under the private ``_resolved_mode`` section) so the
    adapter gates -- whose signatures take only ``policy`` -- all observe the
    SAME mode for the whole run without a module-level global. A gate that
    raises is converted into a FAIL result so one broken gate never aborts the
    whole run (robustness requirement).

    ``category`` filters to a single category and COMPOSES with ``only``: a gate
    must satisfy both to run (``only=None`` means no name filter, so a category
    alone selects the whole category). Selection changes which gates RUN, never
    a gate's verdict -- a FAIL is still a FAIL.

    ``phase`` additionally narrows the run to the gates that can produce a
    meaningful verdict yet (see the module docstring). It is a third selection
    filter with the same property: it changes which gates RUN, never a verdict,
    and never a selected gate's status. Skipped gates are simply absent from the
    return value; :func:`selected_gates` reports which ones and the renderer
    prints them as labelled SKIPPED lines. ``phase=None`` (the default) skips
    nothing, so the full run stays the full run.
    """
    if policy is None:
        policy = load_policy()
    if category is not None and category not in GATE_CATEGORIES:
        raise ValueError(
            f"unknown category {category!r}; allowed: {', '.join(GATE_CATEGORIES)}"
        )
    try:
        effective_mode = resolve_submission_mode(policy, cli_mode=cli_mode)
        effective_source = _mode_source(cli_mode)
    except ValueError:
        # An unknown mode should not crash the library entrypoint (red-tests call
        # run_all directly). The CLI validates the mode and reports a FATAL before
        # ever getting here; this is the defensive fallback.
        effective_mode = DEFAULT_MODE
        effective_source = "fallback:default(submit)"
    policy.setdefault("_resolved_mode", {})["mode"] = effective_mode
    policy["_resolved_mode"]["source"] = effective_source
    selected, _skipped = selected_gates(only=only, category=category, phase=phase)
    results: List[GateResult] = []
    for name, fn in selected:
        try:
            results.append(fn(policy))
        except Exception as exc:  # noqa: BLE001 - deliberate: never crash the runner
            results.append(GateResult(name, FAIL, f"gate raised an unhandled error: {exc}",
                                     f"{type(exc).__name__}: {exc}",
                                     "Inspect this gate; an exception is a bug, not a verdict."))
    return results


# ---------------------------------------------------------------------------
# Exit semantics — SEPARATED from reporting
# ---------------------------------------------------------------------------
def partition_fails(results: Sequence[GateResult]) -> Tuple[List[GateResult], List[GateResult]]:
    """Split FAIL results into (gating, non_gating) by gate CATEGORY.

    A FAIL is *gating* only when its gate is in the ``submission`` category.
    ``post_run`` and ``hygiene`` FAILs are real and must be REPORTED, but they
    are verdicts about a historical run or about repository hygiene, not about
    whether the artifact being submitted is valid -- so they must not veto it.
    """
    gating: List[GateResult] = []
    non_gating: List[GateResult] = []
    for r in results:
        if r.status != FAIL:
            continue
        # An unknown name cannot happen (the registry is asserted at load time),
        # but default to gating rather than silently waiving an unclassifiable
        # FAIL -- fail closed if this code ever outlives the registry.
        if GATE_CATEGORY.get(r.name, CAT_SUBMISSION) == CAT_SUBMISSION:
            gating.append(r)
        else:
            non_gating.append(r)
    return gating, non_gating


def exit_code_for(results: Sequence[GateResult], selected_category: Optional[str] = None) -> int:
    """The process exit code: 1 iff a GATING FAIL is present.

    ``selected_category`` is the explicit ``--category`` the operator asked for.
    When the operator EXPLICITLY selects a non-submission category, they are
    asking specifically about that category, so a FAIL in it MUST be loud in the
    exit code too -- that is how ``--category post_run`` can ever be used as a
    CI signal about run health. With no explicit selection (the default run, or a
    bare ``--only``), the exit code is governed SOLELY by submission-category
    FAILs, which is the whole point of the change.
    """
    gating, non_gating = partition_fails(results)
    if gating:
        return 1
    if non_gating and selected_category is not None and selected_category != CAT_SUBMISSION:
        return 1
    return 0


# ---------------------------------------------------------------------------
# Output rendering
# ---------------------------------------------------------------------------
_STATUS_MARK = {PASS: "PASS", FAIL: "FAIL", WARN: "WARN"}


def render_text(results: List[GateResult], mode: Optional[str] = None,
                skipped: Optional[Sequence[str]] = None,
                phase: Optional[str] = None) -> str:
    """Render the human-readable report.

    A non-gating FAIL is labelled with an explicit ``NON-GATING:`` prefix and its
    category, so no reader can mistake a historical-run verdict for a
    submission blocker. The gate's own message is preserved verbatim inside the
    line -- notably ``INFRASTRUCTURE FAILURE, NOT A QUALITY RESULT`` -- because
    that phrase is the signal we must not lose while demoting its veto power.

    Gates skipped by ``phase`` (``--pre-pack``) are rendered as explicit
    ``SKIPPED (pre-pack): <gate>`` lines in their registry position, so a skip is
    as visible as a verdict. They are counted separately from the pass/fail/warn
    totals and NAMED in the summary together with the sentence saying where they
    are actually checked, because "10 passed, 0 failed" must never be readable as
    "everything was verified".
    """
    lines: List[str] = []
    skipped = list(skipped or [])
    if mode:
        lines.append(f"submission mode: {mode}")
        lines.append("")
    if phase == PRE_PACK_PHASE:
        lines.append(
            f"phase: {PRE_PACK_PHASE} -- validating the SOURCE TREE; "
            f"{len(skipped)} zip-dependent gate(s) are deferred to the post-pack check"
        )
        lines.append("")
    last_section = None
    # One ordered walk over the registry emits both verdicts and skips in
    # registry order, so a skipped gate appears exactly where it would have run
    # and its section header opens even when nothing in it produced a verdict.
    by_name = {r.name: r for r in results}
    skipped_set = set(skipped)
    for name, _fn in ALL_GATES:
        if name in skipped_set:
            if name not in by_name:
                section = _SECTION.get(name, "GATE")
                if section != last_section:
                    lines.append("")
                    lines.append(f"== {section} ==")
                    last_section = section
                lines.append(f"[{PRE_PACK_SKIP_LABEL}] {name}: {PRE_PACK_SKIP_REASON}")
            continue
        r = by_name.get(name)
        if r is None:
            continue
        section = _SECTION.get(r.name, "GATE")
        if section != last_section:
            lines.append("")
            lines.append(f"== {section} ==")
            last_section = section
        mark = _STATUS_MARK.get(r.status, r.status)
        category = GATE_CATEGORY.get(r.name)
        non_gating = r.status == FAIL and category != CAT_SUBMISSION
        if non_gating:
            lines.append(
                f"[{mark}] {NON_GATING_LABEL}: {r.name} FAILED ({category} category) "
                f"-- reported, does not block submission: {r.message}"
            )
        else:
            lines.append(f"[{mark}] {r.name}: {r.message}")
    # Defensive: a caller may hand us a result for a gate that is not in the
    # registry (the old renderer printed whatever it was given). Never drop a
    # verdict just because the registry walk did not know about it.
    _registered = {n for n, _fn in ALL_GATES}
    for r in results:
        if r.name in _registered:
            continue
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
    gating, non_gating = partition_fails(results)
    lines.append("")
    lines.append(f"{n_pass} passed, {n_fail} failed, {n_warn} warnings (of {len(results)} gates)")
    if skipped:
        lines.append(
            f"{PRE_PACK_SKIP_LABEL}: {len(skipped)} gate(s) skipped, NOT verified: "
            + ", ".join(skipped)
        )
        lines.append(f"  {_pre_pack_phase_hint()}")
    lines.append(
        f"exit code governed SOLELY by '{CAT_SUBMISSION}'-category FAILs: "
        f"{len(gating)} gating FAIL(s), {len(non_gating)} non-gating FAIL(s) "
        f"({', '.join(sorted(r.name for r in non_gating)) if non_gating else 'none'})"
    )
    if non_gating:
        lines.append(
            f"{NON_GATING_LABEL}: "
            + "; ".join(
                f"{r.name} FAILED ({GATE_CATEGORY.get(r.name, 'unclassified')} category) "
                f"-- reported, does not block submission"
                for r in non_gating
            )
        )
    if gating:
        lines.append("BLOCKING: " + "; ".join(f"{r.name} ({CAT_SUBMISSION})" for r in gating)
                     + " -- submission must not proceed")
    return "\n".join(lines)


def to_json(results: List[GateResult], mode: Optional[str] = None,
            skipped: Optional[Sequence[str]] = None,
            phase: Optional[str] = None) -> str:
    """Machine-readable JSON.

    The per-gate result shape is UNCHANGED (``name``, ``status``, ``message``,
    ``evidence``, ``remediation``). The category is reported as a sibling
    ``category`` key per result and summarized in ``gating``/``non_gating`` --
    additive only, so an existing consumer of the five original keys keeps
    working. The phase keys (``phase``, ``skipped``) are likewise additive: a
    full run emits ``phase: null`` and an empty ``skipped`` list.
    """
    gating, non_gating = partition_fails(results)
    skipped = list(skipped or [])
    payload = {
        "mode": mode,
        "phase": phase,
        "skipped": skipped,
        "results": [
            dict(asdict(r), category=GATE_CATEGORY.get(r.name, "unclassified"),
                 gating=(r.status == FAIL and GATE_CATEGORY.get(r.name) == CAT_SUBMISSION))
            for r in results
        ],
        "summary": {
            "passed": sum(1 for r in results if r.status == PASS),
            "failed": sum(1 for r in results if r.status == FAIL),
            "warnings": sum(1 for r in results if r.status == WARN),
            "total": len(results),
            "skipped_count": len(skipped),
            "gating_failures": [r.name for r in gating],
            "non_gating_failures": [r.name for r in non_gating],
        },
    }
    return json.dumps(payload, indent=2)


def render_classification_table() -> str:
    """Human-readable gate -> category table (the classification, item 5).

    Also names the PHASE column, so a reader can see at a glance which gates
    need a packed zip and would therefore be skipped by ``--pre-pack``.
    """
    lines = ["gate".ljust(30) + "category".ljust(14) + "runs-by-default".ljust(17)
             + "FAIL blocks submission".ljust(24) + "needs zip"]
    lines.append("-" * 104)
    for name, _fn in ALL_GATES:
        cat = GATE_CATEGORY[name]
        blocks = "YES" if cat == CAT_SUBMISSION else "no"
        needs_zip = "yes (skipped by --pre-pack)" if name in ZIP_DEPENDENT_GATES else "no"
        lines.append(name.ljust(30) + cat.ljust(14) + "yes".ljust(17)
                     + blocks.ljust(24) + needs_zip)
    lines.append("-" * 104)
    counts: Dict[str, int] = {c: 0 for c in GATE_CATEGORIES}
    for name, _fn in ALL_GATES:
        counts[GATE_CATEGORY[name]] += 1
    lines.append(f"total gates: {len(ALL_GATES)}; classified: {len(GATE_CATEGORY)}; "
                 + ", ".join(f"{c}={counts[c]}" for c in GATE_CATEGORIES))
    lines.append(f"zip-dependent (skipped in --pre-pack): {len(ZIP_DEPENDENT_GATES)}; "
                 f"pre-pack runs {len(ALL_GATES) - len(ZIP_DEPENDENT_GATES)}")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ironclad submission gates (Gemma 4 Kaggle).",
        epilog=(
            "Submission modes (default: submit). In 'submit', an adapter MUST be "
            "declared in agent.yaml AND present in adapters/, else FAIL. In "
            "'local_test', the adapter MUST be explicitly OFF (no 'adapter:' key); "
            "a still-declared adapter FAILs. Precedence: --mode > "
            f"{MODE_ENV_VAR} env var > policy adapter.submission_mode.\n"
            f"\n"
            f"Gate categories. Every gate is exactly one of: "
            f"{', '.join(GATE_CATEGORIES)}.\n"
            f"  {CAT_SUBMISSION}  a defect in the artifact being shipped; a FAIL "
            f"blocks the submission and sets a non-zero exit.\n"
            f"  {CAT_POST_RUN}  a verdict about a COMPLETED RUN's health, not "
            f"about the artifact; reported, does not block.\n"
            f"  {CAT_HYGIENE}  repository hygiene, irrelevant to the artifact; "
            f"reported, does not block.\n"
            f"With no flags, ALL gates run but the exit code is governed SOLELY by "
            f"{CAT_SUBMISSION}-category FAILs. Passing --category for a "
            f"non-{CAT_SUBMISSION} category makes that category's FAILs exit "
            f"non-zero too (you asked about it specifically). --only and "
            f"--category compose.\n"
            f"\n"
            f"TWO PHASES (--pre-pack). Four gates read submission.zip: "
            f"{', '.join(ZIP_DEPENDENT_GATES)}. Before a pack, their verdict is about "
            f"an artifact that does not exist yet, and g_zip_directory_drift can only "
            f"be FIXED by the pack -- so judging it early can refuse to proceed to the "
            f"very step that would resolve the refusal. --pre-pack therefore skips "
            f"exactly those four, printing an explicit '{PRE_PACK_SKIP_LABEL}' line "
            f"and a summary count for each; every other gate runs and keeps its verdict, "
            f"so a genuine pre-pack {CAT_SUBMISSION} FAIL still exits non-zero. Use it "
            f"to validate the SOURCE TREE, then run the full check on the FINISHED zip."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--only", action="append", metavar="GATE",
                        help="run only the named gate (repeatable; composes with --category)")
    parser.add_argument("--category", choices=GATE_CATEGORIES, default=None,
                        help=f"run only gates in this category ({', '.join(GATE_CATEGORIES)}); "
                             f"composes with --only. Selecting a non-{CAT_SUBMISSION} "
                             f"category makes its FAILs exit non-zero")
    parser.add_argument("--show-categories", action="store_true",
                        help="print the gate -> category classification table and exit 0")
    parser.add_argument("--pre-pack", action="store_true",
                        help="validate the SOURCE TREE only: run every gate EXCEPT the "
                             f"{len(ZIP_DEPENDENT_GATES)} that read submission.zip "
                             f"({', '.join(ZIP_DEPENDENT_GATES)}), printing one "
                             f"'{PRE_PACK_SKIP_LABEL}' line per skipped gate. Use this "
                             "BEFORE packing (step 1 of submit_safe.sh); the full check "
                             "runs after the pack (step 3) and is what validates the "
                             "artifact that will be uploaded. A genuine pre-pack "
                             f"{CAT_SUBMISSION} FAIL still exits non-zero.")
    parser.add_argument("--mode", choices=ALLOWED_MODES, default=None,
                        help="submission mode (default: submit); overrides "
                             f"{MODE_ENV_VAR} and the policy default")
    args = parser.parse_args(argv)

    if args.show_categories:
        print(render_classification_table())
        return 0

    try:
        policy = load_policy()
    except (OSError, KeyError) as exc:
        print(f"FATAL: could not load gate policy ({POLICY_PATH}): {exc}", file=sys.stderr)
        return 1

    unknown = [g for g in (args.only or []) if g not in dict(ALL_GATES)]
    if unknown:
        print(f"FATAL: unknown gate(s): {', '.join(unknown)}", file=sys.stderr)
        return 1

    try:
        effective_mode = resolve_submission_mode(policy, cli_mode=args.mode)
    except ValueError as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        return 1

    phase = PRE_PACK_PHASE if args.pre_pack else None
    # selected_gates and run_all must agree on what runs, so derive the skip set
    # from the SAME predicate (run_all applies it identically).
    _selected, skipped = selected_gates(only=args.only, category=args.category,
                                         phase=phase)
    results = run_all(policy, only=args.only, cli_mode=args.mode,
                      category=args.category, phase=phase)

    if args.json:
        print(to_json(results, mode=effective_mode, skipped=skipped, phase=phase))
    else:
        print(render_text(results, mode=effective_mode, skipped=skipped,
                          phase=phase))
    # Exit code: governed ONLY by submission-category FAILs, unless the operator
    # explicitly selected a non-submission category (see exit_code_for).
    return exit_code_for(results, selected_category=args.category)


if __name__ == "__main__":
    raise SystemExit(main())
