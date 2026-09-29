# 09 — Gated Roadmap

Scope: theory-first. Code/YAML only after explicit approval.

## Phase 0 — Theory (current, docs 01–08)
- Finish 01–08 design docs from HARNESS_README + sample_submission.
- Gate: user approves theory before any YAML draft.

## Phase 1 — YAML draft (after approval)
- Mirror `sample_submission` filenames (`agent.yaml`, `eval_config.yaml`,
  `configs/sampling.yaml`, `prompts/system.md` + `analyzer.md`,
  `sub_agents/code_analyzer.yaml`).
- Keep sample `sampling.yaml` (0.2 / 16384 / 4096); single model
  `gemma-4-31b-it-qat-w4a16-ct`; hybrid main + searcher via
  `agent_tool skip_summarization:true`.
- No LoRA adapters v1.

## Phase 2 — Local test + iterate
- Run recipe from 08-eval-plan on 1–2 fastapi tasks (50 calls / 30 min).
- Inspect `summary.json`, `patches/`, `traces/`; fix prompts/budgets.
- Iterate until source-only patches resolve reliably.

## Do-NOT list
- NO `my_submission/` without explicit user approval.
- NO `agent.py` — declarative YAML only (`compile_submission`).
- NO bare `pytest` in agent instructions; NO test-file edits.
- NO repro files in `/workspace`; NO LoRA v1; NO `..` in `!include`.
