# REORG proposal 2026-10-06 — separate submission / simulation / analytical (DRAFT, not executed)

## Problem (user report)
Training data vs submission data indistinguishable; competition vs simulation submissions
unlabelled; analytical evidence mixed with shippable trees.

## Current pain points (verified 2026-10-06)
- 3 `submission.zip` copies: root, `kaggle_baseline_v1/`, `kaggle_submission_dataset/` — unclear which scored.
- `my_submission/` (live Track-1 tree) vs `sample_submission/` (competition scaffold) vs
  `cloud_results/my_submission/` (analytical copy) — same name, three roles.
- 6 `kaggle_*` dirs mix diagnostic kernels, adapter datasets, training notebooks.
- `data/unsloth_sft_*.jsonl` (TRAINING data) sits beside submission-adjacent dirs with no label.
- `results/run_B*` (local SIMULATION) vs `cloud_results/results` (GRADED cloud) — same dirname.
- `docs/` mixes specs, workplans, and analytical reports (`FINDINGS.md`, `gemma-and-the-shape-of-doubt.md`).

## Proposed structure (live paths renamed minimally; harness inputs untouched)

```
submissions/               # EVERYTHING THAT SHIPS — competition-scored or ship-candidate
  track1_live/             #  <- my_submission (TRACKED; git mv)
  track1_scaffold/         #  <- sample_submission (TRACKED; git mv; READ-ONLY ref)
  adapter_dataset/         #  <- kaggle_adapter_dataset (TRACKED; git mv)
  ship_dataset/            #  <- kaggle_submission_dataset (TRACKED; git mv)
simulation/                # LOCAL runs only — never scored, never shipped
  kernels_diag/            #  <- 4 kaggle kernel dirs (TRACKED; git mv)
  runs_local/              #  <- results/run_B* (IGNORED; plain mv, no history to keep)
training/                  # TRACK 2 (LoRA upgrade) inputs only — all TRACKED; git mv
  notebooks/               #  <- kaggle_unsloth/*.ipynb
  sft_data/                #  <- data/unsloth_sft_*.jsonl
  gcp/                     #  <- gcp/ (unchanged)
evidence/                  # GRADED / analytical — read-only record, never shipped
  cloud_runs_results/      #  <- cloud_results/results (IGNORED; plain mv)
  cloud_runs_my_submission/#  <- cloud_results/my_submission (TRACKED; git mv)
  canary/                  #  <- cloud_results/canary_test_results (TRACKED; git mv)
reports/                   #  <- cloud_results/*.md (TRACKED; git mv)
docs/                      # specs only (unchanged files stay)
HARNESS INPUTS (untouched — harness/start.sh expect them): tasks.jsonl, graphs/,
embeddings/, snapshots/, wheels/, sandbox/, scripts/, start.sh, tests/
```

## Rules the structure enforces
1. If it's under `submissions/`, it ships or is ship-candidate. Everything else is not scored.
2. `submission.zip` copies live ONLY under `submissions/` (root copy deleted; it rebuilds via script).
3. `training/` vs `submissions/*/dataset` disambiguates training data vs submission data by PATH.
4. `simulation/` vs `evidence/` disambiguates local-proxy runs vs graded cloud runs by PATH.
5. `track1_scaffold/` is read-only reference (no edits; gates enforce).

## Execution (after approval)
`scripts/reorg_repo.sh --dry-run` prints every `git mv` + reference update without touching
`evidence/reorg_manifest_2026-10-06.log`. Reference updates (verified holders):
`scripts/submit_safe.sh`, `scripts/check_submission.py`, `start.sh`, `AGENTS.md`
-> `submissions/track1_live` (exact list in script header). No root README.md exists
today — the script creates it with the repo-map sentence. Harness-input
paths are NOT moved, so eval behaviour is unchanged; verification = `check_submission.py`
gates green + `git status` clean before/after diff review.
