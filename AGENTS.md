# AGENTS.md — gemma4-dev

## Goal
Win the **Google Gemma 4 Developer Agent** Kaggle competition: autonomous SWE-bench-style agent that fixes GitHub issues in unseen Python repos. Resolution Rate is the metric.

Source of truth: `HARNESS_README.md` (671 lines). Read it before any design work.

## Strict Constraints (from harness)
- **Declarative-only:** no `agent.py`. Submission = `agent.yaml` + `sub_agents/*.yaml` + `prompts/*.md` + `configs/*.yaml` compiled by `compile_submission`. `!include` depth ≤10, no `..` traversal.
- **Single model:** `gemma-4-31b-it-qat-w4a16-ct` for all agents. Context 32K (`max_output_tokens` + `thinking_budget` ≤32768).
- **9 tools only:** `run_command`, `submit_patch` (free), `get_status` (free), `read_file` (150 lines/10K chars), `edit_file` (3-tier match), `write_file`, `search_similar_code`, `get_code_neighbors`, `get_code_subgraph`.
- **Patch = `git add -N . && git diff HEAD`** in Container A. Test-file edits are discarded in Container B. Scratch repro in `/tmp`, never `/workspace`.
- Compaction already exists (`token_threshold` 14336). `agent_tool skip_summarization:true` is the blessed isolation pattern.

## Repo Layout
- `tasks.jsonl` — 129 tasks (fastapi 67, rich 48, requests 13, httpx 1)
- `sample_submission/` — baseline: `agent.yaml`, `eval_config.yaml`, `configs/sampling.yaml` (0.2/16384/4096), `prompts/system.md` + `analyzer.md`, `sub_agents/code_analyzer.yaml`, dummy LoRAs (213K each)
- `graphs/` (127 .json), `embeddings/` (.npz), `snapshots/`, `wheels/`, `docker/`, `sandbox/`
- `gemma-4-developer-agent/` — empty. `my_submission/` — does NOT exist (do not create without approval).

## Locked v1 Decisions (bd remember `gemma4-agent-v1-decisions-*`)
1. Budgets: harness defaults (50 calls/30min standard eval), not 4-min rumor
2. Main = hybrid: keeps `read_file`, delegates graph tools to searcher
3. Delegation via `agent_tool skip_summarization:true`
4. Searcher returns strict schema (file, lines, root cause, minimal change, confidence), no raw dumps
5. Verify: `/tmp` repro + targeted single-file pytest, `submit_patch` last
6. Keep sample `sampling.yaml`
7. Mirror `sample_submission` filenames
8. No LoRA adapters v1
9. Local test: `--max-tool-calls 50 --max-time-minutes 30` on 1–2 fastapi tasks

## Current Scope
User cancelled YAML drafting (`projects-ey0` closed). Key task is LLM context only. Do NOT create `my_submission/` or draft YAML without explicit approval.

## Workflow
- `bd` for all tracking. Non-interactive shell flags (`cp -f`, `mv -f`, `rm -f`, `rm -rf`).
- Verify by reading files / running `swegemma eval --task-id ...`, never by guessing.
- **CRITICAL EXECUTION PROTOCOL (bd `execution-protocol-only-start-sh`):** The user ONLY runs `./start.sh` to execute SWE-Gemma evaluations and tests. Agents must NEVER run evaluation runners directly, NEVER invoke `scripts/run_eval.py`, NEVER launch evaluations in tmux windows, and NEVER execute tests automatically. All test executions are initiated exclusively by the user running `./start.sh`.
