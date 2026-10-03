# 05 — Thesis: Context-Preserving Map-Reduce

> One-liner: beat compaction not by raising the context ceiling, but by
> keeping exploration tokens out of the root history.

## 1. Problem: compaction kills long trajectories

- Context 32K shared by `max_output_tokens + thinking_budget` (sample: 16384/4096, temp 0.2).
- Harness auto-compaction: `token_threshold` 14336, `compaction_interval` 5,
  `overlap_size` 2, `event_retention_size` 5 (`HARNESS_README.md` §7.2).
- Once ~14K tokens are hit, only the last 5 events survive in full; older
  `read_file` (150 lines / 10K chars each) and graph dumps get summarized away.
- Failure mode: agent re-reads files it already saw, re-searches symbols,
  drifts from the plan, burns 50-call / 30-min budget.

## 2. Thesis: split Executor from Investigator

**Main = Executor.** Reads issue, plans, edits, verifies, submits.
Keeps `read_file` for surgical confirms only. Holds NO raw graph tools.

**Searcher = Investigator.** Owns all expensive exploration
(`search_similar_code`, `get_code_neighbors`, `get_code_subgraph` + `read_file`)
behind `agent_tool skip_summarization:true`. Returns ONLY a condensed schema
(see doc 06). Intermediate reads never enter root history (gotcha #4).

## 3. Text diagram

```
Issue → MAIN (Executor, root context)
  │ 1. delegate: ask_search_subagent(keywords, symbols)
  ▼
  SEARCHER (agent_tool, skip_summarization:true, isolated history)
  │ graph + read_file fan-out → condense → strict schema back
  ▼
MAIN receives ~15 lines (file, lines, cause, change, confidence)
  │ 2. read_file confirm (1 call) → 3. edit_file → 4. /tmp repro
  ▼ 5. targeted single-file pytest → 6. submit_patch (free, last)
```

## 4. Why it beats compaction

- Isolation, not summarization: searcher's N reads collapse to one short
  return value in root history. Root stays under `token_threshold` longer.
- Retention-friendly: with `event_retention_size` 5, root's last-5 events are
  plan → schema → edit → test → submit, not 5× raw file dumps.
- Matches blessed pattern: harness §10 gotcha #4 explicitly recommends
  `AgentTool skip_summarization:true` for exactly this.

## 5. Trade-offs vs baseline

| Axis | Baseline (`swe_baseline_agent`) | v1 one-up (this thesis) |
|---|---|---|
| Root tools | All 9 tools + sub-agent ref | Executor: `run_command, read_file, edit_file, write_file, get_status, submit_patch` + `agent_tool` only |
| Graph tools | Duplicated in root AND analyzer | Searcher-only (single owner) |
| Context risk | Every search pollutes root history | Exploration isolated; root sees schema only |
| Failure risk | Wandering, re-reads after compaction | Extra delegation hop; depends on schema discipline |
| Cost | No delegation overhead | +1 tool call per investigation (pays for itself by call 3+) |

## 6. Locked v1 scope (no LoRA, no new filenames)

- Mirror `sample_submission` filenames; keep `configs/sampling.yaml` (0.2/16384/4096).
- No LoRA adapters v1. Single model `gemma-4-31b-it-qat-w4a16-ct` everywhere.
- Delegation rule: broad search ⇒ searcher first; `read_file` in root is confirm-only.
- Verify: `/tmp` repro + targeted single-file pytest, `submit_patch` last.
- Local test: `--max-tool-calls 50 --max-time-minutes 30` on 1–2 fastapi tasks.
