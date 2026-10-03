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

---

# Agent Instructions

This project uses **bd** (beads) for issue tracking. Run `bd prime` for full workflow context.

> **Architecture in one line:** Issues live in a local Dolt database
> (`.beads/dolt/`); cross-machine sync uses `bd dolt push/pull` (a
> git-compatible protocol), stored under `refs/dolt/data` on your git
> remote — separate from `refs/heads/*` where your code lives.
> `.beads/issues.jsonl` is a passive export, not the wire protocol.
>
> See [sync-concepts](https://github.com/gastownhall/beads/blob/main/docs/core-concepts/sync-concepts.md)
> for the one-screen overview and anti-patterns (don't treat JSONL as the
> source of truth; don't `bd import` during normal operation; don't
> reach for third-party Dolt hosting before trying the default).

## Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work atomically
bd close <id>         # Complete work
bd dolt push          # Push beads data to remote
```

## Non-Interactive Shell Commands

**ALWAYS use non-interactive flags** with file operations to avoid hanging on confirmation prompts.

Shell commands like `cp`, `mv`, and `rm` may be aliased to include `-i` (interactive) mode on some systems, causing the agent to hang indefinitely waiting for y/n input.

**Use these forms instead:**
```bash
# Force overwrite without prompting
cp -f source dest           # NOT: cp source dest
mv -f source dest           # NOT: mv source dest
rm -f file                  # NOT: rm file

# For recursive operations
rm -rf directory            # NOT: rm -r directory
cp -rf source dest          # NOT: cp -r source dest
```

**Other commands that may prompt:**
- `scp` - use `-o BatchMode=yes` for non-interactive
- `ssh` - use `-o BatchMode=yes` to fail instead of prompting
- `apt-get` - use `-y` flag
- `brew` - use `HOMEBREW_NO_AUTO_UPDATE=1` env var

<!-- BEGIN BEADS INTEGRATION v:1 profile:full hash:9c890b20 -->
## Issue Tracking with bd (beads)

**IMPORTANT**: This project uses **bd (beads)** for ALL issue tracking. Do NOT use markdown TODOs, task lists, or other tracking methods.

### Why bd?

- Dependency-aware: Track blockers and relationships between issues
- Git-friendly: Dolt-powered version control with native sync
- Agent-optimized: JSON output, ready work detection, discovered-from links
- Prevents duplicate tracking systems and confusion

### Quick Start

**Check for ready work:**

```bash
bd ready --json
```

**Create new issues:**

```bash
bd create "Issue title" --description="Detailed context" -t bug|feature|task -p 0-4 --json
bd create "Issue title" --description="What this issue is about" -p 1 --deps discovered-from:bd-123 --json
```

**Claim and update:**

```bash
bd update <id> --claim --json
bd update bd-42 --priority 1 --json
```

**Complete work:**

```bash
bd close bd-42 --reason "Completed" --json
```

### Issue Types

- `bug` - Something broken
- `feature` - New functionality
- `task` - Work item (tests, docs, refactoring)
- `epic` - Large feature with subtasks
- `chore` - Maintenance (dependencies, tooling)

### Priorities

- `0` - Critical (security, data loss, broken builds)
- `1` - High (major features, important bugs)
- `2` - Medium (default, nice-to-have)
- `3` - Low (polish, optimization)
- `4` - Backlog (future ideas)

### Workflow for AI Agents

1. **Check ready work**: `bd ready` shows unblocked issues
2. **Claim your task atomically**: `bd update <id> --claim`
3. **Work on it**: Implement, test, document
4. **Discover new work?** Create linked issue:
   - `bd create "Found bug" --description="Details about what was found" -p 1 --deps discovered-from:<parent-id>`
5. **Complete**: `bd close <id> --reason "Done"`

### Quality
- Use `--acceptance` and `--design` fields when creating issues
- Use `--validate` to check description completeness

### Lifecycle
- `bd defer <id>` / `bd supersede <id>` for issue management
- `bd stale` / `bd orphans` / `bd lint` for hygiene
- `bd human <id>` to flag for human decisions
- `bd formula list` / `bd mol pour <name>` for structured workflows

### Sync

bd stores issue history in Dolt:

- Each write auto-commits to Dolt history
- Do not treat `.beads/issues.jsonl` as the sync protocol

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/core-concepts/sync-concepts.md for details and anti-patterns.

### Important Rules

- ✅ Use bd for ALL task tracking
- ✅ Always use `--json` flag for programmatic use
- ✅ Link discovered work with `discovered-from` dependencies
- ✅ Check `bd ready` before asking "what should I work on?"
- ❌ Do NOT create markdown TODO lists
- ❌ Do NOT use external issue trackers
- ❌ Do NOT duplicate tracking systems

For more details, see README.md and https://github.com/gastownhall/beads/blob/main/docs/getting-started/quickstart.md.

## Agent Context Profiles

The managed Beads block is task-tracking guidance, not permission to override repository, user, or orchestrator instructions.

- **Conservative (default)**: Use `bd` for task tracking. Do not run git commits, git pushes, or Dolt remote sync unless explicitly asked. At handoff, report changed files, validation, and suggested next commands.
- **Minimal**: Keep tool instruction files as pointers to `bd prime`; use the same conservative git policy unless active instructions say otherwise.
- **Team-maintainer**: Only when the repository explicitly opts in, agents may close beads, run quality gates, commit, and push as part of session close. A current "do not commit" or "do not push" instruction still wins.

## Session Completion

This protocol applies when ending a Beads implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create beads for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Handle git/sync by active profile**:
   ```bash
   # Conservative/minimal/default: report status and proposed commands; wait for approval.
   git status

   # Team-maintainer opt-in only, unless current instructions forbid it:
   git pull --rebase
   git push
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this Beads block.
- Do not commit or push without clear authority from the active profile or the current user request.
- If a required sync or push is blocked, stop and report the exact command and error.

<!-- END BEADS INTEGRATION -->
