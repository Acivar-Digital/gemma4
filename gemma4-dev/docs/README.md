# Gemma 4 Developer Agent — Win Plan (Theory First, Test Second)

> Method: paper first, then code. No `my_submission/` until theory is approved.
> Source of truth: `HARNESS_README.md` (671 lines). Baseline: `sample_submission/`.

## Table of Contents (docs vault)

| # | Doc | Question it answers |
|---|-----|---------------------|
| 0 | [README.md](README.md) (this file) | Where are we, what is the TOC? |
| 1 | [01-competition.md](01-competition.md) | What is the game, metric, lifecycle? |
| 2 | [02-dataset.md](02-dataset.md) | What are the 129 tasks? Where is the weight? |
| 3 | [03-constraints.md](03-constraints.md) | What are the hard limits? (declarative-only, 1 model, 9 tools, 32K) |
| 4 | [04-failure-modes.md](04-failure-modes.md) | How does the baseline die? (compaction, truncation, patch pollution, test-tamper) |
| 5 | [05-theory-oneup.md](05-theory-oneup.md) | Our thesis: Context-Preserving Map-Reduce via `agent_tool skip_summarization:true` |
| 6 | [06-prompt-contracts.md](06-prompt-contracts.md) | Exact Main vs Searcher tool split + strict return schema |
| 7 | [07-verify-protocol.md](07-verify-protocol.md) | `/tmp` repro + single-file pytest + `submit_patch` last |
| 8 | [08-eval-plan.md](08-eval-plan.md) | How we test: `swegemma eval --task-id` on 1–2 fastapi tasks, 50 calls / 30 min |
| 9 | [09-roadmap.md](09-roadmap.md) | Theory → YAML draft → local test → iterate. Gates + approvals |

## Ensemble status
- Tried `opencode-ensemble` scout split (harness reader / baseline mapper / decisions checker).
- Subagent backend failed: `Model unavailable: openrouter/google/gemini-3.5-flash-lite` ×3 → lead did direct recon (see docs 01–04). No code changed.
- Next: fill docs 01–09 one by one, get approval, only then draft YAML.

## Key facts (locked v1, from AGENTS.md + recon today)
- Metric: Resolution Rate. Phase 1 Container A (`/workspace`, `git add -N . && git diff HEAD`), Phase 2 Container B (fresh snapshot + `agent_patch` + `test_patch` + hermetic pytest, JUnit `exit_code==0`).
- Submission = `agent.yaml` + `sub_agents/*.yaml` + `prompts/*.md` + `configs/*.yaml`, `!include` depth ≤10, no `..`, <3 GiB. No `agent.py`.
- Single model: `gemma-4-31b-it-qat-w4a16-ct`. Context 32K (`max_output_tokens` + `thinking_budget` ≤32768). Sample: 16384/4096, temp 0.2.
- 9 tools only: `run_command`, `submit_patch` (free), `get_status` (free), `read_file` (150 lines/10K chars), `edit_file` (3-tier), `write_file`, `search_similar_code`, `get_code_neighbors`, `get_code_subgraph`.
- Compaction: `token_threshold` 14336, interval 5. Blessed isolation: `agent_tool skip_summarization:true`.
- Test edits discarded in Container B (`git checkout HEAD` on `tests/`, `conftest.py`, `pytest.ini`). Scratch repro in `/tmp`, never `/workspace`.
- Tasks: 129 = fastapi 67, rich 48, requests 13, httpx 1. Sample eval_config is 10 calls/1 min — real test uses 50 calls/30 min.
- Baseline: root `swe_baseline_agent` holds ALL 9 tools + `code_analyzer` sub-agent. Our v1 thesis: Main = hybrid (keep `read_file`, delegate graph tools to searcher).
- User correction active: 4-min limit in pasted prompt is rumor; use harness defaults (50 calls/30min). Do NOT create `my_submission/` without approval.
