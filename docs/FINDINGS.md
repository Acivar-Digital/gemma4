# FINDINGS — GAP AUDIT EVIDENCE STORE (append-only)

Lookup table. Every claim carries a `file:line` or a recomputation command so it is never
re-searched. Status vocabulary: **CONFIRMED** (independently reproduced by lead),
**UNVERIFIED** (single source, not reproduced), **REFUTED** (reproduction failed).

---

## F1 — CRITICAL — the 43.4% baseline is NOT a Gemma 4 number

**Status: CONFIRMED (lead, reproduced from traces)**

Every local run in `results/run_B*` was served a LiteRouter proxy model, never Gemma 4.
Recomputation: read `model_name` from every `steps[]` in every `results/run_B*/traces/*.json`.

| Run | turns w/ model | model actually served | score |
|---|---|---|---|
| run_B35 | 6167 | `stealth/space-bunny-alpha` | 45.0% |
| run_B37 | 5986 | `stealth/space-bunny-alpha` | 45.7% |
| run_B39 | 5137 | `stealth/space-bunny-alpha` | 43.4% |
| run_B40 | 3154 | `stealth/space-bunny-alpha` | 64.9% (77-task subset) |
| run_B02–B03, B21–B29 | small | `thinkingmachines/inkling-small:free` | — |

**Zero local runs served `gemma-4-31b-it-qat-w4a16-ct`.**

Consequence: the "43.4% baseline to beat" recorded in `AGENTS.md` is a **space-bunny-alpha**
number. Every behavioral statistic derived from it (patch-size curve, zero-match dose-response,
first-edit buckets, nudge counts, thinking-truncation counts) describes **proxy-model
behaviour, not Gemma 4 behaviour**.

What survives (model-independent, because these are harness constants not model traits):
50-call budget, `max_nudges=3`, Container B test-file discard, `submit_patch` semantics,
the `git add -N . && git diff HEAD` patch rule, and the patch-size curve *direction*
(sprawl is bad) which is corroborated by SWE-agent/Agentless literature.

What does NOT survive as a tuned constant: any specific threshold (4096 thinking budget,
26+ turns, 1200B) — those are proxy-calibrated.

---

## F2 — CRITICAL — the only real Gemma 4 run scored 0/129

**Status: CONFIRMED (lead)**

`cloud_results/results/task_results.jsonl` — 129 rows, `resolved` is `False` for all 129.
```
resolved:      {'False': 129}
test_exit_code:{-1: 115, '1': 6, '2': 5, '124': 3}
```
`test_exit_code = -1` on 115/129 means the test stage never produced a usable result — i.e. a
harness/infra failure, not 115 wrong patches. Several rows have `patch_length = 0`.

**This is not a quality signal, it is a broken run.** The real Gemma 4 baseline is **UNKNOWN**.

The only Gemma 4 configuration actually observed on disk is a reference sub-agent pair
(`sub_agents/engineer.yaml` / `reviewer.yaml`, both `model: gemma-4-31b-it-qat-w4a16-ct`)
found in `cloud_results/` — NOT the shipped `my_submission/agent.yaml`.

### F2b — ROOT CAUSE of the 0/129: the model emitted NOTHING on 81% of tasks

**Status: CONFIRMED (lead, traced)** — this is a generation/serving crash, not agent reasoning.

Scan of `cloud_results/results/traces/trace_*.json` (95 trace files for 129 tasks):
- **77 traces (81%) have `total_completion_tokens: 0`** and **zero tool calls**. Structure is just
  `[system, user]` — the Gemma 4 model produced **not a single token**. e.g. `trace_fastapi_11194.json`.
- Only **18** tasks produced any tokens. Of those, **zero** produced a source edit (F2c).
- One trajectory burned **97 `run_skill_script` calls** without ever editing (get stuck in search loop).

So the 0/129 is dominated by an empty-generation crash. This matches
`cloud_results/canary_test_results/CANARY_ANALYSIS_REPORT.md:16,37` — the "0.03 (1/33)" Oct 1
Kaggle submission was "an infrastructure and sampling configuration crash," specifically
LiteLLM translating `thinking_level: 2` → `reasoning_effort: medium`, rejected by the Gemma 4
bridge (`RuntimeError: unsupported reasoning_effort in Gemma bridge`). The canary was built to
prove this by *omitting* `thinking_level`.

### F2c — HEAD shipped `max_output_tokens: 16384` (the canary's flagged context-starvation bug)

**Status: CONFIRMED (lead)**

`CANARY_ANALYSIS_REPORT.md` objective #2: 16384 "consumed 50% of the entire 32,768-token
context budget for output generation alone, starving prompt history down to 16K." The
canary's fix was to set `max_output_tokens: 4096` (git `8fef9a6`).

But **current HEAD `my_submission/configs/sampling.yaml:3` is back to `max_output_tokens: 16384`**
(commit `bfc0614`, "configure LiteRouter directive"). The Kaggle 0/129 run shipped this 16384
version (its log lists `configs/sampling.yaml: 117 bytes`). HEAD (121 bytes) still has 16384.

Two live defects in the shipped sampling config, both named in the canary report:
1. `max_output_tokens: 16384` → context starvation / compaction. (fix = 4096)
2. `thinking_budget: 4096` present with `include_thoughts: true` → risk of the reasoning-effort
   bridge path that crashed the Oct 1 submission. (canary validated *omitting* thinking_level;
   this file has no thinking_level, but budget+thoughts may still trip LiteLLM translation.)

---

## F3 — the 129-task suite has never been scored with the shipped agent on Gemma 4

**Status: CONFIRMED (lead, by exhaustion over F1 + F2)**

Consequence for planning: we are optimising against a proxy's failure modes, and we have
**no measurement of the actual target system**. The first real priority is a working
Gemma 4 eval that returns a non-degenerate score — otherwise every diff is speculative.

---

## F10 — CRITICAL: the LoRA adapter is not in the submission, and its base model is WRONG

**Status: CONFIRMED (lead, from disk + canary log)**

Three separate defects in the LoRA path, any one of which can cause empty generation:

**(a) The submission ships NO adapter and does not declare one.**
`my_submission/adapters/main_lora/` exists but is **EMPTY** (0 files, created 3 Oct 22:44).
`my_submission/agent.yaml` contains **no** `adapter:` / `lora:` / `main_lora` reference — verified by
grep, zero matches. Yet `gemma4-canary-eval.log` shows the Kaggle run DID mount an adapter:
`LoRA adapter mounted at: /kaggle/working/submission/adapters/main_lora` from dataset
`francisclyap/gemma4-lora-adapter`. **So the adapter came from a side-channel Kaggle dataset,
not from the submission.** The graded `agent.yaml` therefore does not declare the LoRA it was
evaluated with — a reproducibility defect regardless of score.

**(b) The adapter was trained on the WRONG base model.**
`adapters_staging/main_lora/adapter_config.json` → `base_model_name_or_path:
'unsloth/gemma-4-31B-it-unsloth-bnb-4bit'`.
The competition serves **`gemma-4-31b-it-qat-w4a16-ct`** (per `my_submission/agent.yaml:2`).
A LoRA fit against a **4-bit bnb quantized** base, applied to a **QAT w4a16** checkpoint, is a
base/quantization mismatch — a well-known cause of degraded and empty generations. This is a
*second*, independent candidate for the 0-token crash alongside F2c.

**(c) The adapter is genuinely trained but the WRONG VERSION shipped.**
Not a dummy: `r=8`, `lora_alpha=16`, rank-8 q/v/o targeting (matches the locked spec), real
checkpoints at steps 15/30/45/60. But: staged adapter = **90,098,488 bytes** (3 Oct 23:33);
the adapter Kaggle mounted = **72,549,760 bytes** (per canary log). 72,549,760 matches the OLDER
`checkpoints/main_lora/adapter_model.safetensors` (3 Oct / 2 Oct, 72,549,760 B), not the staged one.
**So the run used a superseded adapter.**

**Consequence:** the canary's "zero infrastructure crashes, weights loaded properly" conclusion
(CANARY_ANALYSIS_REPORT.md) may be wrong — a LoRA/base quantization mismatch can load without
error yet produce garbage or nothing. This must be resolved before trusting any Gemma-4 number.

---

## F4 — CONFIRMED: patch size predicts failure (proxy-calibrated)

**Status: CONFIRMED (lead recomputed; matches builder's numbers independently)**

From `results/run_B39/patches/` sizes vs `task_results.jsonl` `resolved`:
| patch size | n | resolved | rate |
|---|---|---|---|
| ≤1200B | 48 | 32 | **66.7%** |
| 1200–4000B | 56 | 23 | 41.1% |
| 4000–6000B | 9 | 1 | 11.1% |
| >6000B | 12 | 0 | **0.0%** |

Direction is corroborated by SWE-agent ACI (succinct match lists) and Agentless (cap sprawl).
Absolute cutoffs are proxy-specific. The `>6000B → 0/12` is small-n; treat as directional.

---

## F5 — CONFIRMED: tool-call census across all 129 B39 tasks

`run_skill_script` 2098 · `read_file` 875 · `edit_file` 587 · `submit_patch` 124 ·
`get_status` 31 · `write_file` 14 · `load_skill_resource` 2.
`search_similar_code`, `get_code_neighbors`, `get_code_subgraph`, `run_command` = **0 calls each**.
Matches builder exactly. The three graph tools are advertised by the harness
(`HARNESS_README.md:333-340`) but the shipped `my_submission/agent.yaml:4-9` does not attach them.

---

## F6 — UNVERIFIED: zero-match grep dose-response (65% → 8%)

**Status: UNVERIFIED — lead's reproduction found nothing.**

Lead parser string-matched `"zero"` in `run_skill_script` args: 128/129 tasks had **0** such
turns, 1 task had 1, none had 3+. Cannot confirm or refute. Either the builder used a different
definition, or the statistic is an artifact. **Must not be used as a tuned constant.**

---

## F7 — UNVERIFIED: first-source-edit turn buckets (62% / 34% / 5%)

**Status: UNVERIFIED — lead's parser FAILED (returned `none` for all 129).**

Lead's extraction of `edit_file` path arguments did not match the actual trace argument shape.
This is a lead tooling bug, not evidence against the claim. Needs a corrected parser before use.

---

## F8 — Ruled out (negative results, keep recorded so effort is not wasted)

- **Zero test-file edits across all 129 tasks.** `main.md` test-file prohibition is working.
- **"Forgot submit_patch" is NOT a knowledge gap** — `main.md` already mandates it; the 4
  non-submitters are truncation cases.
- **Temperature 0.15 is not pathological** — no evidence for forced diversity.

---

## F9 — RESOLVED: the submitted eval_config DID govern Kaggle, and it is TIGHTER than every proxy run

**Status: CONFIRMED (lead, evidence below)**

`my_submission/eval_config.yaml` declares `timeout_seconds: 60 / max_tool_calls: 40 /
max_time_minutes: 4.5 / max_turns: 100`. `HARNESS_README.md:98` confirms submissions may ship
`eval_config.yaml` under an `evaluation:` key to customise Stage-1 per-task budgets
(`load_submission_eval_config` in `scripts/inference.py`).

The Gemma-4 `get_status` trace (`cloud_results/results/traces/trace_fastapi_15661.json`) returns:
```
max_tool_calls = 40   max_time_minutes = 4.5   max_turns = 100   command_timeout_seconds = 60
```
All four match the submitted file exactly. **The submission's eval_config won** — the harness
default of 50 (`scripts/run_eval.py:48-52`) did NOT apply.

**CONSEQUENCE (important):** every behavioural statistic in this audit was measured on proxy
runs at **50 tool calls** (B35/B37/B39 died at 50). The graded configuration allows **40** — a
20% smaller budget. The real Gemma-4 failure profile is therefore *worse* than the proxy data
implies, and any threshold tuned on the proxy is tuned for the wrong budget too.

## F11 — CONFIRMED: submission.zip is byte-identical to my_submission/ (no stale-package risk)

**Status: CONFIRMED (lead, md5 of all 32 entries)**

19 files in zip, 19 on disk, **all identical**; no file only-in-zip, none only-on-disk.
`adapters/` and `__pycache__`/`.DS_Store` excluded from both sides. The packaged artifact is
current — so the graded submission reflects the files reviewed in this audit.

**Note:** the zip contains **no `adapters/` directory and no `.safetensors`** — consistent with
F10(a): the LoRA is not part of the graded artifact.