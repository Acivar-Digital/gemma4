#!/usr/bin/env python3
"""Red-proof test suite for ``scripts/check_submission.py``.

Principle: every FAIL-severity gate must be proven RED against a REAL
already-broken artifact that exists in this repo, never a synthetic fixture
hand-made solely to trip a code path. A gate that cannot be shown red is
skipped and reported as unproven, not quietly passed.

Real broken artifacts used (none are created or mutated by this suite):
  * adapters_staging/main_lora/adapter_config.json -> wrong base model
    (unsloth/gemma-4-31B-it-unsloth-bnb-4bit != served gemma-4-31b-it-qat-w4a16-ct).
    The shipped LoRA has since been purged, so the gate no longer reads a real
    submission config; the mismatch branch is reconstructed on tmp_path instead,
    and the withdrawn-FABRICATION guard below still runs against the real tree.
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
  * The historical adapter-less / adapter-present-but-empty submission states were
    REAL defects in both directions and neither is the live state today (the LoRA
    was purged), so both are reconstructed on tmp_path from the real files and
    exercised in an explicit ``submit`` mode, where they are the required state.

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
    """Reconstruct the adapter-less submission on tmp_path.

    Copies the REAL current my_submission/agent.yaml verbatim, then removes any
    ``adapter:`` line, producing the exact overnight defect these gates prove red
    on (agent.yaml declared no adapter). The shipped adapter has since been
    purged, so the real file already has no such line -- the reconstruction is
    then simply a faithful copy. Either way the copy carries no declaration.
    ``SUBMISSION_DIR`` is pointed at the copy; the real my_submission/ is never
    written.

    Returns the tmp submission dir.

    LOAD-BEARING for callers: this proves the ADAPTER-LESS state, which is a hard
    FAIL only in ``submit`` mode. Callers that need the FAIL must pin submit
    mode (via the policy's ``_resolved_mode`` stash and/or ``--mode submit``);
    under the repo's current ``local_test`` policy an absent declaration is the
    correct PASS.
    """
    sub = tmp_path / "my_submission"
    sub.mkdir()
    real_agent = os.path.join(cs.SUBMISSION_DIR, "agent.yaml")
    assert os.path.isfile(real_agent), "real agent.yaml missing; cannot reconstruct"
    with open(real_agent, "r", encoding="utf-8") as fh:
        lines = fh.readlines()
    kept = [ln for ln in lines if not ln.strip().startswith("adapter:")]
    removed = len(lines) - len(kept)
    # The real agent.yaml may or may not still carry an `adapter:` line -- the
    # shipped adapter was purged, so today it does not. Either way, what matters
    # for the reconstruction is only that the copy ends up with NO declaration:
    # if there was a line we removed exactly one, and if there was none the copy
    # is already the adapter-less state. Assert that invariant, not the count.
    assert removed <= 1, (
        f"expected at most one 'adapter:' line in the real agent.yaml, removed {removed}"
    )
    (sub / "agent.yaml").write_text("".join(kept), encoding="utf-8")
    assert not any(ln.strip().startswith("adapter:") for ln in kept), (
        "the reconstructed agent.yaml must carry no 'adapter:' declaration"
    )

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

    A LoRA fit against a different quantization than the served model is a real
    numerical-fidelity risk, so the gate must surface it -- as an advisory WARN.
    The shipped submission currently declares no adapter at all, so the wrong-base
    branch is reconstructed on tmp_path from a synthetic adapter_config.json and
    the module's SUBMISSION_DIR is pointed at the copy; my_submission/ is never
    written to.

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

    # A base that is deliberately NOT the served one (a bnb-4bit fit served onto a
    # QAT w4a16 base -- the historical real-world shape of this defect).
    wrong_base = "unsloth/gemma-4-31B-it-unsloth-bnb-4bit"
    assert wrong_base != served, "the fixture base must actually differ from the served model"

    # --- Hermetic reconstruction of a wrong-base submission on tmp_path. -------
    tmp_sub = tmp_path / "my_submission"
    cfg_dir = tmp_sub / "adapters" / "main_lora"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "adapter_config.json").write_text(
        json.dumps({"r": 8, "lora_alpha": 16, "base_model_name_or_path": wrong_base}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cs, "SUBMISSION_DIR", str(tmp_sub))

    result = cs.g_adapter_base_model(policy)

    # The load-bearing property: a wrong base is a WARN, never a FAIL.
    assert result.status == cs.WARN, (
        f"expected WARN on the wrong-base adapter, got {result.status}: {result.message}"
    )
    assert result.status != cs.FAIL, (
        "the withdrawn fabricated rule must not FAIL the base-model gate"
    )

    # Evidence must name the resolved config and BOTH sides of the mismatch.
    assert "my_submission/adapters/main_lora/adapter_config.json" in result.evidence
    assert wrong_base in result.evidence
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
    """Yield every distinct output the base-model gate can produce.

    Exercises each branch of g_adapter_base_model:
      * the live tree as it stands (currently: no adapter shipped), and
      * a wrong-base mismatch on a tmp copy -- reconstructed because the shipped
        LoRA was purged, so no live config reaches this branch any more, and
      * a config with no base_model_name_or_path (temp copy).
    For each result it yields the rendered CLI line plus the message, evidence,
    and remediation, so the guard inspects exactly what a reader would see.
    """
    # Branch 0: the real tree, untouched.
    real = cs.g_adapter_base_model(policy)
    yield cs.render_text([real])
    yield f"{real.message} {real.evidence} {real.remediation}"

    # Branch 1: a wrong-base adapter_config.json on a tmp copy. The shipped LoRA
    # is gone, so the mismatch branch is unreachable from the live tree; the
    # withdrawn-fabrication guard must still see its output.
    served = "gemma-4-31b-it-qat-w4a16-ct"
    sub_mismatch = tmp_path / "my_submission_mismatch"
    cfg_mismatch = sub_mismatch / "adapters" / "main_lora"
    cfg_mismatch.mkdir(parents=True)
    (cfg_mismatch / "adapter_config.json").write_text(
        '{"r": 8, "base_model_name_or_path": "unsloth/gemma-4-31B-it-unsloth-bnb-4bit"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(cs, "SUBMISSION_DIR", str(sub_mismatch))
    mismatch = cs.g_adapter_base_model(policy)
    assert mismatch.status == cs.WARN, (
        f"precondition broken: wrong-base fixture must WARN, got {mismatch.status}"
    )
    assert served in mismatch.evidence
    yield cs.render_text([mismatch])
    yield f"{mismatch.message} {mismatch.evidence} {mismatch.remediation}"

    # Branch 2: a config missing base_model_name_or_path, on a second temp copy.
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
# TWO-MODE CONTRACT — submit vs local_test adapter obligations.
#
# submit: adapter MUST be declared in agent.yaml AND present in adapters/;
#   either missing is a hard FAIL (HARNESS_README.md:202-203).
# local_test: adapter MUST be explicitly turned OFF; a still-declared adapter is
#   a hard FAIL (no silent middle state). The repo policy currently selects
#   local_test, because the submission ships no adapter.
# Whichever mode the repo declares, proofs that need one specific mode pin it
# explicitly (--mode flag, or the _resolved_mode stash for direct gate calls) so
# they assert the gate's behaviour rather than the repo's current setting.
# The real agent.yaml/adapters are NEVER mutated: every proof uses tmp_path
# copies with the module's path constants pointed at the copy.
# ===========================================================================


def test_default_submission_mode_resolves_to_the_policy_value(policy, monkeypatch):
    """No --mode flag and no env var -> the POLICY's declared mode wins.

    The load-bearing behaviour is the precedence rule, not the particular mode
    string: with neither override present, resolution must return whatever
    ``adapter.submission_mode`` declares. The repo policy legitimately declares
    ``local_test`` (the submission ships no adapter), so re-pinning the literal
    ``submit`` here would encode mutable repo state, not a contract. The
    resolved value is compared against the policy file, never against a literal.
    """
    monkeypatch.delenv(cs.MODE_ENV_VAR, raising=False)
    declared = str(cs._policy_get(policy, "adapter", "submission_mode")).strip().lower()
    assert declared in cs.ALLOWED_MODES, (
        f"policy declares an unknown submission_mode {declared!r}"
    )
    assert cs.resolve_submission_mode(policy, cli_mode=None) == declared, (
        f"with no --mode flag and no env var the policy value must win; policy "
        f"declares {declared!r}"
    )


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


def test_g_adapter_declared_passes_on_missing_declaration_in_submit_mode(policy, tmp_path, monkeypatch):
    """submit mode: an agent.yaml with NO 'adapter:' key -> PASS.

    The harness PERMITS an adapter but never REQUIRES one. Every mention of
    adapters/ in HARNESS_README.md is marked Optional (:38, :85, :110), and
    :128/:134 impose only a 3 GiB unpacked-size CEILING that an adapter must fit
    inside -- a ceiling is not a presence requirement. An adapter-less
    submission is therefore valid and must not hard-FAIL. This test pins that
    contract so a future "restore the requirement" change has to argue with it.
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
    assert result.status == cs.PASS, (
        f"expected PASS when no adapter ships in submit mode, got {result.status}: {result.message}"
    )
    assert "OPTIONAL" in result.message


def test_g_adapter_declared_still_fails_on_wrong_declared_name(policy, tmp_path, monkeypatch):
    """submit mode: a WRONG 'adapter:' value still FAILs.

    Absence is legitimate; inconsistency is not. A declared name that does not
    equal the policy's ``declared_name`` is a packaging defect, so the gate keeps
    vetoing it.
    """
    sub = tmp_path / "my_submission"
    sub.mkdir(parents=True)
    (sub / "agent.yaml").write_text(
        "name: main\nmodel: gemma-4-31b-it-qat-w4a16-ct\nadapter: wrong_name\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cs, "SUBMISSION_DIR", str(sub))
    monkeypatch.delenv(cs.MODE_ENV_VAR, raising=False)

    pol = dict(policy)
    pol["_resolved_mode"] = {"mode": cs.MODE_SUBMIT, "source": "test"}
    result = cs.g_adapter_declared(pol)
    assert result.status == cs.FAIL, (
        f"expected FAIL on a wrong adapter name, got {result.status}: {result.message}"
    )
    assert "declared_name" in result.evidence or "declared_name" in result.remediation


def test_g_adapter_present_passes_on_empty_adapters_in_submit_mode(policy, tmp_path, monkeypatch):
    """submit mode: an EMPTY adapters/ dir -> PASS (it ships no adapter)."""
    sub = tmp_path / "my_submission"
    (sub / "adapters" / "main_lora").mkdir(parents=True)  # exists, 0 files
    monkeypatch.setattr(cs, "SUBMISSION_DIR", str(sub))
    monkeypatch.delenv(cs.MODE_ENV_VAR, raising=False)

    pol = dict(policy)
    pol["_resolved_mode"] = {"mode": cs.MODE_SUBMIT, "source": "test"}
    result = cs.g_adapter_present(pol)
    assert result.status == cs.PASS, (
        f"expected PASS on empty adapters/ in submit mode, got {result.status}: {result.message}"
    )
    assert "empty" in result.message


def test_g_adapter_present_still_fails_on_populated_dir_without_weights(policy, tmp_path, monkeypatch):
    """submit mode: a POPULATED adapters/ with no .safetensors still FAILs.

    Shipping a broken adapter is worse than shipping none, so a half-populated
    adapters/ keeps its veto.
    """
    sub = tmp_path / "my_submission"
    (sub / "adapters" / "main_lora").mkdir(parents=True)
    (sub / "adapters" / "main_lora" / "adapter_config.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(cs, "SUBMISSION_DIR", str(sub))
    monkeypatch.delenv(cs.MODE_ENV_VAR, raising=False)

    pol = dict(policy)
    pol["_resolved_mode"] = {"mode": cs.MODE_SUBMIT, "source": "test"}
    result = cs.g_adapter_present(pol)
    assert result.status == cs.FAIL, (
        f"expected FAIL when adapters/ has no weights, got {result.status}: {result.message}"
    )



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


def test_g_no_embedded_code_in_docs_fails_on_real_doc(policy, monkeypatch):
    """A docs/*.md line over the 5000-char threshold -> FAIL.

    The offender is the committed fixture tests/fixtures/hygiene_offender_doc.md,
    a REAL markdown file on disk (not an in-memory string) whose single padded
    line exceeds the threshold. DOCS_DIR is redirected at the directory holding
    it, mirroring how sibling tests redirect SUBMISSION_DIR.

    The live docs/gemma-and-the-shape-of-doubt.md is deliberately NOT used here:
    it is a research evidence log that intentionally embeds source verbatim, and
    it is exempt by recorded decision (hygiene.embedded_code_doc_exemptions in
    scripts/gate_policy.yaml). Depending on it would make this test assert the
    ABSENCE of a deliberate exemption. Gate logic is what this proves, and a
    committed fixture proves it without entangling the gate's policy.
    """
    fixture_dir = os.path.join(REPO_ROOT, "tests", "fixtures")
    fixture = os.path.join(fixture_dir, "hygiene_offender_doc.md")
    assert os.path.isfile(fixture), f"red-proof fixture missing: {fixture}"
    monkeypatch.setattr(cs, "DOCS_DIR", fixture_dir)

    result = cs.g_no_embedded_code_in_docs(policy)
    assert result.status == cs.FAIL, (
        f"expected FAIL on the doc with an embedded literal, got {result.status}: {result.message}"
    )
    assert "escaped code literal" in result.message
    # Evidence must name the offending file (and the threshold that tripped).
    assert "docs/hygiene_offender_doc.md" in result.evidence
    assert "threshold=5000" in result.evidence


def test_g_no_embedded_code_in_docs_exempts_policy_named_doc(policy):
    """A doc named in policy is exempt, and the exemption is NOT a silent skip.

    This is the GREEN half of the pair above: the live
    docs/gemma-and-the-shape-of-doubt.md embeds source on purpose, so it must
    PASS -- but only because scripts/gate_policy.yaml says so, and the evidence
    must NAME the doc and the recorded reason so a maintainer sees a deliberate
    decision rather than a blind spot.
    """
    assert os.path.isfile(os.path.join(cs.DOCS_DIR, "gemma-and-the-shape-of-doubt.md")), (
        "the exempt evidence doc is missing; this test would be vacuous"
    )
    # The exemption and its reason come from POLICY, not from gate logic.
    exempt = cs.resolve_embedded_code_doc_exemptions(policy)
    assert "gemma-and-the-shape-of-doubt.md" in exempt, (
        f"policy must list the evidence doc as exempt; got {sorted(exempt)}"
    )
    assert exempt["gemma-and-the-shape-of-doubt.md"], "exemption must carry a reason"

    result = cs.g_no_embedded_code_in_docs(policy)
    assert result.status == cs.PASS, (
        f"the policy-exempt doc must not FAIL the gate, got {result.status}: {result.message}"
    )
    # Visible, not silent: the exempt doc AND its recorded reason are in evidence.
    assert "gemma-and-the-shape-of-doubt.md" in result.evidence
    assert exempt["gemma-and-the-shape-of-doubt.md"] in result.evidence
    assert "EXEMPT" in result.evidence


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

    g_adapter_declared is a submission gate that is genuinely red on a submission
    declaring the WRONG adapter name in ``submit`` mode, so the FAIL is reproduced
    on a faithful tmp copy of agent.yaml; the real my_submission/ is never mutated.
    Driving that reconstruction alone through main() --only must return a non-zero
    exit code, because a defect in the artifact being shipped is exactly what must
    veto a submission.

    CONTRACT CHANGE 2026-10-05: this test previously reconstructed the ADAPTER-LESS
    agent.yaml, which was a hard FAIL under the old "an adapter is mandatory"
    contract. The harness permits shipping no adapter (HARNESS_README.md:38,85,110
    mark adapters/ Optional), so that reconstruction is now a correct PASS. The
    surviving defect is a WRONG declared name, which is what this test now uses.

    submit mode is pinned explicitly (policy stash for the direct gate call,
    ``--mode submit`` for the CLI) rather than inherited from whatever the repo
    policy currently declares. The obligation under test here is the SUBMIT-mode
    one, and this test deliberately says nothing about the live tree's mode.

    LOAD-BEARING: if exit_code_for treated submission FAILs as non-gating (the
    demotion bug), this returns 0 and the assertion fires. The test therefore
    distinguishes 'the new post_run demotion' from 'FAILs stopped gating at all'.
    """
    # --- Red half: reconstruct a wrong-name declaration so the gate FAILs. -----
    sub = tmp_path / "my_submission"
    sub.mkdir(parents=True, exist_ok=True)
    (sub / "agent.yaml").write_text(
        "name: main\nmodel: gemma-4-31b-it-qat-w4a16-ct\nadapter: wrong_name\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cs, "SUBMISSION_DIR", str(sub))
    monkeypatch.delenv(cs.MODE_ENV_VAR, raising=False)
    pol = dict(policy)
    pol["_resolved_mode"] = {"mode": cs.MODE_SUBMIT, "source": "test"}
    result = dict(cs.ALL_GATES)["g_adapter_declared"](pol)
    assert result.status == cs.FAIL, f"precondition broken: {result.status}: {result.message}"
    assert cs.category_of("g_adapter_declared") == cs.CAT_SUBMISSION

    rc, out = _main_exit(["--only", "g_adapter_declared", "--mode", cs.MODE_SUBMIT])
    assert rc == 1, (
        f"a submission-category FAIL must exit non-zero, got {rc}. Output:\n{out}"
    )
    # A submission FAIL is reported as a hard blocker, never labelled NON-GATING.
    assert "[FAIL] g_adapter_declared" in out
    assert "BLOCKING:" in out
    assert _NON_GATING not in out, (
        "a submission FAIL must never be labelled NON-GATING"
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


def test_hygiene_fail_alone_exits_zero_and_is_labelled_non_gating(policy, monkeypatch):
    """A hygiene FAIL alone -> exit 0, with the same explicit NON-GATING label.

    g_no_embedded_code_in_docs is a real, FAILing hygiene gate: the committed
    fixture tests/fixtures/hygiene_offender_doc.md has a padded line over the
    5000-char threshold. It lints the repository's docs and says nothing about
    the artifact being shipped, so it must not veto -- but it must still be
    reported and labelled NON-GATING so a maintainer sees it is a real finding,
    not a blocker.

    The FAIL precondition is produced from the FIXTURE (DOCS_DIR redirected),
    not from the live docs/: the real evidence doc is exempt by recorded policy
    decision and would PASS. Everything asserted below -- exit 0, [FAIL], the
    NON-GATING label, the hygiene category, and the absence of a BLOCKING
    banner -- is the actual subject of this test and is unchanged.

    LOAD-BEARING: if hygiene FAILs gated, rc would be 1 and this fires. If the
    NON-GATING label were missing, the label assertion fires.
    """
    # Sanity on the underlying verdict: this really is a FAILing hygiene gate.
    monkeypatch.setattr(cs, "DOCS_DIR", os.path.join(REPO_ROOT, "tests", "fixtures"))
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
         adapter-less agent.yaml, exits 1. (The FAIL is reproduced on a faithful
         tmp copy in explicit ``submit`` mode -- the mode under which an adapter
         is mandatory -- so the exit-1 half of the composition contract stays
         proven independently of whatever the live tree ships.)

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
    # Reconstruct a submission with a WRONG 'adapter:' value so g_adapter_declared
    # genuinely FAILs, and pin submit mode. CONTRACT CHANGE 2026-10-05: this used
    # to reconstruct the ADAPTER-LESS submission, which was a hard FAIL then; the
    # harness permits shipping no adapter, so that reconstruction is now a correct
    # PASS. A wrong declared name is still a packaging defect and remains a hard
    # FAIL, so it is the right vehicle for exercising exit-code composition --
    # which is what this test is actually about. A shallow copy of the policy is
    # used (with any _resolved_mode stash from the run_all calls above dropped) so
    # this run's mode is unambiguous and cannot be left behind on the shared
    # module-scoped fixture.
    sub = tmp_path / "my_submission"
    sub.mkdir(parents=True, exist_ok=True)
    (sub / "agent.yaml").write_text(
        "name: main\nmodel: gemma-4-31b-it-qat-w4a16-ct\nadapter: wrong_name\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cs, "SUBMISSION_DIR", str(sub))
    monkeypatch.delenv(cs.MODE_ENV_VAR, raising=False)
    pol = dict(policy)
    pol.pop("_resolved_mode", None)
    res3 = cs.run_all(pol, only=["g_adapter_declared"], category=cs.CAT_SUBMISSION,
                      cli_mode=cs.MODE_SUBMIT)
    assert [r.name for r in res3] == ["g_adapter_declared"]
    assert res3[0].status == cs.FAIL, (
        f"precondition broken: g_adapter_declared must FAIL on the wrong-name "
        f"reconstruction, got {res3[0].status}"
    )
    rc3, out3 = _main_exit(["--only", "g_adapter_declared", "--category", "submission",
                            "--mode", cs.MODE_SUBMIT])
    assert rc3 == 1, f"a FAILing submission gate under its own category must exit 1, got {rc3}"
    # Exactly one gate ran and it FAILed -- so the filters narrowed to 1, not 14.
    assert "0 passed, 1 failed, 0 warnings (of 1 gates)" in out3, (
        f"--category submission + --only must run exactly the one named gate. "
        f"Output:\n{out3}"
    )


def test_every_gate_is_classified_into_exactly_one_valid_category():
    """All 15 gates are classified; none uncategorized; valid set is exactly the 3.

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
    assert len(cs.ALL_GATES) == 15, f"expected 15 registered gates, got {len(cs.ALL_GATES)}"
    assert len(cs.GATE_CATEGORY) == 15, (
        f"expected 15 classified gates, got {len(cs.GATE_CATEGORY)}"
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
# Both were genuinely red in this repo. The live tree no longer carries either
# state: the LoRA was purged, so my_submission/agent.yaml declares no adapter and
# my_submission/adapters/ does not exist. Each test below therefore reconstructs
# the exact historical defect on tmp_path from the real files and points the gate
# at the copy, and pins submit mode explicitly (the mode in which a missing
# declaration / empty adapters dir is a hard FAIL) rather than inheriting whatever
# the repo policy happens to declare. Nothing in my_submission/ is mutated. The
# PASS halves use tmp_path copies and exist only to prove the gates are not
# stuck-red.
# ===========================================================================

def test_g_adapter_declared_passes_on_real_missing_declaration(policy, tmp_path, monkeypatch):
    """agent.yaml with no 'adapter:' key, in submit mode -> PASS (reconstructed).

    CONTRACT CHANGE 2026-10-05: this test previously asserted FAIL. The harness
    PERMITS an adapter but never REQUIRES one -- every mention of adapters/ in
    HARNESS_README.md is marked Optional (:38, :85, :110) and :128/:134 impose
    only a 3 GiB unpacked-size ceiling, not a presence requirement. An
    adapter-less submission is valid, so the gate must not veto it.

    It still reconstructs the adapter-less agent.yaml on tmp_path (never the
    live tree) and pins submit mode explicitly, so the proof does not depend on
    whatever the repo policy currently declares. Note the counterpart test
    ``test_g_adapter_declared_still_fails_on_wrong_declared_name`` pins the
    invariant that survives: a WRONG declared name is still a packaging defect.
    """
    # --- Reconstruction of the adapter-less agent.yaml. -------------------------
    sub = _make_adapterless_submission(tmp_path, monkeypatch)
    assert not any(
        ln.strip().startswith("adapter:") for ln in (sub / "agent.yaml").read_text().splitlines()
    ), "reconstruction failed to remove the adapter: line"
    monkeypatch.delenv(cs.MODE_ENV_VAR, raising=False)
    pol = dict(policy)
    pol["_resolved_mode"] = {"mode": cs.MODE_SUBMIT, "source": "test"}

    result = cs.g_adapter_declared(pol)
    assert result.status == cs.PASS, (
        f"expected PASS on the adapter-less agent.yaml, got {result.status}: {result.message}"
    )
    # The verdict must be the optional-adapter one, not the local_test one.
    assert "OPTIONAL" in result.message
    # Evidence must cite the harness rule so the reasoning is auditable.
    assert "HARNESS_README.md" in result.evidence


def test_g_adapter_declared_passes_on_declared_temp_copy(policy, tmp_path, monkeypatch):
    """submit mode: a tmp copy that DOES declare the adapter -> PASS (not stuck-red).

    A declared adapter is only correct in ``submit`` mode; under ``local_test``
    a surviving declaration is deliberately a FAIL (see
    test_g_adapter_declared_fails_on_still_declared_adapter_in_local_test_mode).
    So submit mode is pinned explicitly here via the policy stash rather than
    inherited from the repo policy, keeping this proof independent of whichever
    mode the repo happens to ship in.
    """
    sub = tmp_path / "my_submission"
    sub.mkdir(parents=True)
    (sub / "agent.yaml").write_text(
        "name: main\nmodel: gemma-4-31b-it-qat-w4a16-ct\nadapter: main_lora\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cs, "SUBMISSION_DIR", str(sub))
    monkeypatch.delenv(cs.MODE_ENV_VAR, raising=False)
    pol = dict(policy)
    pol["_resolved_mode"] = {"mode": cs.MODE_SUBMIT, "source": "test"}

    result = cs.g_adapter_declared(pol)
    assert result.status == cs.PASS, (
        f"expected PASS when adapter is declared in submit mode, got {result.status}: {result.message}"
    )
    assert "adapter: main_lora" in result.evidence

def test_g_adapter_present_passes_on_real_empty_adapters_dir(policy, tmp_path, monkeypatch):
    """submit mode: adapters/ exists but is EMPTY -> PASS (reconstructed on tmp_path).

    CONTRACT CHANGE 2026-10-05: was FAIL. An empty adapters/ ships no adapter,
    which the harness permits. Reconstructed on tmp_path so the live
    my_submission/ is never mutated. The invariant that still holds is pinned by
    ``test_g_adapter_present_still_fails_on_populated_dir_without_weights``: a
    populated adapters/ with no .safetensors is a broken adapter and still FAILs.
    """
    # --- Reconstruction of an empty-but-present adapters/ dir on tmp_path. ------
    sub = tmp_path / "my_submission"
    (sub / "adapters" / "main_lora").mkdir(parents=True)  # exists, 0 files
    monkeypatch.setattr(cs, "SUBMISSION_DIR", str(sub))
    monkeypatch.delenv(cs.MODE_ENV_VAR, raising=False)
    pol = dict(policy)
    pol["_resolved_mode"] = {"mode": cs.MODE_SUBMIT, "source": "test"}

    result = cs.g_adapter_present(pol)
    assert result.status == cs.PASS, (
        f"expected PASS on the empty adapters dir, got {result.status}: {result.message}"
    )
    # The verdict must be the empty-ships-nothing one, not the missing-dir one.
    assert "empty" in result.message



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