# 08 — Local Eval Plan

Source: HARNESS_README §9 + locked decision #9. Theory only — no run yet.

## 1. Recipe (1–2 fastapi tasks)
```bash
swegemma eval --task-id <fastapi-id> --max-tool-calls 50 --max-time-minutes 30
```
- Add `--tasks tasks.jsonl --snapshots-dir snapshots` + `--submission-dir`
  pointing at the approved submission dir, `--results-dir results/run_XX`.
- Keep `--sandbox docker` default; `--task-id` for single-task debugging.

## 2. Artifacts (`--results-dir`)
- `summary.json` — aggregate resolution rate, resolved count, per-repo split.
- `task_results.jsonl` — one line per task: metrics, exit codes, errors.
- `patches/<id>.patch` — exact Container A diff (`git add -N . && git diff`).
- `test_outputs/<id>.log` — Container B hermetic pytest stdout/stderr.
- `traces/trace_<id>.json` — ATIF steps, thoughts, tool calls, tokens.
- `logs/<id>.log` — Phase 1 agent session transcript.

## 3. What to measure
- Resolution: `exit_code == 0` AND JUnit `passed > 0, failures = errors = 0`.
- Efficiency: tool calls used vs 50 budget, wall-clock vs 30 min.
- Context health: compaction events (threshold 14336), `budget_warning`
  appearances, `<|tool_call>` truncation incidents.
- Patch quality: non-empty, source-only, applies in 4-pass `git apply`.

## 4. Budget warning
- Sample `eval_config.yaml` (10 calls / 1 min) is a smoke-test stub,
  NOT the real budget. Locked v1 uses harness defaults: **50 / 30**.
- Do not ship the sample values; override at CLI or set eval_config to 50/30.

## 5. Pass criteria
- 1–2 fastapi tasks resolve with source-only patches; no bare-pytest
  timeouts; no /workspace repro pollution.
