# 03 — Hard Constraints (Theory)

Source: HARNESS_README §§2–7 + `sample_submission/`. All values are harness ground truth, not tuning advice.

## 1. Declarative-Only Submission

| Rule | Mechanism |
|---|---|
| No `agent.py` / no Python entrypoints | `compile_submission` sandboxed YAML compiler replaces ADK `from_config()`; resolves only against closed `ToolRegistry`, `ModelRegistry`, `SkillRegistry`, `CallbackRegistry` |
| Submission = YAML + MD + adapters | `agent.yaml` (root, exactly one) + `sub_agents/*.yaml` + `prompts/*.md` + `configs/*.yaml` + optional `adapters/` + `skills/` |
| Archive ceiling | Unpacked total `< 3 GiB` (3,221,225,472 bytes) including `adapters/` |
| Structural ceilings | 10K files, 1K YAML files, 50 MiB per YAML / cumulative `!include` expansion, 500 agents, 50 sub-agent depth, 500 loop iterations |

## 2. Single-Model Rule

| Rule | Mechanism |
|---|---|
| One base model for ALL agents | `validate_single_declared_model` walks root + every `sub_agents[].config_path` + every `tools[].agent_tool.config_path`; strips provider prefixes; requires `len(models) == 1` |
| Competition model | `gemma-4-31b-it-qat-w4a16-ct` only (`ALLOWED_MODEL_NAMES`); any other or second model → `ParticipantVisibleError` |
| LoRA exception | Different agents MAY use different adapters (`adapter: main_lora` vs `tool_lora`); adapters route via `resolve_swegemma_adapter`, served with `enable_lora=True, max_loras=8, max_lora_rank=128` |

## 3. The 9 Tools (exact signatures + limits)

| # | Tool | Signature | Budget? | Key limit |
|---|---|---|---|---|
| 1 | `run_command` | `(command: str)` | Yes | 300 s timeout (min of config vs remaining time); stdout/stderr truncated 5,000 chars; `TimeoutExceeded` does not end session |
| 2 | `submit_patch` | `()` | **Free** | `git add -N .` + `git diff HEAD`; sets `patch_submitted=True`; exits loop at turn end |
| 3 | `get_status` | `()` | **Free** | Returns tool_calls_used/remaining, patch status, time remaining; callable even at budget exhaustion |
| 4 | `read_file` | `(filepath, start_line?, end_line?)` | Yes | 150 lines AND 10K chars dual cap; 1-indexed inclusive slicing; `..` traversal → `ValidationError` |
| 5 | `edit_file` | `(filepath, old_string, new_string, allow_multiple=False)` | Yes | 3-tier match: exact → flexible (whitespace strip + re-indent) → regex (delimiter-tokenized `\s*`); uniqueness enforced unless `allow_multiple`; empty file/empty `old_string` → `FileEditError` |
| 6 | `write_file` | `(filepath, content)` | Yes | Create-or-overwrite + `mkdir -p`; use for new files only |
| 7 | `get_code_neighbors` | `(node, edge_type?, max_neighbors=50)` | Yes | 4-tier symbol resolution (exact → suffix → case-insensitive → substring); optional `CALLS`/`DEFINED_IN`/`IMPORTS` filter |
| 8 | `search_similar_code` | `(query, k=10)` | Yes | Offline — pass symbol names (`HTTPConnection`), NOT natural-language sentences; cosine over precomputed `.npz` |
| 9 | `get_code_subgraph` | `(nodes: list[str])` | Yes | Induced subgraph (nodes + interconnecting edges) for listed symbols |

Budget nudge: when `tool_calls >= 20` and `remaining <= 10`, every response appends `budget_warning`.

## 4. `!include` Rules

- `.md`/`.txt` → raw UTF-8 string (for `instruction`); `.yaml`/`.yml` → recursive parse, max depth **10** with cycle detection.
- Absolute paths, null bytes, `..` components, symlinks escaping submission root → `PathTraversalError`.
- Sample pattern: root `instruction: !include prompts/system.md`, `generate_content_config: !include configs/sampling.yaml`; sub-agent uses `../prompts/analyzer.md` (relative, no root escape).

## 5. 4×L4 32K Ceiling

- Hardware: 4× L4 24 GB, `tensor_parallel_size=4`, `gpu_memory_utilization=0.80`, vLLM `max_model_len=32768`.
- `max_output_tokens`: 1–32768 (sample: 16384). `thinking_budget`: 0–32768 (sample: 4096 + `include_thoughts: true`).
- Rule: `max_output_tokens` + `thinking_budget` must fit 32K combined prompt+reasoning+output; exceeding → truncation nudges (§5.3).
- Sampling otherwise unrestricted: `temperature ≥ 0`, `0 ≤ top_p ≤ 1`, `top_k ≥ 1`, penalties/seed/stops free. Banned inside `generate_content_config`: `tools`, `system_instruction`, `http_options`, `safety_settings`, `response_schema`.

## 6. Compaction (already in harness)

- `EventsCompactionConfig`: interval 5, overlap 2, **`token_threshold 14336`**, retention 5 — fires long before 32K.
- `ContextCacheConfig`: min 2,048 tokens, TTL 1,800 s, intervals 10 (prefix caching).
- `ModelRetryPlugin`: 5 retries, 2 s / 2× / 60 s cap / ±20 % jitter on 429/5xx/connection errors.
- Design implication: keep per-turn output small; delegate with `agent_tool skip_summarization: true` so sub-agent history does not flood main context.
