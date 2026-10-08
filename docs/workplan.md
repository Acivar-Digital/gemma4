# Workplan — Gemma 4 Developer Agent: Error Taxonomy & Isolation Sequence

**Created:** 2026-10-05 | **Updated:** 2026-10-08
**Status:** ACTIVE (Track 1 Locked at 0.13; Track 2 Master Plan in §7 — Epic `gemma4-wzlk`)
**Rule:** one variable per submission. No bundling. Execution is user-only via `./start.sh`.

---

## 0A. Findings ledger — what is certain, and what is not

**Verified 2026-10-05 against primary artifacts + the Kaggle API. Read this before Section 1;
Section 1 predates it and is partly superseded by C5.**

### 0A.1 Timeline — two eras that must never be conflated

| Event | UTC | Tree state |
|---|---|---|
| `cloud_results` run (0/129) | 2026-10-01 06:59 → 14:08 | **HAD** `thinking_level: 2` |
| Submission `56765397` → **0.03** | 2026-10-02 04:10 | **HAD** `thinking_level: 2` |
| Commit `bfc0614` removes `thinking_level` | 2026-10-03 11:31 | — |
| Submission `56810465` → **0.00** | 2026-10-04 00:51 | **DID NOT have it** (never re-added) |
| **Submission `56883026` → ✅ COMPLETED (Scored 0.13)** | **2026-10-06 14:21** | **Track 1 verified adapter-less baseline LOCKED** (`configs/baseline_registry.json`, sha256 `10e32ceb...`) |
| **Kernel `francisclyap/gemma4-eval-40calls` → ✅ COMPLETED** | **2026-10-06 14:20** | **Kaggle Compute diagnostic notebook** (197 KB, 6 fail-loud guards) |
The 0/129 diagnosis and the 0.00 score come from **different trees**. Any sentence that treats
them as one measurement is wrong.

### 0A.2 CERTAIN — re-derived from artifacts this session

- **C1 — Our leaderboard standing.** Three submissions, all `COMPLETE` (none ever failed
  technically). Best **0.03**, latest **0.00**. Top of leaderboard **0.24**; ten-plus teams sit at
  0.15–0.18. We are at the floor, and the task is demonstrably *not* unsolvable.
- **C2 — The only real Gemma 4 measurement is 0/129**, and **0/18** restricted to tasks that
  actually executed a tool loop. That 0/18 is a number, not an absence.
- **C3 — The dominant failure is NON-EXECUTION.** `tool_calls == 0` for **111/129 (86%)**;
  **117/129 (91%)** produced no patch. "Wrong fix" is ~5%. Optimising the prompt against a
  5% bucket while 86% never run is misallocated effort.
- **C4 — Model identity is a clean binary partition, zero crossover.** `cloud_results` traces
  record the Kaggle serve path `…/gemma-4-31b-it-qat-w4a16-ct/2`; all 5,137 steps of `run_B39`
  record `stealth/space-bunny-alpha`. No run is a blend.
- **C5 — ⚠️ RETRACTED 2026-10-05, then re-derived. `thinking_level` was NEVER in the artifact.**
  My earlier claim ("bfc0614 removed `thinking_level`, so the E1 fix was already in the 0.00
  submission and failed to move it") was **wrong on its mechanism**, and I retract it.
  Verified by unscoped search — `git log --all -S'thinking_level' -- '*sampling.yaml'` returns
  **empty**, and `git grep thinking_level` over the entire **Oct-1 submitted tree** returns
  **empty**. No `sampling.yaml`, at any path, in any revision, ever contained the key.
  `bfc0614` actually changed `include_thoughts: false → true`, `thinking_budget: 0 → 4096`,
  `max_output_tokens: 4096 → 16384` — i.e. it brought the config into compliance with
  `HARNESS_README.md:149`, which prescribes exactly that. It was a **compliance fix, not a
  crash fix.**
- **C5b — The 115/129 `exit_code -1` crash has NO established cause.** The only diagnosis we
  held (`thinking_level` → `reasoning_effort` → bridge `RuntimeError`) describes a key that was
  not in the artifact that crashed. Treat E1 as **unexplained**, not as fixed.
- **C5c — ⚠️ `g_sampling_no_thinking_level` IS AN UNFALSIFIABLE GATE.** It asserts the absence
  of a key that has never existed, so it can never go red. By our own rule
  (`docs/IRONCLAD_GATES_PLAN.md`: *"a gate never shown red is a comment, not a gate"*) it is
  invalid and must either be red-proven against a real bad artifact or removed.
- **C5d — The real untested config delta.** The Oct-1 artifact ran with **thinking fully
  disabled** (`include_thoughts: false`, `thinking_budget: 0`); every artifact since runs with
  thinking **on** (4096). That single flip has **never been A/B tested** on a leaderboard
  submission. It is now a first-class isolation candidate — stated as an untested delta, **not**
  as a diagnosis.
- **C6 — Observability is narrow, not absent.** 0/129 run logs are non-empty (rich's
  `_is_jupyter()` gate under Kaggle), but **95/129 traces survive** with full step structure.
  The blind spot is the 34 tasks with no trace file, not the whole run.
- **C7 — Packaging is sound and reproducible.** 14 files, correct root layout, no bytecode,
  **0 gating FAILs**, and a byte-reproducible build (`sha256 16f318b2…` on two clean rebuilds).
  Packaging is not the reason we score zero.
- **C8 — There is no "V6".** The competition has accepted exactly **3** submissions
  (`56744693`, `56765397`, `56810465`). Any reference to a v6 describes work that has not been
  submitted and therefore has **no score and no evidence**.

### 0A.3 REFUTED — do not re-investigate

| Claim | Verdict |
|---|---|
| 43.4% / 64.9% are our Gemma 4 baseline | **REFUTED** — proxy model, C4 |
| `thinking_level` explains the 0.00 score | **REFUTED** — C5 |
| `max_output_tokens: 16384` causes the crash | **REFUTED** — harness default (`HARNESS_README.md:147`) |
| `thinking_budget: 4096` + `include_thoughts: true` is wrong | **REFUTED** — harness recommends this pair (`:149`) |
| pydantic missing in the eval container | **REFUTED** — 0 `ImportError` across 4,196 invocations |
| `run_skill_script` is fictional | **REFUTED** — demonstrably works |
| Thought-drop (E2) reproduces on our data | **REFUTED** — prompt growth 3.506× vs the thread's 0.35× |

### 0A.4 UNDETERMINED — the real remaining unknowns

- **U1 — Why 111 tasks never ran.** "Server degraded after ~18 tasks" is a *signature*
  (live traces ~07:00, dead traces ~14:08 the same day), **not a proven cause**. Never
  promoted to a diagnosis.
- **U2 — Why did `56810465` score 0.00 with the E1 fix present?** This is now the
  highest-value open question in the repo: it is the only scored data point produced by a
  post-fix artifact, and we cannot explain it.
- **U3 — Will the scoring runtime re-score?** (Kaggle thread Q2/Q3.)
- **U4 — Did the 0.00 artifact's working tree match HEAD?** Its sha `1018a128…` (79.5 MB) is
  unreconstructable — the adapter was later purged at `53cbb4c`. C5 assumes `sampling.yaml`
  tracked HEAD; this is **inferred, not verified** for the full artifact.

### 0A.5 The strategic read

**0.00 is not evidence that the agent is bad. It is evidence that we have never had a scored
measurement of a post-fix artifact on a healthy inference path.** Both explanations we have
been carrying — E1 and E3 — are now either refuted (C5) or mis-sized (C3). Until U1/U2 are
answered, prompt tuning is unmeasurable: there is no signal to tune against.

The only thing that produces signal is a **real Gemma 4 run that actually executes the agent on
most tasks**. That is `gemma4-sts8`, and it is gated on Kaggle quota, not on anything we can fix
in this repo.

---

## 0B. Correction log (read first — my own errors, so they are not repeated)

| Date | Claim I made | Reality | How it happened |
|---|---|---|---|
| 2026-10-05 | "95/95 traces have zero completion tokens" | **Wrong.** 77/95 zero, 18 non-zero | Field-path bug: read `d['total_completion_tokens']` (top level, absent → defaulted to 0) instead of `d['final_metrics']['total_completion_tokens']` |
| 2026-10-05 | "failures write bloated patches (2.2×)" | **Withdrawn** — difficulty confound. At 0–20 tool calls failures are *smaller* (fastapi 0.81×, requests 0.82×) | Aggregates not stratified by repo and tool_calls |
| 2026-10-05 | "success collapses monotonically with tool_calls" | **Withdrawn** — non-monotonic (45–50 bucket is 25%, above 40–44's 0%). Correct: `tc>=40` ≈ 18% (6/33), a weak trend | Did not check curve monotonicity before asserting it |
| 2026-10-05 | "turning thinking off is our best lever on the 0/129" | **Withdrawn** — unsupported causal link. Dropped *input* cannot suppress *output* generation | Fused two independent failure modes |
| 2026-10-05 | F2c: "of the tasks that produced tokens, zero produced a source edit" | **Wrong.** 19 `edit_file` calls across 12/18 traces; 13/18 called `submit_patch` | Searched step `message`/`event_type` fields instead of `tool_calls[].function_name` |

**Lesson:** verify the field exists before quoting a metric, and re-run the count before citing it.

---

## 1. Error taxonomy — 5 confirmed types

Measured from `cloud_results/results/traces/` (95 traces, real Gemma 4 per `model_name`) and the 2026-10-05 Kaggle thread (discussion/744354).

### E1 — Empty generation (`exit_code -1`) — **HARNESS-SIDE — ROOT CAUSE UNKNOWN (my diagnosis was WRONG)**
- **Evidence:** 77/95 traces, `final_metrics.total_completion_tokens: 0`, `total_steps: 2`, structure `[system, user]`. Model emitted nothing.
- **Formerly-claimed cause — RETRACTED:** `thinking_level: 2` → LiteLLM → `reasoning_effort: medium` → `RuntimeError`. That key was never in the artifact that crashed (C5). **Do not cite this.**
- **Status: NO KNOWN FIX.** `bfc0614` did **not** remove `thinking_level` — the key was never there (C5). It aligned the config with `HARNESS_README.md:149`. The crash is **unexplained**, and `g_sampling_no_thinking_level` is an unfalsifiable gate (C5c).

### E2 — Thought-dropped-before-template — **HARNESS-SIDE, MITIGABLE**
- **Evidence:** Kaggle discussion/744354. ADK sends thought as `reasoning_content`; vLLM 0.19.1 reads only `reasoning` (`chat_utils.py:1512`). Measured on 3,640 tool-call steps: prompt grows **0.35×** previous reply thinking-on vs **1.1×** thinking-off.
- **Cause:** upstream vllm#38488, fix proposed in vllm#42664. "submissions cannot reach this layer."
- **Our exposure — CLAIM WITHDRAWN.** An earlier revision of this line asserted that our `thinking_budget: 4096` tokens are generated and never returned to the model. **That premise is refuted** by the 3.506× measurement in the REVOKED section below. Whether the thought is returned to the model in our environment is **unresolved**; do not budget tokens on the assumption that it is lost.
- **Distinct from E1:** E2 loses *prior* context; E1 loses *all* output. E2 cannot cause E1.

### E3 — Search-loop / low edit-conversion — **PARTIALLY OURS**
- **Evidence:** across the 18 non-degenerate traces: `run_skill_script` **328**, `read_file` 58, `edit_file` **19**, `submit_patch` 14. Ratio ~5.6:1 search-to-edit. One trace burned 97 `run_skill_script` calls (F2b).
- **Read:** the agent searches far more than it commits. The mandatory Turns 1–10 discovery window in `prompts/main.md:68` is a likely contributor.
- **Fixable?** Yes — prompt-side. This is the only genuinely behavioural defect in the table.

### E4 — LoRA/Track 2 poisoned training data — **OURS, HARD NO-GO [✅ RESOLVED / SUPERSEDED 2026-10-08 IN §7 PHASE 1]**
- **Evidence:** three independent fatal defects (`decision-track2-no-go`):
  1. **Tokenizer:** `build_unsloth_dataset.py:319` emits `<|tool_call|>` on both sides; staged tokenizer wants asymmetric pair. All 1,107 rows malformed.
  2. **Provenance:** 100% rows distilled from `space-bunny-alpha`, never Gemma 4.
  3. **No error filter:** `compact_observation` keeps failures verbatim → ≥166/306 rows train on pytest FAILED output.
  - Plus: served base is QAT INT4, inference-only — not a supported fine-tuning target.
- **Status:** adapter NOT shipped in Track 1 (verified: no `adapters/` in `submission.zip`). **[✅ RESOLVED 2026-10-08: Rebuilt `scripts/build_unsloth_dataset.py` with official Gemma 4 `chat_template.jinja`, 0% `space-bunny-alpha` local `run_B*` traces, 0% `tasks.jsonl` benchmark overlap, and 100% resolved external Source B trajectories (`swe_smith`, `swe_rebench`, `swe_zero`). See §7 Phase 1.]**

### E5 — Adapter obligation coupled to submission mode — **FIXED, SHIPPED [✅ COMPLETED]**
- **Evidence:** `local_test` was the effective pack-time mode and FAILed any declared adapter; would have blocked Track 2 packaging.
- **Status:** fixed via policy scalar `adapter.required`, commit `665d352`, pushed. Tests pass (87).

---

### REVOKED 2026-10-05 — E2 does NOT reproduce on our own data

Tested directly against the 18 non-degenerate traces using `extra.usage.prompt_tokens` /
`completion_tokens` per `tool_call`. For 405 consecutive-step pairs:

```
median (prompt[n+1] - prompt[n]) / completion[n]  =  3.506x
Kaggle measured: 0.35x (thinking ON, dropped)  |  1.1x (thinking OFF, retained)
```

Ours is **~10× above their dropped case**. The prior thought is not being dropped here. **T2 is revoked** — disabling thinking would remove 4,096 real reasoning tokens for no measurable gain. (Caveat: this tests prompt *growth*, so it refutes systematic mass-drop, not every subtle variant.)

### REFRAMED TWICE 2026-10-05 — the dominant failure is NO-PATCH-AT-ALL

My first reframe ("wrong-fix, not search-loop") was still wrong, because I sized it from exit codes. The correct decomposition of 129 tasks, resolved **0**:

```
EMPTY PATCH  : 117/129  (91%)   ← the real failure
exit -1      : 115  (89%)   ... with a NON-EMPTY patch: 0
```

The binding split is `tool_calls`, not exit code:

| Bucket | n | Share | Meaning |
|---|---|---|---|
| `tool_calls == 0` | **111** | **86%** | agent never ran — serving/infra |
| ran, empty patch | 6 | 5% | ran, submitted nothing |
| ran, real patch | 12 | 9% | ran, patch applied, tests failed |

`fastapi_15280` (exit 1, `patch_length` 0, 31 tool_calls) and `fastapi_15661` (exit 2, `patch_length` 0, 30 tool_calls) are the **same no-patch bug wearing different exit codes** — exit code conceals it.

#### The nulls split into TWO bugs — and duration does not explain either

Split by trace-file existence (95 trace files for 129 tasks). `predictions.csv` independently confirms **117/129 prediction strings are empty**, and exactly the 12 with text are the 12 with real diffs — so there is **no unrecorded agent output**. The "agent ran, only recording broke" hypothesis is refuted.

| Bucket | n | Meaning | Owner |
|---|---|---|---|
| **(A)** no trace file | **34** | harness never constructed an agent | harness/orchestration |
| **(B)** trace exists, `total_completion_tokens == 0` | **77** | agent started, model never returned | serving |
| **(D)** ran with tool calls | 18 | normal | — |

**(A) and (B) are different bugs with different owners.** "The agent never ran" conflates them and must not be used as one bucket.

**Repo DOES separate the buckets; position separates D but not A from B.** An earlier revision of this file claimed the opposite ("not repo, not position") — that was false and is retracted here.

| Bucket | rich | fastapi | requests | httpx |
|---|---|---|---|---|
| **(A)** no trace | **34** | 0 | 0 | 0 |
| **(B)** zero-token | 14 | 57 | 5 | 1 |
| **(D)** ran | **0** | 10 | 8 | 0 |

Zero crossover on the rich axis: rich never produced a working agent; non-rich never produced a no-trace.

Per-repo sequences:

```
fastapi/fastapi   DDDDDDDDDD BBBBBBBBBBBBBBBBBBBBBBBBBBBB   → 10 D, then B forever, 0 A
psf/requests      DDDDDDDD   BBBBBB                          →  8 D, then B forever, 0 A
Textualize/rich   AAAAAAAAAAAAAAAAABAAAAABAAAA…BBBBBBBB    → 34 A, 14 B, 0 D
```

**Observed pattern (NOT a diagnosed mechanism):** within each repo's own sequence, non-rich tasks produced tool calls for exactly the first 18 and none after; rich produced none at any point. **Attribution is unresolved** — repo and position are confounded (next line). Do not read this as an established cause.

**The two refutations that stand:**

1. *Duration explains ran-vs-null* — refuted: `D median 123.4 s | B 110.9 s | A 104.9 s`, heavily overlapping.
2. *Monotone capacity decay* — refuted as stated: A and B interleave in contiguous blocks (`A 18–23, 66–76, 99–103, 105–116`), they do not degrade in order.

**Unresolvable with this data:** repo and position are **confounded** — runs were repo-sequential (non-rich 0–97, rich 18–128 interleaved), so the rich `B` tasks at idx 98, 104, 117–128 cannot be attributed to repo *or* position with this sample. Do not claim either alone is the cause.

**Method note:** I asserted "process died at index 18", then "capacity decayed", then "not repo, not position" — each from ordering without first checking whether the field separated the classes. All three overreached. Always verify the field exists, then verify it discriminates, before writing the claim into a durable record.

> **Superseded records.** Four earlier memories that asserted false mechanisms were deleted (`bd forget`), not annotated: "positional/process death at index 18", "three sequential phases P1/P2/P3", "wrong-fix is the leading failure mode", and an intermediate null-bucket note that itself ended with a false claim. Their findings are either refuted above or restated correctly. The single authority is `null-bucket-structure-single-source-of-truth-2026`; the test plan is `isolation-sequence-final-2026-10-05-replaces-a`. The table above this line is the substantive record and does not depend on any memory.

**"Wrong-fix" is the smallest bucket (6/129 = 5%), not the leading failure mode.** The 5.6:1 search-to-edit ratio is a side-show. **T3 is deferred** until execution is restored. Correct order: (1) restore execution for the 111, (2) stop empty-patch submissions for the 6, (3) only then examine wrong-fix.
## 2. What is NOT an error (recurring false leads — do not re-investigate)

| Claim | Verdict |
|---|---|
| `max_output_tokens: 16384` causes the crash | **REFUTED.** Harness default (`HARNESS_README.md:147`), recommended at `:663` |
| `thinking_budget: 4096` + `include_thoughts: true` is wrong | **REFUTED.** Harness recommends exactly this pair (`:149`) — *pre-dates E2* |
| pydantic missing in eval container | **REFUTED.** 4,196 `run_skill_script` invocations across run_B39, 0 `ImportError` |
| `run_skill_script` is fictional | **REFUTED.** Absent from HARNESS_README but demonstrably works |
| 43.4% is our Gemma 4 baseline | **REFUTED.** Served model was `space-bunny-alpha` proxy in 5,137/5,137 steps |

---

## 3. Isolation sequence — REVISED 2026-10-05

**Two of the four original tests are dead.** T2 is revoked (E2 premise refuted on our own traces). T3 is deferred (E3 misdiagnosed as wrong-fix). The sequence is now **one real test**, because 89% of tasks crash before reasoning can be measured at all.

| # | Variable | Isolates | Status |
|---|---|---|---|
| **T1** | baseline, adapter-less | **E1 / Base Gemma 4** | **✅ COMPLETED (2026-10-06)** — Leaderboard ref `56883026` scored **0.13**; locked as Track 1 Baseline (`configs/baseline_registry.json`) |
| ~~T2~~ | `include_thoughts: false` | E2 | **❌ DROPPED / REVOKED** — premise refuted (3.506× vs 0.35×); thinking (`4096`) retained |
| ~~T3~~ | relax Turns 1–10 window | E3 | **🔄 SUPERSEDED** — superseded by locked Track 1 `0.13` prompt governor and Track 2 LoRA SFT (§7) |
| ~~T4 (old)~~ | LoRA Upgrade on 77 Tier-1 tasks | Target: 77 Tier-1 tasks | **🔄 DROPPED / SUPERSEDED BY §7** — training on 77 Tier-1 tasks from `tasks.jsonl` (local `run_B*`) was **DROPPED** due to test-set benchmark leakage; superseded by Zero-Leakage External Source B SFT (§7) |

**T1 dispatched (2026-10-06):** verified by 15 automated submission quality gates (`python3 scripts/check_submission.py`),
14 PASS / 0 gating FAIL. Package `submission.zip` = **124,196 bytes**, SHA-256 **`10e32ceb9b2ca6bf40b40c485d9279e837a1e4ce67fa2f4df5c3fcb5e4bc4a83`**,
strictly adapter-less, 0 stray weights.

**Diagnostic Kernel dispatched (2026-10-06):** `francisclyap/gemma4-eval-40calls` (197 KB, 5 cells, 6 fail-loud runtime guards).

**Next Action (Historical 2026-10-06 — Preserved with Status):**
1. **[✅ COMPLETED]** Read graded public score from ref `56883026` (**Scored 0.13** on Public Leaderboard; locked in `configs/baseline_registry.json`) and runtime trace metrics from kernel `francisclyap/gemma4-eval-40calls`.
2. **[❌ DROPPED / 🔄 SUPERSEDED BY §7]** ~~Once pure base resolution rate is confirmed, execute Track 2 LoRA fine-tuning using Unsloth on `google/gemma-4-31B-it-qat-q4_0-unquantized` trained exclusively on the 77 Tier 1 task trajectories.~~ *(Dropped training on the 77 Tier-1 benchmark tasks / local `run_B*` traces because they are evaluations on the 129 `tasks.jsonl` benchmark tasks and would leak the test set into SFT. Superseded by the Zero-Leakage External Source B Track 2 Master Plan in Section 7 below.)*

**Why T1 dominates — REWRITTEN after C5.** The argument is **not** "E1 is 89% of tasks": E1's
mechanism is refuted (C5), so we cannot lean on its share. The argument is that **no post-Oct-1
Gemma 4 measurement exists at all**. Every leaderboard number we hold comes from an artifact
that ran with thinking *disabled*; every artifact since runs with thinking *on* (C5d); and the
one real Gemma 4 run predates every fix in the tree. T1 is not "a cheap datapoint" — it is the
precondition for having a dataset at all.

**T1 success criteria — REWRITTEN. Two earlier versions were based on false models and are withdrawn** ("process dies at index 18"; then "capacity decay"). Both were refuted: the nulls interleave, and duration does not separate ran from null.

T1's output metric is a **count**, not a boundary: **how many of 129 produce `tool_calls > 0`** (baseline **18/129 = 14%**). Do not read an index boundary into the result.

| Observation | Reading |
|---|---|
| Count rises well above 18 | Nulls were a run artifact; behavioural data becomes measurable |
| Count stays ~18 | Systematic. (A)/(B) are not caused by submission content — pursue harness/serving |
| Count drops to ~0 | The `thinking_level` change hurt; revert and escalate to the bridge |

**Free check, zero quota:** after T1, read `final_metrics.total_completion_tokens` per trace **and** the trace-existence split. Pre-fix baseline: **34 no-trace (A) / 77 zero-token (B) / 18 ran (D)**. **Verify the field paths exist before quoting them** (see Correction log).

**Not a third bug:** `fastapi_14360` (idx 54, 9,461.78 s) has a trace structurally identical to the 77 zero-token traces — 2 steps, 0 tokens, no `model_name`. Same signature, extreme duration.

## 4. Open question

**Is the scoring environment patched, and will existing submissions be re-scored?** (Kaggle thread Q2/Q3.)

- If **yes** → E2 moot; T2 stays revoked.
- If **no** → still revoked. Our own traces show the thought is not dropped. Re-open only on evidence from *our* runs, not the thread alone.

Also unresolved: F10 reports the canary mounted an adapter from a side-channel dataset. Our submission ships none. If the Kaggle runtime mounts adapters from a path we do not control, what we submit may not be what is served.

---

## 5. Commands (user-executed)

```bash
# Pre-flight
cd /home/vps466a/arthityap/gemma4
python3 scripts/check_submission.py          # expect: 0 gating FAILs

# T1 submission
./start.sh
```

Agents must NOT run evaluations. `AGENTS.md`: execution is exclusively the user's via `./start.sh`.

---

## 6. Success criteria per test

- **T1:** score > 0 → E1 fixed. Score == 0 with non-zero completion tokens → E1 was not the binding constraint; escalate to E3.
- **T2:** improvement over T1 → E2 confirmed and mitigated. No change → thought-drop is not binding; treat as informational and move to T3.
- **T3:** edit-conversion improves on the 5.6:1 baseline → prompt is a real lever.

Read `final_metrics.total_completion_tokens` per trace to distinguish E1 recurrence from behavioural failure. **Verify the field exists first** (see Correction log).


---

## 7. Track 2 LoRA Master Plan (2026-10-08 — Active Workplan, Epic `gemma4-wzlk`)

**References:**
- **Beads Epic:** `gemma4-wzlk` (`bd show gemma4-wzlk`)
- **Beads Persistent Memory:** `track-2-lora-master-plan-logged-in-bd`, `planning-mode-rule-when-planning-with-the-user`
- **Deep Research Engineering Specification:** `/home/vps466a/services/agy-agents/deep-research/reports/Gemma4_Unsloth_LoRA_Adapter_Settings_Eng_20261008_1303.md` (918 lines)

### 7.1 Activity Status Ledger (Historical & Current)

| Activity / Milestone | Status | Outcome / Notes |
|---|---|---|
| **Track 1 Adapter-less Baseline (`56883026`)** | ✅ **COMPLETED** | Scored **0.13** on Public Leaderboard; locked in `configs/baseline_registry.json` (`sha256: 10e32ceb...`). |
| **16-Gate Submission & Proxy Eval Shield** | ✅ **COMPLETED** | `scripts/check_submission.py` (14 veto gates + 2 hygiene/health checks) and `scripts/baseline_gate.py` active. |
| **T2 (`include_thoughts: false` ablation)** | ❌ **DROPPED / REVOKED** | Premise refuted by 3.506× token growth measurement on cloud traces. |
| **T3 (Turns 1–10 prompt window relaxation)** | 🔄 **SUPERSEDED** | Superseded by locked 0.13 baseline governor and Track 2 LoRA fine-tuning. |
| **Old T4 (LoRA SFT on 77 Tier-1 / 223 `run_B*` local traces)** | ❌ **DROPPED / SUPERSEDED** | **Dropped** because `run_B*` traces are evaluations on the 129 `tasks.jsonl` benchmark tasks (test-set leakage + `space-bunny-alpha` proxy provenance). Superseded by External Source B SFT below. |
| **Track 2 Prep A: External Source B Dataset Download** | ✅ **COMPLETED** | Downloaded 14.31 GB across 79 Parquet shards in `data/source_b/` (`swe_smith` 1.00 GB, `swe_rebench` 1.94 GB, `swe_zero` 11.37 GB). |
| **Track 2 Prep B: Deep Research Engineering Spec** | ✅ **COMPLETED** | Completed 5-persona engineering report (`Gemma4_Unsloth_LoRA_Adapter_Settings_Eng_20261008_1303.md`) establishing exact FP4/QAT autograd, LoRA module count, and vLLM key mapping invariants. |
| **Track 2 Phase 1a: Initial 3-Source SFT Draft (`500/500/500`)** | 🔄 **SUPERSEDED** | Initial 1,500-sample build (`500 swe_smith`, `500 swe_rebench`, `500 swe_zero`) superseded after audit showed `swe_rebench` has median 51 tool calls (98.9% $>30$ calls) and multi-file noise. |
| **Track 2 Phase 1b: Zero-Leakage Single-File $\le 20$-Call Curriculum** | 🔄 **SPEC REFINED (LOCKDOWN PENDING)** | Refined with strict 100% single-file `.py` gate, $\le 20$ tool-call ceiling, `swe_rebench` dropped, and Straight-Shot (4,387) vs. Constructive Pivot (1,834) mining from 6,221 candidate pool on disk. |
| **Track 2 Phase 2: Unsloth FP4 Training Script Alignment** | ⏸️ **PENDING REVIEW** | Waiting on joint plan review before modifying `scripts/train_gemma4_unsloth_cloud.py` and notebook builders. |
| **Track 2 Phase 3: vLLM Multimodal Key Normalizer** | ✅ **SCRIPT COMPLETED / ⏸️ RUN PENDING** | `scripts/normalize_adapter_vllm.py` created on disk; will run post-training to remap keys to `base_model.model.language_model.model.layers.*` and verify 340 BF16 tensors (<35 MB). |
| **Track 2 Phase 4: 14-Task Gauntlet / Compute Staging (`gemma4-9r1`)** | ⏸️ **PENDING** | Evaluate normalized LoRA under authentic vLLM `w4a16-ct` before touching `submission.zip`. |

---

### 7.2 End-to-End Track 2 Architecture Flow

```
  [External Source B Parquet Shards: swe_smith + swe_zero (swe_rebench dropped)]
                         │
                         ▼  Strict Filter: 100% single-file .py, <=20 calls, 0% tasks.jsonl
     [Candidate Pool: 6,221 challenges (4,387 Straight-Shot, 1,834 Constructive Pivot)]
                         │
                         ▼  Balanced Sampling (~1,500 decision step windows)
        [data/unsloth_sft/train.jsonl (~1,350 samples / ~80-120 tasks)]
        [data/unsloth_sft/val.jsonl   (  ~150 samples / ~10-15 disjoint tasks)]
                         │
                         ▼  Pre-tokenize full_text + slice labels[:K] = -100
  [Unsloth Training: google/gemma-4-31B-it-qat-q4_0-unquantized (BnB FP4)]
    • 170 Attention Modules: q_proj (60), v_proj (50), o_proj (60) -> 340 tensors
    • r = 8, lora_alpha = 16, use_rslora = False, neftune_noise_alpha = None
    • LR = 1.5e-4 (cosine), B = 1, GAS = 8, ~170 steps, eval_strategy = "no"
                         │
                         ▼  Post-training hook
       [scripts/normalize_adapter_vllm.py]
    • Rewrite prefix -> base_model.model.language_model.model.layers.{i}...
    • Verify 340 torch.bfloat16 tensors, file size < 35.0 MB
                         │
                         ▼  Staging Gate (gemma4-9r1 + vLLM smoke check)
  [vLLM w4a16-ct Serving -> 1-2 Task Smoke Check -> 14-Task Gauntlet]
                         │
                         ▼  Promote ONLY if > 0.13 Track 1 Baseline
                  [submission.zip]
```

---

### 7.3 Phase-by-Phase Engineering Plan

#### Phase 1: Zero-Leakage Multi-Turn SFT Dataset (**🔄 SPEC REFINED (LOCKDOWN PENDING)**)
- **Script**: `scripts/build_unsloth_dataset.py`
- **Benchmark Leakage Guard**: Loads all 129 `instance_id`s from `tasks.jsonl` into `benchmark_exclusions` and excludes all local `run_B*` traces (100% external Source B only).
- **Single-File Scope Constraint**: 100% single-file `.py` fixes only (0% multi-file, 0% non-`.py`). Eliminates multi-file trajectory wandering in SFT (`max_seq_length=3072`) and aligns with the 85.3% 1-2 file complexity ceiling of `tasks.jsonl`.
- **Strict Budget Ceiling**: Trajectory total tool calls $\le 20$. Pruning long trajectories guarantees a 20+ call safety margin inside the competition's 40-call budget for reasoning, exploration, and recovery.
- **Source Dataset Filtering**:
  - `swe_smith`: Retained (Claude 3.7 Sonnet tool-split trajectories with native thoughts and tool calls).
  - `swe_rebench`: **Dropped entirely** (median 51 tool calls, 98.9% $>30$ calls; teaches budget thrashing and exceeds the 40-call budget).
  - `swe_zero`: Retained (OpenHands trajectories with verified non-empty patches $\le 150$ lines).
- **Curriculum Stratification (Straight-Shot vs. Constructive Pivot)**:
  - **Straight-Shot Challenges**: 0 tool errors, clean linear exploration and edit execution in $\le 20$ calls.
  - **Constructive Pivot Challenges**: Measured causal disconfirmation and recovery in $\le 20$ calls:
    - *Red-to-Green Test Pivots*: Pre-edit test execution fails with `AssertionError` / `exit_code != 0` $\to$ edit applied $\to$ post-edit test passes (`exit_code == 0`). Teaches genuine hypothesis testing and test-driven repair.
    - *Tool Error Recovery*: Tool call fails or returns 0 matches $\to$ assistant immediately pivots strategy without repeating the mistake.
- **Measured Empirical Pool on Disk (`data/source_b/`)**:
  - `swe_smith`: 1,077 eligible single-file $\le 20$-call challenges (1,015 Straight-Shot, 62 Constructive Pivot / 32 Red-to-Green).
  - `swe_zero` (first 5 shards): 5,144 eligible single-file $\le 20$-call challenges (3,372 Straight-Shot, 1,772 Constructive Pivot / 1,767 Red-to-Green).
  - **Combined Pool**: 6,221 unique qualified challenges (4,387 Straight-Shot, 1,834 Constructive Pivot) vs. 1,500 target sample size ($>4\times$ surplus).
- **Production Tool & Skill Contract**:
  - Strictly 6 callable tools: `read_file`, `edit_file`, `write_file`, `get_status`, `submit_patch`, `run_skill_script` (`run_command` = 0).
  - Exact parameter schema matching `HARNESS_README.md:433-460` and `submissions/track1_live/prompts/main.md` (`filepath`, `old_string`, `new_string`, `allow_multiple`).
  - OpenHands/Claude actions translated cleanly (`str_replace_editor` $\to$ `read_file`/`edit_file`/`write_file`, `pytest` $\to$ `test-gate`, `grep` $\to$ `fast-grep`, `python -c` $\to$ `repro-check`, `think` folded into `reasoning`).
- **Gemma 4 Chat Template & Prefix-Delta Formatting**:
  - Rendered with `models/gemma-4-31b-it-qat-w4a16-ct/chat_template.jinja` (`enable_thinking=True`, `preserve_thinking=True`).
  - Verified `full_text.startswith(prefix_text)` on 100% of samples.
#### Phase 2: Unsloth LoRA Training on 1x 24GB L4 GPU (**⏸️ PENDING REVIEW**)
- **Target Scripts**: `scripts/train_gemma4_unsloth_cloud.py`, `scripts/build_unsloth_notebook.py`, `scripts/build_unsloth_training_kernel.py`.
- **Locked Engineering Parameters**:

| Parameter | Locked Value | Engineering Rationale |
|---|---|---|
| **Base Checkpoint** | `google/gemma-4-31B-it-qat-q4_0-unquantized` | `w4a16-ct` (`CompressedLinear`) lacks PyTorch autograd backward dequant kernels for $\nabla_X = \nabla_Y W^T$. |
| **Quantization Config** | `BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="fp4", bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)` | Uniform symmetric `fp4` grid aligns with Google's symmetric `q4_0` QAT training grid; `nf4` non-linear quantiles distort QAT weights. Fits in ~15.35 GiB static VRAM. |
| **Target Modules** | `["q_proj", "v_proj", "o_proj"]` | **170 modules** across 60 layers (10 global full-attention layers have `attention_k_eq_v=True` and omit `v_proj`). Freeze `k_proj`, MLPs, and vision tower. Trainable params: **13,926,400** (26.56 MB in BF16). |
| **LoRA Rank & Alpha** | `r = 8`, `lora_alpha = 16`, `lora_dropout = 0.0`, `bias = "none"` | Scaling $\alpha/r = 2.0$; `lora_dropout = 0.0` required for Unsloth fast Triton kernels. |
| **rsLoRA & NEFTune** | `use_rslora = False`, `neftune_noise_alpha = None` | `use_rslora=True` increases effective step size by $\sqrt{8} \approx 2.83\times$; NEFTune corrupts discrete control tokens (`<|tool_call>`, `<|"|>`). |
| **Tokenization & Masking** | Pre-tokenized `.map()` on `full_text` with `labels[:K] = -100` | Avoids SentencePiece boundary merge misalignment ($\text{enc}(A) + \text{enc}(B) \neq \text{enc}(A+B)$) and prevents `SFTTrainer` from stripping custom columns. |
| **Sequence Length & Eval** | `max_seq_length = 3072`, `eval_strategy = "no"` | `eval_strategy="steps"` materializes a 7.50 GiB `[1, 3072, 262144]` FP32 logit tensor and OOMs a 24GB L4 GPU. Peak training VRAM with `eval_strategy="no"`: **~20.43 GiB**. |
| **Optimizer & Schedule** | `optim = "paged_adamw_8bit"`, `LR = 1.5e-4`, `cosine`, `warmup_steps = 15`, `B = 1`, `GAS = 8`, `num_train_epochs = 1` (~170 steps) | Effective batch size 8; `weight_decay = 0.01`, `max_grad_norm = 1.0`, `seed = 3407`. |

#### Phase 3: Post-Training vLLM Key Normalization & Gate (**✅ SCRIPT COMPLETED / ⏸️ EXECUTION PENDING**)
- **Script**: `scripts/normalize_adapter_vllm.py` (created and executable).
- **Why**: vLLM instantiates Gemma 4 via multimodal `Gemma4ForConditionalGeneration`, which namespaces text layers under `language_model.model.layers.{i}`. Standard PEFT/Unsloth text saves emit `base_model.model.model.layers.{i}`, which vLLM silently ignores during LoRA loading.
- **Verification Assertions**:
  1. All 340 tensor keys start with `base_model.model.language_model.model.layers.`.
  2. Exact tensor count = **340** ($170 \times 2$).
  3. All tensors cast to `torch.bfloat16`.
  4. `adapter_model.safetensors` size $< 35.0\text{ MB}$ (~26.6 MB expected).

#### Phase 4: Staging Verification Before Touching `submission.zip` (**⏸️ PENDING**)
- Stage normalized adapter in a compute/test submission directory (never overwrite `submissions/track1_live/` or `submission.zip` unverified).
- Run the **14-task gauntlet (`gemma4-9r1`)** / Kaggle Compute diagnostic kernel under authentic vLLM `gemma-4-31b-it-qat-w4a16-ct`.
- Compare resolution rate, tool-call syntax validity, and patch submission rate against the locked **0.13** Track 1 baseline.

---

### 7.4 Locked Planning Decisions (User Approved 2026-10-08)

1. **Compute Target**: **Option A (GCP 1x L4 24GB VM)** via `gcp/deploy_gemma4_lora.sh` + `scripts/train_gemma4_unsloth_cloud.py`. Provides dedicated VRAM, avoids Kaggle kernel queue timeouts, and runs 170 steps in ~25–35 mins.
2. **Dataset Action Distribution**: **Keep Natural Trajectory Step Ratio** (`read_file` 40.7%, `run_skill_script` 33.5%, `edit_file` 11.9%, `write_file` 7.9%, `submit_patch` 5.4%, `get_status` 0.7%). Preserves authentic agent exploration-to-repair balance without artificial distortion.
3. **Cross-Quantization Smoke Check**: **Approved**. Run a 1–2 task vLLM `w4a16-ct` adapter-loading smoke check on Kaggle Compute immediately after normalizing the adapter before committing GPU quota to the 14-task gauntlet (`gemma4-9r1`).
4. **Complexity & Budget Guardrails**: **Locked**. Enforce 100% single-file `.py` fixes, strict $\le 20$ tool-call budget ceiling, prune `swe_rebench`, and mine Straight-Shot vs. Constructive Pivot challenges from the 6,221-challenge verified pool.
