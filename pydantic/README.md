# Pydantic AI 2.0 & pydantic_graph SFT Trajectory Translation Pipeline

Autonomous pipeline converting raw Source B trajectories (`data/source_b/swe_zero` and `swe_smith`) into verified Gemma 4 prefix-delta decision windows (`models/gemma-4-31b-it-qat-w4a16-ct`) using the production 153-line prompt (`submissions/track1_live/prompts/main.md`).

---

## 1. Architecture Overview & Data Flow

```
Raw Candidate Trajectory (pydantic/gold/raw_candidates_1500.jsonl)
    │
    ▼
[Node 1: IngestRawTaskNode]
    │ Filters out 129 eval tasks in tasks.jsonl (0% leakage)
    │ Validates single-file Python patch scope & target .py filepath
    ▼
[Node 2: RunPydanticAgentNode]
    │ Pydantic AI 2.0 translation agent (`build_translator_agent`)
    │ Multi-turn diagnostic feedback loop (max 3 pivots with message_history)
    │ Formats raw actions into 5 declarative tools + 5 competition skills
    │ Self-corrects via `@agent.output_validator` ModelRetry + JSON recovery
    ▼
[Node 3: ReconcileObservationsNode]
    │ Pairs translated actions with real observations from raw trajectory
    │ Replaces synthetic bash/editor returns with skill stdout / file contents
    ▼
[Node 4: RenderGemma4JinjaNode]
    │ Renders official Gemma 4 `chat_template.jinja` multi-turn turns
    │ Validates prefix-delta token ID equality (`full_ids[:len(prefix_ids)] == prefix_ids`)
    │ Verifies completion starts with `<|tool_call>call:` and zero thought tokens
    │ Enforces sequence length ceiling (<= 3072 tokens)
    ▼
[Node 5: PersistTaskArtifactsNode / PersistRejectionNode]
    │ Saves verified SFT windows atomically with os.fsync to `pydantic/output/`
    │ Updates `pydantic/output/checkpoint_state.json`
```

---

## 2. Key Scaffolding Patterns (Integrated from `pydantic/sample/`)

1. **Multi-Turn Pivot Feedback Loop:**
   When an LLM generates a trajectory that violates domain invariants (e.g., editing the wrong file, missing `submit_patch`, consecutive duplicate actions), `RunPydanticAgentNode` catches the diagnostic errors, builds a targeted pivot directive (`build_pivot_prompt`), and re-invokes the agent passing `message_history` with the specific diagnostic errors.
2. **Robust JSON & Markdown Stripping:**
   `convert_raw_llm_text_to_trajectory` strips `<think>...</think>` tags and markdown code fences (````json ... ````) and extracts balanced JSON blocks as a fallback if provider structured output wrapper fails.
3. **Atomic File I/O (`os.fsync`):**
   All file writes (`save_atomically`, `append_jsonl_fsync`) flush to disk and call `os.fsync(f.fileno())` to guarantee corruption-proof state even across sudden process kills.
4. **Tool Arguments Dictionary Serialization:**
   In Gemma 4's official `chat_template.jinja:258`, `tool_calls[].function.arguments` strictly requires a Python `dict` mapping, not a serialized JSON string. `ReconcileObservationsNode` passes dictionary arguments directly.

---

## 3. Strict Qualification Filters Enforced on Gold Set

The candidate dataset at `pydantic/gold/raw_candidates_1500.jsonl` contains **1,500 qualified tasks** conforming to:
1. **0% Benchmark Contamination**: Zero overlap with the 129 instance IDs in `tasks.jsonl`.
2. **Strict Single-File Python Patch**: Gold patch modifies exactly 1 `.py` file (no multi-file patches, no test-only patches).
3. **Single Target File Scoping**: The edit action must strictly target the qualified Python file identified in the patch.
4. **5-Skill + 5-Tool Contract**: No raw bash or OpenHands commands; mapped to `fast-grep`, `code-map`, `code-oracle`, `repro-check`, `test-gate`, `read_file`, `edit_file`, `write_file`, `get_status`, and `submit_patch`.

---

## 4. Telemetry & Observability

All execution spans and network traffic are logged in real-time to JSONL:

- **OpenTelemetry Spans**:
  Written to `pydantic/logs/logfire_spans.jsonl` via `JsonlFileSpanExporter` using `logfire`.
- **Raw HTTP Wire Telemetry**:
  Logged to `pydantic/logs/http_raw.jsonl` via httpx event hooks capturing exact request payloads, response codes, and wire timings.

---

## 5. Verification & Unit Tests

Deterministic test suite verifying schema validation, forbidden extra fields, structural trajectory rules, `ModelRetry` self-correction, Gemma 4 Jinja prefix-delta tokenization, and multi-turn diagnostic pivots:

```bash
.venv/bin/pytest pydantic/test_translate_sft_dag.py -v
```
*(5/5 passing in ~11s)*:
- `test_action_models_validation_and_forbid_extra`: Strict Pydantic V2 schema, `extra="forbid"`, skill-to-script pairing.
- `test_translated_trajectory_structural_rules`: Trajectory invariants, discovery/edit/verification/submit_patch order, anti-thrashing.
- `test_agent_model_retry_self_correction`: Pydantic AI `@agent.output_validator` with `ModelRetry`.
- `test_gemma4_jinja_rendering_and_invariants`: Gemma 4 `chat_template.jinja` prefix-delta loss masking, zero-thought invariant.
- `test_agent_multi_turn_pivot_loop`: Multi-turn diagnostic pivot loop with `message_history` self-correction.

---

## 6. Live Smoke Test Results (1 Task)

Executed smoke test on LiteRouter (`thinkingmachines/inkling:free`):
```bash
.venv/bin/python3 pydantic/translate_sft_dag.py --limit 1 --smoke-test --model thinkingmachines/inkling:free
```
- **Task:** `scipy__scipy-13879`
- **Result:** Succeeded on attempt 2 after initial retry pivot.
- **Translated Steps:** 5 steps (fast-grep $\rightarrow$ read_file $\rightarrow$ edit_file $\rightarrow$ repro-check $\rightarrow$ submit_patch).
- **Generated SFT Windows:** 5 windows rendered, prefix-delta loss masking verified against `models/gemma-4-31b-it-qat-w4a16-ct`.
- **Smoke Output Files:**
  - `pydantic/test_results/smoke_test_task.json`
  - `pydantic/test_results/smoke_test_sft_windows.jsonl`

---

## 7. Overnight Batch Execution in Detached `tmux`

To translate the 1,500 gold candidate tasks overnight with automatic checkpointing and resume:

### Launch Session
```bash
tmux new-session -d -s sft_translation \
  "bash -c 'cd /home/vps466a/arthityap/gemma4 && \
   .venv/bin/python3 pydantic/translate_sft_dag.py \
     --candidates pydantic/gold/raw_candidates_1500.jsonl \
     --model thinkingmachines/inkling:free \
     --resume 2>&1 | tee pydantic/logs/translation_run.log'"
```

### Attach / Monitor
```bash
tmux attach -t sft_translation
```

### Live Progress Query
```bash
# Monitor checkpoint progress
cat pydantic/output/checkpoint_state.json | jq .

# Count generated SFT windows
wc -l pydantic/output/sft_windows.jsonl

# Inspect rejected tasks and failure reasons
cat pydantic/output/rejected_tasks.jsonl | jq '{task_id, rejection_reason}'
```
