# Baseline diff: ryanholbrook (~0.12) vs our scored trees

Source: `kaggle kernels output ryanholbrook/getting-started-gemma-4-developer-agent -p /tmp/rh`
(2-task demo log + full `sample_submission/` tree + `submission.zip`, 0.17 MiB, 16 files).
Reference tree = stock `sample_submission` + getting-started notebook. All cites re-runnable from `/tmp/rh`.

## Headline

Mental model ("everything same except skills/instructions") is **half-refuted**: model, layout, hygiene,
and timeout_seconds match, but the **adapter lineage, adapter size/targets, toolset, and eval budgets all differ** —
and the differences point the same way as Part 1 (R1). Theory survives; one axis strengthened.

## Diff table (baseline vs our Oct-4 0.00 tree @8f96a94)

| Surface | Baseline (~0.12) | Ours Oct-4 (0.00) | Verdict |
|---|---|---|---|
| model | `gemma-4-31b-it-qat-w4a16-ct` (agent.yaml) | identical | SAME |
| adapter key | `adapter: main_lora` PRESENT | `adapter: main_lora` PRESENT | SAME presence |
| adapter base | `google/gemma-4-31b-it-qat-w4a16-ct` = served checkpoint (correct lineage) | `unsloth/gemma-4-31B-it-unsloth-bnb-4bit` (wrong family) | **DIFFERENT — R1** |
| adapter shape | r=4, alpha=8, `q_proj+o_proj` only, 217 KB dummies ×2 | r=8, alpha=16, regex over attn **+MLP**, 90 MB real | DIFFERENT, ours riskier on all 4 axes |
| adapter served? | YES — demo trace steps carry `model_name='main_lora'` (vLLM `--lora-modules` loaded it) | unknown; 77 two-step zero-token traces suggest never served | contrast supports R1 mechanism |
| tools | all 9 + `agent_tool` code_analyzer (`skip_summarization:true`) | 5 only (no `run_command`, no graph tools) + 5 skills via `run_skill_script` | DIFFERENT |
| sub-agent | `code_analyzer` (own `tool_lora`) | none | DIFFERENT |
| prompt | minimal/fast, "under 8–10 turns", no skills, never-touch-tests | 40-call ladder + skill orchestration | DIFFERENT (as expected) |
| eval budget | 10 calls / 1 min / 50 turns / timeout 60 s | 40 calls / 4.5 min / 100 turns / timeout 60 s | **DIFFERENT — 4× calls, 4.5× wall** |
| sampling | 0.2 / 16384 / nested `thinking_config` 4096 + thoughts | 0.15 / 16384 / flat 4096 + thoughts | cosmetic |
| zip hygiene/layout | root `agent.yaml`, 0 pyc | root `agent.yaml`, 0 pyc | SAME |

## Does he make our "mistakes"?

- **Adapter presence: same, yet scores** — kills any residual "any adapter crashes the run" story (already refuted in S1:
  our v2 shipped none). The live variable is **lineage + shape, not presence**: correct-base dummy loads, serves
  (`model_name='main_lora'` in-trace proof), and scores; wrong-base full-finetune-shaped adapter coincides with 0.00.
- **Timeout/-1/empty: YES, identical signature on real Gemma 4.** Both demo tasks:
  `agent timed out` → `completed without explicit submit_patch call and no working tree modifications` →
  `resolved=False, exit_code=-1, patch_chars=0, tool_calls=4` (76.1 s / 73.1 s vs his 60 s timeout + 1 min cap).
  R5's Container-A empty mode is genuine harness behavior under a tight budget — not our artifact, not our bug.
- **But different failure depth.** His agent ACTS (4 calls) then wall-clock kills it. Our cloud artifact's dominant mode is
  111× `tool_calls==0` never-act — a deeper failure than his timeout. If cloud ≡ graded Oct-4 run (0/129 = 0.00;
  95 trace files = 129−34 tracelsess, consistent), the coherent story is: wrong-lineage adapter fails at
  load/first-inference → 2-step zero-token traces → tc=0 → −1 → 0.00. Status: **strong hypothesis, needs graded-trace
  error text** (unchanged measurement from Part 1).
- **Same-task contrast exists.** His demo ran fastapi_15661 + fastapi_15588 (both −1/empty there). In our cloud artifact,
  15661 ran 30 calls (exit 2, empty) and 15588 shipped a real `sse.py` diff (exit 1, nonempty). Our bigger budget lets the
  agent wander further — and still fail. Budget direction (his 10/1-min vs our 40/4.5-min) is a second candidate
  differentiator: tight budget forces submit-or-die; loose budget funds thrash. Untested; cheap test = resubmit current
  tree with his budget numbers.
- **thinking_level / nesting / bytecode / 50-call trip: same-clean on both sides** — no information, consistent with
  Part 1 refutations.

## Net vs Part 1

- R1 (wrong-lineage adapter): **strengthened** — baseline is the control experiment (correct lineage + dummy weights → loads,
  serves, 0.12; wrong lineage + 90 MB → 0.00). Presence-vs-absence is ruled out as the axis; lineage/shape is the axis.
- R2 (0.03 cause open): unchanged. Note v2 (no adapter, 40-call budget) scored 0.03 < baseline 0.12 — budget/prompt/skill
  surface is now the lead suspect for the v2→baseline gap, with the adapter absent in both causal pictures.
- R5 (Container-A empty): **confirmed as real-harness mode**, recalibrated — his empty comes with action-then-timeout;
  ours (cloud) is mostly never-act. Two different depths, possibly two different causes.
- New candidate (not in Part 1): **eval-budget generosity as harm** — 40 calls/4.5 min vs 10/1 min. Untested.

## Suggested next measurements (no action taken)

1. Graded-trace error text for Oct-4 (closes R1 causality).
2. Served-model census over `cloud_results/results/traces/*.json` (S2 method; unknown whether cloud ran proxy or Gemma 4 —
   required before comparing cloud rows to his real-Gemma demo).
3. Cheap A/B: current tree with his budget block (10 / 1 min / 50 turns) in a local proxy run — tests budget-generosity harm
   without spending quota.
