# 04 — Budget Math & Turn-Cost Economics (Updated 2026-09-29)

## 1. Context & Compaction Bounds
- **Token Ceiling**: 32,768 max tokens (vLLM on 4x NVIDIA L4 GPUs).
- **Sampling Allocation**: `max_output_tokens: 8192` + `thinking_budget: 3072` = 11,264 tokens reserved for generation.
- **Compaction Threshold**: 14,336 tokens (`token_threshold` in ADK `EventsCompactionConfig`).
  - Interval: 5 events.
  - Overlap: 2 events.
  - Retention: 5 events.
- **Compaction Hazard**: Once context reaches 14,336 tokens, ADK replaces earlier verbatim tool calls and file reads with loose textual summaries. The agent loses verbatim indentation and exact lines required for 3-tier `edit_file` matching.

---

## 2. Quadratic Token Expansion: Mouse-Reading vs. Batching

In an autoregressive multi-turn agent loop, input tokens re-processed at turn $t$ equal the initial prompt $C_0$ plus the cumulative history of all prior turns:
$$\text{Input Tokens}(t) = C_0 + \sum_{i=1}^{t-1} \Delta_i$$

Assuming an average observation + thought payload of $\bar{K} \approx 600$ tokens per turn:
$$\text{Total Cumulative Tokens}(T) = T \cdot C_0 + \frac{T(T-1)}{2} \bar{K}$$

### Comparison Table: 50-Turn Mouse-Reading vs. 12-Turn POSIX Batching

| Metric | Mouse-Reading Trajectory (50 turns) | Batched Anti-Mouse Trajectory (12 turns) | Delta / Savings |
|---|---|---|---|
| **Tool Calls ($T$)** | 50 (budget exhausted) | 12 (budget preserved) | **-76.0% tool calls** |
| **Turns to Compaction (14.3K)** | Turn 20 (30 turns run post-compaction) | Never (peaks at ~8.5K tokens) | **Zero compaction loss** |
| **Per-Turn Avg History ($C_t$)** | ~18,500 tokens (clamped by compaction) | ~5,200 tokens (clean, verbatim) | **-71.9% KV cache load** |
| **Total Tokens Processed** | **~1,250,000 tokens / task** | **~145,000 tokens / task** | **-88.4% token compute** |
| **API Latency (sequential)** | ~180–300s per task | ~35–60s per task | **~4.5x faster turnaround** |
| **Exact `old_string` Retained** | Paraphrased / Degraded | 100% Verbatim in Context | Eliminates `EditApplyError` |

---

## 3. Anti-Mouse Reading Economics

### The "Mouse-Reading" Defect
When models receive issues with partial context, naive exploration manifests as:
1. `read_file(path, offset=1, limit=30)`
2. `read_file(path, offset=31, limit=30)`
3. `read_file(path, offset=61, limit=30)`
... repeating 10–15 times down a single file. Each turn burns 1 tool call against the 50-call budget and injects overlapping lines into context history.

### The POSIX Multi-File & Windowing Solution
Instead of sequential reads or unmounted host scripts:
1. **Multi-File Batching (1 Tool Call)**:
   ```bash
   head -n 60 file1.py file2.py file3.py
   ```
   Inspects up to 3 candidate files in 1 tool call without paginating.
2. **Line Windowing (1 Tool Call)**:
   ```bash
   nl -ba file.py | sed -n '120,180p'
   ```
   Directly isolates the 60 lines around the stack trace or symbol definition.
3. **Zero-Cost Thought Scratchpad**:
   ```markdown
   - EXAMINED: [file:lines - summary]
   - ROOT CAUSE: [defect]
   - NEVER RE-READ: [files understood]
   ```
   Internal `<thought>` tokens are free of tool-call cost, preventing redundant re-reads across turns with zero disk footprints.

---

## 4. Run B07 Empirical Baseline

From the 33-task baseline run (`run_B07`):
- **Overall Resolution Rate**: **30.3% (10/33 resolved)** (outperforming Kaggle LB #1 at 0.15).
- **FastAPI**: 7/19 (36.8%)
- **Requests**: 3/8 (37.5%)
- **Rich**: 0/6 (0.0%)
- **Primary Failure Modes Identified**:
  1. *Tool exhaustion at 46–50 calls*: `fastapi_14986`, `fastapi_14978`, `fastapi_15030`. Subagent and mouse-reading burned 80% of budget before patch generation.
  2. *Untested boolean inversion*: `rich_4077` (fixed code but inverted boolean without running targeted pytest).
  3. *Local subprocess dependency gap*: `inline_snapshot` missing in python 3.14 subprocess sandbox on modern fastapi tasks.
