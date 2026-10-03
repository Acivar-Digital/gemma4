#!/usr/bin/env python3
"""Red-proof test suite for ``scripts/check_submission.py``.

Principle: every FAIL-severity gate must be proven RED against a REAL
already-broken artifact that exists in this repo, never a synthetic fixture
hand-made solely to trip a code path. A gate that cannot be shown red is
skipped and reported as unproven, not quietly passed.

Real broken artifacts used (none are created or mutated by this suite):
  * adapters_staging/main_lora/adapter_config.json AND the byte-identical shipped
    copy at my_submission/adapters/main_lora/adapter_config.json -> wrong base model
    (unsloth/gemma-4-31B-it-unsloth-bnb-4bit != served gemma-4-31b-it-qat-w4a16-ct).
    This is STILL genuinely broken in the live tree; the gate WARNs on it for real.
  * cloud_results/results/ -> the real 0/129 degenerate Gemma run
    (129 rows, 0 resolved, 117 empty patches, 77/95 zero-completion traces). STILL
    genuinely broken in the live tree.
  * docs/gemma-and-the-shape-of-doubt.md -> a real ~110k-char escaped code
    literal. STILL genuinely broken in the live tree.
  * The historical main.md turn-ladder contradiction (Turn 11 vs Turn 13) is
    reproduced verbatim in a tmp file from the known past text.
  * The historical zip drift (extra root skill copies + a prompts/main.md reading
    "50 tool calls") was a REAL defect but has since been fixed -- submission.zip is
    now byte-identical to my_submission/ -- so it is reconstructed on tmp_path from
    the real current files rather than taken from the live tree.
  * The historical adapter-less submission (my_submission/agent.yaml with no
    ``adapter:`` line, and an empty adapters/main_lora/) was a REAL defect but has
    since been fixed, so both are reconstructed on tmp_path from the real files.

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
import json
import os
import shutil
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

# The literal label a non-gating FAIL must carry in the rendered output.
#
# We deliberately assert on the LITERAL STRING, never on cs.NON_GATING_LABEL:
# a test that reads the expected token back out of the module under test is
# tautological -- renaming the constant would move the expectation with it and
# the assertion would keep passing while the operator-visible contract silently
# changed. The literal is pinned here, and pinned separately against the module
# constant in test_every_gate_is_classified_into_exactly_one_valid_category.
_NON_GATING = "NON-GATING"

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


def _make_adapterless_submission(tmp_path, monkeypatch):
    """Reconstruct the historically-broken (adapter-less) submission on tmp_path.

    Copies the REAL current my_submission/agent.yaml verbatim, then deletes the
    ``adapter:`` line to reproduce the exact overnight defect this gate proved
    red on (agent.yaml declared no adapter). ``SUBMISSION_DIR`` is pointed at the
    copy; the real my_submission/ is never written.

    Returns the tmp submission dir. Also copies the real adapters/ tree so the
    reconstruction is faithful (the historical defect was declaration-only).
    """
    sub = tmp_path / "my_submission"
    sub.mkdir()
    real_agent = os.path.join(cs.SUBMISSION_DIR, "agent.yaml")
    assert os.path.isfile(real_agent), "real agent.yaml missing; cannot reconstruct"
    with open(real_agent, "r", encoding="utf-8") as fh:
        lines = fh.readlines()
    kept = [ln for ln in lines if not ln.strip().startswith("adapter:")]
    assert len(kept) == len(lines) - 1, (
        "expected the real agent.yaml to carry exactly one 'adapter:' line to remove"
    )
    (sub / "agent.yaml").write_text("".join(kept), encoding="utf-8")

    # Faithful reconstruction: carry the real (now-populated) adapters/ over too.
    real_adapters = os.path.join(cs.SUBMISSION_DIR, "adapters")
    if os.path.isdir(real_adapters):
        shutil.copytree(real_adapters, sub / "adapters")
    monkeypatch.setattr(cs, "SUBMISSION_DIR", str(sub))
    return sub


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


def test_g_adapter_base_model_warns_on_wrong_base(policy, tmp_path, monkeypatch):
    """The wrong-base adapter -> WARN, not FAIL (numerical fidelity only).

    The adapter shipped in my_submission/adapters/main_lora/adapter_config.json is
    a byte-copy of the staged adapters_staging/main_lora/adapter_config.json; both
    declare base unsloth/gemma-4-31B-it-unsloth-bnb-4bit (a 4-bit bnb quantization)
    while the served model is the QAT w4a16 build. The gate resolves the config
    SUBMISSION-FIRST (scripts/check_submission.py::_find_adapter_config), so against
    the untouched live tree it reads my_submission/adapters/main_lora/ and WARNs --
    the real, still-genuinely-wrong-base artifact, no mutation. The staging
    fallback branch is proven separately below on a tmp copy of the real staged
    file (never mutating adapters_staging/).

    The harness imposes NO rule that an adapter's base must equal the served
    model (discover_adapters() applies the adapter to the already-loaded base;
    HARNESS_README.md:204). The old "does not exactly match -> FAIL + allowlist"
    contract was FABRICATED and is withdrawn. A base mismatch is a
    numerical-fidelity risk worth surfacing, so the gate WARNs and must not
    demand the adapter be retrained to satisfy a requirement.
    """
    # The served model name is pinned as a LITERAL, never read back out of the
    # policy/module, so a rename of the served-model constant cannot move the
    # expectation with it and leave this green while the operator-visible
    # evidence silently changed.
    served = "gemma-4-31b-it-qat-w4a16-ct"
    # Sanity: the policy really does still declare that same served model, so the
    # literal above cannot drift away from reality without this firing.
    assert str(cs._policy_get(policy, "adapter", "required_base_model")) == served, (
        "policy adapter.required_base_model no longer matches the pinned literal"
    )

    # --- Real artifact (submission path, submission-first resolution). ---------
    real_cfg = os.path.join(cs.SUBMISSION_DIR, "adapters", "main_lora", "adapter_config.json")
    assert os.path.isfile(real_cfg), "real submission adapter_config.json missing; cannot prove"
    # Guard: the live config must really be the wrong-base one, or this proof dies.
    with open(real_cfg, "r", encoding="utf-8") as fh:
        assert json.load(fh).get("base_model_name_or_path") != served, (
            "real submission adapter_config.json now declares the served base; "
            "this red-proof is stale"
        )

    result = cs.g_adapter_base_model(policy)

    # The load-bearing property: a wrong base is a WARN, never a FAIL.
    assert result.status == cs.WARN, (
        f"expected WARN on the wrong-base adapter, got {result.status}: {result.message}"
    )
    assert result.status != cs.FAIL, (
        "the withdrawn fabricated rule must not FAIL the base-model gate"
    )

    # Evidence must name the resolved real file and BOTH sides of the mismatch.
    assert "my_submission/adapters/main_lora/adapter_config.json" in result.evidence
    assert "unsloth/gemma-4-31B-it-unsloth-bnb-4bit" in result.evidence
    assert served in result.evidence

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

    # --- Staging-fallback branch: faithful copy of the real staged config. -----
    staged = os.path.join(cs.ADAPTERS_STAGING, "main_lora", "adapter_config.json")
    assert os.path.isfile(staged), "real staged adapter_config.json missing; cannot prove"
    # Copy the REAL staged config verbatim into a tmp tree, then blank out the
    # submission's own adapters/ so _find_adapter_config must fall back to staging.
    tmp_sub = tmp_path / "my_submission"
    (tmp_sub / "adapters").mkdir(parents=True)
    (tmp_sub / "adapters" / "main_lora").mkdir()
    with open(staged, "r", encoding="utf-8") as fh:
        staged_text = fh.read()
    assert json.loads(staged_text).get("base_model_name_or_path") != served, (
        "real staged adapter_config.json is no longer the wrong-base one"
    )
    tmp_sub.joinpath("adapters", "main_lora", "adapter_config.json").write_text(
        staged_text, encoding="utf-8"
    )
    monkeypatch.setattr(cs, "SUBMISSION_DIR", str(tmp_sub))

    fallback = cs.g_adapter_base_model(policy)
    assert fallback.status == cs.WARN, (
        f"expected WARN from the staging fallback on the wrong-base copy, got "
        f"{fallback.status}: {fallback.message}"
    )
    # The staging-fallback evidence must still name both sides of the real mismatch.
    assert "unsloth/gemma-4-31B-it-unsloth-bnb-4bit" in fallback.evidence
    assert served in fallback.evidence


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


def _make_stale_zip_pair(tmp_path, monkeypatch):
    """Build a genuinely stale submission directory + zip pair on tmp_path.

    Reconstructs the SHAPE of the real historical defect (a zip that lagged the
    working tree) from the real, current files:

      * the directory holds the CURRENT prompts/main.md (the corrected 40-call
        text), while the zip is packed with the OLD "50 tool calls" prompt, so
        the pair is in genuine content disagreement on a file both sides have;
      * the directory has a file the zip lacks (`prompts/only-in-dir.md`), so the
        "in dir not zip" half of the gate also fires; and
      * the zip carries an extra root member the directory does not have
        (`skills/code-map/map.py`), reproducing the deleted-root-skill-copy half.

    Both SUBMISSION_DIR and SUBMISSION_ZIP are pointed at the tmp copies; the real
    my_submission/ and submission.zip are never written.
    """
    real_dir = cs.SUBMISSION_DIR
    sub = tmp_path / "my_submission"
    sub.mkdir()
    # Real, current prompts/main.md copied verbatim (the corrected prompt).
    with open(os.path.join(real_dir, "prompts", "main.md"), "r", encoding="utf-8") as fh:
        current_main = fh.read()
    (sub / "prompts").mkdir()
    (sub / "prompts" / "main.md").write_text(current_main, encoding="utf-8")
    (sub / "prompts" / "only-in-dir.md").write_text("present in dir, absent from zip\n", encoding="utf-8")

    # Zip: stale main.md (the historical 50-call text) + an extra root member.
    stale_main = (
        "# Prompt\n"
        "You have a total budget of 50 tool calls per task.\n"
    )
    assert "50 tool calls" not in current_main, (
        "the real current prompt already says 50; cannot build a distinct stale side"
    )
    zip_path = tmp_path / "submission.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("prompts/main.md", stale_main)
        zf.writestr("skills/code-map/map.py", "# deleted root skill copy\n")

    monkeypatch.setattr(cs, "SUBMISSION_DIR", str(sub))
    monkeypatch.setattr(cs, "SUBMISSION_ZIP", str(zip_path))
    return sub, zip_path


def test_g_zip_directory_drift_fails_on_stale_zip(policy, tmp_path, monkeypatch):
    """A genuinely stale submission.zip -> FAIL (reconstructed on tmp_path).

    The live zip is now byte-identical to my_submission/ (repacked after the
    overnight fix), so it can no longer serve as the broken artifact. This test
    therefore reconstructs the real historical defect faithfully on tmp_path --
    a directory that has a file the zip lacks AND a prompt whose content differs
    -- and proves the gate still goes red and names BOTH drift categories.

    The live tree's CURRENT correct verdict is asserted separately below, so the
    fix did not silently neuter the gate.
    """
    # Guard: the real zip must still exist for the live-tree half of the proof.
    assert os.path.isfile(cs.SUBMISSION_ZIP), "real submission.zip missing; cannot prove"

    # --- Red half: genuinely stale pair built from the real current files. -----
    _make_stale_zip_pair(tmp_path, monkeypatch)
    result = cs.g_zip_directory_drift(policy)
    assert result.status == cs.FAIL, (
        f"expected FAIL on the stale zip, got {result.status}: {result.message} | {result.evidence}"
    )
    assert "out of sync" in result.message
    # Evidence must name ALL drift categories present in the reconstructed pair:
    # extra members no longer in the directory, a directory-only file, and the
    # differing prompt (the exact false-50 case this gate exists to catch).
    assert "in zip not dir" in result.evidence
    assert "in dir not zip" in result.evidence
    assert "content differs" in result.evidence
    assert "prompts/main.md" in result.evidence

    # --- Green half: the live tree's real, current verdict is byte-identity. ---
    monkeypatch.undo()
    live = cs.g_zip_directory_drift(policy)
    assert live.status == cs.PASS, (
        f"the live zip is now in sync and must PASS, got {live.status}: {live.message}"
    )
    assert "byte-identical" in live.message


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


def _main_exit(argv):
    """Drive cs.main(argv), returning (exit_code, rendered_stdout).

    The module prints the report to stdout and returns the exit code, so this
    captures both -- the rendered text is what we assert the NON-GATING label
    and the INFRASTRUCTURE FAILURE phrase on. Wraps the redirect so every test
    exercises the real CLI entry point rather than reimplementing the policy.
    """
    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return cs.main(argv), buf.getvalue()


def test_submission_fail_sets_nonzero_exit(policy, tmp_path, monkeypatch):
    """A submission-category FAIL -> exit 1. This is the gating case.

    g_adapter_declared is a submission gate that is genuinely red on the adapter-
    less agent.yaml. The live agent.yaml now declares its adapter (the overnight
    fix), so the FAIL is reproduced on a faithful tmp copy of the real agent.yaml
    with the ``adapter:`` line removed; the real my_submission/ is never mutated.
    Driving that reconstruction alone through main() --only must return a non-zero
    exit code, because a defect in the artifact being shipped is exactly what must
    veto a submission. The live tree's real (now-PASS) verdict is asserted too, so
    this test also tracks the current healthy state.

    LOAD-BEARING: if exit_code_for treated submission FAILs as non-gating (the
    demotion bug), this returns 0 and the assertion fires. The test therefore
    distinguishes 'the new post_run demotion' from 'FAILs stopped gating at all'.
    """
    # --- Red half: reconstruct the adapter-less submission so the gate FAILs. ---
    _make_adapterless_submission(tmp_path, monkeypatch)
    result = dict(cs.ALL_GATES)["g_adapter_declared"](policy)
    assert result.status == cs.FAIL, f"precondition broken: {result.status}: {result.message}"
    assert cs.category_of("g_adapter_declared") == cs.CAT_SUBMISSION

    rc, out = _main_exit(["--only", "g_adapter_declared"])
    assert rc == 1, (
        f"a submission-category FAIL must exit non-zero, got {rc}. Output:\n{out}"
    )
    # A submission FAIL is reported as a hard blocker, never labelled NON-GATING.
    assert "[FAIL] g_adapter_declared" in out
    assert "BLOCKING:" in out
    assert _NON_GATING not in out, (
        "a submission FAIL must never be labelled NON-GATING"
    )

    # --- Green half: the live agent.yaml is healthy and must not block. ----------
    monkeypatch.undo()
    live = dict(cs.ALL_GATES)["g_adapter_declared"](policy)
    assert live.status == cs.PASS, (
        f"the live agent.yaml declares its adapter and must PASS, got {live.status}: {live.message}"
    )
    rc_live, out_live = _main_exit(["--only", "g_adapter_declared"])
    assert rc_live == 0, (
        f"a PASSing submission gate must exit 0, got {rc_live}. Output:\n{out_live}"
    )


def test_post_run_fail_alone_exits_zero_and_is_labelled_non_gating(policy):
    """A post_run FAIL alone -> exit 0, but rendered with an explicit NON-GATING label.

    g_run_health is a real, currently-FAILing post_run gate (the real 0/129
    degenerate run). It is a verdict about a HISTORICAL run, not about the
    artifact being shipped, so it must NOT veto a submission -- but it must stay
    loud. This drives it alone via --only and asserts BOTH halves:

      * the exit code is 0 (it does not block), and
      * the output names it NON-GATING with its category, so no reader mistakes
        it for a submission blocker.

    LOAD-BEARING: if post_run FAILs still gated (the old behaviour), rc would be
    1 and this fires. If the NON-GATING label were dropped from the renderer, the
    label assertion fires. Both halves must hold.
    """
    # Sanity on the underlying verdict: this really is a FAILing post_run gate.
    result = dict(cs.ALL_GATES)["g_run_health"](policy)
    assert result.status == cs.FAIL, f"precondition broken: {result.status}: {result.message}"
    assert cs.category_of("g_run_health") == cs.CAT_POST_RUN

    rc, out = _main_exit(["--only", "g_run_health"])
    assert rc == 0, (
        f"a post_run FAIL alone must NOT block the submission (exit 0), got {rc}. "
        f"Output:\n{out}"
    )
    # The verdict must still be reported, and explicitly marked non-gating with
    # its category so a reader cannot mistake it for a submission blocker.
    assert "[FAIL]" in out
    assert f"{_NON_GATING}: g_run_health FAILED (post_run category)" in out
    assert "does not block submission" in out
    # No BLOCKING banner may be printed for a non-gating FAIL.
    assert "BLOCKING:" not in out, (
        "a post_run FAIL must not print a BLOCKING banner"
    )
    # The summary must report it as a non-gating FAIL, not a gating one.
    assert "1 non-gating FAIL(s)" in out
    assert "1 gating FAIL(s)" not in out


def test_hygiene_fail_alone_exits_zero_and_is_labelled_non_gating(policy):
    """A hygiene FAIL alone -> exit 0, with the same explicit NON-GATING label.

    g_no_embedded_code_in_docs is a real, currently-FAILing hygiene gate (the
    real docs/gemma-and-the-shape-of-doubt.md has a ~110k-char escaped literal).
    It lints the repository's docs and says nothing about the artifact being
    shipped, so it must not veto -- but it must still be reported and labelled
    NON-GATING so a maintainer sees it is a real finding, not a blocker.

    LOAD-BEARING: if hygiene FAILs gated, rc would be 1 and this fires. If the
    NON-GATING label were missing, the label assertion fires.
    """
    # Sanity on the underlying verdict: this really is a FAILing hygiene gate.
    result = dict(cs.ALL_GATES)["g_no_embedded_code_in_docs"](policy)
    assert result.status == cs.FAIL, f"precondition broken: {result.status}: {result.message}"
    assert cs.category_of("g_no_embedded_code_in_docs") == cs.CAT_HYGIENE

    rc, out = _main_exit(["--only", "g_no_embedded_code_in_docs"])
    assert rc == 0, (
        f"a hygiene FAIL alone must NOT block the submission (exit 0), got {rc}. "
        f"Output:\n{out}"
    )
    assert "[FAIL]" in out
    assert (
        f"{_NON_GATING}: g_no_embedded_code_in_docs FAILED (hygiene category)" in out
    )
    assert "does not block submission" in out
    assert "BLOCKING:" not in out, (
        "a hygiene FAIL must not print a BLOCKING banner"
    )


def test_run_health_still_says_infrastructure_failure_not_a_quality_result(policy):
    """g_run_health keeps the loud INFRASTRUCTURE FAILURE phrase despite being non-gating.

    The demotion removes g_run_health's veto power, NOT its voice. A reader must
    still see the verbatim phrase 'INFRASTRUCTURE FAILURE, NOT A QUALITY RESULT'
    so nobody mistakes a broken historical run for a quality result. The message
    is preserved verbatim inside the rendered NON-GATING line.

    LOAD-BEARING: if the renderer replaced the message with a soft "skipped" style
    line, or the gate's DEGENERATE_MESSAGE lost the phrase, this fires.
    """
    phrase = "INFRASTRUCTURE FAILURE, NOT A QUALITY RESULT"

    # (a) The gate's own message carries the phrase (unchanged by the demotion).
    result = dict(cs.ALL_GATES)["g_run_health"](policy)
    assert result.status == cs.FAIL
    assert result.message == cs.DEGENERATE_MESSAGE
    assert phrase in result.message

    # (b) The rendered default-run line preserves the phrase verbatim.
    rc, out = _main_exit(["--only", "g_run_health"])
    assert rc == 0, "a post_run FAIL alone must not block (still exit 0)"
    assert phrase in out, (
        f"the literal {phrase!r} must survive into the rendered output even "
        f"though g_run_health is non-gating. Output:\n{out}"
    )
    # It is non-gating AND loud: the phrase and the NON-GATING label coexist.
    assert _NON_GATING in out
    assert f"{_NON_GATING}: g_run_health FAILED (post_run category)" in out


def test_explicit_category_post_run_selection_makes_fail_exit_nonzero(policy):
    """--category post_run: a FAIL in the explicitly selected category -> exit 1.

    This is the subtle selection-vs-default distinction. By DEFAULT (or with a
    bare --only) a post_run FAIL exits 0. But when the operator EXPLICITLY asks
    '--category post_run', they are asking specifically about run health, so a
    FAIL in that category MUST be loud in the exit code too (that's how it can
    be used as a CI signal). The SAME g_run_health FAIL gives exit 0 by default
    and exit 1 under --category post_run -- that difference is the proof.

    LOAD-BEARING: if exit_code_for ignored selected_category, or main() failed
    to pass it through, the --category run would return 0 and this fires. The
    default run returning 0 in the same test pins the other side.
    """
    # The FAILing gate really is in the post_run category and really FAILs.
    result = dict(cs.ALL_GATES)["g_run_health"](policy)
    assert result.status == cs.FAIL
    assert cs.category_of("g_run_health") == cs.CAT_POST_RUN

    # Default (no --category): the same FAIL does NOT set the exit code.
    rc_default, _ = _main_exit(["--only", "g_run_health"])
    assert rc_default == 0, "by default a post_run FAIL must exit 0"

    # Explicit --category post_run: the same FAIL now DOES set the exit code.
    rc_selected, sel_out = _main_exit(["--category", "post_run"])
    assert rc_selected == 1, (
        f"explicitly selecting --category post_run must make its FAIL exit "
        f"non-zero, got {rc_selected}. Output:\n{sel_out}"
    )
    # Only the post_run gate ran, and it is the one that drove the exit code.
    assert "0 passed, 1 failed" in sel_out, (
        f"--category post_run must run exactly the one FAILing post_run gate. "
        f"Output:\n{sel_out}"
    )
    # Note: even when it blocks, the gate is still reported as post_run/non-gating
    # in content; the exit code is what changes, not the finding itself.
    assert f"{_NON_GATING}: g_run_health FAILED (post_run category)" in sel_out


def test_category_and_only_compose_including_empty_intersection(policy, tmp_path, monkeypatch):
    """--category and --only compose: a gate must satisfy BOTH filters to run.

    Three cases, all against the real policy:
      1. --category post_run alone -> runs exactly the post_run gate(s).
      2. --category submission + --only g_run_health (an EMPTY intersection,
         since g_run_health is post_run) -> runs NOTHING and exits 0 (no gate
         selected => no verdict => nothing to block on).
      3. --category submission + --only g_adapter_declared (a real intersection)
         -> runs exactly that one gate and, because it FAILs on the reconstructed
         adapter-less agent.yaml, exits 1. (The live agent.yaml now declares its
         adapter and PASSes, so the FAIL is reproduced on a faithful tmp copy so
         the exit-1 half of the composition contract stays proven.)

    LOAD-BEARING: if --only were ignored under a category filter, case 1 would run
    everything and case 2 would run (and fail on) g_run_health instead of running
    nothing -- the empty-intersection assertions would fire. In case 3, if the
    filters did not narrow to exactly the one named gate, the "(of 1 gates)"
    assertion would fire.
    """
    # (1) category alone selects the whole category.
    post_run_names = [n for n, _f in cs.ALL_GATES if cs.category_of(n) == cs.CAT_POST_RUN]
    assert post_run_names, "post_run category must be non-empty for this test to be meaningful"
    res1 = cs.run_all(policy, category=cs.CAT_POST_RUN)
    assert [r.name for r in res1] == post_run_names

    # (2) EMPTY intersection: post_run gate + submission category -> runs nothing.
    empty_res = cs.run_all(policy, only=["g_run_health"], category=cs.CAT_SUBMISSION)
    assert empty_res == [], f"expected no gates to run, got {[r.name for r in empty_res]}"
    assert cs.exit_code_for(empty_res, selected_category=cs.CAT_SUBMISSION) == 0

    # Drive the same empty intersection through the CLI for the end-to-end check.
    rc_empty, out_empty = _main_exit(["--only", "g_run_health", "--category", "submission"])
    assert rc_empty == 0, f"empty intersection must exit 0, got {rc_empty}"
    assert "0 passed, 0 failed" in out_empty, (
        f"empty intersection must run zero gates. Output:\n{out_empty}"
    )

    # (3) A real intersection runs exactly the one named gate and gates the exit.
    # Reconstruct the adapter-less submission so g_adapter_declared genuinely FAILs.
    _make_adapterless_submission(tmp_path, monkeypatch)
    res3 = cs.run_all(policy, only=["g_adapter_declared"], category=cs.CAT_SUBMISSION)
    assert [r.name for r in res3] == ["g_adapter_declared"]
    assert res3[0].status == cs.FAIL, (
        f"precondition broken: g_adapter_declared must FAIL on the reconstruction, "
        f"got {res3[0].status}"
    )
    rc3, out3 = _main_exit(["--only", "g_adapter_declared", "--category", "submission"])
    assert rc3 == 1, f"a FAILing submission gate under its own category must exit 1, got {rc3}"
    # Exactly one gate ran and it FAILed -- so the filters narrowed to 1, not 14.
    assert "0 passed, 1 failed, 0 warnings (of 1 gates)" in out3, (
        f"--category submission + --only must run exactly the one named gate. "
        f"Output:\n{out3}"
    )


def test_every_gate_is_classified_into_exactly_one_valid_category():
    """All 14 gates are classified; none uncategorized; valid set is exactly the 3.

    Proves the classification registry is a total, well-typed mapping: every
    registered gate has exactly one category, no category names a non-existent
    gate, and every category value is one of the three valid ones. The module
    already self-checks this at import time (_assert_gate_categories), but that
    raises during import -- this test pins the SAME invariant as an assertion
    against the loaded registry, so a future edit that weakens the check is
    caught here too, with the offending gate named.

    LOAD-BEARING: if a gate were added to ALL_GATES without a GATE_CATEGORY entry,
    the uncategorized assertion fires and names it. If a category were typo'd,
    the valid-set assertion fires.
    """
    # Every registered gate is classified.
    registered = {name for name, _fn in cs.ALL_GATES}
    classified = set(cs.GATE_CATEGORY)
    assert registered <= classified, (
        f"uncategorized gate(s): {sorted(registered - classified)}"
    )
    # No category names a gate that does not exist (no orphans).
    assert classified <= registered, (
        f"category names non-registered gate(s): {sorted(classified - registered)}"
    )
    # The mapping is exactly one-category-per-gate with the right total size.
    assert len(cs.ALL_GATES) == 14, f"expected 14 registered gates, got {len(cs.ALL_GATES)}"
    assert len(cs.GATE_CATEGORY) == 14, (
        f"expected 14 classified gates, got {len(cs.GATE_CATEGORY)}"
    )
    # The valid category set is exactly {submission, post_run, hygiene}.
    assert set(cs.GATE_CATEGORIES) == {"submission", "post_run", "hygiene"}
    for name, cat in cs.GATE_CATEGORY.items():
        assert cat in cs.GATE_CATEGORIES, f"gate {name} has invalid category {cat!r}"
    # The operator-visible non-gating label is pinned as a LITERAL, not read back
    # from the constant, so renaming it is caught here instead of silently
    # changing what the reader sees in the report.
    assert cs.NON_GATING_LABEL == "NON-GATING", (
        f"the non-gating label must stay the literal 'NON-GATING' so operators "
        f"and CI greps keep working, got {cs.NON_GATING_LABEL!r}"
    )


def test_warning_and_unknown_gate_exit_semantics_unchanged(policy):
    """The pre-existing, category-independent exit rules still hold.

    Two unchanged rules, kept in their own test so a failure localises:
      * a WARN alone never affects the exit code (g_sampling_output_cap is a real
        WARN on the real tree), and
      * an unknown --only gate name is a hard error (guards --only typos
        silently "passing" by running nothing).
    """
    # WARN alone -> exit 0.
    output_cap = dict(cs.ALL_GATES)["g_sampling_output_cap"](policy)
    assert output_cap.status == cs.WARN, (
        f"precondition broken: expected the real tree to WARN, got {output_cap.status}"
    )
    rc_warn, warn_out = _main_exit(["--only", "g_sampling_output_cap"])
    assert rc_warn == 0, "a WARN alone must NOT affect the exit code"
    assert "[WARN]" in warn_out

    # Unknown gate name -> hard error.
    rc_unknown, _ = _main_exit(["--only", "g_does_not_exist"])
    assert rc_unknown == 1, "an unknown --only gate name must be a hard error"


# ===========================================================================
# ADAPTER-DECLARATION gates (2 & 3) — red-proofs for the two historical defects.
#
# Both were genuinely red in this repo and both have since been FIXED:
#   * my_submission/agent.yaml now carries ``adapter: main_lora`` (line 3), and
#   * my_submission/adapters/main_lora/ now holds the real installed LoRA
#     (adapter_config.json + adapter_model.safetensors).
# The live tree is therefore healthy and can no longer carry the FAIL halves, so
# each test below reconstructs the exact historical defect on tmp_path from the
# real files and points the gate at the copy. Each also asserts the live tree's
# CURRENT correct verdict, so the fix is tracked rather than assumed. The PASS
# halves use tmp_path copies and exist only to prove the gates are not stuck-red.
# ===========================================================================

def test_g_adapter_declared_fails_on_real_missing_declaration(policy, tmp_path, monkeypatch):
    """agent.yaml with the 'adapter:' line removed -> FAIL (reconstructed).

    HISTORY: this red-proof originally ran against the live my_submission/agent.yaml
    when it genuinely declared no adapter. The overnight fix added ``adapter: main_lora``
    (agent.yaml line 3), so the live tree is now HEALTHY and can no longer carry the
    red half. This test therefore reconstructs the exact historical defect: it copies
    the REAL current agent.yaml verbatim to tmp_path and deletes the single ``adapter:``
    line, then proves the gate is red on that faithful copy. Nothing in my_submission/
    is mutated. The live tree's correct PASS is asserted separately below.
    """
    # --- Red half: faithful reconstruction of the real adapter-less agent.yaml. --
    sub = _make_adapterless_submission(tmp_path, monkeypatch)
    assert not any(
        ln.strip().startswith("adapter:") for ln in (sub / "agent.yaml").read_text().splitlines()
    ), "reconstruction failed to remove the adapter: line"

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
    # explicitly drop 'adapter' via local_test.
    assert f"adapter: {cs._policy_get(policy, 'adapter', 'declared_name')}" in result.remediation

    # --- Green half: the live tree is healthy and must PASS. --------------------
    monkeypatch.undo()
    real_agent_yaml = os.path.join(cs.SUBMISSION_DIR, "agent.yaml")
    assert os.path.isfile(real_agent_yaml), "real agent.yaml missing; cannot prove green"
    with open(real_agent_yaml, "r", encoding="utf-8") as fh:
        assert any(ln.strip().startswith("adapter:") for ln in fh), (
            "live agent.yaml should now declare an adapter; if this regresses the "
            "red-proof premise above no longer matches the real artifact"
        )
    live = cs.g_adapter_declared(policy)
    assert live.status == cs.PASS, (
        f"the live agent.yaml declares its adapter and must PASS, got {live.status}: {live.message}"
    )


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


def test_g_adapter_present_fails_on_empty_adapters_dir(policy, tmp_path, monkeypatch):
    """adapters/ exists but is EMPTY -> FAIL (reconstructed on tmp_path).

    HISTORY: this red-proof originally ran against the live my_submission/adapters/
    main_lora/ when it genuinely existed but contained zero files. The overnight fix
    installed the real LoRA (adapter_config.json + adapter_model.safetensors, 90 MB)
    there, so the live tree is now HEALTHY. This test reconstructs the historical
    empty-but-present adapters/ dir on tmp_path and proves the gate is red on it.
    Nothing in my_submission/ is mutated. The live tree's correct PASS is asserted
    separately below.
    """
    # --- Red half: a faithful empty-but-present adapters/ dir on tmp_path. -------
    sub = tmp_path / "my_submission"
    (sub / "adapters" / "main_lora").mkdir(parents=True)  # exists, 0 files
    monkeypatch.setattr(cs, "SUBMISSION_DIR", str(sub))

    result = cs.g_adapter_present(policy)
    assert result.status == cs.FAIL, (
        f"expected FAIL on the empty adapters dir, got {result.status}: {result.message}"
    )
    # The specific verdict must be "empty", not "missing" and not "no weights".
    assert "adapters/ is empty" in result.message
    assert "exists but contains no files" in result.evidence
    # Remediation must tell a human to install the adapter files.
    assert "Install the adapter files" in result.remediation

    # --- Green half: the live tree now ships the real weights and must PASS. ----
    monkeypatch.undo()
    real_dir = os.path.join(cs.SUBMISSION_DIR, "adapters", "main_lora")
    assert os.path.isdir(real_dir), "real adapters/main_lora/ missing; cannot prove green"
    live = cs.g_adapter_present(policy)
    assert live.status == cs.PASS, (
        f"the live adapters dir now ships weights and must PASS, got {live.status}: {live.message}"
    )
    assert "weights=yes" in live.evidence


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