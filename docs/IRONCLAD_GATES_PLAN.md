# Ironclad Submission Gates — Plan

Authored 2026-10-04. Status: PROPOSED, nothing implemented. No file in
`my_submission/` or `submission.zip` has been modified.

## 1. Thesis

**One command. One verdict. Four gates, ordered by cost.**

The graded artifact is `submission.zip`. Every gate must read the zip, not the
directory, except where the directory is genuinely the input — and a dedicated
drift check must reconcile the two. That single rule is the spine of this plan.

## 2. Why 0.03 and 0/129 both got through

Three independent causes, each verified:

| Cause | Evidence |
|---|---|
| **Preflight checked the wrong layer.** 8 real checks (module imports, 124 wheels, compilation, sandbox pytest, snapshot pytest, live diagnostics) and **zero** references to `max_output_tokens`, `thinking_config`, `adapter`, `lora`, `sampling.yaml`. It never opens the file that broke. | `scripts/preflight_check.py` — no `import yaml` anywhere |
| **Packaging gate checked the wrong artifact.** Legacy packaging check (:59) read `agent.yaml` from `my_submission/`; `:62` read `adapters/` from the zip; `:105/:117/:136` all read the directory. An adapter injected into the directory but absent from the zip **passed the gate** and silently served the base model. | Legacy packaging check (deleted) |
| **The kernel was written to swallow the exact errors we needed.** `litellm.drop_params = True` discards unrecognised params instead of erroring; `except Exception` at cell_3 converts every per-task fault to a printed line never written to `task_results.jsonl`; `MODEL_PATH.exists()` is printed but never asserted; the full-eval kernel has **no adapter mount step and no adapter print**. | `scripts/build_kaggle_kernel.py:149`, `:153-157`, `:288` |

A lesson was written down and lost anyway: `gotcha-litellm-reasoning-effort-rejection`
records `include_thoughts: false`, while `my_submission/configs/sampling.yaml:6`
still reads `include_thoughts: true`. Recording is level 1. Gates are level 2.

## 3. The four gates

| Gate | Catches | Needs | Cost | Catches retroactively? |
|---|---|---|---|---|
| **G1 static config** | Bad YAML values in the shipped config | nothing | <1s | yes, on the current tree |
| **G2 artifact** | Zip/dir drift, missing adapter, junk, size, allowlist | nothing | <1s | yes |
| **G3 kernel health** | Degenerate generation, unmounted adapter, unready server | a serving endpoint | ~30s | no |
| **G4 postmortem** | A run that scored ~0 because infra was broken | existing artifacts | <2s | **yes — on the 0/129 run already on disk** |

### G1 — Static config gates

Assertions, all from `HARNESS_README.md` with line numbers recorded in
`docs/IRONCLAD_RULE_TABLE.md`:

1. `max_output_tokens + thinking_budget <= 32768` (README:128,178).
2. `max_output_tokens <= 4096`. **Not a README rule** — a project rule derived
   from `token_threshold: 14336`. At 16384 the prompt is starved to ~16K and
   compaction fires mid-task. The README sum-limit *passes* at 20480, so rule 1
   alone would green-light the exact value that broke the run. This is why the
   interaction rule exists separately.
3. `sampling.yaml` contains **no** `thinking_level` key (README:149 — must be
   omitted when serving LoRA via vLLM; LiteLLM maps it to `reasoning_effort`,
   which the Gemma bridge rejects).
4. Every `model:` across `agent.yaml` + all `sub_agents/*.yaml` resolves to the
   single allowed model `gemma-4-31b-it-qat-w4a16-ct` (README:177,185).
5. `timeout_seconds <= 300` (README:381).
6. `max_tool_calls >= 20`, else the harness budget warning can never fire
   (README:371).
7. **Prompt/eval budget coherence**: parse every integer budget the model is
   told about out of `prompts/*.md` and `SKILL.md`, and assert each is `<=`
   `eval_config.yaml`'s `max_tool_calls`. **This is the gate that catches the
   live 50-vs-40 lie at `prompts/main.md:59`.** A hardcoded number in prose
   cannot be caught by a schema validator — it needs a prose parser.
8. `thinking_budget >= 1` if present (CHANGELOG.md:21 — `0` is rejected by the
   ADK Pydantic validator). Reconciles the apparent conflict between rule 3 and
   the canary's advice.

**DoD:** G1 fails on the current tree. Specifically `max_output_tokens: 16384`
(rule 2) and `include_thoughts: true` / `thinking_budget: 4096` (rule 3) must be
reported as failures. A gate that passes on the tree that produced 0/129 is
useless by construction.

### G2 — Artifact gates on the zip

1. **Drift**: every file in the zip is byte-identical to its directory
   counterpart (sha256), and every non-excluded directory file is present in
   the zip. This is the check that does not exist today.
2. `agent.yaml` at zip root, exactly one root config (README:72,97).
3. **Adapter coherence, three-part**: if any agent declares `adapter:` then
   (a) `adapters/<name>/adapter_model.safetensors` exists **in the zip**, (b)
   `r <= 128` (README:169), (c) recorded sha256 equals the recorded build
   manifest. Today only (a)-in-zip and (b) are partially attempted, and (a) is
   satisfied by *either* signal so a directory-only adapter passes.
   **RETRACTED 5 Oct 2026:** the former clause (b), which required an adapter's recorded base
   model to equal the served model, was a **fabricated requirement** — no such harness rule
   exists. See `SHARED_UNDERSTANDING.md:192`. `ALLOWED_MODEL_NAMES` (README:185) constrains the
   `model:` field declared in `agent.yaml`, not the adapter's own config, and
   `discover_adapters()` (README:204) applies LoRA modules to the already-loaded base without
   ever consulting the adapter's base string. The gate above is therefore three-part, not four.
4. Extension allowlist `.yaml,.yml,.md,.txt,.py,.json,.safetensors` (README:144).
   `.DS_Store` is **disallowed** and is currently present on disk in
   `my_submission/` — it survives only because the zip excludes it.
5. `.DS_Store`/`._*`/`.pyc`/`__pycache__` count == 0 in the zip.
6. **Unpacked** total < 3 GiB (README:134). Today's gate uses
   `ZIP_PATH.stat().st_size` — the *compressed* size — against a 3072 MB
   threshold (legacy packaging check :78-79). Wrong metric, and the message even
   prints "< 3 GiB". Fix to sum the unpacked entry sizes.
7. `max_file_count <= 10000`, `max_yaml_files <= 1000`, YAML <= 50 MiB,
   skill dir <= 50 MiB (README:135-138).
8. `!include` graph: depth <= 10, no `..`, no absolute paths, no symlink escape,
   extension allowlist `.md/.txt/.yaml/.yml` (README:100-102).
9. Agent tree: one root config, `max_agents <= 500`, `max_sub_agent_depth <= 50`,
   `instruction` <= 1e6 chars each and <= 1e7 total (README:139-141).
10. **Dead-file check**: assert `skills/<n>/<n>.py` and
    `skills/<n>/scripts/<n>.py` are byte-identical, or delete the unused copy.
    Today both exist and only the `scripts/` copy executes — a 200 KB doubled
    review surface that already confused a consultant into patching the wrong
    copy.
11. `compile_submission` runs against the **zip**, not the directory.

**DoD:** G2 fails today because `my_submission/.DS_Store` is present and
`adapters/` is an empty directory that will vanish from the zip. It must also
fail if the adapter is declared in the directory but absent from the zip —
reproducing the F10/F11 state on demand.

### G3 — Kernel health gate (runs inside the Kaggle kernel, not locally)

The user has no local GPU, so a local smoke test is not the answer. The answer
is to make the *kernel* assert its own health before the eval loop, so a
degenerate run produces **no score at all** instead of 0.03.

Insert as the last cell of `build_kaggle_kernel.py`, after server start and
before `Evaluator.evaluate_task`:

1. **Assert** `MODEL_PATH.exists()` — currently printed, never asserted.
2. GET `/health` and `/v1/models`; assert HTTP 200 and that the served model id
   matches the declared `agent.yaml` model. **Neither probe exists anywhere in
   the repo today.**
3. If any adapter is declared: assert `discover_adapters` returned non-empty,
   print the manifest, and assert `enable_lora` is true. The full-eval kernel
   currently has no adapter step at all, so this is unobservable.
4. **One warm-up `/v1/chat/completions` call.** Assert HTTP 200,
   `choices[0].message.content` non-empty, `usage.completion_tokens > 0`, and
   that the model id in the response matches. This single call would have
   caught the 0/129 run.
5. Report `litellm.drop_params` dropped-parameter list, or set it to `False`
   so a rejected parameter raises instead of being discarded.
6. Write a machine-readable `kernel_health.json` next to `task_results.jsonl`.

**DoD:** the gate raises and the kernel exits non-zero before the eval loop on
any of: model path missing, server not ready, no adapter when one is declared,
or empty completion. **Honest limit: I cannot prove this against real Gemma 4
serving from here — it needs one Kaggle run.** It is designed to fail loudly, not
to be a proven-true assertion.

### G4 — Postmortem gate (highest leverage, runs on artifacts already on disk)

`cloud_results/results/` already contains everything needed to detect a broken
run. This gate parses a completed run and **fails loudly on the degenerate
signature**, turning "0.03 discovered days later" into "this run produced zero
tokens".

1. `task_results.jsonl`: `resolved` count, `test_exit_code` histogram,
   `tool_calls` histogram, empty `patch` count.
2. `traces/*.json`: `total_completion_tokens == 0` count, `total_steps` <= 2
   count, `tool_calls == 0` count.
3. **Degenerate-run verdict**: if `completion_tokens == 0` for a majority of
   traces, or `tool_calls == 0` for a majority, or zero non-empty predictions —
   emit `INFRASTRUCTURE FAILURE, NOT A QUALITY RESULT` and exit non-zero.
4. Distinguish the four causes by fingerprint:
   - all-zero tokens, server never ready -> serving
   - tokens present, no source edit -> tool-call / prompt
   - edits present, `resolved=false`, test_exit_code=1 -> genuine quality
   - `test_exit_code=-1` majority -> test harness / timeout, not the agent
5. Compare against the previous run and flag regressions > 20%.
6. Scan prompts and skills for the recorded prompt-layer defects: backtick
   pseudo-code fences, `python3 <script>` shell affordances in a shell-less
   agent, duplicate-deadline numbers.

**DoD:** run against `cloud_results/results/`. It must report
`INFRASTRUCTURE FAILURE` and reproduce 77/95 zero-token traces, 117/129 empty
predictions, and the `test_exit_code` histogram. **This gate is provable today
with no GPU and no Kaggle quota.** It is the one deliverable that converts a
known-bad run into a regression test.

## 4. The moving-parts problem

The user's complaint is "too many moving parts". The anti-pattern is adding six
new scripts. The design constraint is therefore:

- **One entrypoint**: `scripts/check_submission.py --gate all` (or a `make
  check`). Prints one verdict line and exits 0/1.
- **Four gate modules**, one file each, sharing one `CheckResult` Pydantic model
  and one reporter.
- **Tiered by dependency**, so a partial environment degrades to a clear
  "SKIPPED (needs serving endpoint)" rather than a false pass.
- **G1/G2/G4 require nothing.** They run anywhere, in under 4 seconds total.
  They are the ones that must always run.
- **Reuse, do not rewrite**: `preflight_check.py` keeps its 6 checks as a
  sub-suite invoked by G2; legacy packaging check's valid checks are folded in
  rather than duplicated. Net new files: 4, not 10.
- **One report format** (JSON) written to `artifacts/gate_report.json` so runs
  are diffable across time.

## 5. What this plan does NOT cover

Stated plainly, because a false assurance is worse than a known gap:

- It cannot prove G3 against real Gemma 4 serving. Only one Kaggle run can.
- It cannot detect upstream LiteLLM bugs — the `json.loads` crash on unescaped
  multi-line tool args affected 5 tasks and is unpatchable in Container B.
- It cannot make a *correct* submission score higher. Infra correctness is
  necessary and not sufficient.
- It does not address that all local benchmarks ran a proxy model, so no local
  number is a Gemma 4 number. That is a separate, unresolved problem.
- 18 of the 28 catalogued failure modes are runtime-only and are not fully
  gate-able. G3 and G4 cover them as *detection*, not prevention.

## 6. Order of work

| # | Slice | Depends on | Effort |
|---|---|---|---|
| S1 | G4 postmortem | nothing | 3h — **do first**, provable today |
| S2 | G1 static config + prose budget parser | nothing | 4h |
| S3 | G2 artifact, incl. drift + adapter coherence | nothing | 5h |
| S4 | Single entrypoint + shared model/reporter | S1-S3 | 2h |
| S5 | G3 kernel health cell | S2 (reuses rule table) | 4h — needs a Kaggle run to prove |
| S6 | Docs + onboarding + `bd` memory | S1-S5 | 2h |

S1-S3 are independent and parallelisable: no shared file. S4 depends on all
three. S5 is independent of S4.

## 7. The validation principle

**Every gate must be proven to FAIL on a known-bad artifact that already exists
in this repository.** Not a synthetic fixture — the real thing that produced
0.03 and 0/129. A gate that has never been shown red is not a gate, it is a
comment. This is the specific lesson of this project: `preflight_check.py` was
substantial, competent, and had never been shown red against the config that
scored zero.
