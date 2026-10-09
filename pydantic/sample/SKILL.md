# ═══════════════════════════════════════════════════════════════════════
# MASTER SKILL: MODULAR RAG CORPUS BUILDER & BATCH ENRICHMENT SCAFFOLDING
# ═══════════════════════════════════════════════════════════════════════

**SKILL NAME:** `modular-rag-corpus-builder`  
**CANONICAL TEMPLATE SOURCE:** `infrastructure/workflow_tmp/`  
**REFERENCE IMPLEMENTATIONS:** `infrastructure/generators/archetypes/clean/`, `infrastructure/generators/hidden/clean/`

---

## 1. Architectural Blueprint & Decoupled Separation of Concerns

When instantiating or customizing a batch LLM generation, cleaning, or RAG enrichment pipeline, **NEVER** write monolithic scripts, ad-hoc loops, or unverified spaghetti code.

The scaffolding follows a strict **Decoupled Architecture**:
```text
infrastructure/generators/<domain>/
├── [INFRASTRUCTURE PLUMBING - DO NOT TOUCH]
│   ├── runner.py              # Dedicated HTTP/2 worker pool, 429 key-hop, jittered backoff, FIFO queue
│   ├── storage.py             # Atomic disk I/O (os.fsync), staging cache auto-purge, JSONL checkpoints
│   └── preflight.py           # Multi-point health checks (storage, gateway probe, Qdrant vector status)
│
├── [DOMAIN CUSTOMIZATION POINTS - ONLY EDIT THESE 3 FILES]
│   ├── models.py              # Domain input/output Pydantic v2 schemas (RawSpec & CleanStagePayload)
│   ├── stages.py              # Domain prompt prefix, 7-Cube rubric, PASS exemplars & agent bindings
│   └── config.py              # Domain directory paths, model routing, and domain-specific constants
│
└── [CLI & DOCUMENTATION]
    ├── generate_<domain>.py   # Top-level CLI entrypoint with customizable constants
    ├── SKILL.md               # Domain operational playbook & architectural invariants
    └── PROMPT.md              # Domain prompt template & 7-cube rubric
```

### 🚨 Placed-In-Stone Directive: Zero Infrastructure Tampering
* **DO NOT MODIFY** `runner.py`, `storage.py`, or `preflight.py`. These files encapsulate hardened enterprise networking, concurrency, backoff, and atomic disk persistence logic proven across 10,000+ catalog generations.
* **ONLY CUSTOMIZE**:
  1. `models.py`: Domain source/target schemas (`RawSpec`, `CleanStagePayload`, and assembled entries).
  2. `stages.py`: Domain prompt engineering (`SIFU_CLEANING_USER_PREFIX`), 7-cube self-audit rubric, and PASS exemplars.
  3. `config.py`: Directory paths (`WORK_DIR`), model selection, and domain-specific type constants.

---

## 2. The 8 Core Architectural Invariants

Every generator instantiated from this scaffolding strictly enforces eight core engineering invariants:

### A. Decoupled Architecture
* Infrastructure plumbing (`runner.py`, `storage.py`, `preflight.py`) is completely separated from domain logic.
* The worker pool treats domain stages as black-box coroutines returning strictly typed Pydantic payloads.
* Domain adjustments never risk breaking socket timeouts, backoff math, atomic disk syncing, or queue saturation.

### B. Dedicated Per-Worker HTTP/2 Socket Isolation
* In Python `httpx`/`h2`, sharing a single `AsyncClient(http2=True)` across concurrent coroutines serializes execution behind Python's internal `h2` multiplexer lock, causing catastrophic head-of-line blocking and false timeouts.
* Every worker lane **MUST** own its dedicated `httpx.AsyncClient(http2=True)` created via `create_isolated_worker_client(...)` with bounded socket timeouts (`connect=15.0s`, `read=300.0s`, `write=30.0s`, `pool=15.0s`).
* Each worker clones the chat model to bind its private client: `clone_model_with_client(model, worker_client)`.
* Worker clients are cleanly disposed of in teardown: `finally: await worker_client.aclose()`.

### C. Zero SDK Micro-Retries (`max_retries = 0`)
* The OpenAI SDK / AsyncOpenAI client defaults to rapid sub-second micro-retries (`max_retries=2` ~0.4s/0.8s).
* When operating against shared reverse proxies (LiteRouter, OpenRouter) or shared upstream key pools (e.g. Google Vertex/GCP Gemma pools with 65-second quarantine windows), sub-second micro-retries from concurrent workers instantly exhaust and quarantine all available keys across the entire pool.
* We strictly enforce `max_retries = 0` on all `AsyncOpenAI` instances (`orig_provider.client.max_retries = 0` or passing `max_retries=0` into `AsyncOpenAI(...)`).
* All transient failures and rate limits bubble immediately up to the runner's jittered macro-backoff schedule.

### D. 429 Key-Hopping (`MAX_429_KEY_HOPS = 2`) & Jittered Exponential Backoff
* When LiteRouter or an upstream gateway returns an HTTP 429, the key assigned to that request is quarantined.
* Rather than immediately going to sleep for minutes, the worker executes a fast key-hop (`MAX_429_KEY_HOPS = 2`, `FAST_429_RETRY_DELAY = 1.0s`) to advance the gateway's round-robin pointer to a fresh, active API key.
* If 429s persist after `MAX_429_KEY_HOPS`, the worker transitions to macro exponential backoff with decorrelated uniform jitter:
  $$\text{delay} = (\text{initial\_delay} \times \text{factor}^{\text{attempt}-1}) \times \text{Uniform}(0.75, 1.25)$$
* Workers hold their slot in the fixed worker pool during backoff, naturally shedding network traffic without spawning runaway coroutines or losing FIFO ordering.

### E. Streaming Token Execution with Automatic Fallback (`_run_stream_with_fallback`)
* Upstream reverse proxies and load balancers aggressively terminate idle HTTP connections after 30–60 seconds if no bytes are sent.
* Complex LLM generation passes (e.g. 1,000+ token structured JSON) exceed idle socket thresholds before the final byte is emitted.
* The runner executes via `agent.run_stream(...)` to stream response chunks and keep sockets active.
* If streaming validation encounters an `UnexpectedModelBehavior` error (e.g., partial chunk parsing), it automatically falls back to direct `agent.run(...)`:
  ```python
  async def _run_stream_with_fallback(agent, prompt, model):
      try:
          async with agent.run_stream(prompt, model=model) as stream_result:
              raw_output = await stream_result.get_output()
              return _parse_output(raw_output)
      except UnexpectedModelBehavior as exc:
          logger.warning("Streaming validation failed (%s); falling back to direct run...", exc)
          result = await agent.run(prompt, model=model)
          return _parse_output(result.output)
  ```

### F. Multi-Layer Text Sanitization & Anti-COT Defense
* **Strip `<think>` Tags**: Reasoning models often leak thinking blocks; our parsers extract the outermost valid JSON object (`{...}`), discarding outer `<think>...</think>` artifacts.
* **Strip Markdown Fences**: Leading and trailing ` ```json ` fences are safely stripped.
* **Latin-First Bracketed Hanzi Rule**: All English narrative fields MUST use Latin-first bracketed Chinese:
  - ✅ `'Direct Officer (正官)'`, `'Jia Wood (甲木)'`, `'Di Tian Sui (滴天髓)'`
  - ❌ `'正官 (Direct Officer)'`, `'((滴天髓))'`, raw `'甲木'` inside English text.
* **Anti-COT Validation**: The regex `BANNED_COT_RE` immediately rejects conversational retry leaks (`"Wait, let me restart"`, `"Actually, let me rethink"`, `"Oops,"`).

### G. Atomic File Writes with `os.fsync` & Staging Cache Auto-Purge
* Every cell output is written to a temporary `.tmp` file, explicitly flushed and fsynced to disk, and atomically renamed:
  ```python
  tmp_path.write_text(entry.model_dump_json(indent=2), encoding="utf-8")
  with tmp_path.open("r+", encoding="utf-8") as f:
      f.flush()
      os.fsync(f.fileno())
  tmp_path.replace(target_path)
  ```
* Intermediate stage outputs are cached in `staging/{cell_id}_stageN.json` to allow granular resume upon interruption.
* Corrupted staging files are detected and automatically purged on reload.
* Upon final cell assembly and verified write to `cells/`, staging cache files for that item are auto-purged (`cleanup_stage_cache(...)`).

### H. 100% Pydantic V2 Compliance & Zero-Tolerance Integrity
* **Strict Configuration**: All models MUST declare `model_config = ConfigDict(extra="forbid", validate_assignment=True)`.
* **PEP 695 Type Aliases**: MUST use `type Foo = Bar` syntax (Python 3.14+ standard; Ruff UP040).
* **Zero `typing.Any`**: Completely banned across all models and function signatures.
* **Zero Silent Fallbacks / Empty Shells**: No `Model()`, `None`, or empty defaults for required mathematical/metaphysical fields. If upstream data is missing, Pydantic MUST crash loudly.

---

## 3. Step-by-Step Execution Playbook for Future LLMs

Follow this exact 6-step sequence whenever building a new catalog or RAG corpus generator:

### Step 1: Copy Template Scaffolding
Create the target generator domain directory and clone the template files:
```bash
mkdir -p infrastructure/generators/<domain>
cp infrastructure/workflow_tmp/config.py infrastructure/generators/<domain>/
cp infrastructure/workflow_tmp/models.py infrastructure/generators/<domain>/
cp infrastructure/workflow_tmp/stages.py infrastructure/generators/<domain>/
cp infrastructure/workflow_tmp/runner.py infrastructure/generators/<domain>/
cp infrastructure/workflow_tmp/storage.py infrastructure/generators/<domain>/
cp infrastructure/workflow_tmp/preflight.py infrastructure/generators/<domain>/
cp infrastructure/workflow_tmp/generate_template.py infrastructure/generators/<domain>/generate_<domain>.py
```

### Step 2: Define Domain Schemas in `models.py`
In `infrastructure/generators/<domain>/models.py`:
1. Define `RawSpec` (Stage 0 pure Python combinatorial spec, 0 LLM tokens).
2. Define `CleanStagePayload` (the structured output model returned by the LLM stage).
3. Define the final verified entry model `Verified<Domain>Entry` with:
   - Metadata and coordinate fields.
   - Verified classical citations (`ClassicalCitation`).
   - Cleaned bilingual narratives (`sifu_diagnostic`, `behavioral_antidote`, `sifu_advisory`).
   - Actionable behaviors (2–4 items) and pitfall traps (1–3 items).
   - `content_hash: str` and `verified_at: str`.
4. Ensure all models declare:
   ```python
   model_config = ConfigDict(extra="forbid", validate_assignment=True)
   ```

### Step 3: Write Prompt, Rubric Cube & Exemplars in `stages.py`
In `infrastructure/generators/<domain>/stages.py`:
1. Define `SIFU_CLEANING_USER_PREFIX`: Persona, role, and critical directives (see `PROMPT.md`).
2. Define `RUBRIC_QUESTION_CUBE`: The 7-Cube Self-Audit questions covering:
   - D1: Citation fidelity & Latin-first bracketing.
   - D2: Posture-aware medicine & modern de-fatalization.
   - D3: Diagnostic depth & Sifu voice.
   - D4: Antidote actionability & agency restoration.
   - D5: Advisory non-determinism & zero Western jargon.
   - D6: Actionable behaviors (2–4 items with caps/cadences).
   - D7: Pitfall traps (1–3 items) & clause-complete translation.
3. Define `EXEMPLARS_BLOCK`: Provide 2 verified PASS exemplars (one Strong posture, one Weak posture).
4. Implement `build_stage1_user_prompt(...)` assembling: Prefix + Rubric Cube + Exemplars + Draft JSON.
5. Bind `cleaner_agent = Agent(generator_model, output_type=CleanStagePayload, retries=3)`.

### Step 4: Configure Paths & Model in `config.py`
In `infrastructure/generators/<domain>/config.py`:
1. Set `WORK_DIR = PROJECT_ROOT / "infrastructure/generators/<domain>"`.
2. Ensure `CELLS_DIR = WORK_DIR / "cells"`, `STAGING_DIR = WORK_DIR / "staging"`.
3. Configure `generator_model: OpenAIChatModel = CONTROL_SHEET.prompt_rag or CONTROL_SHEET.rag_model`.
4. Set execution constants (`CONCURRENCY = 10`, `TAKEOFF_SPACING = 1.0`, `STREAM = True`).

### Step 5: Run Unified Quality Gate
Audit all files using the native repository guard tool:
```python
guard({ filePath: "infrastructure/generators/<domain>/models.py" })
guard({ filePath: "infrastructure/generators/<domain>/stages.py" })
guard({ filePath: "infrastructure/generators/<domain>/config.py" })
guard({ filePath: "infrastructure/generators/<domain>/storage.py" })
guard({ filePath: "infrastructure/generators/<domain>/runner.py" })
```
All files must pass with **Radon CC < 6**, **Kill-Tries nesting depth $\le 3$**, **0 Pyright errors**, and **0 Ruff errors**.

### Step 6: Launch Batch Enrichment & Verification
Test with a single target cell first:
```bash
uv run python infrastructure/generators/<domain>/generate_<domain>.py --limit 1
```
Inspect the output in `cells/0001_<cell_id>.json` to verify:
- Citations are Latin-first and quote is authentic classical Chinese.
- Zero doom cues or fatalistic predictions.
- All English text has Latin-first bracketed Hanzi.
- All JSON schema fields match `Verified<Domain>Entry`.

Once verified, launch the full concurrent run:
```bash
uv run python infrastructure/generators/<domain>/generate_<domain>.py --concurrency 10
```

---

## 4. Operational CLI Controls Reference

The generated CLI entrypoint (`generate_<domain>.py` / `runner.py`) provides full runtime orchestration flags:

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--concurrency` | `10` | Number of parallel worker lanes. |
| `--takeoff-spacing` | `1.0` | Staggered delay (seconds) between worker boots to prevent thundering herds. |
| `--start` | `1` | 1-based catalog index to start processing from. |
| `--limit` | `0` | Max items to process (0 = process all pending). |
| `--target` | `""` | Target specific cell ID or index (e.g. `--target ARCH_JIA_BI_JIAN_STRONG`). |
| `--retry-failed` | `False` | Reprocess only entries recorded in `failed_items.jsonl`. |
| `--force` | `False` | Force regenerate existing cells and bypass intermediate staging cache. |
| `--stream / --no-stream` | `True` | Stream response tokens to prevent socket timeouts on long generations. |
| `--skip-preflight` | `False` | Bypass preflight gateway and vector DB readiness checks. |
