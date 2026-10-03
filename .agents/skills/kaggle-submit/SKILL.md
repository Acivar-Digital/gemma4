---
name: kaggle-submit
description: Playbook for validating, packaging, and submitting Google Gemma 4 Developer Agent competition submissions to the Kaggle Leaderboard. Use when preparing, checking, or executing Kaggle submissions, diagnosing submission failures, or preventing low-score regressions (such as the 0.03 score failure).
---

# Kaggle Leaderboard Submission Playbook (`kaggle-submit`)

This skill defines the mandatory protocol for submitting entries to the **Google Gemma 4 Developer Agent** Kaggle competition (`gemma-4-developer-agent`).

> **AUTHORITATIVE REFERENCES — read these, not this prose.**
> - `scripts/check_submission.py` — the gates themselves (implementation).
> - `scripts/gate_policy.yaml` — **every threshold, with `file:line` citations.**
>
> **Policy is the single source of truth.** This runbook deliberately does *not*
> restate a threshold the checker already enforces; where a number matters, the
> number lives in `gate_policy.yaml` and the gate reads it from there. Prose that
> duplicates an enforced value is a second source of truth, and a second source
> of truth is how the false-50 budget defect (Section 1.4) and the false-5 quota
> defect (Section 4.1) shipped in the first place. **If you need a threshold,
> read it from `gate_policy.yaml`; never copy it from this file.**
>
> If this file and `gate_policy.yaml` ever disagree, **`gate_policy.yaml` is
> right and this file is stale** — fix this file.

---

## 1. Post-Mortem: Why Past Submissions Scored 0.03

On 2026-10-02, submission `56765397` ("Submission v2: Rank-8 LoRA Adapter + 5-Skill Architecture") scored a catastrophic **0.03** (3% resolution rate) on the public leaderboard. 

Investigation revealed the root causes behind this and other low-score traps:

1. **Un-Trained / Placeholder LoRA Adapter**:
   - `agent.yaml` mounted `adapter: main_lora`, which contained un-trained 69 MB placeholder weights.
   - In ADK, declaring an adapter instructs the runtime to route queries through adapter hooks. On Kaggle's evaluation containers, this caused either invalid output generation or inference crashes on Turn 1.
   - **RULE:** Never submit an adapter unless it has been empirically verified to score $\ge 43.4\%$ on the 14-task local validation suite.
2. **Directory Nesting Defect**:
   - Packaging the directory `my_submission/` directly (e.g. `zip -r submission.zip my_submission/`) places `my_submission/agent.yaml` inside the archive instead of `agent.yaml` at the root.
   - The competition evaluator (`adk-submission`) expects `agent.yaml` strictly at the root of `submission.zip`. Root discovery failure causes immediate zero scores across all tasks.
3. **Test-File Pollution & Container B Discard**:
   - Agents that modify files in `tests/`, `test_*.py`, `conftest.py`, or `pyproject.toml` have their edits completely wiped by Container B's checkout before the evaluation test patch is applied.
   - If the agent "fixed" the problem by modifying a test, Container B discards the fix, leaving the unresolved bug and scoring 0.
4. **Budget Ladder Mismatch & Early Circuit-Breaking**:
   - **The harness enforces a 40-call limit, not 50.** A prompt that claims a different budget paces the agent against a ladder that does not exist, so agents trip emergency fallback routines early and fail to complete complex multi-file fixes.
   - **Direction of causation (previously written backwards in this file):** the harness limit of **40** is the ground truth; a prompt asserting **50** was the *bug*. The false-50 prompt was corrected to 40 on 2026-10-04. `my_submission/prompts/main.md` now correctly paces against 40.
   - Ground truth: `my_submission/eval_config.yaml:4` sets `evaluation.max_tool_calls: 40`; recorded in `scripts/gate_policy.yaml` under `tool_budget.max_tool_calls`.
5. **Bytecode & OS Metadata Bloat**:
   - Including `__pycache__`, `.pyc`, and `.DS_Store` files pollutes the archive and risks import path collisions or container extraction errors.
6. **Direct Skill Invocation Hallucination Trap (`ValueError: Tool '<skill_name>' not found`)**:
   - In Google ADK's `SkillToolset`, skills (like `fast-grep` or `code-map`) are NOT exposed as direct top-level tools in `tools_dict`.
   - Instead, ADK provides meta-tools: `run_skill_script`, `list_skills`, `load_skill`, `load_skill_resource`.
   - If system instructions tell the model to call `fast-grep(...)` directly, the model emits `<|tool_call|fast-grep(...)>`, causing ADK to raise `ValueError: Tool 'fast-grep' not found` and aborting the turn.
   - **RULE:** Prompt instructions must strictly instruct the model to use either native tools (`read_file`, `edit_file`, `write_file`, `get_status`, `submit_patch`) or invoke skills via `run_skill_script(skill_name="...", script_name="...", ...)`.

---

## 2. The Gates

Before ANY submission is sent to Kaggle, the candidate package MUST pass the gate suite implemented in `scripts/check_submission.py` (**14 gates**). The gates below are listed for **orientation and rationale only** — the enforcement, the thresholds, and the ordering all live in the code and policy. **Do not hand-run these.**

```text
[Required files] ─────► required submission files present
[Adapter declared] ───► adapter obligation per submission mode (see Section 5)
[Adapter present] ────► adapters/ populated as declared
[Adapter base model] ─► WARN-only numerical-fidelity signal (never a FAIL)
[Tool budget parity] ─► eval_config.yaml and the prompt agree
[Prompt ladder] ──────► the prompt's ladder matches the true budget
[Sampling keys] ──────► forbidden sampling keys absent
[Output-token cap] ───► max_output_tokens within policy
[Unpacked size] ──────► total UNPACKED size under policy (not zip file size)
[Zip directory drift]► every in-tree file is accounted for in the zip
[Zip root layout] ────► agent.yaml at the archive root
[Disallowed exts] ───► no bytecode / OS metadata / junk in the zip
[Run health] ─────────► degenerate-run fingerprint (post_run; cannot veto)
[No embedded code] ───► docs code-block lint (hygiene; cannot veto)
```

**Veto power is by category, not by prominence.** `submission` gates can FAIL and stop a submission. `post_run` (a verdict about a *historical* run) and `hygiene` (repository cleanliness) still run and still print their FAILs loudly, but they are labelled `NON-GATING` and cannot block a submission unless explicitly selected. A gate that is registered but uncategorized raises at load time rather than silently guessing.

### How to read the gate results

```bash
# The supported way to see gate verdicts for the CURRENT artifact:
scripts/submit_safe.sh --dry-run
```

- `--dry-run` runs the gate phases and prints what a real run *would* do. It **never packs and never submits.** This is the safe mode for rehearsing.
- Exit codes: `0` success · `1` gate/trap failure · `2` usage error · `3` user declined · `4` quota refusal · `5` no interpreter.
- To inspect a single gate or the category model directly, use `scripts/check_submission.py` (`--only GATE`, `--category`, `--show-categories`, `--pre-pack`, `--mode`, `--json`).

### Rationale worth keeping

- **Root layout** — `agent.yaml` must sit at the archive root; anything else scores zero across the board (Section 1.2).
- **Unpacked size** — the harness limit applies to the **total unpacked** submission, *not* the compressed `.zip` file size. Measuring `du submission.zip` understates the real footprint and is the wrong measurement.
- **Directory drift** — a file present in `my_submission/` but missing from the zip is a packaging defect; conversely, files the packer *correctly* excludes must not be reported as drift. Both the gate and the packer derive their exclusion vocabulary from `packaging.excluded_globs` in `gate_policy.yaml`, so they cannot disagree about what is junk.
- **Test-file pollution** — edits to `tests/` are discarded by Container B before the test patch is applied (Section 1.3). Scratch repro goes to `/tmp`.
- **Tool/Skill API** — skills are meta-tools, not direct tools; a prompt telling the model to call a skill name directly triggers `ValueError: Tool '<name>' not found` and aborts the turn (Section 1.6).
- **Adapter gates** — see Section 5 for the two-mode rule.

> **Preflight (legacy, not a submission gate).** An environment/sandbox preflight suite exists at `scripts/preflight_check.py` (6 tiers, `[1/6]`..`[6/6]`: dependency imports, wheels, real-ADK compilation, sandbox subprocess isolation, live snapshot pytest, live agent diagnostics). It is a **developer-environment** diagnostic, **not** part of the 14 submission gates — per `docs/IRONCLAD_GATES_PLAN.md`, its original failure mode was checking the wrong layer and never opening the files that actually broke. It requires the `adk_submission` harness package, which is **not importable from any interpreter in this environment** (verified: `adk_submission` is absent from the system `python3` and from the private interpreter this file used to hardcode). That hardcoded interpreter path has been removed because it does not contain the harness packages; it is not a working command. Preflight is also **operator-run only** — tiers 5–6 execute pytest and a live LLM call, and the repo execution protocol (`AGENTS.md`, `execution-protocol-only-start-sh`) reserves all evaluation/test execution for the user via `./start.sh`. Agents must not run it. Use `scripts/submit_safe.sh --dry-run` for gate evidence instead.

---

## 3. Packaging Protocol

**There is one supported way to package, and it is not a hand-run recipe.** `scripts/submit_safe.sh` performs packaging in strict, gated order — gate the working tree, pack, gate the freshly built zip, hash, check quota, prompt, submit. Hand-rolling a `find`-purge plus a `zip -x` list here would create a second procedure that can silently drift from the enforced one, which is precisely the failure class this tooling exists to eliminate.

```bash
# The single supported packaging path (gate → pack → gate-the-zip → hash → quota → prompt → submit)
scripts/submit_safe.sh
```

- Packing happens **inside** `my_submission/` so `agent.yaml` lands at the archive root (Section 1.2).
- Junk purging and the zip exclusion filter are both derived from `packaging.excluded_globs` in `gate_policy.yaml` — **one exclusion vocabulary**, owned by the policy file.
- The freshly built zip is hashed (SHA-256) and printed so the exact bytes that will be uploaded are identifiable.
- **Rehearse without side effects** using `--dry-run`: gates run, nothing is packed, nothing is submitted.

Other flags:

| Flag | Effect |
|---|---|
| `--dry-run` | Rehearse: run the gate phases, never pack, never submit. |
| `--yes` | Skip the interactive prompt **only**. Gates still must pass. |
| `--override-quota` | Deliberate second-submit case; bypasses the daily-quota refusal. **Bypasses no gate.** |
| `-h` / `--help` | Usage. |

---

## 4. Kaggle Leaderboard Submission Execution

Submission is performed by the same wrapper — it invokes `kaggle competitions submit` as its final step. Do not run the `kaggle` submit command by hand; running it outside the wrapper skips the gate/quota/confirm ordering that protects the daily slot.

### 4.1 Check Quota Availability

**The quota is 1 submission per day — not 5.** (An earlier version of this file misstated the quota as five per 24-hour UTC window; that was wrong and is corrected here. Ground truth: `submission_quota.per_day` in `scripts/gate_policy.yaml`, sourced from `docs/gemma-and-the-shape-of-doubt.md:136`, which states the rules allow **one** submission per day.)

`scripts/submit_safe.sh` reads `submission_quota.per_day` from `gate_policy.yaml` and refuses to continue (exit `4`) if a submission already exists for today (UTC). It does not hardcode the number. To view history manually:
```bash
kaggle competitions submissions -c gemma-4-developer-agent | head -n 10
```

### 4.2 Confirm and Submit

`submit_safe.sh` prompts before submitting:

- Submission requires typing an explicit **`y`**. The default is **NO**.
- Anything other than `y` (including no input / EOF / non-interactive) aborts with exit `3`. Nothing is submitted.
- `--yes` skips the prompt but **only after the gates pass**.

Because the daily quota is 1, a submission consumes the slot immediately and irreversibly.

### 4.3 Monitor Submission Status
Kaggle takes 15–45 minutes to run the container evaluation:
```bash
kaggle competitions submissions -c gemma-4-developer-agent | head -n 5
```
Watch for `SubmissionStatus.COMPLETE` and verify that `publicScore` is updated.

---

## 5. The Two-Mode Adapter Rule

The adapter gates are **mode-dependent**, because "no adapter" is a legitimate state for local harness testing and an illegitimate state for a real submission. `scripts/check_submission.py` enforces exactly two modes; there is no middle state where an adapter is silently absent.

| Mode | Use for | Adapter obligation |
|---|---|---|
| `submit` (**DEFAULT**) | A real Kaggle submission. This tree is what gets uploaded. | `agent.yaml` MUST declare an adapter **and** `adapters/` MUST be populated. A missing adapter is a **hard FAIL — fail loudly, fail fast.** |
| `local_test` | Validating the harness locally without shipping an adapter. | The adapter MUST be **explicitly turned OFF** (no `adapter:` key in `agent.yaml`). A still-declared adapter in `local_test` is a **hard FAIL.** |

Mode precedence: `--mode` CLI flag › `GATE_SUBMISSION_MODE` env var › the `adapter.submission_mode` default in `scripts/gate_policy.yaml` (which is `submit`). Run `--show-categories` / `--mode` to inspect; consult `gate_policy.yaml` for the current defaults rather than trusting this table for a value.

### Base-model comparison is a WARNING, not a harness rule

The `g_adapter_base_model` gate compares `adapter_config.json`'s `base_model_name_or_path` against the served model. **This comparison is advisory and NEVER a FAIL in either mode.**

- **The harness imposes NO rule that an adapter's base must equal the served model.** `discover_adapters()` (`HARNESS_README.md:204`) registers adapters as `--lora-modules name=path`, and vLLM applies them to the already-loaded base, so the adapter's own base string is never consulted when choosing serving weights.
- A mismatch (e.g. a bnb-4bit-trained adapter served onto a QAT w4a16 base) is a real **numerical-fidelity risk**, so the gate **WARNs** to surface it — but it does **not** demand a retrain and does **not** block submission.
- `ALLOWED_MODEL_NAMES` (`HARNESS_README.md:185`) constrains the `model:` field declared in `agent.yaml` — a **different field**. Do not conflate the two.

Preferring an adapter trained against the served quantization is a **quality choice**, not a gate requirement. Treat a WARN here as a signal to consider, never as a blocker.
