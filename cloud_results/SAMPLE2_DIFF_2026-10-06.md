# SAMPLE2 cross-validation 2026-10-06 — prvsiyan/gemma-and-the-shape-of-doubt (official 0.08) vs our theories

Provenance: `kaggle kernels output prvsiyan/gemma-and-the-shape-of-doubt -p /tmp/ps`.
`/tmp/ps/official-score-evidence.json`: server ref 56528080, publicScore **0.08** (user's "0.8" is a typo;
log line 133 "Confirmed official score: 0.08", leader 0.13). Scored-tree sha256 `c3f13174…95440`
matches the log (lines 99/113/138) AND the downloaded submission.zip (23023 B, 8 files) — byte-parity,
the strongest provenance in this investigation. NOTE: the downloaded kernel output is the author's
newer dev state (candidate screens, comparison JSONs); the 16-task graded log in the goal attachment
is the scored-behavior record. Both agree on the tree below.

## Scored tree (S2) vs sample1 (S1, ~0.12) vs ours

| surface | S1 ryanholbrook | S2 prvsiyan (0.08) | ours (v2 0.03 / Oct-4 0.00) |
|---|---|---|---|
| adapter | dummy r=4, CORRECT base | NO adapter key, no adapters/ dir | v2: none; Oct-4: WRONG BnB base |
| tools | all 9 + analyzer sub-agent | all 9 + reviewer sub-agent (skip_summarization **false**) | 5 tools (no run_command, no graph trio), no sub-agent |
| skills | 0 | 1 (repo-lens, read-only localizer) | 5 (orchestrated via run_skill_script) |
| sampling | 0.2 / 16384 / 4096 | **1.0** / 2048 / 2048 / thoughts **false** | 0.15 / 16384 / 4096 / thoughts true |
| budget | 10 calls / 1 min / 50 turns | 45 / 5 min / 80 | 40 / 4.5 min / 100 |
| include_contents | (not recorded) | default | key absent |
| size | ~221 KB w/ adapter | 23 KB, 8 files | 0.5 MB unpacked |

## User's question — adjudicated

**Neither sample is the same as us.** Both scoring samples share the SAME direction away from us:
full 9-tool surface (incl. run_command) + a reviewer/analyzer sub-agent + minimal skill layer (0–1 skills).
We are the outlier: 5 tools + 5 skills + no sub-agent. S1 and S2 differ from EACH OTHER mainly in
adapter (correct-dummy vs none), budget generosity, temperature, and prompt — i.e. the
adapter/budget/sampling axes move scores between 0.08–0.12, but the tool+sub-agent shape is common
to both scorers and absent in both our submissions (0.03, 0.00).

## Theory verdicts

- **R1 (wrong-lineage adapter → Oct-4 0.00): SUPPORTED, still not isolated.** Score ordering is now
  four-deep: Oct-4 wrong-adapter 0.00 < v2 no-adapter 0.03 < S2 no-adapter 0.08 < S1 correct-adapter ~0.12.
  No-adapter brackets us on both sides, so the adapter axis only explains Oct-4. Isolation caveat stands:
  Oct-4 vs v2 changed 3 variables (adapter + max_output 4096→16384 + thoughts true). Needs graded-trace text.
- **R2 (v2 0.03 cause OPEN): NARROWED.** v2 vs S2 are both adapter-less (0.03 vs 0.08) → that gap is
  prompt/tools, not adapter. New lead suspect for the v2 gap: **run_command absence**. S2's prompt
  (log lines 87/89) centers on inline heredoc reproducers via run_command; our agent cannot run any
  ad-hoc reproducer (only fixed skill scripts). S2 resolves 6/16 with reproducer-led loops; v2's
  ceiling without run_command is untested but structurally lower.
- **R5 (Container-A empty as real mode): CONFIRMED, recalibrated.** S2's 16-task log shows empty
  extractions WITH action (timeouts, budget, context blowup — never silent). Our cloud 111× tc=0
  (never-act) has no counterpart in S2: every S2 task enters the agent loop. Never-act remains abnormal
  → submission-side load failure, consistent with R1.
- **Budget-generosity-harm: RETIRED as primary cause.** S2 at 45/5min still scores 0.08 WITH 4 resource
  deaths (2 session timeouts: httpx_3672, rich_4006; 1 budget exhaustion: fastapi_14512 at 45 calls;
  1 context blowup: rich_3772). S1 at 10/1min scores ~0.12. Both envelopes score; our 40/4.5/100 sits
  inside the scoring envelope → budget size is not our killer.
- **Context starvation: UPGRADED with real-harness proof.** S2 rich_3772 died
  `ContextWindowExceededError: prompt 30721 + requested 2048 > 32768` (log line 284) — prompt-history
  growth, not output cap, is the binding constraint. Our 16384-output + 4096-thoughts + thoughts:true
  config is MORE exposed than S2's frugal 2048/2048/false. New sub-finding: output/thinking frugality
  beats ceiling arithmetic under history growth.
- **E2 tension (honest):** S2 runs thoughts:false and scores — existence proof thoughts-off CAN score.
  This does not overturn the E2 measurement (our traces retain thoughts; premise for disabling was false),
  but it retires "thoughts:false always hurts" if anyone held it.
- **Tier-3 poison pills: VALIDATED.** S2 fails exactly our census Tier-3 rows: httpx_3672 (timeout),
  fastapi_15661 and fastapi_15280 (clean false). requests_7502 (our cloud tc=6 empty) resolves TRUE here —
  solvable task,ieger our cloud never-act was not task difficulty.
- **arch-decision no-sub-agent rule: now TWO counterexamples.** S1 (skip_summarization:true) AND S2
  (skip_summarization:false) both score with a sub-agent; flag value doesn't decide. Rule status remains
  CHALLENGED, awaiting user decision — S2 strengthens the challenge.
- **Author's own confound note (log line 131):** "This comparison does not isolate the effect of the
  prompt or tool changes." Respected — S1-vs-S2 deltas are multi-variable, same as ours.

## Net effect on the ranked list

1. Wrong-lineage adapter → Oct-4 0.00 (prime suspect, needs graded-trace confirmation). STRONGER.
2. v2 0.03 gap = prompt/tools, lead suspect run_command absence + no sub-agent. NEW/SHARPENED.
3. Budget size exonerated as primary cause. RETIRED.
4. Sampling frugality (small outputs, thoughts off) is a live lever for context survival. NEW.
5. Tier-3 concessions + never-act abnormality + no-sub-agent challenge all reinforced.
