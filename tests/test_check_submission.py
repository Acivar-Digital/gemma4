#!/usr/bin/env python3
"""Red-proof test suite for ``scripts/check_submission.py``.

Principle: every FAIL-severity gate must be proven RED against a REAL
already-broken artifact that exists in this repo, never a synthetic fixture
hand-made solely to trip a code path. A gate that cannot be shown red is
skipped and reported as unproven, not quietly passed.

Real broken artifacts used (none are created or mutated by this suite):
  * adapters_staging/main_lora/adapter_config.json -> wrong base model
    (unsloth/gemma-4-31B-it-unsloth-bnb-4bit != served gemma-4-31b-it-qat-w4a16-ct).
  * cloud_results/results/ -> the real 0/129 degenerate Gemma run
    (129 rows, 0 resolved, 117 empty patches, 77/95 zero-completion traces).
  * submission.zip -> genuinely stale vs my_submission/ (extra root skill
    copies, stale prompts/main.md).
  * docs/gemma-and-the-shape-of-doubt.md -> a real ~110k-char escaped code
    literal.
  * The historical main.md turn-ladder contradiction (Turn 11 vs Turn 13) is
    reproduced verbatim in a tmp file from the known past text.

The suite NEVER writes to my_submission/, submission.zip, adapters_staging/ or
cloud_results/. Any artifact that must be varied is copied into ``tmp_path``
and the gate is pointed at the copy by monkeypatching the module's path
constants (the gate functions read these module globals at call time).

Run with:
    python3 -m pytest tests/test_check_submission.py -v
"""

from __future__ import annotations

import ast
import importlib.util
import os
import sys
import zipfile

import pytest

# ---------------------------------------------------------------------------
# Import the module under test the same way the sibling suite does:
# spec_from_file_location, but we MUST register it in sys.modules BEFORE
# exec_module because the module uses `from __future__ import annotations`
# together with @dataclass; the dataclass machinery resolves the defining
# module via sys.modules and would raise AttributeError('NoneType') otherwise.
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK_PATH = os.path.join(REPO_ROOT, "scripts", "check_submission.py")


def _load_check_submission():
    spec = importlib.util.spec_from_file_location("check_submission", CHECK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_submission"] = module  # register BEFORE exec
    spec.loader.exec_module(module)
    return module


cs = _load_check_submission()

# Snapshot the real, immutable path constants so each test can be restored.
_REAL_PATHS = {
    name: getattr(cs, name)
    for name in ("SUBMISSION_DIR", "SUBMISSION_ZIP", "ADAPTERS_STAGING",
                 "TASK_RESULTS", "TRACES_DIR", "DOCS_DIR")
}


@pytest.fixture(autouse=True)
def _restore_module_paths():
    """Guarantee no test can leak a monkeypatched path into another test.

    We restore by direct assignment in teardown (not by relying on pytest's
    monkeypatch, because some tests assign via ``monkeypatch.setattr`` and some
    assign directly). Restoring unconditionally keeps the real-artifact tests
    honest: if a temp-dir test forgot to reset, the next real-artifact test
    would still see the true repo state.
    """
    yield
    for name, value in _REAL_PATHS.items():
        setattr(cs, name, value)


@pytest.fixture(scope="module")
def policy():
    """The real central gate policy, loaded through the module's own loader."""
    return cs.load_policy()


def _point_all_at_empty(empty_root, monkeypatch):
    """Point every artifact path constant at an empty directory tree.

    Used to prove the gates degrade to a structured verdict (never an
    exception) when their inputs are absent.
    """
    for name, value in {
        "SUBMISSION_DIR": os.path.join(empty_root, "my_submission"),
        "SUBMISSION_ZIP": os.path.join(empty_root, "submission.zip"),
        "ADAPTERS_STAGING": os.path.join(empty_root, "adapters_staging"),
        "TASK_RESULTS": os.path.join(empty_root, "cloud_results", "results", "task_results.jsonl"),
        "TRACES_DIR": os.path.join(empty_root, "cloud_results", "results", "traces"),
        "DOCS_DIR": os.path.join(empty_root, "docs"),
    }.items():
        monkeypatch.setattr(cs, name, value)


# ===========================================================================
# POSITIVE tests — the gate correctly PASSes on a HEALTHY real artifact.
# ===========================================================================

def test_g_tool_budget_parity_passes_on_current_prompt(policy):
    """main.md and eval_config both say 40 -> the real gate PASSes.

    Proves the parity gate is not stuck-red and really compares equal values.
    """
    result = cs.g_tool_budget_parity(policy)
    assert result.status == cs.PASS, (
        f"expected PASS on the real current prompt, got {result.status}: "
        f"{result.message} | {result.evidence}"
    )
    # Evidence must cite the real files and the agreed number.
    assert "main.md:" in result.evidence
    assert "eval_config.yaml:" in result.evidence
    assert "40" in result.message


def test_g_sampling_no_thinking_level_passes(policy):
    """configs/sampling.yaml has no thinking_level -> the real gate PASSes.

    Proves the forbidden-key gate is not stuck-red on the healthy tree.
    """
    result = cs.g_sampling_no_thinking_level(policy)
    assert result.status == cs.PASS, (
        f"expected PASS (no forbidden key), got {result.status}: {result.message} | {result.evidence}"
    )
    assert "thinking_level" in result.message
    assert "absent" in result.message


def test_g_prompt_ladder_consistency_passes_on_current_prompt(policy):
    """The CORRECTED main.md (Turns 1-10 / Turn 11 / 12-32 / 33-36) -> PASS.

    Proves the ladder gate does not false-positive on a consistent ladder.
    """
    result = cs.g_prompt_ladder_consistency(policy)
    assert result.status == cs.PASS, (
        f"expected PASS on the corrected prompt, got {result.status}: "
        f"{result.message} | {result.evidence}"
    )
    # The real prompt's consistent schedule must appear in the evidence.
    assert "Turns1–10" in result.evidence
    assert "Turns12–32" in result.evidence


def test_g_required_files_passes(policy):
    """All required submission files + 5 skills are present -> the gate PASSes."""
    result = cs.g_required_files(policy)
    assert result.status == cs.PASS, (
        f"expected PASS on the real submission, got {result.status}: "
        f"{result.message} | {result.evidence}"
    )
    # Every named skill in the evidence is backed by SKILL.md + scripts/*.py.
    for skill in ("code-map", "code-oracle", "fast-grep", "repro-check", "test-gate"):
        assert f"skills/{skill}:" in result.evidence, f"missing evidence for {skill}"


# ===========================================================================
# NEGATIVE / RED-PROOF tests — the gate correctly FAILs on a REAL bad artifact.
# ===========================================================================

def test_g_run_health_fails_on_real_zero_129_run(policy):
    """The real 0/129 degenerate Gemma run -> FAIL with INFRASTRUCTURE FAILURE.

    Runs against the untouched cloud_results/ artifacts (129 rows, 0 resolved,
    117 empty patches, 77/95 zero-completion traces). This is a real infra
    failure, not a synthetic fixture.
    """
    # Guard: only meaningful if the real run artifacts are present and broken.
    assert os.path.isfile(cs.TASK_RESULTS), "real task_results.jsonl missing; cannot prove red"
    assert os.path.isdir(cs.TRACES_DIR), "real traces/ dir missing; cannot prove red"

    result = cs.g_run_health(policy)
    assert result.status == cs.FAIL, (
        f"expected FAIL on the real degenerate run, got {result.status}: {result.message}"
    )
    # The message must name the infra-failure verdict, not a quality claim.
    assert "INFRASTRUCTURE FAILURE" in result.message
    assert result.message == cs.DEGENERATE_MESSAGE
    # Evidence must quote the real degenerate fingerprint from the artifacts.
    assert "rows=129" in result.evidence
    assert "resolved=0" in result.evidence
    assert "empty_patch=117" in result.evidence
    assert "zero_completion=77" in result.evidence
    # Remediation must steer away from reading the score as quality.
    assert "infrastructure" in result.remediation.lower()


def test_g_adapter_base_model_warns_on_wrong_base(policy):
    """The staged wrong-base adapter -> WARN, not FAIL (numerical fidelity only).

    Uses the untouched adapters_staging/main_lora/adapter_config.json whose base
    is unsloth/gemma-4-31B-it-unsloth-bnb-4bit (a 4-bit bnb quantization) while
    the served model is the QAT w4a16 build.

    The harness imposes NO rule that an adapter's base must equal the served
    model (discover_adapters() applies the adapter to the already-loaded base;
    HARNESS_README.md:204). The old "does not exactly match -> FAIL + allowlist"
    contract was FABRICATED and is withdrawn. A base mismatch is a
    numerical-fidelity risk worth surfacing, so the gate WARNs and must not
    demand the adapter be retrained to satisfy a requirement.
    """
    # Guard: only meaningful if the real staging artifact is present and is the
    # genuinely-wrong-base one (proves this is the real broken artifact).
    real_cfg = os.path.join(cs.ADAPTERS_STAGING, "main_lora", "adapter_config.json")
    assert os.path.isfile(real_cfg), "real staged adapter_config.json missing; cannot prove"

    result = cs.g_adapter_base_model(policy)

    # The load-bearing property: a wrong base is a WARN, never a FAIL.
    assert result.status == cs.WARN, (
        f"expected WARN on the wrong-base adapter, got {result.status}: {result.message}"
    )
    assert result.status != cs.FAIL, (
        "the withdrawn fabricated rule must not FAIL the base-model gate"
    )

    # Evidence must name the real staging file and BOTH sides of the mismatch.
    assert "adapters_staging/main_lora/adapter_config.json" in result.evidence
    assert "unsloth/gemma-4-31B-it-unsloth-bnb-4bit" in result.evidence
    assert "gemma-4-31b-it-qat-w4a16-ct" in result.evidence

    # It must be framed as numerical fidelity, explicitly NOT a harness rule.
    assert "numerical-fidelity" in result.message.lower()
    assert "not a harness rule" in result.message.lower()

    # Must NOT assert the adapter must be retrained, and must NOT cite a harness
    # requirement that the bases match (the withdrawn fabrication).
    blob = f"{result.message} {result.evidence} {result.remediation}".lower()
    assert "retrain" not in blob or "no retrain is required" in blob, (
        "the gate must not demand a retrain to satisfy a requirement"
    )
    assert "does not exactly match" not in blob, (
        "the withdrawn 'does not exactly match' FAIL phrasing must be gone"
    )
    assert "allowlist" not in blob, (
        "the withdrawn allowlist remediation must be gone"
    )


# ===========================================================================
# REGRESSION GUARD — the fabricated "base must exactly equal the served model"
# rule (once asserted as a hard FAIL with an allowlist remediation) is WITHDRAWN.
# HARNESS_README.md contains no such rule. This test fails if that fabrication
# ever creeps back into the gate's own OUTPUT, regardless of severity.
# ===========================================================================

# Phrases that would re-introduce the fabricated claim: telling the reader the
# bases must be equal as a REQUIREMENT (harness rule / must equal / must match /
# exact-match obligation / allowlist / retrain-or-fail). The correct output says
# the opposite ("NOT a harness rule", "no retrain is required").
_FORBIDDEN_BASE_EQUALITY_CLAIMS = (
    "must exactly match",
    "must match the served",
    "must equal the served",
    "harness requires the base",
    "harness requires the adapter's base",
    "base must equal",
    "allowlist",
    "retrain the adapter",
    "requires a retrain",
    "fails on wrong base",
)


def _all_base_model_outputs(policy, tmp_path, monkeypatch):
    """Yield every distinct output the base-model gate can produce, on real artifacts.

    Exercises each real branch of g_adapter_base_model:
      * the wrong-base mismatch (the REAL adapters_staging artifact), and
      * a config with no base_model_name_or_path (temp copy).
    For each result it yields the rendered CLI line plus the message, evidence,
    and remediation, so the guard inspects exactly what a reader would see.
    """
    # Branch 1: the real wrong-base artifact (untouched).
    real = cs.g_adapter_base_model(policy)
    yield cs.render_text([real])
    yield f"{real.message} {real.evidence} {real.remediation}"

    # Branch 2: a config missing base_model_name_or_path, on a temp copy so the
    # real staging artifact is never mutated.
    sub = tmp_path / "my_submission"
    cfg_dir = sub / "adapters" / "main_lora"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "adapter_config.json").write_text(
        '{"r": 8, "lora_alpha": 16}\n', encoding="utf-8"
    )
    monkeypatch.setattr(cs, "SUBMISSION_DIR", str(sub))
    nokey = cs.g_adapter_base_model(policy)
    yield cs.render_text([nokey])
    yield f"{nokey.message} {nokey.evidence} {nokey.remediation}"


def test_no_gate_output_claims_base_equality_is_a_harness_requirement(policy, tmp_path, monkeypatch):
    """No output may assert base==served is a harness REQUIREMENT (fabricated rule).

    The withdrawn rule was "the adapter's base_model_name_or_path must EXACTLY
    equal the served model". This guards against it reappearing as a FAIL-severity
    or retrain-demanding claim in ANY of the base-model gate's own output text,
    across every branch it can emit.
    """
    for output in _all_base_model_outputs(policy, tmp_path, monkeypatch):
        low = output.lower()
        for claim in _FORBIDDEN_BASE_EQUALITY_CLAIMS:
            assert claim not in low, (
                f"withdrawn fabricated base-equality rule leaked into gate output "
                f"({claim!r}):\n{output}"
            )
        # The correct framing must explicitly disclaim the harness requirement.
        if "harness" in low:
            assert "no requirement" in low or "not a harness rule" in low or (
                "does not require" in low
            ), f"gate mentions 'harness' without disclaiming the base-equality rule:\n{output}"


# ===========================================================================
# TWO-MODE CONTRACT — submit (default) vs local_test adapter obligations.
#
# submit (default): adapter MUST be declared in agent.yaml AND present in
#   adapters/; either missing is a hard FAIL (HARNESS_README.md:202-203).
# local_test (explicit opt-in): adapter MUST be explicitly turned OFF; a
#   still-declared adapter is a hard FAIL (no silent middle state).
# The real agent.yaml/adapters are NEVER mutated: local_test proofs use tmp_path
# copies with the module's path constants pointed at the copy.
# ===========================================================================


def test_default_submission_mode_resolves_to_submit(policy, monkeypatch):
    """No --mode flag and no env var -> the policy default 'submit' wins."""
    monkeypatch.delenv(cs.MODE_ENV_VAR, raising=False)
    assert cs.resolve_submission_mode(policy, cli_mode=None) == cs.MODE_SUBMIT
    # And the policy file genuinely declares 'submit' as its default.
    assert str(cs._policy_get(policy, "adapter", "submission_mode")) == cs.MODE_SUBMIT


def test_submission_mode_precedence_cli_over_env_over_policy(policy, monkeypatch):
    """Precedence is --mode CLI > GATE_SUBMISSION_MODE env > policy default."""
    # Policy default is submit; set env to local_test -> env wins over policy.
    monkeypatch.setenv(cs.MODE_ENV_VAR, cs.MODE_LOCAL_TEST)
    assert cs.resolve_submission_mode(policy, cli_mode=None) == cs.MODE_LOCAL_TEST
    # Now set the CLI flag to submit -> CLI beats env.
    assert cs.resolve_submission_mode(policy, cli_mode=cs.MODE_SUBMIT) == cs.MODE_SUBMIT
    # An unknown mode is rejected.
    with pytest.raises(ValueError):
        cs.resolve_submission_mode(policy, cli_mode="not_a_mode")


def test_g_adapter_declared_fails_on_missing_declaration_in_submit_mode(policy, tmp_path, monkeypatch):
    """submit mode: a tmp agent.yaml with NO 'adapter:' key -> FAIL.

    The default submit obligation requires the adapter to be declared. This uses
    a temp copy (never the real agent.yaml) and pins submit mode via the stash
    that run_all writes, so the assertion is unambiguous.
    """
    sub = tmp_path / "my_submission"
    sub.mkdir(parents=True)
    (sub / "agent.yaml").write_text(
        "name: main\nmodel: gemma-4-31b-it-qat-w4a16-ct\n", encoding="utf-8"
    )
    monkeypatch.setattr(cs, "SUBMISSION_DIR", str(sub))
    monkeypatch.delenv(cs.MODE_ENV_VAR, raising=False)

    pol = dict(policy)
    pol["_resolved_mode"] = {"mode": cs.MODE_SUBMIT, "source": "test"}
    result = cs.g_adapter_declared(pol)
    assert result.status == cs.FAIL, (
        f"expected FAIL when adapter is undeclared in submit mode, got {result.status}: {result.message}"
    )
    assert "does not declare the required adapter" in result.message
    # Must name the local_test escape hatch as the explicit alternative.
    assert cs.MODE_LOCAL_TEST in result.remediation


def test_g_adapter_present_fails_on_empty_adapters_in_submit_mode(policy, tmp_path, monkeypatch):
    """submit mode: an EMPTY adapters/ dir -> FAIL (must be populated to submit)."""
    sub = tmp_path / "my_submission"
    (sub / "adapters" / "main_lora").mkdir(parents=True)  # exists, 0 files
    monkeypatch.setattr(cs, "SUBMISSION_DIR", str(sub))
    monkeypatch.delenv(cs.MODE_ENV_VAR, raising=False)

    pol = dict(policy)
    pol["_resolved_mode"] = {"mode": cs.MODE_SUBMIT, "source": "test"}
    result = cs.g_adapter_present(pol)
    assert result.status == cs.FAIL, (
        f"expected FAIL on empty adapters/ in submit mode, got {result.status}: {result.message}"
    )
    assert "adapters/ is empty" in result.message
    assert cs.MODE_LOCAL_TEST in result.remediation


def test_g_adapter_declared_fails_on_still_declared_adapter_in_local_test_mode(policy, tmp_path, monkeypatch):
    """local_test: a still-declared 'adapter:' -> FAIL (no silent middle state).

    The adapter must be explicitly OFF under local_test; a surviving declaration
    is a hard FAIL so the local path cannot pretend to use an adapter it lacks.
    Proved on a temp copy -- the real agent.yaml is never mutated.
    """
    sub = tmp_path / "my_submission"
    sub.mkdir(parents=True)
    (sub / "agent.yaml").write_text(
        "name: main\nmodel: gemma-4-31b-it-qat-w4a16-ct\nadapter: main_lora\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cs, "SUBMISSION_DIR", str(sub))

    pol = dict(policy)
    pol["_resolved_mode"] = {"mode": cs.MODE_LOCAL_TEST, "source": "test"}
    result = cs.g_adapter_declared(pol)
    assert result.status == cs.FAIL, (
        f"expected FAIL on a still-declared adapter in local_test mode, got {result.status}: {result.message}"
    )
    assert "still declares an adapter" in result.message
    assert cs.MODE_SUBMIT in result.remediation  # escape: run in submit mode


def test_g_adapter_declared_passes_when_explicitly_off_in_local_test_mode(policy, tmp_path, monkeypatch):
    """local_test: NO 'adapter:' key -> PASS (the correct OFF state)."""
    sub = tmp_path / "my_submission"
    sub.mkdir(parents=True)
    (sub / "agent.yaml").write_text(
        "name: main\nmodel: gemma-4-31b-it-qat-w4a16-ct\n", encoding="utf-8"
    )
    monkeypatch.setattr(cs, "SUBMISSION_DIR", str(sub))

    pol = dict(policy)
    pol["_resolved_mode"] = {"mode": cs.MODE_LOCAL_TEST, "source": "test"}
    result = cs.g_adapter_declared(pol)
    assert result.status == cs.PASS, (
        f"expected PASS when adapter is explicitly off in local_test mode, got {result.status}: {result.message}"
    )
    assert "explicitly OFF" in result.message


def test_g_adapter_present_passes_when_absent_in_local_test_mode(policy, tmp_path, monkeypatch):
    """local_test: an ABSENT adapters/ dir -> PASS (nothing ships)."""
    sub = tmp_path / "my_submission"
    sub.mkdir(parents=True)  # no adapters/ dir at all
    monkeypatch.setattr(cs, "SUBMISSION_DIR", str(sub))

    pol = dict(policy)
    pol["_resolved_mode"] = {"mode": cs.MODE_LOCAL_TEST, "source": "test"}
    result = cs.g_adapter_present(pol)
    assert result.status == cs.PASS, (
        f"expected PASS when adapters/ is absent in local_test mode, got {result.status}: {result.message}"
    )
    assert "absent" in result.message


def test_g_tool_budget_parity_fails_on_mismatch(policy, tmp_path, monkeypatch):
    """Prompt budget != eval_config budget -> FAIL (proves parity really compares).

    Uses a tmp eval_config whose max_tool_calls (55) disagrees with a tmp prompt
    stating 40. This proves the gate is not a no-op that always passes when a
    budget line exists.
    """
    sub = tmp_path / "my_submission"
    (sub / "prompts").mkdir(parents=True)
    (sub / "prompts" / "main.md").write_text(
        "You have a total budget of 40 tool calls per task.\n", encoding="utf-8"
    )
    (sub / "eval_config.yaml").write_text(
        "evaluation:\n  timeout_seconds: 60\n  max_tool_calls: 55\n", encoding="utf-8"
    )
    monkeypatch.setattr(cs, "SUBMISSION_DIR", str(sub))

    result = cs.g_tool_budget_parity(policy)
    assert result.status == cs.FAIL, (
        f"expected FAIL on a 40-vs-55 mismatch, got {result.status}: {result.message}"
    )
    assert "!=" in result.message or "does not" in result.message
    # Evidence must cite BOTH numbers and both files so it is provably comparing.
    assert "40" in result.evidence
    assert "55" in result.evidence
    assert "main.md:" in result.evidence
    assert "eval_config.yaml:" in result.evidence


def test_g_prompt_ladder_consistency_fails_on_historical_contradiction(policy, tmp_path, monkeypatch):
    """The historical Turn 11 vs Turn 13 contradiction -> FAIL.

    This is the exact defect the gate was written for: the Section-6 ladder said
    Turns 1-10 / Turn 11 while the Phase headers still said Turns 1-12 / Turn 13,
    giving the model two contradictory deadlines. We rebuild that real past text
    in a tmp main.md and require the real gate to go red and to name the specific
    contradiction class.
    """
    sub = tmp_path / "my_submission"
    (sub / "prompts").mkdir(parents=True)
    historical = (
        "# Prompt\n"
        "You have a total budget of 40 tool calls per task.\n"
        "\n"
        "### Phase 1: Search (Turns 1-12: Discovery)\n"
        "- work\n"
        "\n"
        "### Phase 3: Fix (Turn 13: Mandatory Initial Edit)\n"
        "- MANDATORY INITIAL EDIT (TURN 13): apply your initial surgical fix.\n"
        "\n"
        "  * Turns 1-10: Mandatory discovery.\n"
        "  * Turn 11: Mandatory initial edit.\n"
    )
    (sub / "prompts" / "main.md").write_text(historical, encoding="utf-8")
    monkeypatch.setattr(cs, "SUBMISSION_DIR", str(sub))

    result = cs.g_prompt_ladder_consistency(policy)
    assert result.status == cs.FAIL, (
        f"expected FAIL on the historical Turn 11 vs 13 contradiction, "
        f"got {result.status}: {result.message} | {result.evidence}"
    )
    # Must catch BOTH contradiction classes present in the real defect:
    # the same-start/different-end range, and the disagreeing edit deadline.
    assert "contradictory range end for Turn 1" in result.evidence
    assert "mandatory-edit deadline disagrees" in result.evidence
    # Both conflicting turn numbers must be visible as evidence.
    assert "Turn 13" in result.evidence
    assert "Turn 11" in result.evidence


def test_g_zip_directory_drift_fails_on_stale_zip(policy):
    """The current genuinely-stale submission.zip -> FAIL.

    The zip contains 5 root skill copies (skills/code-map/map.py etc.) that were
    deleted from my_submission/, and its prompts/main.md differs from the tree.
    """
    # Guard: only meaningful if the real zip is present and actually stale.
    assert os.path.isfile(cs.SUBMISSION_ZIP), "real submission.zip missing; cannot prove red"
    result = cs.g_zip_directory_drift(policy)
    assert result.status == cs.FAIL, (
        f"expected FAIL on the stale zip, got {result.status}: {result.message} | {result.evidence}"
    )
    assert "out of sync" in result.message
    # Evidence must name the real drift categories present in the current zip:
    # extra members that no longer exist in the directory, and a differing prompt.
    assert "in zip not dir" in result.evidence
    assert "prompts/main.md" in result.evidence


def test_g_no_embedded_code_in_docs_fails_on_real_doc(policy):
    """docs/gemma-and-the-shape-of-doubt.md contains a ~110k-char literal -> FAIL.

    This is a real embedded code literal in a real doc, not a synthetic fixture.
    """
    doc = "docs/gemma-and-the-shape-of-doubt.md"
    assert os.path.isfile(os.path.join(cs.DOCS_DIR, "gemma-and-the-shape-of-doubt.md")), (
        "real offender doc missing; cannot prove red"
    )
    result = cs.g_no_embedded_code_in_docs(policy)
    assert result.status == cs.FAIL, (
        f"expected FAIL on the doc with an embedded literal, got {result.status}: {result.message}"
    )
    assert "escaped code literal" in result.message
    # Evidence must name the real offender file (and the threshold that tripped).
    assert "docs/gemma-and-the-shape-of-doubt.md" in result.evidence
    assert "threshold=5000" in result.evidence


# ===========================================================================
# STRUCTURAL / CONTRACT tests — the gates are wired correctly.
# ===========================================================================

def test_every_policy_value_is_read_not_hardcoded():
    """No policy threshold appears as a literal in the executable source.

    Uses AST (not grep) so docstrings and comments — which legitimately *mention*
    the numbers in prose, e.g. the docstring on _parse_tool_calls_from_prompt —
    are excluded, while any value actually used in logic would appear as an
    ast.Constant and be caught. This enforces the "no hardcoded policy" rule
    (single source of truth = scripts/gate_policy.yaml).
    """
    with open(CHECK_PATH, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    # Collect every numeric and string literal that appears anywhere in the AST.
    int_literals = set()
    str_literals = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                continue
            if isinstance(node.value, (int, float)):
                int_literals.add(node.value)
            elif isinstance(node.value, str):
                str_literals.add(node.value)

    # Read the authoritative values straight from the policy file so the test
    # tracks policy.yaml rather than a hand-copied list.
    pol = cs.load_policy()
    served_model = pol["served_model"]["name"]
    tool_budget = pol["tool_budget"]["max_tool_calls"]
    unpacked_mb = pol["submission"]["max_unpacked_mb"]
    project_cap = pol["serving"]["max_output_tokens_project_cap"]
    ceiling = pol["submission"]["max_output_tokens_ceiling"]

    for value in (served_model,):
        assert value not in str_literals, f"served-model string hardcoded in source: {value!r}"
    for value in (unpacked_mb, project_cap, ceiling, tool_budget):
        assert value not in int_literals, f"policy number hardcoded as a literal: {value}"

    # Sanity: the constants we just checked are plausible magnitudes, so a bug in
    # load_policy (e.g. returning strings) cannot make this test vacuous.
    assert served_model.startswith("gemma-")
    assert all(isinstance(v, int) for v in (unpacked_mb, project_cap, ceiling, tool_budget))


def test_gates_run_without_traceback_when_artifacts_missing(tmp_path, monkeypatch, policy):
    """With every artifact absent, gates return a structured verdict, not a raise.

    run_all() must convert any internal exception into a FAIL GateResult rather
    than aborting; this asserts the contract holds by checking that NO result
    reports an internal error and every result has a valid status.
    """
    empty = tmp_path / "nothing_here"
    empty.mkdir()
    _point_all_at_empty(str(empty), monkeypatch)

    results = cs.run_all(policy)

    # Every registered gate produced a structured result (no gate was skipped).
    assert len(results) == len(cs.ALL_GATES)
    valid = {cs.PASS, cs.FAIL, cs.WARN}
    for r in results:
        assert isinstance(r, cs.GateResult)
        assert r.status in valid, f"{r.name} returned invalid status {r.status!r}"
        assert "unhandled error" not in r.message, (
            f"{r.name} raised internally instead of degrading: {r.message}"
        )
        assert r.message, f"{r.name} produced an empty message"


def test_summary_and_exit_semantics(policy):
    """A FAIL makes the run exit non-zero; WARN alone does not.

    Drives the module's own main() --only entry points against the real current
    artifacts: g_run_health is currently a FAIL (-> exit 1) while
    g_sampling_output_cap is currently a WARN (-> exit 0). This is a real,
    unmutated state, so the two outcomes genuinely differ only by severity.
    """
    import contextlib
    import io

    def _exit_code(argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            return cs.main(argv), buf.getvalue()

    # Sanity on the underlying verdicts driving the exit codes.
    run_health = dict(cs.ALL_GATES)["g_run_health"](policy)
    assert run_health.status == cs.FAIL
    output_cap = dict(cs.ALL_GATES)["g_sampling_output_cap"](policy)
    assert output_cap.status == cs.WARN

    rc_fail, _ = _exit_code(["--only", "g_run_health"])
    assert rc_fail == 1, "a FAILing gate must exit non-zero"

    rc_warn, warn_out = _exit_code(["--only", "g_sampling_output_cap"])
    assert rc_warn == 0, "a WARN alone must NOT affect the exit code"
    assert "[WARN]" in warn_out

    # An unknown gate name is a hard error (guards --only typos silently passing).
    rc_unknown, _ = _exit_code(["--only", "g_does_not_exist"])
    assert rc_unknown == 1


# ===========================================================================
# ADAPTER-DECLARATION gates (2 & 3) — red-proof on the REAL shipped artifacts.
#
# Both of these gates are genuinely red in this repo right now, with no
# synthetic fixture required:
#   * my_submission/agent.yaml has NO ``adapter:`` line at all, so
#     g_adapter_declared FAILs with "does not declare the required adapter".
#   * my_submission/adapters/main_lora/ exists but is EMPTY (0 files), so
#     g_adapter_present FAILs with "adapters/ is empty".
# The FAIL halves below are the load-bearing half; the PASS halves use tmp_path
# copies and exist only to prove the gates are not stuck-red.
# ===========================================================================

def test_g_adapter_declared_fails_on_real_missing_declaration(policy):
    """The real agent.yaml declares no adapter -> FAIL.

    This is the real shipped artifact: my_submission/agent.yaml (16 lines) has
    no ``adapter:`` key anywhere, so the gate cannot find a declaration matching
    policy adapter.declared_name (main_lora) and goes red. Nothing is mocked or
    mutated; this proves the gate is red on what would actually be submitted.
    """
    # Guard: only meaningful if the real agent.yaml exists AND truly omits it.
    real_agent_yaml = os.path.join(cs.SUBMISSION_DIR, "agent.yaml")
    assert os.path.isfile(real_agent_yaml), "real agent.yaml missing; cannot prove red"
    with open(real_agent_yaml, "r", encoding="utf-8") as fh:
        assert not any(ln.strip().startswith("adapter:") for ln in fh), (
            "real agent.yaml now declares an adapter; this red-proof is stale"
        )

    result = cs.g_adapter_declared(policy)
    assert result.status == cs.FAIL, (
        f"expected FAIL on the adapter-less agent.yaml, got {result.status}: {result.message}"
    )
    # The specific verdict must be "no declaration found", not "agent.yaml missing".
    assert "does not declare the required adapter" in result.message
    # Evidence must name the required name so the reader knows what was missing.
    assert "adapter: main_lora" in result.evidence
    assert "line found in agent.yaml" in result.evidence
    # Remediation must point at the concrete fix: add the declaration, or
    # explicitly drop 'adapter' via local_test. (The two-mode contract reworded
    # this from the bare "D9" pointer; the load-bearing property is that it
    # names the actionable declaration, not that it carries a decision token.)
    assert f"adapter: {cs._policy_get(policy, 'adapter', 'declared_name')}" in result.remediation


def test_g_adapter_declared_passes_on_declared_temp_copy(policy, tmp_path, monkeypatch):
    """A tmp copy that DOES declare the adapter -> PASS (gate is not stuck-red)."""
    sub = tmp_path / "my_submission"
    sub.mkdir(parents=True)
    (sub / "agent.yaml").write_text(
        "name: main\nmodel: gemma-4-31b-it-qat-w4a16-ct\nadapter: main_lora\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cs, "SUBMISSION_DIR", str(sub))

    result = cs.g_adapter_declared(policy)
    assert result.status == cs.PASS, (
        f"expected PASS when adapter is declared, got {result.status}: {result.message}"
    )
    assert "adapter: main_lora" in result.evidence


def test_g_adapter_present_fails_on_empty_adapters_dir(policy):
    """The real adapters/main_lora/ is empty -> FAIL.

    my_submission/adapters/main_lora/ genuinely exists but contains zero files
    (the LoRA has not been trained/installed yet), so the gate finds no
    adapter_model.safetensors and goes red on the real, unmutated tree.
    """
    # Guard: only meaningful if the real dir exists AND is genuinely empty.
    real_dir = os.path.join(cs.SUBMISSION_DIR, "adapters", "main_lora")
    assert os.path.isdir(real_dir), "real adapters/main_lora/ missing; cannot prove red"
    assert not any(names for _r, _d, names in os.walk(real_dir)), (
        "real adapters/main_lora/ now has files; this red-proof is stale"
    )

    result = cs.g_adapter_present(policy)
    assert result.status == cs.FAIL, (
        f"expected FAIL on the empty adapters dir, got {result.status}: {result.message}"
    )
    # The specific verdict must be "empty", not "missing" and not "no weights".
    assert "adapters/ is empty" in result.message
    assert "exists but contains no files" in result.evidence
    # Remediation must tell a human to install the adapter files.
    assert "Install the adapter files" in result.remediation


def test_g_adapter_present_passes_on_populated_temp_dir(policy, tmp_path, monkeypatch):
    """A tmp adapters/ containing adapter_model.safetensors -> PASS (not stuck-red)."""
    sub = tmp_path / "my_submission"
    adir = sub / "adapters" / "main_lora"
    adir.mkdir(parents=True)
    (adir / "adapter_model.safetensors").write_bytes(b"\x00" * 8)
    monkeypatch.setattr(cs, "SUBMISSION_DIR", str(sub))

    result = cs.g_adapter_present(policy)
    assert result.status == cs.PASS, (
        f"expected PASS with a populated adapters dir, got {result.status}: {result.message}"
    )
    assert "populated with adapter" in result.message
    # Evidence must confirm the weights were found (proves it truly checked).
    assert "weights=yes" in result.evidence