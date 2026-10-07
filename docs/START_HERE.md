# START HERE — orientation for a new agent on this repo

Read this before touching anything. It exists because a recorded lesson was lost
three separate times, and because three consultants produced confident fixes for
bugs that had already been fixed.

## What this repo is

A Kaggle competition entry: an autonomous SWE agent that fixes GitHub issues in
unseen Python repos. Metric is Resolution Rate over 129 hidden tasks
(fastapi 67, rich 48, requests 13, httpx 1). Submission is **declarative only**:
`agent.yaml` + `sub_agents/*.yaml` + `prompts/*.md` + `configs/*.yaml`, compiled by
the harness' `compile_submission`. There is no `agent.py`.

## Five hard constraints — violating any of these is a serious error

1. **The user alone runs `./start.sh`.** Never run `scripts/run_eval.py`, never
   launch an evaluation, never run tests that execute the agent. Agents read
   artifacts; they do not produce runs.
2. **Model selection belongs to the user.** Never change, propose, enumerate, or
   guess a model ID. Never edit `opencode.json` or any agent definition naming a
   model. Never pass an explicit `model:` argument to a delegation tool unless
   the user gave that exact model in this session. *Passing an explicit model
   killed three spawned agents outright.*
3. **Conservative git.** Do not commit or push unless explicitly asked. Report
   `git status` and propose commands instead.
4. **Use `bd` (beads) for all tracking.** Run `bd prime` at session start. Key
   work into files and memories; do not carry detail in context.
5. **Scratch goes in the scratchpad dir**, never in `/workspace` or the repo.

## The current state of reality — read this twice

- **No local benchmark number is a Gemma 4 number.** Every run in
  `results/run_B*` was served a LiteRouter proxy (`stealth/space-bunny-alpha`).
  The widely-quoted 56/129 = 43.4% is a *proxy* figure. Verified by reading
  `model_name` from every `steps[]` in every trace.
- **The only real Gemma 4 run scored 0/129** (`cloud_results/results/`). Root
  cause is **not** model quality: 77 of 95 traces have
  `total_completion_tokens: 0` and zero tool calls. The model emitted nothing.
  117 of 129 predictions were empty.
- **The gates do not cover this.** `scripts/preflight_check.py` runs 8 real
  checks and never opens `sampling.yaml`.
  The legacy packaging check read `agent.yaml` from the *directory* while
  reading `adapters/` from the *zip* — so an adapter present in one and absent
  from the other passes the gate and silently serves the base model.
- **The graded artifact is `submission.zip`, not `my_submission/`.** Three
  divergent packagers exist and none is authoritative.
  `scripts/verify_and_install_adapter.py` mutates the directory **without**
  repacking the zip, which desynchronises them.

## Strategy (the user's own decision, not a guess)

Build a **model-agnostic harness** first, because Gemma 4 is still an infant and
a Gemma-shaped harness would be wrong once Gemma improves. Then distil what a
strong model does into Gemma 4 via LoRA SFT. Roughly two months of runway.

## File map

| Path | What it is |
|---|---|
| `my_submission/` | the live submission source tree (19 files) |
| `submission.zip` | **the graded artifact** |
| `HARNESS_README.md` | harness contract; every hard limit lives here |
| `docs/IRONCLAD_GATES_PLAN.md` | the four-gate plan to make infra failures impossible |
| `docs/IRONCLAD_RULE_TABLE.md` | machine-checkable constraint list with current values |
| `docs/FINDINGS.md` | evidence store, F1-F11, each with a `file:line` |
| `docs/0*.md` | numbered context docs (constraints, failure modes, verify protocol) |
| `scripts/preflight_check.py` | current gate — 8 checks, **no config/serving layer** |
| legacy packaging check (deleted) | packaging gate — **wrong artifact for most checks** |
| `scripts/build_kaggle_kernel.py` | builds the Kaggle notebook; contains the silent-failure code |
| `cloud_results/` | the only real Gemma 4 artifacts |
| `adapters_staging/`, `checkpoints/` | LoRA weights; **not** in the submission |
| `tasks.jsonl`, `test.txt`, `test_all.txt` | 129 tasks; 77-task and 129-task manifests |

## Traps that have already cost real time

- `my_submission/skills/<n>/<n>.py` **and** `skills/<n>/scripts/<n>.py` both
  exist. Only the `scripts/` copy executes. A fix applied to one copy ships a
  no-op — this already misled a consultant.
- `.DS_Store` is a **disallowed extension** per `HARNESS_README.md:144`. One is
  currently on disk in `my_submission/`. It survives only because the zip excludes
  it; any rebuild that omits the exclusion fails validation.
- Empty directories vanish from zips. `my_submission/adapters/` is empty and
  therefore absent from `submission.zip`.
- Do **not** re-apply the consultant patches at
  `cloud_results/canary_test_results/consultants/20261003/`. They analysed a
  stale `paste.txt` bundle; six of their recommendations are already implemented.
  See `gotcha-consultant-patches-already-applied`.
- A confidence interval is not evidence. Before acting on any behavioural
  statistic, control for task difficulty — the "cap patch size at 1200 bytes"
  recommendation survived an independent recomputation and was *still wrong*,
  because it was Simpson's paradox that would have blocked all 17 winnable tasks.
  See `gotcha-check-confound-before-acting`.
- Shell commands containing literal `\uXXXX`-style escapes break the tool call.
  Use the read tool for those files.

## First three things worth doing

1. Build **G4** (postmortem gate) from `docs/IRONCLAD_GATES_PLAN.md`. It needs no
   GPU, no Kaggle quota, and works on artifacts already on disk. It must report
   `INFRASTRUCTURE FAILURE` on `cloud_results/results/`.
2. Build **G1** (static config gates) — including the prose budget parser that
   catches `prompts/main.md:59` telling the model 50 calls when
   `eval_config.yaml` enforces 40.
3. Build **G2** (artifact gates on the zip) — the drift check and the four-part
   adapter coherence check are the two things that do not exist in any form today.

Do not modify `my_submission/` or `submission.zip` without explicit approval.
