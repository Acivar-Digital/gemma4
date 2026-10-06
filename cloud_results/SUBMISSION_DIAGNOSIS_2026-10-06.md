# Submission diagnosis 2026-10-06 — ranked failure points

Scope: why submissions scored **0.03** (56765397, Oct 2 04:10 UTC) and **0.00** (56810465, Oct 4 00:51 UTC),
plus why the Oct 5 diagnostic kernel aborted. Diagnosis only; no fix applied.
Six read-only slices (S1–S6); every entry cites the artifact that proves it.
Tracker note: `bd` store unreachable this session (`database not found: gemma4`), so no tickets were filed;
findings stand on commands/output below, not on ticket state.

## Ranked list (scored-artifact proof > local-run proof > harness-text inference)

**R1 — Oct-4 0.00: wrong-lineage adapter shipped in the scored tree (PROVEN present; causality = prime suspect, needs graded-trace confirmation).**
`git show 8f96a94:my_submission/agent.yaml:3` = `adapter: main_lora`; scored-era zip blob holds
`adapters/main_lora/adapter_model.safetensors` (90,098,488 B) + `adapter_config.json` declaring
`base_model_name_or_path: unsloth/gemma-4-31B-it-unsloth-bnb-4bit` (BnB NF4 family) while the served model is
`gemma-4-31b-it-qat-w4a16-ct` (QAT family). Score delta 0.03 → 0.00 coincides exactly with this adapter's
introduction (fix commit 2a1ea19 predates submission). Closing measurement: graded-trace harness-side load error.
(S4)

**R2 — v2 0.03: cause OPEN; 4 of 5 skill post-mortem claims REFUTED against the scored-era artifact.**
Scored-era tree 667472e (no commits Oct 2, nearest to submission): no `adapter` key in agent.yaml, exactly one
root `agent.yaml` in the tracked zip (19 files), prompt names no budget number (thresholds only: fix by call 10,
guard ≥30, emergency ≥36), sampling 4096/4096/`include_thoughts:false`, 0 `.pyc`/`__pycache__`/`.DS_Store`.
Claim 3 (test-discard) mechanism PROVEN in harness text but its firing UNPROVEN (no graded patches in repo).
Caveat: v2 was described as "Rank-8 LoRA Adapter" yet the committed tree/zip contain none — actual uploaded bytes
UNPROVEN from git (Oct-1→Oct-3 commit gap); af860e3 later detached a 72,549,760-B premature adapter, so a 67 MB
adapter-bearing zip existed in working trees but was never committed. (S1, S4)

**R3 — Oct-5 diagnostic abort: Chain A transport structurally incapable (PROVEN, would fail identically on re-push).**
ERROR kernel `francisclyap/gemma4-baseline-v1` pushed via `scripts/push_kernel_safe.sh:517`
(`kaggle kernels push -p $KERNEL_DIR`). Installed client `kaggle_api_extended.py` `kernels_push` (:6319–6452)
uploads only the single `code_file` text + declared source slugs — sibling `submission.zip` never leaves the machine.
Runtime proof: notebook `locate_submission_zip()` rglob → None, `submission_zip_found FAIL`, `SystemExit(1)`,
task loop never started (8/10 checks passed). Dataset hop also carried no zip at runtime (live dataset unpacks to
a loose tree, no zip). Ordered fix (not applied): embed zip as base64 per `scripts/build_kaggle_kernel.py:230` +
cell_1_unpack (:326–331) — proven by `francisclyap/gemma4-eval-40calls` COMPLETE with unpacked `my_submission/`
in outputs — or publish a dataset version containing the zip. Do NOT re-push as-is. (S6)

**R4 — Local run_B39 (56/129) and run_B40 (50/77): 100% proxy data, QUARANTINED.**
Step-level `model_name` census over ALL traces: B39 129/129 files dominant `stealth/space-bunny-alpha`
(5137 proxy vs 382 `none` harness steps vs 0 Gemma); B40 77/77 (3154 vs 158 vs 0). Distinct model strings = proxy only.
`'gemma'` substring = `swegemma_sandbox_*` container paths, never a model id. Proxy defaults confirmed literally:
`start.sh:18` (`thinkingmachines/inkling:free`), `scripts/run_eval.py:32,288`, `scripts/preflight_check.py:235,406`
(`stealth/space-bunny-alpha`). Observed runs used space-bunny (not the start.sh default → launched via run_eval
direct). Quarantined: both resolution rates, all by-repo splits, and every behavioural decomposition (wrong-fix share,
patch-size ratios, tool-call/success curves, token-nudge rates). No local number constrains the graded scores. (S2)

**R5 — Cloud 129-row artifact (`cloud_results/results/task_results.jsonl`, 0/129): silent zero is Container-A empty extraction, not Container-B discard.**
Row schema (dumped first): `[task_id, repo, resolved, test_exit_code, tool_calls, duration_seconds, patch_length, patch]`,
129/129, no `error`/`aborted` key (vs `build_kaggle_kernel.py:725–732` exception writer which emits error+aborted
without test_exit_code — so -1 rows are harness-native, not kernel-exception rows). Buckets: `-1`: 115 empty / 0 non-;
`1`: 1/5; `2`: 1/4; `124`: 0/3. Totals 117 empty, 12 non-empty. P2/P3 (test-path checkout/clean,
HARNESS_README :590–595) run only on non-empty patches after `patch_length` is recorded (Container A, :570–578) —
structurally cannot make a `patch_length==0` row: NOT-OBSERVED. P1 (4-pass apply failure, :583–589) leaves a non-empty
patch + error field: zero supporting rows. Of 115 exit −1: 111 `tool_calls==0` never-acted (77 proven empty-generation
via 2-step zero-token traces + 34 same-profile sans trace file); 6 acted-but-diff-less (4 exit −1 with tc 2–16,
plus fastapi_15280 exit-1/tc31 and fastapi_15661 exit-2/tc30 with 30+ step traces, mechanism OPEN — needs trace
tool-call enumeration). Provenance note: this artifact is NOT byte-linked to either scored submission (S4 byte-parity gap). (S3)

**R6 — Config surface clean; no budget/sampling cause for either score (PROVEN line refs).**
40-call budget unanimous: `main.md:58–59,143–150`, `eval_config.yaml:4` (`max_tool_calls: 40`, ground truth),
`gate_policy.yaml:90`; every harness "50" non-normative (`:418` example JSON, S7.1 turns-not-calls, `:627` CLI example).
Sampling 16384+4096=20480 ≤ 32768 ceiling PASS (`g_sampling_no_thinking_level` PASS); 16384 > 4096 project cap is
WARN-by-design (`g_sampling_output_cap`, never FAIL). `run_skill_script` reconciled: SkillRegistry layer via
`compile_submission` (HARNESS :69), not one of the harness 9 (ToolRegistry) — no conflict; `agent.yaml:4–15`
consistent with `main.md:9–21`. Skill prose gaps already corrected in-tree (55c1e59: 15 gates, 1/day quota, 40-call truth). (S5)

## Skill corrections owed (diagnosis-only: reported, not applied)

1. Prior finding F13's paths `skill_toolset.py:584–585` + `_utils.py:165` do not exist in this repo (repo-wide find:
   zero hits) — recite contract from `my_submission/skills/*/SKILL.md` + `agent.yaml:10–15` + `main.md:9–21`, or mark external-harness. (S5)
2. Preflight `SHIPPED_*` defaults (`{}`/`[]` when zip missing) let `agent_yaml_has_no_adapter_key`,
   `submission_ships_no_adapter_files`, thinking_level-absent checks PASS vacuously — Oct-5 report read 8/10 PASS
   while measuring nothing. Gate-weakness note for `check_submission.py`/preflight hardening. (S6 side observation)

## Open measurements (exact closer for each)

- Graded-trace harness-side error for the Oct-4 adapter (proves R1 causality, not just lineage mismatch).
- Graded-run agent_patch corpus for Oct-2 (closes S1-claim-3 firing for the 0.03).
- Trace tool-call enumeration for the 6 acted-but-empty cloud rows (closes R5 mechanism).
- Byte-parity: no committed `submission.zip` blob (11 hashed) matches submitted sha `1018a128bd4c`; v2 bytes unknowable
  across the Oct-1→Oct-3 commit gap (needs Kaggle-side download).
- Live-gate confirmation already taken this session (see Verification) — closed.

## Verification (implementer-run, 2026-10-06)

- `unzip -l submission.zip | grep -E '(^| )agent\.ya?ml$'` → exactly one root line (`agent.yaml`).
- `grep -c adapter my_submission/agent.yaml` → 0 (current tree ships no adapter).
- `python3 scripts/check_submission.py` → exit 0; 13 passed, 1 non-gating FAIL (`g_run_health`, post_run/infra),
  1 WARN (`g_sampling_output_cap`, by design). 0 gating FAILs — matches plan expectation.
- `find . -name skill_toolset.py` → zero hits (F13 correction owed, above).
- `git status --porcelain`: diagnosis wrote nothing except this file; listed modifications
  (`M`/staged `D` of `*.safetensors`, incl. competition-scaffold deletions) pre-date this session — untouched per scope.
