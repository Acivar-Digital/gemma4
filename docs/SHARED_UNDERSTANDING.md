# Shared Understanding — Ironclad Submission Gates

Status: agreed, not yet implemented. Date: 2026-10-04.
Exception: D10 has been REWRITTEN after its original claim was proven false and withdrawn; the replacement mode-aware rule is implemented and landed (`3a63fd5`). See §6.

## 1. The problem

The graded submission can be internally inconsistent and still ship: the prompt
tells the model 50 tool calls while `eval_config.yaml` enforces 40
(`my_submission/prompts/main.md:59`; `my_submission/eval_config.yaml` `max_tool_calls: 40`);
`docs/gemma-and-the-shape-of-doubt.md:136` documents a one-submission-per-day
quota while `.agents/skills/kaggle-submit/SKILL.md:171` asserts five; and the only
real Gemma 4 run scored 0/129 (`docs/FINDINGS.md:41`). Because a false-negative
gate can burn the single daily slot for 24h, the fix must be *provable gates*, not
prose. This record captures 23 decisions so implementation needs no re-litigation.

## 2. Decisions

### D1 — Extend the existing 9 gates, do not build a parallel system
- **Decision:** Add to the EXISTING 9 gates in `.agents/skills/kaggle-submit/SKILL.md:40-53`.
- **Rationale:** That 9-gate audit already existed; a second list is the "too many moving parts" problem.
- **Source of truth:** `.agents/skills/kaggle-submit/SKILL.md:40-53`.

### D2 — Run-health detector is a separate post-run section
- **Decision:** Make the run-health / zero-token detector a SEPARATE POST-RUN SECTION in the same skill, not a numbered pre-submission gate.
- **Rationale:** It runs on completed-run artifacts (`task_results.jsonl`, `traces/*.json`), not submission files, so it does not fit the pre-submission frame.
- **Source of truth:** `.agents/skills/kaggle-submit/SKILL.md` structure; run artifacts under `cloud_results/results/`.

### D3 — Correct 50 -> 40 tool calls everywhere
- **Decision:** The harness enforces 40. Fix the live shipping prompt, `kaggle-submit` Gate 7 (the "50-call ladder", `SKILL.md:51`), and re-tune ladder thresholds (currently calibrated for 50, e.g. "used >= 36") to be proportionate to a 40-call budget. A gate must assert prompt<->eval_config budget parity so it can never drift again. The exact prompt diff is owed to the user before writing it.
- **Rationale:** A false budget in the shipped prompt misleads the model; parity must be machine-enforced.
- **Source of truth:** `my_submission/eval_config.yaml` `max_tool_calls: 40` (vs `prompts/main.md:59` "budget of 50 tool calls", `SKILL.md:51`).

### D4 — Serving config, source-verified: keep thinking ON, delete only `thinking_level`
- **Decision:** Assert `include_thoughts: true` and `enable_thinking: true`; assert `reasoning_effort` is absent from the model's `_additional_args` (i.e., `thinking_level` must be deleted). Matches the LoRA recipe at `HARNESS_README.md:149`.
- **Rationale:** Harness compiled-agent smoke assertions raise if `include_thoughts is not True`, raise if `chat_template_kwargs.enable_thinking is not True`, and raise if `reasoning_effort` appears in `_additional_args`; `reasoning_effort` is exactly what `thinking_level` translates into. IMPORTANT: `my_submission/` currently contains ZERO `thinking_level` occurrences, so the graded submission already complies; the gate asserts absence rather than fixing a present defect.
- **Source of truth:** `docs/gemma-and-the-shape-of-doubt.md` (assertions quoted verbatim in prose; NEGATIVE result: zero hits for `reasoning_effort` in every notebook — `kaggle_canary_eval/canary_eval.ipynb`, `kaggle_test_adk/test_thinking_settings.ipynb` — and in every `scripts/*.py`: `build_canary_eval_kernel.py`, `build_kaggle_kernel.py`, `build_test_notebook.py`; D23). Corroborated by `cloud_results/canary_test_results/CANARY_ANALYSIS_REPORT.md:38-39`; `HARNESS_README.md:149`; current `my_submission/configs/sampling.yaml` has no `thinking_level`.

### D5 — Baseline commit before any gate work, scoped to `my_submission/` only
- **Decision:** Commit a baseline of ONLY the 9 modified files under `my_submission/` before gate work. A blanket `git commit -A` is forbidden. Conservative git profile: no push.
- **Rationale:** The working tree actually has 30 modified files: 2 `data/*.jsonl`, `submission.zip`, `docs/`(5), `tests/`(2), `scripts/`(4), `.gitignore`, `.agents/`, `AGENTS.md`, `CHANGELOG.md`.
- **Source of truth:** working-tree state (30 modified files; D-section correction).

### D6 — One wrapper script replaces the fragile markdown checklist
- **Decision:** A wrapper enforces strict order: gate the working tree -> pack `submission.zip` -> gate the FINISHED zip (drift + root layout) -> print summary + hash -> prompt `Submit? [y/N]` -> only then `kaggle competitions submit`. Refuses to submit on any gate failure.
- **Rationale:** The current checklist packs BEFORE gates can validate the zip, hardcodes a dead interpreter path (`/private/tmp/brun/venv/bin/python`, `SKILL.md:131` — note: this path DOES exist on this machine but does NOT contain swegemma/litellm), and permits submitting an ungated artifact.
- **Source of truth:** `.agents/skills/kaggle-submit/SKILL.md:131`.

### D7 — Submit prompts rather than auto-submits
- **Decision:** The submit step PROMPTS; it never auto-submits.
- **Rationale:** Quota is 1/day, so a gate false-negative burns the slot for 24h irreversibly.
- **Source of truth:** `docs/gemma-and-the-shape-of-doubt.md:136`.

### D8 — Submission quota is ONE per day, not five
- **Decision:** Official rules are one submission/day plus a 12h patch-generation budget. `.agents/skills/kaggle-submit/SKILL.md:171` ("5 submissions per 24-hour UTC window", uncited) is a defect to fix. The wrapper shows today's usage and hard-refuses a second same-day submit without an explicit override flag.
- **Rationale:** The official-rules doc is authoritative; SKILL.md:171 is the lie.
- **Source of truth:** `docs/gemma-and-the-shape-of-doubt.md:136`; `.agents/skills/kaggle-submit/SKILL.md:171`.

### D9 — The graded submission MUST ship the LoRA adapter
- **Decision:** `my_submission/adapters/` must be populated and `adapter: main_lora` declared in `agent.yaml`. The earlier apparent policy flip-flop is explained: local validation runs through a non-Gemma LiteRouter proxy that cannot load a Gemma LoRA, so the adapter is stripped for LOCAL tests only. This is a DECLARATION-and-PRESENCE obligation (`HARNESS_README.md:202-203`) and nothing more — it carries no implication about which base model the adapter was trained on; see D10 for how the base comparison is handled (WARN) and for the `submit`/`local_test` mode split that encodes this local-vs-graded distinction.
- **Rationale:** The graded artifact on Kaggle must carry the adapter; only local runs omit it.
- **Source of truth:** `my_submission/agent.yaml` (no `adapter:` key today); `my_submission/adapters/main_lora/` (empty today); `HARNESS_README.md:202-203`.

### D10 — Adapter gate is MODE-AWARE; the base-model comparison is a WARN, not a harness rule
- **Decision:** The adapter gates enforce one of two modes, selected by `--mode` CLI flag > `GATE_SUBMISSION_MODE` env var > policy default `submission_mode: submit` (`scripts/gate_policy.yaml` `adapter.submission_mode`). The default is fail loudly. `submit` (default): the adapter MUST be declared in `agent.yaml` AND MUST be present in `adapters/`; either missing is a hard FAIL. `local_test` (explicit opt-in): the adapter MUST be explicitly turned OFF (no `adapter:` key) — a still-declared adapter is a hard FAIL, so there is no silent middle state in which an adapter is nominally in use but absent. In BOTH modes the adapter's `base_model_name_or_path` vs the served model is a WARN about numerical fidelity only: it never FAILs, and it never claims the harness requires a match or that a retrain is required.
- **Rationale:** `HARNESS_README.md` contains ZERO rules requiring an adapter's `base_model_name_or_path` to equal the served model. `ALLOWED_MODEL_NAMES` (`:185`) constrains the `model:` field DECLARED in `agent.yaml` — a different field from the adapter's own config. `discover_adapters()` (`:204`) registers adapters as `--lora-modules name=path` and vLLM applies them to the ALREADY-LOADED base, so the adapter's base string is never consulted when choosing serving weights. The real obligations are only declaration and presence (`:202-203`). A bnb-4bit-trained adapter (`unsloth/gemma-4-31B-it-unsloth-bnb-4bit`) served onto a QAT w4a16 base is still a real numerical-fidelity risk worth surfacing — which is why it is a WARN, not silence.
- **Source of truth:** `HARNESS_README.md:202-203` (adapter placement + `adapter:` declaration are the only adapter obligations), `:185` (`ALLOWED_MODEL_NAMES` governs the declared `model:` field, not the adapter's base), `:204` (`discover_adapters()` / `--lora-modules`; the adapter's own base string is never consulted); implementation `scripts/check_submission.py` `g_adapter_declared`, policy `scripts/gate_policy.yaml` `adapter.*`; landed in `3a63fd5`. Staged adapter base observed at `adapters_staging/main_lora/adapter_config.json`; served model `gemma-4-31b-it-qat-w4a16-ct` (`scripts/build_kaggle_kernel.py` `TARGET_MODEL_NAME`).

### D11 — Delete the 5 duplicated root skill scripts
- **Decision:** Delete `my_submission/skills/<n>/<n>.py`; keep `skills/<n>/scripts/<n>.py` as the single source of truth. Verified safe: all 5 pairs are byte-identical (md5), nothing imports the root copies, SKILL.md references the script as a bare `file_path="<n>.py"` which the harness resolves into `scripts/`, and harness-dumped manifests show only the `scripts/` copy executing. NOTE: this reverses an earlier finding that called the root copy a "dead duplicate" — the CHANGELOG says the mirroring was INTENTIONAL ("mirrored across `scripts/` and root", `CHANGELOG.md:503`), so the real risk was drift.
- **Rationale:** Root copies are unused duplicates that can drift; `scripts/` copy is what runs.
- **Source of truth:** md5 identity of the 5 pairs (verified identical); `CHANGELOG.md:503`.

### D12 — Keep the shared workspace-resolution logic duplicated (tech debt)
- **Decision:** The `_orig_cwd` stack-frame inspection + `SWEGEMMA_WORKSPACE`/`WORKSPACE_DIR` env-var ladder, duplicated across all 5 executed skill scripts, plus scattered output caps, STAYS duplicated — filed as tech debt, deliberately out of scope.
- **Rationale:** Extracting it now risks the proven scripts; tracked for later.
- **Source of truth:** the 5 `my_submission/skills/<n>/scripts/<n>.py`.

### D13 — One central policy file
- **Decision:** Gate policy (served model name, 9-tool allowlist, context limits, adapter base model [advisory/WARN — D10], size/extension caps, dirty/drift rules) lives in ONE central policy file; every gate reads it.
- **Rationale:** Policy scattered across files is precisely how the 50-vs-40 lie survived in three places.
- **Source of truth:** (this decision).

### D14 — Gate code layout is exactly THREE new files
- **Decision:** `scripts/check_submission.py` (all gate checks as functions, shared result shape), the central policy file (D13), and the wrapper script (D6). `SKILL.md` stays the human-readable description and points at the script as executable truth.
- **Rationale:** Keep gate logic executable and singular; prose describes, script enforces.
- **Source of truth:** (this decision).

### D15 — G3 IS IN SCOPE: fix silent-failure sites in `build_kaggle_kernel.py`
- **Decision:** Fix the three silent-failure sites — `:149` `litellm.drop_params = True` masking unsupported params; `:153-157` prints `MODEL_PATH.exists()` but never asserts; `:288` bare `except Exception` that never writes `task_results.jsonl` — AND wire in the live bridge health gate, REUSING the existing implementation already written in `docs/gemma-and-the-shape-of-doubt.md:2818` (D19), not authoring a fresh one. HONEST CAVEAT (unchanged): the health gate cannot be proven without a real Kaggle run; only the user can start one. It must fail loudly and early, and be labelled as needing the user's first run to validate.
- **Rationale:** These swallow real failures and produced a 0/129 run; making them loud is the point.
- **Source of truth:** `scripts/build_kaggle_kernel.py:149`, `:153-157`, `:288`.

### D16 — Validation is a pytest suite in the EXISTING `tests/` directory
- **Decision:** Every gate test asserts PASS on current HEAD and FAIL on a real known-bad artifact already in this repo: `sampling.yaml` with `max_output_tokens: 16384`, `prompts/main.md` claiming 50 calls, the 0/129 `cloud_results/` run, and the missing-adapter state (`my_submission/agent.yaml` has no `adapter:` key; `my_submission/adapters/main_lora/` is empty). NO synthetic fixtures. A gate that cannot be shown red against a genuinely bad artifact is marked unproven in the policy file and reported as such, never quietly passing. CORRECTION (see D10 and §6): the `adapters_staging/` base-model mismatch is deliberately NOT a red fixture — that comparison is a WARN, so it cannot FAIL. Its test asserts the WARN and asserts the gate never claims a match is required (`test_no_gate_output_claims_base_equality_is_a_harness_requirement`).
- **Rationale:** A gate never seen red is a gate of unknown behavior; real artifacts are the only honest proof.
- **Source of truth:** `tests/` (already holds `test_code_map_gauntlet.py`, `test_code_oracle.py`, `test_fast_grep_gauntlet.py`, `test_repro_check_diagnostics.py`, `test_test_gate.py`); known-bad `my_submission/configs/sampling.yaml:3` `max_output_tokens: 16384`.

### D17 — Scope THIS pass
- **Decision:** Baseline commit (`my_submission/` only); the 50->40 prompt correction + ladder re-tune; verify `sampling.yaml` serving values; delete the 5 root skill copies; central policy file; `scripts/check_submission.py`; proven-red pytest suite; the gate->pack->gate->prompt->submit wrapper; kernel silent-failure fixes + live health cell.
- **Rationale:** This is the set that can be implemented and proven before spending the daily slot.
- **Source of truth:** (this decision).

### D18 — DEFERRED to tickets
- **Decision:** Defer: an OPTIONAL, purely numerical-fidelity LoRA retrain onto `gemma-4-31b-it-qat-w4a16-ct` (needs user GPU) — NOT required by any harness rule and NOT required by any gate; it is deferred only as a quality improvement the owner may optionally take (see D10, which demoted this from an obligation to a WARN); Type A shared-config extraction across the 5 skill scripts; prompt-level hardening for the ~18 runtime-only infra failure modes.
- **Rationale:** Each needs GPU time or touches proven scripts; out of scope for this pass.
- **Source of truth:** (this decision).

### D19 — Reuse the existing health gate; do not write a fresh one
- **Decision:** PORT the already-complete, hash-pinned inference health gate out of `docs/gemma-and-the-shape-of-doubt.md:2818` (an escaped Python string literal, `SAMPLING_HEALTH_RUNNER`) into a real reviewable `.py` module and wire it into the kernel builder. Do NOT author a fresh health cell — the prior art already solved the hard parts.
- **Rationale:** That literal implements the ENTIRE G3 design (D15): `_probe_endpoint()` calls `/health` then `/v1/chat/completions` and asserts the reply is exactly `"4"`; `probe_endpoint()` wraps the call in a daemon thread with an ABSOLUTE wall deadline (its comment states plainly that "Socket timeouts alone do not bound a slow-drip response"); `install_health_gate()` runs the probe before every task, writes rows to `endpoint_health.jsonl`, sets `enters_agent_history=False`, and raises `EndpointUnhealthy(BaseException)` — deliberately outside ordinary per-task error handling — so an infra failure aborts the campaign rather than retrying; `checked_base()` hash-pins the evaluator to `BASE_SHA256 = fd8578f06a727d5eea1a247acb9e98a82b01d8e89cb45d868239f3fce25b5aa4`.
- **Source of truth:** `docs/gemma-and-the-shape-of-doubt.md:2818`.

### D20 — Extract ALL embedded code literals from docs into real files
- **Decision:** Extract every escaped code literal that the project depends on into real files, so nothing operational hides in prose.
- **Rationale:** SIX escaped code literals live in `docs/gemma-and-the-shape-of-doubt.md` (761,598 bytes, 4,161 lines — the largest doc in the repo). They are substantial Python programs: the health runner, the adviser diagnostic, audit/verifier logic, and plotting/rendering code. They are invisible to any `grep` of `.py` files, which is exactly how the earlier research wrongly concluded "no `/health`, no `/v1/models`, no warm-up exists anywhere in the repo." That is a whole failure class — code the project depends on, invisible to search.
- **Source of truth:** `docs/gemma-and-the-shape-of-doubt.md:2695`, `:2696`, `:2794`, `:2818`, `:2819`, `:1175`.

### D21 — Extraction fidelity: verbatim, annotate, and gate
- **Decision:** Extract each of the 6 literals VERBATIM (byte-identical behavior to what the doc describes) into a real `.py` under `scripts/`. KEEP the markdown copies intact — annotate the doc to point at the new real file. Add a gate that FAILS if any `docs/*.md` still contains a large escaped code literal.
- **Rationale:** The doc appears designed as a portable, self-contained auditable artifact; deleting the literals would destroy that reproducibility record, so annotate rather than remove. Verbatim extraction is the lowest-risk way to make invisible code visible without changing behavior. Because a fresh doc could hide new code, the presence gate is required — otherwise the failure class recurs.
- **Source of truth:** (this decision); doc-integrity constraint per `docs/gemma-and-the-shape-of-doubt.md` structure.

### D22 — Use `git grep`, never `grep -r`, in this repo
- **Decision:** Use `git grep -l` over tracked files for all repo-wide search. Use `git ls-files --error-unmatch <path>` (sentinel exit code) rather than `[ -e ]` or bare `git ls-files` output when proving a file is tracked.
- **Rationale:** Plain `grep -r` TIMES OUT in this repo — 60s and 90s attempts both failed — because of large directories (`data/`, `models/`, `checkpoints/`, `backups/`, `embeddings/`, `cloud_results/`). `git grep -l` over tracked files is fast and complete.
- **Source of truth:** two timed-out `grep -r` invocations this session.

### D23 — The smoke-assertion citations resolve to a doc, not a notebook
- **Decision:** When citing the compiled-adviser smoke assertions (`include_thoughts is not True`, `enable_thinking is not True`, and `"reasoning_effort" in _additional_args` → "Unsupported reasoning_effort must not reach the endpoint"), cite the DOC, never a notebook path.
- **Rationale:** Those three assertions exist in NO notebook and NO `scripts/*.py`: `kaggle_canary_eval/canary_eval.ipynb`, `kaggle_test_adk/test_thinking_settings.ipynb`, `scripts/build_canary_eval_kernel.py`, `scripts/build_kaggle_kernel.py`, and `scripts/build_test_notebook.py` ALL have ZERO hits for `reasoning_effort`. They are quoted verbatim inside `docs/gemma-and-the-shape-of-doubt.md` (see D4).
- **Source of truth:** `git grep -ln reasoning_effort -- '*.ipynb' 'scripts/*.py'` returns zero matches; the assertions appear in `docs/gemma-and-the-shape-of-doubt.md`.

## 3. What we are NOT doing (and why)

- Not replacing `SKILL.md` — extend its 9 gates (D1).
- Not auto-submitting — prompt, because a false-negative costs the daily slot (D7).
- Not inventing an adapter-base ALLOWLIST — there is no harness rule to allowlist against in the first place, and the gate WARNs on base mismatch for numerical fidelity rather than claiming a match is required (D10).
- Not deleting the `scripts/` skill copies — those are the ones that run (D11).
- Not extracting shared skill config now — tech debt, deliberately out of scope (D12).
- Not asserting gate thresholds derived only from `HARNESS_README` — project-rule limits must be asserted separately (D-section correction).
- Not inventing synthetic test fixtures — gates prove red only against real known-bad artifacts (D16).
- Not authoring a fresh health cell — the complete hash-pinned gate already exists and is ported verbatim (D19).
- Not deleting the markdown code literals — annotate the doc and extract alongside, preserving the self-contained auditable record (D21).
- Not using `grep -r` — it times out in this repo; `git grep -l` is fast and complete over tracked files (D22).
- Not doing prompt-level hardening for the ~18 runtime-only infra modes — deferred (D18).
- Not attempting to fix the upstream LiteLLM `json.loads` crash on unescaped multi-line tool args: unpatchable in Container B. Affects `fastapi_15588`, `rich_3894`, `rich_3521`, `rich_3676`, `fastapi_14258`.

## 4. Files to be created or modified

| File | Action | Decision |
| :--- | :--- | :--- |
| `scripts/check_submission.py` | create | D14 |
| central policy file (path TBD) | create | D13 |
| wrapper script (path TBD) | create | D6 |
| `scripts/candidate_gpu_validation_runner.py` | create (extract from `CANDIDATE_GPU_VALIDATION_RUNNER`, doc `:2695`) | D20,D21 |
| `scripts/fastapi_test_environment.py` | create (extract from `FASTAPI_TEST_ENVIRONMENT`, doc `:2696`) | D20,D21 |
| `scripts/comparison_report_source.py` | create (extract from `COMPARISON_REPORT_SOURCE`, doc `:1175`) | D20,D21 |
| `scripts/screen_bundle_builder.py` | create (extract from `SCREEN_BUNDLE_BUILDER`, doc `:2794`) | D20,D21 |
| `scripts/sampling_health_runner.py` | create (extract from `SAMPLING_HEALTH_RUNNER`, doc `:2818`) | D19,D20,D21 |
| `scripts/v18_comparison_plot.py` | create (extract from `V18_COMPARISON_PLOT`, doc `:2819`) | D20,D21 |
| `docs/gemma-and-the-shape-of-doubt.md` | modify (annotate the 6 literals to point at their extracted `.py`; literals stay) | D21 |
| `.agents/skills/kaggle-submit/SKILL.md` | modify (extend gates, fix `:171` quota 5/day→1/day per D8, add post-run section, annotate extracted-code pointers) | D1,D2,D6,D8,D21 |
| `my_submission/prompts/main.md` | modify (50->40) | D3 |
| `my_submission/skills/<n>/<n>.py` (x5) | delete | D11 |
| `scripts/build_kaggle_kernel.py` | modify (silent-failure fixes + wire in reused health gate) | D15,D19 |
| `tests/test_check_submission.py` | create | D16 |
| baseline commit of 9 `my_submission/` files | git commit (scoped, no push) | D5 |

Deferred/not touched this pass: optional numerical-fidelity LoRA retrain (not required by any harness rule — D10), shared-config extraction, prompt hardening (D18).

## 5. Honest limits — what this cannot fix

- ~18 of 28 catalogued infra failure modes are RUNTIME-ONLY: test edits silently reset in Container B; scratch swept into the patch by `git add -N . && git diff HEAD`; bare `pytest` exceeding the 300s `run_command` kill; FAIL_TO_PASS SKIPPED with exit 0; exceptions swallowed at `build_kaggle_kernel.py:288`; regex backtracking in `code-oracle`; missing `setitimer` guard on `--eval`. Gates make these DETECTABLE, not preventable. (`docs/IRONCLAD_GATES_PLAN.md:198`)
- G3 cannot be proven from this machine. Do not claim otherwise.
- D4 is corroborated from a SECOND, independent source: `cloud_results/canary_test_results/CANARY_ANALYSIS_REPORT.md:38-39` records the same root cause — "LiteLLM in the Kaggle runner was translating `thinking_level: 2` into `reasoning_effort: medium`, which the Gemma 4 C++ bridge rejected with `RuntimeError: unsupported reasoning_effort in Gemma bridge`" — and states the canary's objective was to "Validate that omitting `thinking_level` completely from `configs/sampling.yaml`" allows native Gemma 4 execution without bridge crashes. This is the same conclusion D4 reaches, from a different artifact.
- No valid Gemma 4 measurement exists: the only real run scored 0/129 with 77/95 traces at zero completion tokens. All local benchmarks ran a LiteRouter proxy (`stealth/space-bunny-alpha`), so NO local number is a Gemma 4 number. (`docs/FINDINGS.md:41`; `docs/START_HERE.md:38`; `docs/IRONCLAD_GATES_PLAN.md:163`)
- The legacy packaging check (:59) read `agent.yaml` from the DIRECTORY while `:62` read `adapters/` from the ZIP, and `verify_and_install_adapter.py` injected into the directory without repacking — so the packaging gate could pass while Kaggle received a zip with no adapter. Zip-vs-directory byte identity was not verified in-session.
- The legacy packaging check (:78) computed `size_mb` from the COMPRESSED zip size against a 3072MB threshold and printed "< 3 GiB", but `HARNESS_README.md:134` requires the limit on UNPACKED total.

## 6. Corrections made during the interview (things asserted then retracted)

- RETRACTED: "4096 / thinking 4096 was canary-proven." The canary actually shipped `max_output_tokens: 2048`, `thinking_budget: 2048` (`docs/gemma-and-the-shape-of-doubt.md:236-238`).
- RETRACTED: "omit `thinking_config` entirely." That disables thinking, which the harness treats as off-profile.
- RETRACTED (a relayed CHANGELOG claim): "`thinking_budget: 0` is rejected by the ADK validator." `kaggle_test_adk/test_thinking_settings.ipynb:103` shows `thinking_budget: 0` was written and run; `HARNESS_README.md:148` says use 0 or `include_thoughts: false` to disable thinking.
- RETRACTED: "`my_submission/.DS_Store` is git-tracked, a committed defect." It is NOT tracked; the earlier `git ls-files` line was echoed output from a different command. It is an on-disk file that survives only because the zip command excludes it.
- RETRACTED: "the working tree has 9 modified files." It has 30.
- CORRECTED: "4096/16384 is wrong because the README sum-limit would green-light it." The real defect is that the `max_output_tokens <= 4096` rule is a PROJECT rule derived from `token_threshold: 14336` and must be asserted separately — the README limit alone (`max_output_tokens + thinking_budget <= 32768`) passes at 16384+4096=20480.
- NOTE (open, unresolved tension): `HARNESS_README.md:148` says the canary validated omitting `thinking_level`; `docs/FINDINGS.md:90-92` adds the caveat that `thinking_budget: 4096` with `include_thoughts: true` "may still trip LiteLLM translation". Recorded as open, not settled.
- RETRACTED (tooling): "no `/health`, no `/v1/models`, no warm-up exists anywhere in the repo." WRONG. A working, hash-pinned implementation already existed — as an escaped Python string literal inside `docs/gemma-and-the-shape-of-doubt.md:2818` (`SAMPLING_HEALTH_RUNNER`), invisible to any grep of `.py` files. Cause: searching for code by scanning source files, when the code was embedded in prose. Fix: extract embedded literals to real files (D20) and gate that no `docs/*.md` hides a large literal again (D21). Generalizable lesson — a search that only looks in one file type cannot prove a negative.
- RETRACTED (tooling): "use `grep -r` for repo-wide search." It TIMES OUT here (60s and 90s attempts both failed) on large directories (`data/`, `models/`, `checkpoints/`, `backups/`, `embeddings/`, `cloud_results/`). Use `git grep -l` over tracked files, and `git ls-files --error-unmatch <path>` (sentinel exit code) to prove a path is tracked — not `[ -e ]`, not bare `git ls-files` output (D22). This was the second tooling cause of the wrong negative above: a timed-out search was mistaken for an empty result.
- RETRACTED (fabricated requirement): "the gate requires the adapter's `base_model_name_or_path` to equal the served model exactly." FABRICATED — no such rule exists in the harness. `HARNESS_README.md` has ZERO hits for any adapter-base-equals-served-model requirement. The nearest real constraints are different fields and different mechanisms: `ALLOWED_MODEL_NAMES` (`:185`) constrains the `model:` field declared in `agent.yaml`, NOT the adapter's own config; `discover_adapters()` (`:204`) registers adapters as `--lora-modules name=path` and vLLM applies them to the ALREADY-LOADED base, so the adapter's base string is never consulted when choosing serving weights. The only real adapter obligations are declaration and presence (`:202-203`). Cause: a plausible-sounding constraint was asserted as an established harness requirement without a `file:line` citation proving it — the one citation in the original D10 pointed at the adapter's own config and at a served-model constant, i.e. it proved only that the two STRINGS DIFFER, never that the harness FORBIDS it. Damage: presented to the owner as a harness requirement, producing a bad recommendation to retrain the LoRA onto the QAT base — an expensive action that also needs a GPU the owner does not have. Fix (landed `3a63fd5`): D10 rewritten to the implemented mode-aware rule — `submit` (default) requires the adapter declared AND present, `local_test` requires it explicitly off, and in both modes the base comparison is a WARN about numerical fidelity that never claims a harness rule or a retrain. Regression guard: `test_no_gate_output_claims_base_equality_is_a_harness_requirement` in `tests/test_check_submission.py` fails if any gate output ever re-asserts that base equality is a harness requirement. Generalizable lesson — a constraint without a `file:line` citation is a hypothesis, not a requirement; the same discipline D22 applies to proving a negative applies to asserting a positive.