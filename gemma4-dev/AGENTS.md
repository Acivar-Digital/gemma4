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
- `gemma-4-developer-agent/` — empty.
- `my_submission/` — Active Track 1 baseline submission (declarative ADK agent with 5 pre-installed skills: `fast-grep`, `code-map`, `code-oracle`, `repro-check`, `test-gate`). Scored 56/129 (43.4%) in run_B39.
- `submission.zip` — Packaged and verified 221 KB competition submission archive.

## Canonical Architecture Source of Truth
Read `docs/EXTERNAL_REVIEW_PACKET.md` (or `EXTERNAL_REVIEW_PACKET.md` in root) for the final, locked architectural truth on:
- SFT Dataset: Multi-turn tool calling trajectories (never single-turn markdown diffs).
- Sequence Length: `max_seq_length=16384` with gradient checkpointing (never 4096).
- LoRA Specs: Rank 8 on `q_proj`, `v_proj`, `o_proj` only (freeze MLPs).
- Prompt Governor: Dynamic 4-probe scratchpad, anti-thrashing circuit breaker, 2-strike edit oscillation rule.
- Subprocess Shield: 3.0s socket timeout, 1GB memory runaway guard, process-group SIGKILL cleanup.

## Current Operational Scope (Dual-Track Master Plan)
- **Track 1 (Immediate Lock-In):** Submit verified `submission.zip` to Kaggle leaderboard upon daily quota reset tonight at 00:00:00 UTC.
- **Track 2 (LoRA Upgrade):** Train Rank-8 LoRA with Unsloth on single L4 GPU on Oct 3 when 30h GPU quota refreshes; mount as `adapter: main_lora` only if Resolution Rate >= 43.4%.

## Workflow
- `bd` for all tracking. Non-interactive shell flags (`cp -f`, `mv -f`, `rm -f`, `rm -rf`).
- Verify by reading files / running `swegemma eval --task-id ...`, never by guessing.
- **CRITICAL EXECUTION PROTOCOL (bd `execution-protocol-only-start-sh`):** The user ONLY runs `./start.sh` to execute SWE-Gemma evaluations and tests. Agents must NEVER run evaluation runners directly, NEVER invoke `scripts/run_eval.py`, NEVER launch evaluations in tmux windows, and NEVER execute tests automatically. All test executions are initiated exclusively by the user running `./start.sh`.

## Instructions
- Run `bd prime` at the start of the session or after compact to refresh persist memories.
