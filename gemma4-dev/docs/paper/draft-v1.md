# Autonomous Issue Resolution under a Declarative Agent Contract: Design for the Gemma 4 Developer Agent Competition

**Table of Contents**

1. [Abstract](#1-abstract)
2. [Introduction](#2-introduction)
3. [Data: Tasks and Graph Sidecars](#3-data-tasks-and-graph-sidecars)
4. [Method: Lean Monolith with Deterministic Skill Gates](#4-method-lean-monolith-with-deterministic-skill-gates)
5. [Failure Modes and Evaluation Plan](#5-failure-modes-and-evaluation-plan)
6. [Results](#6-results)
7. [Conclusion and Living-Doc Status](#7-conclusion-and-living-doc-status)

## 1. Abstract

We describe the design of an autonomous software-engineering agent for the Google Gemma 4 Developer Agent competition, a SWE-bench-style benchmark in which agents fix GitHub issues in unseen Python repositories. The competition metric is Resolution Rate: the fraction of tasks for which hermetic pytest execution returns exit code zero and produces valid JUnit XML with all FAIL_TO_PASS and PASS_TO_PASS tests passing and no failures, errors, or skips. Evaluation follows a two-container lifecycle. In Container A, the agent operates on a snapshotted repository at the task base commit and its edits are extracted as a unified git diff (`git add -N . && git diff HEAD`, or an explicit `submit_patch`). In Container B, a fresh sandbox applies the agent patch, discards any agent edits to test files, applies the reference test patch, and runs hermetic pytest to determine the binary per-task outcome. Submissions are declarative-only: compiled from `agent.yaml`, sub-agent YAML, prompts, and configs by `compile_submission`, with no executable `agent.py`. All agents share a single model, `gemma-4-31b-it-qat-w4a16-ct`, under a 32K context budget, and interact with the repository through nine sandboxed tools. This paper presents our agent architecture, tool-use policy, verification discipline, and evaluation protocol. Result numbers are TBD slots pending controlled runs.

## 2. Introduction

SWE-bench-style evaluation reduces autonomous software engineering to a falsifiable question: does the repository pass a held-out test specification after the agent's patch is applied? The Gemma 4 competition adopts this framing directly. Each task pairs a problem statement with a repository snapshot at a base commit, and success is binary per task. The aggregate, Resolution Rate in [0.0, 1.0], is computed by `score()` over hermetic pytest results with JUnit XML validation. This strict gate shapes every design decision: speculative edits, untested refactors, and test-file manipulation cannot score, because Container B resets test files before applying the reference test patch.

The two-phase lifecycle enforces this separation. Container A is the agent sandbox: snapshot extraction via `git fast-import`, editable install, generated `pytest.ini` and hermetic `conftest.py` committed into the baseline, and a tool loop against `/workspace` under offline, resource-capped execution. Container B is the verification sandbox: fresh bootstrap, resilient application of the agent patch, checkout and clean of test files, application of the task test patch, and a hermetic pytest invocation whose exit code and JUnit XML determine resolution. The agent must therefore produce minimal source-only diffs that generalize to unseen test files, and must verify before submitting, since `submit_patch` terminates the session.

The submission contract further constrains the solution space. No Python entrypoints are permitted; the entire agent is declared in YAML and resolved against closed host registries. The single-model rule fixes all reasoning to `gemma-4-31b-it-qat-w4a16-ct` with `max_output_tokens + thinking_budget` bounded by the 32K context window. The action space is nine tools: `run_command`, `submit_patch`, `get_status`, `read_file` (150 lines / 10K chars), `edit_file` (3-tier match), `write_file`, `search_similar_code`, `get_code_neighbors`, and `get_code_subgraph`. This work is therefore a study in budgeting: how to allocate limited context, tool calls, and time across localization, reproduction, editing, and verification within a declarative, single-model, nine-tool envelope.

### Contributions

- A declarative agent decomposition (`my_submission/agent.yaml`) compliant with the `compile_submission` contract and the single-model constraint, implemented as a lean monolith with deterministic skill gates.
- A tool-use policy that maps the nine sandboxed tools to localization, editing, and verification roles under the 32K context budget.
- A verify-before-submit discipline using `/tmp` reproduction scripts and targeted single-file pytest, consistent with the Container A / Container B patch-extraction lifecycle.
- An evaluation protocol reporting Resolution Rate with per-task binary outcomes and controlled ablations; all result tables are TBD slots.

## 3. Data: Tasks and Graph Sidecars

### 3.1 Task split

The benchmark comprises 129 tasks drawn from four Python repositories (`tasks.jsonl`; method in `docs/02-dataset.md`): fastapi 67, rich 48, requests 13, httpx 1. Full repository ids are `fastapi/fastapi`, `Textualize/rich`, `psf/requests`, and `encode/httpx`. The distribution is sharply skewed: fastapi plus rich account for 115 of 129 tasks (approximately 89%), so any retrieval or prompting strategy stands or falls on those two repositories' conventions, with requests and httpx as a long tail.

### 3.2 Row schema

Each row carries eight keys: `instance_id, repo, base_commit, patch, test_patch, problem_statement, hints_text, created_at` (`docs/02-dataset.md`). Roles are fixed by the harness: `problem_statement` is the issue text that seeds the agent prompt; `base_commit` (40-hex SHA) anchors the snapshot; `patch` is the held-out gold fix, never shown to the agent; `test_patch` is applied only in the hermetic evaluation container before pytest. An example row (`fastapi_15661`) shows the scale: an approximately 1K-character problem statement against an approximately 7K-character gold patch and an approximately 7.8K-character test patch.

Notably, `hints_text` is empty for 0 of 129 non-empty rows — every row is `""` (`docs/02-dataset.md`; corroborated on a 6-task sample in `docs/research/01-task-autopsy.md`). Any prompt section conditioned on hints never fires and should not be relied upon.

### 3.3 Graphs and embeddings

Sidecar coverage is near-complete but not total: `graphs/` holds 127 `.json` files and `embeddings/` holds 127 `.npz` files, so 2 of 129 tasks lack graph data (`docs/02-dataset.md`). The harness appends its Code-Intelligence prompt section only when both files exist and exceed 100 bytes. Direct inspection of two graphs (`docs/research/02-graph-truth.md`) confirms embeddings are 256-dimensional float32, one vector per graph node (for example, 4,287 vectors for 4,287 nodes).

The node schema is minimal — `{name, text, id}` only, with no file-path field (`docs/research/02-graph-truth.md`). Ids are dotted symbols such as `tests.test_bar.test_render` or `path_operation_advanced_configuration.tutorial004_py310.Item`, so mapping a retrieved symbol back to a file requires a follow-up read, not the graph alone.

### 3.4 Noise profile and takeaway

Signal-to-noise differs sharply by repository. The fastapi graph (`fastapi_016ab76`, 4,287 nodes) contains only 566 library nodes (13.2%) against 3,721 noise nodes (86.8%) — roughly 7:1 noise, dominated by `tutorialXXX` symbols. The rich graph (`rich_01b85ac11`, 1,925 nodes) inverts this: 1,105 library nodes (approximately 57%) versus 820 noise nodes from `tests.*` and examples (`docs/research/02-graph-truth.md`).

The implication is twofold. First, strategy weight belongs on fastapi plus rich (89% of tasks). Second, AST and graph retrieval is viable only as a candidate generator, not a primary locator: unfiltered similarity search on fastapi returns tutorial symbols, so the searcher must filter (`tutorial|tests\.|examples\.|benchmarks\.`), issue symbol names rather than sentences, and confirm via `read_file` — which remains a mandatory fallback in the main agent.

## 4. Method: Lean Monolith with Deterministic Skill Gates

Our agent (`my_submission/agent.yaml`) is a deliberate lean monolith: a single root agent holding all 9 harness tools (`run_command`, `read_file`, `edit_file`, `write_file`, `get_status`, `submit_patch`, `get_code_neighbors`, `search_similar_code`, `get_code_subgraph`), zero subagents (`my_submission/sub_agents/` is empty; no `agent_tool` reference), one model (`gemma-4-31b-it-qat-w4a16-ct`), and two deterministic stdlib skills wired in `agent.yaml` (`skills/patch-gatekeeper`, `skills/code-explorer`). All behavior lives in one prompt (`my_submission/prompts/system.md`, 27 lines) plus two auditable scripts. This section justifies the monolith against the Map-Reduce alternative, then specifies each mechanism.

### 4.1 Monolith thesis: why not Map-Reduce

The prior v1 theory (`docs/05-theory-oneup.md`, `docs/06-prompt-contracts.md`) proposed an Executor/Searcher split: the root delegates exploration behind `agent_tool skip_summarization:true`, and the searcher returns a strict 5-field schema (file, lines, root cause, minimal change, confidence) so raw reads never pollute root history past the 14336-token compaction threshold. That design is sound for the 50-call / 30-minute harness default, where one delegation hop pays for itself by the third investigation.

We reject it for the actual evaluation envelope (`my_submission/eval_config.yaml`: `timeout_seconds: 60`, `max_tool_calls: 40`, `max_time_minutes: 4.5`, `max_turns: 100`). Under 4.5 minutes, every delegation round-trip costs a full model turn plus schema-repair risk: a malformed or low-confidence schema forces a re-ask, burning 2–4 of 40 calls before any edit exists. The monolith instead keeps the full loop in one context and controls bloat procedurally: grep-first localization (`rg -n -F` literal, capped `head -80`), confirm-only narrow reads, no file or tree dumps, and graph tools invoked only with a known symbol name. Compaction pressure is managed by dense one-line observations rather than subagent hiding — fewer moving parts, one auditable prompt, no delegation tax.

### 4.2 Skill 1: patch-gatekeeper (submit blocker)

`my_submission/skills/patch-gatekeeper/check.py` (invoked as `python3 skills/patch-gatekeeper/check.py`, contract in `my_submission/skills/patch-gatekeeper/SKILL.md`) runs inside the mandatory verify gate in `system.md` before `submit_patch`. It has two tiers. The FAIL tier (exit 1, blocks submit) catches the five hollow-patch signatures observed in pilot rollouts: (F1) truncation markers (`... existing code ...`, `[truncated]`, bare `...`) from oversized `edit_file` payloads; (F2) bare `except:`; (F3) swallowed `except Exception` with `pass`/`...` bodies; (F4) hollow except-bodies returning dummy values (`None`/`''`/`0`/`[]`/`{}`) on changed lines; (F5) `py_compile`/`SyntaxError` failure. The WARN tier (exit 0, advisory) flags complexity greater than 5, nesting greater than 3, `typing.Any`, pydantic models without `extra='forbid'`, and `# type: ignore`. The procedure is to fix all FAILs and re-run to `PASS`. Implementation is stdlib `ast` only, with no gateway calls.

### 4.3 Skill 2: code-explorer (grep-first fallback ranker)

`my_submission/skills/code-explorer/explorer.py` (contract in `my_submission/skills/code-explorer/SKILL.md`) is a deterministic stdlib-only bundle providing TF-IDF file ranking plus AST skeleton extraction, used only when `rg` misses. `explorer.py [--top-k N] query...` walks at most 200 `.py` files (hidden directories skipped) and prints `relative/path score` lines, top-K only (default 10); `explorer.py --skeleton <file>` prints `path:line: class|def|async def ...` signatures with no bodies, capped at 80 lines via the `ast` module. The doctrine is grep-first: the prompt mandates starting with a bounded `rg` literal or reading the named file directly, and reaching for the explorer or graph tools only on miss. Repository graphs carry 43–87% tutorial and test noise, so tutorial and test paths are never fix locations. The skill never edits; the caller owns all writes. Both skills comply with the harness skill spec (gotcha-skill-spec-kebab-20260929): each `SKILL.md` carries YAML frontmatter with required `name` and `description` fields, and `name` must be kebab-case identical to its directory name (`patch-gatekeeper`, `code-explorer`) — snake_case names load only behind an experimental flag, so any offline gate that merely checks file existence without parsing frontmatter will pass a tree the real compiler rejects.

### 4.4 Anti-Mouse Reading & Quadratic Token Expansion Economics

A critical discovery in multi-turn SWE-bench trajectories is the **Quadratic Token Expansion Problem**. In an autoregressive agent loop, the input context presented to the model at turn $t$ is strictly cumulative:
$$\text{Input Tokens}(t) = C_0 + \sum_{i=1}^{t-1} (\text{ToolCall}_i + \text{Observation}_i)$$

Where $C_0$ is the initial system prompt and problem description. Assuming an average turn observation of $\bar{K} \approx 600$ tokens, the total cumulative tokens processed by the inference server across a $T$-turn task scales quadratically:
$$\text{Total Tokens Processed}(T) = T \cdot C_0 + \frac{T(T-1)}{2} \bar{K}$$

When an agent falls into naive "mouse-reading" — sequentially calling `read_file` in 20–30 line increments from line 1 of a file — it burns 30–50 tool calls purely on exploration. At $T=50$:
1. **Token Bloat**: The model re-evaluates upwards of **1.25M to 1.5M cumulative tokens** per task, causing massive latency (3–5 minutes per task) and high gateway load.
2. **The 14,336 Compaction Cliff**: At roughly Turn 20, context crosses Google ADK's `token_threshold = 14336`, triggering `EventsCompactionConfig`. Past events (including exact lines and indentation read earlier) are rewritten as lossy textual summaries. When the agent later attempts an `edit_file` call at Turn 45, it fails with `EditApplyError` because the verbatim `old_string` has been summarized away.

To eliminate mouse-reading and compress the agent's turn cost by over 80%, we enforce three strict operational rules:
1. **Native POSIX Multi-File Batching (1 Tool Call)**: Rather than paginating with sequential `read_file` calls, the agent inspects multiple candidate files in a single tool call via `run_command`:
   ```bash
   head -n 60 file1.py file2.py file3.py
   ```
2. **Direct Line Windowing (1 Tool Call)**: Rather than reading from line 1, the agent pinpoints line numbers via `grep -n` and inspects the exact window around the defect in a single call:
   ```bash
   nl -ba file.py | sed -n '120,180p'
   ```
3. **Zero-Cost In-Turn Thought Scratchpad**: Before emitting tool calls, the model maintains a structured 3-bullet scratchpad inside its `<thought>` block:
   ```markdown
   - EXAMINED: [<file>:<lines> - summary of logic]
   - ROOT CAUSE: [exact defect or missing logic]
   - NEVER RE-READ: [files already understood; do NOT call read_file on these again]
   ```
   Because thinking tokens cost 0 tool calls and 0 disk operations, this preserves working memory across turns and compaction without mutating the repository.

### 4.5 Native POSIX Tools vs Sandbox File Injection

A vital architectural boundary is the separation between the host submission directory and the sandbox `/workspace`. Under the competition evaluation lifecycle, `Container A` contains only the extracted repository snapshot. The submission directory is not mounted or copied into `/workspace` (doing so would pollute `git add -N . && git diff HEAD` with non-repo artifacts and cause `Container B` patch application to fail). Furthermore, the harness strictly forbids external symlinks (`PathTraversalError`).

Consequently, agent exploration cannot rely on custom host-side helper scripts inside `/workspace`. By standardizing all multi-file batching and windowing on ubiquitous POSIX core utilities (`head`, `sed`, `nl`, `grep`), the agent achieves 1-call batching natively with zero external dependencies, zero file pollution, and identical behavior across local and Kaggle 4x L4 evaluation environments.

### 4.6 Stdout compression doctrine

Every tool observation is a compaction liability, so `system.md` enforces dense one-liners: short unique `edit_file` matches (3–8 lines), no whole-file re-emission, incremental multi-file edits to avoid `<|tool_call|>` truncation, and a 5K output cap on all `run_command` output. Diff dumps and neighbor or subgraph JSON are never pasted into reasoning. `get_status` (free) is the budget oracle near the limit.

### 4.5 Verify protocol: /tmp repro, one target, submit last

`REPRODUCE` and `VERIFY` in `system.md` define a fixed three-step protocol. First, reproduce cheaply: run the existing target test or a `/tmp` scratch reproducer before editing (scratch never lands in `/workspace`, since `git add -N . && git diff HEAD` ships everything there, and test edits are discarded in Container B). Second, after editing, run one bounded command combining `python -m py_compile`, `git diff --check`, the gatekeeper script, and a single-file scoped pytest; full suites are forbidden. Third, `submit_patch()` is always the final tool action (free, loop-terminating, requires `patch_size > 0`); if time runs low, submit the best nonempty source diff, and never assert a test passed that was not run.

### 4.6 Sampling, budgets, and wiring

Sampling (`my_submission/configs/sampling.yaml`) is `temperature: 0.15`, `top_p: 0.95`, `max_output_tokens: 8192`, `thinking_budget: 3072` with `include_thoughts: false` — low variance for patch precision, short reasoning to fit the 32K shared ceiling. Evaluation (`my_submission/eval_config.yaml`) is 60-second tool timeout, 40 tool calls, 4.5 minutes, 100 turns: the regime Section 4.1 is tuned for. Wiring is minimal and mirrors the sample submission filenames: `agent.yaml` declares the model, `!include prompts/system.md`, the 9 tools, the two `skills/` entries, and `!include configs/sampling.yaml`; no LoRA adapters, no sub-agent YAML.

## 5. Failure Modes and Evaluation Plan

### 5.1 Five baseline killers

Cause, harness mechanism, and v1 mitigation for each killer. Full theory: `docs/04-failure-modes.md`; procedures: `docs/07-verify-protocol.md`.

| # | Killer | Cause | Harness mechanism | Mitigation |
|---|--------|-------|-------------------|------------|
| 1 | Compaction overflow (14336) | Long trajectories (full-file re-reads, verbose reasoning, raw graph dumps) pass the compaction point; summarized history loses exact `old_string` text. | `EventsCompactionConfig` (interval 5, overlap 2, `token_threshold 14336`, retention 5) summarizes old events well before 32K `max_model_len`. Post-compaction contents are paraphrases, not byte-exact quotes. | Main keeps `read_file` for short slices; graph tools scoped to known symbols; dense one-line observations; re-read target block before each edit. |
| 2 | Truncation: unclosed `tool_call`, 3 nudges | One huge `edit_file`/`write_file` payload plus long thought exceeds `max_output_tokens`; response cut mid-tag, no tool runs that turn. | Unclosed `<|tool_call|>` triggers a harness nudge (emit tool call immediately, split edits); repeats burn `max_nudges = 3` and tool budget. | Cap `max_output_tokens` 8192 / `thinking_budget` 3072 (sum well below 32K); brief reasoning per call; one small `edit_file` per turn. |
| 3 | Workspace pollution (`git add -N` diff HEAD) | Scratch repro scripts inside the repo get swept into the submitted patch. | `submit_patch` runs `git add -N . && git diff HEAD` over all `/workspace` — every untracked file included except `__pycache__`/`*.pyc`/`.pytest_cache`. | Scratch repro in `/tmp`, never `/workspace`. Check `get_status` before submitting. |
| 4 | Test-discard (`checkout HEAD`) | Agent edits tests or configs instead of library code. | Phase 2 resets `task.test_patch` files plus `test_*.py` / `tests/` / `conftest.py` / `pytest.ini` / `pyproject.toml` / hooks via `git checkout HEAD` plus `git clean -f`. Test edits vanish, so `resolved = False`. | Fix only library source; tests are read-only oracles. |
| 5 | Bare-pytest 300 s timeout | Full-suite `pytest` exceeds the 300 s `run_command` kill or hits pre-existing failures, wasting budget and signal. | Kill at `min(300 s, remaining_time)`; output cut at 5,000 chars. Phase 2 runs only targeted `<pytest_targets>` (`-q -p no:anyio`), requiring `exit_code == 0` and JUnit `passed > 0, failures = errors = 0`. | Repro in `/tmp`, then one targeted `pytest <file>::<test>` (single file). Ignore unrelated red. |

### 5.2 Local eval recipe

1–2 fastapi tasks at harness defaults (50 calls / 30 min; sample `eval_config.yaml` 10/1 is a smoke stub only):

```bash
swegemma eval --task-id <fastapi-id> --max-tool-calls 50 --max-time-minutes 30 \
  --tasks tasks.jsonl --snapshots-dir snapshots \
  --submission-dir <approved-submission-dir> --results-dir results/run_XX
```

Keep `--sandbox docker`; use `--task-id` for single-task debugging. Never ship sample values.

### 5.3 Artifacts (`--results-dir`)

`summary.json` (resolution rate, counts, per-repo split); `task_results.jsonl` (per-task metrics, exits, errors); `patches/<id>.patch` (Container A diff); `test_outputs/<id>.log` (Container B pytest); `traces/trace_<id>.json` (ATIF steps, calls, tokens); `logs/<id>.log` (Phase 1 transcript).

### 5.4 What to measure

Resolution: `exit_code == 0` plus JUnit `passed > 0, failures = errors = 0`. Efficiency: calls used versus 50, wall-clock versus 30 min. Context health: compaction events (14336), `budget_warning` count, `<|tool_call|>` truncations. Patch quality: non-empty, source-only, passes 4-pass `git apply`. Pass criteria: 1–2 fastapi tasks resolve; no bare-pytest timeouts; no `/workspace` pollution.

### 5.5 Micro-bench plan (graphs/127)

127 precomputed graphs (`graphs/*.json`) enable a cheap offline gate before any 50-call run: sample tasks across repositories; measure (a) affected-function identification (true buggy function in top candidates), (b) dataflow-trace precision (returned callers and callees on the real defect path versus distractors), (c) reuse — feed searcher schema output into the edit step and score first-`edit_file` clean-apply rate (M1 schema validity, M2 exact `old_string` match, M3 FAIL_TO_PASS flip). This isolates retrieval quality from agentic variance.

## 6. Results

### 6.1 Baseline Evaluation: Run B07 (33 Tasks)

In benchmark run `run_B07`, the agent was evaluated across 33 sequential tasks drawn from three representative benchmark repositories (`fastapi/fastapi`, `psf/requests`, and `Textualize/rich`) using LiteRouter endpoint `stealth/space-bunny-alpha` under standard harness budgets (50 tool calls, 30 minutes per task).

**Overall Outcome**:
- **Resolved**: **10 / 33 tasks** (**30.3% resolution rate**), substantially outperforming the Kaggle public leaderboard baseline (0.12–0.13) and rank 1 score (0.15).
- **By Repository**:
  - `fastapi/fastapi`: **7 / 19 resolved (36.8%)** (e.g. `fastapi_15588`, `fastapi_15589`, `fastapi_14873`, `fastapi_14786`, `fastapi_14492`, `fastapi_14463`).
  - `psf/requests`: **3 / 8 resolved (37.5%)** (e.g. `requests_7427`, `requests_7315`, `requests_7309`).
  - `Textualize/rich`: **0 / 6 resolved (0.0%)**.

**Autopsy of Unresolved Tasks & Key Failure Modes**:
1. **Tool Budget Exhaustion (46–50 calls)**: On tasks like `fastapi_14986`, `fastapi_14978`, and `fastapi_15030`, the agent burned 40+ tool calls through sequential mouse-reading (paginating 20–30 lines per turn) and sub-agent looping. Control was returned to the root agent with fewer than 5 calls remaining, forcing an incomplete patch or budget cutoff.
2. **Untested Boolean Inversion**: On `rich_4077`, the agent correctly identified the defect in `rich/file_proxy.py` and modified the source, but inverted the return boolean (`return self.__console.is_terminal` instead of proxying the underlying file) without running the existing targeted test, failing in Container B with a 1-line assertion error.
3. **Subprocess Sandbox Dependency Absence**: On modern FastAPI tasks (`fastapi_14964`, `fastapi_15023`), the test suite failed during test collection because `inline_snapshot` was not present in the local Python 3.14 subprocess sandbox venv.

### 6.2 Target Pilot: Run B08 (Anti-Mouse & Batching Verification)

Run `run_B08` evaluates the impact of the newly introduced Anti-Mouse reading rule, zero-cost scratchpad, and POSIX multi-file batching on the failed tasks from `run_B07` (`rich_4077`, `fastapi_15023`, `fastapi_14986`, `rich_4076`, `requests_7328`).

### 6.3 Planned results table

| Run | Setup | Tasks | Resolved (=) | Calls used | Notes |
|---|---|---|---|---|---|
| M1-pilot | 2-task GPU pilot | 2 (fastapi) | TBD | TBD | Smoke test: harness runs, patch submits, artifacts parse |
| B-local | 2-task local inkling proxy | 2 (fastapi) | TBD | TBD | Prompt-logic check ONLY, not 31B behavior |
| C-Vertex | 31B (`gemma-4-31b-it-qat-w4a16-ct`) | TBD | TBD | TBD | First real-behavior number; gated on quota |
| M3-sweep | 10-task sweep | 10 | TBD | TBD | Pre-registered seed/config; CIs, not point claims |

`Resolved (=)` means exact-match resolved count as reported by the harness `summary.json`, not author re-interpretation. `Calls used` means mean tool calls per task plus max, read from traces.

### 6.2 Ablation plan (one variable at a time)

Three conditions, same tasks, same sampling (`0.2 / 16384 / 4096`):

1. Monolith baseline — single agent, no searcher delegation.
2. Sequential-output_key variant — searcher returns strict schema via `output_key` relay instead of inline summary text.
3. No-skills control — searcher without graph tools (`search_similar_code`, `get_code_neighbors`, `get_code_subgraph`).

Each condition runs on identical task sets; only one factor changes per comparison. With small-N pilots (1–2 tasks), one task is approximately 1.7 points on a 60-task denominator scale — single-task deltas are noise, so we report raw counts plus task IDs, never percentages alone. The M3 10-task sweep is the minimum N at which ablation deltas become worth discussing, and even there the claim is directional only.

### 6.3 Honest limits

- T4 cannot fit 31B-QAT. Any local GPU result is a harness-plumbing check, not evidence about 31B behavior. Do not compare M1/B-local numbers against C-Vertex as if they were the same model.
- Free-proxy runs test prompt logic only. Inkling and small-model trajectories validate that YAML compiles, delegation fires, and the schema round-trips — they say nothing about 31B resolution rate.
- LiteRouter 429 quota discipline. Free-tier rate limits forced small-N pilots; retries and backoff are documented per run. A 429-heavy run is reported as inconclusive, not as zero.
- Sample `eval_config` 10/1 stub versus real 50/30. The sample config (10 calls / 1 min) is a compile-and-smoke stub. All claimed numbers must use the real budget (50 calls / 30 min); stub numbers are labeled as such and never mixed into the main table.

### 6.4 Deferred future (not claimed here)

- LoRA sweet-spot filter (single-file, ≤ 20-line patches): a post-hoc patch-shape analysis, deferred until at least 10 real trajectories exist. No adapter trained, no claim made. TBD.
- SequentialAgent `output_key` relay as measured A–B only: the relay mechanism is described in Section 5; its effect size is TBD until the ablation above runs. No efficiency claim in advance.

### 6.5 Notebook appendix outline

1. `tasks.jsonl` stats cell — N per repo, difficulty proxy, seed list. TBD.
2. Graph-noise cell — dead-end / missing-edge rate per task sample. TBD.
3. Compile-gate demo cell — `compile_submission` pass/fail on the submitted YAML tree (offline gate now uses the wheelhouse-venv real loader, per B01 lesson). TBD.
4. Eval-artifact parse cell — load `summary.json` plus `traces/`, reproduce every table cell from Section 6 mechanically. TBD.

### 6.6 Narrow claim statement

This paper claims only that filtered-subgraph delegation plus compile-gate discipline keeps a 50-call trajectory under the compaction cliff on the studied harness tasks. It does not claim general SWE-bench competence, cross-language transfer, or model-independent gains. Any broader reading is explicitly disclaimed until the TBD cells above are filled with audited artifacts.

## 7. Conclusion and Living-Doc Status

The design presented here fits the competition envelope: a declarative, single-model, nine-tool agent that prioritizes minimal source-only diffs, grep-first localization with deterministic fallbacks, a two-tier patch gate, and a verify-before-submit protocol that respects the Container A / Container B boundary. The dataset is skewed toward fastapi and rich, graph sidecars are noisy and incomplete, and the evaluation gate is binary per task — all of which motivate conservative budgeting of context, calls, and time.

This is a living document. Architecture details, prompts, budgets, and result numbers remain TBD slots to be filled as controlled local evaluations complete. Pending runs: M1-pilot (TBD), B-local (TBD), C-Vertex (TBD), M3-sweep (TBD). No resolution-rate claim is made until `summary.json`, `patches/`, and `traces/` artifacts exist and table cells are mechanically reproduced.

---

Living doc v1 — 3435 words — B01 0/2 negative result recorded, B02/M1/C slots TBD — 2026-09-29
