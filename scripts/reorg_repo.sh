#!/usr/bin/env bash
# reorg_repo.sh — auditable repo reorganization (proposal, NOT yet approved).
# Usage: ./scripts/reorg_repo.sh --dry-run   # print plan only (default-safe)
#        ./scripts/reorg_repo.sh --execute    # perform moves, log manifest
#
# MOVE RULE (verified 2026-10-06 via `git check-ignore` + `git ls-files`):
#   git mv  = TRACKED paths (history preserved): my_submission, sample_submission,
#             kaggle_adapter_dataset, kaggle_submission_dataset, kaggle_baseline_v1,
#             kaggle_canary_eval, kaggle_kernel, kaggle_test_adk,
#             cloud_results/my_submission, cloud_results/canary_test_results,
#             kaggle_unsloth/*.ipynb, data/unsloth_sft_*.jsonl
#   plain mv = IGNORED paths (no git history exists to preserve): results/run_B*,
#             cloud_results/results
# Reference rewrites (files verified to contain `my_submission`):
#   scripts/submit_safe.sh, scripts/check_submission.py, start.sh, AGENTS.md
#   : s|my_submission|submissions/track1_live|g  (sed, logged per file)
# Extras on --execute: delete root submission.zip (rebuilds via submit script);
#   create root README.md with the repo-map sentence (no README.md exists today).
# Verification post-execute: python3 scripts/check_submission.py (gates green).
set -uo pipefail
MODE="${1:---dry-run}"
LOG="evidence/reorg_manifest_$(date +%F).log"
GMV() {  # git mv for TRACKED paths
  if [ "$MODE" = "--dry-run" ]; then echo "GIT-MV $1 -> $2";
  else git mv "$1" "$2" && echo "GIT-MV $1 -> $2" | tee -a "$LOG"; fi
}
PMV() {  # plain mv for IGNORED paths (results/, cloud_results/results)
  if [ "$MODE" = "--dry-run" ]; then echo "MV(ignored) $1 -> $2";
  else mv "$1" "$2" && echo "MV(ignored) $1 -> $2" | tee -a "$LOG"; fi
}
if [ "$MODE" = "--execute" ]; then
  mkdir -p evidence submissions simulation/kernels_diag simulation/runs_local \
    training/notebooks training/sft_data reports
  : > "$LOG"
fi
GMV my_submission submissions/track1_live
GMV sample_submission submissions/track1_scaffold
GMV kaggle_adapter_dataset submissions/adapter_dataset
GMV kaggle_submission_dataset submissions/ship_dataset
GMV kaggle_baseline_v1 simulation/kernels_diag/kaggle_baseline_v1
GMV kaggle_canary_eval simulation/kernels_diag/kaggle_canary_eval
GMV kaggle_kernel simulation/kernels_diag/kaggle_kernel
GMV kaggle_test_adk simulation/kernels_diag/kaggle_test_adk
for d in results/run_B*; do PMV "$d" "simulation/runs_local/$(basename $d)"; done
PMV cloud_results/results evidence/cloud_runs_results
GMV cloud_results/my_submission evidence/cloud_runs_my_submission
GMV cloud_results/canary_test_results evidence/canary
for f in cloud_results/*.md; do GMV "$f" "reports/$(basename $f)"; done
GMV kaggle_unsloth/train_gemma4_lora.ipynb training/notebooks/train_gemma4_lora.ipynb
GMV kaggle_unsloth/train_gemma4_lora_minimal.ipynb training/notebooks/train_gemma4_lora_minimal.ipynb
GMV data/unsloth_sft_train.jsonl training/sft_data/unsloth_sft_train.jsonl
GMV data/unsloth_sft_val.jsonl training/sft_data/unsloth_sft_val.jsonl
for f in scripts/submit_safe.sh scripts/check_submission.py start.sh AGENTS.md; do
  if [ "$MODE" = "--dry-run" ]; then echo "SED my_submission->submissions/track1_live in $f";
  else sed -i 's|my_submission|submissions/track1_live|g' "$f" && echo "SED $f" | tee -a "$LOG"; fi
done
if [ "$MODE" = "--dry-run" ]; then
  echo "RM submission.zip (root; rebuilds via scripts/submit_safe.sh)"
  echo "CREATE README.md (repo-map sentence; none exists today)"
else
  rm -f submission.zip && echo "RM submission.zip" | tee -a "$LOG"
  cat > README.md <<'EOF'
# gemma4 — Gemma 4 Developer Agent competition
If it ships, it lives under `submissions/` (`track1_live` = the scored Track-1 tree,
`track1_scaffold` = read-only baseline, `*_dataset` = upload staging); local sim runs live
under `simulation/`, LoRA training inputs under `training/`, graded evidence under `evidence/`,
and analytical reports under `reports/` — see `docs/REORG_PROPOSAL.md`.
EOF
  echo "CREATE README.md" | tee -a "$LOG"
fi
echo "MODE=$MODE done. Review docs/REORG_PROPOSAL.md before --execute."
