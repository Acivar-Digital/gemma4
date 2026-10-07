# Current Situation: Competition Architecture, Provenance & Task Census

## 1. Competition Runtime & Two-Container Evaluation Harness

The **Google Gemma 4 Developer Agent** Kaggle competition evaluates autonomous software engineering agents built on the declarative Google Agent Development Kit (`adk_submission` / `swegemma`) against 129 real-world Python repository issues (`fastapi`, `rich`, `requests`, and `httpx`).

### 1.1 Serving Infrastructure
- **Model**: `google/gemma-4-31b-it-qat-w4a16-ct` (`23,265,352,448` bytes across `2,009` tensors; Quantization-Aware Trained INT4 `pack-quantized` `compressed-tensors` on the 60-layer language tower, BF16 on the vision tower).
- **Compute**: 4x NVIDIA L4 GPUs (`4 x 24 GB = 96 GB` total VRAM) running vLLM with tensor parallelism `tp=4`, `max_model_len=32768`, `gpu_memory_utilization=0.90`, and `--enable-lora` (when `adapters/` is populated in `submission.zip`).
- **Quota & Packaging**: Strictly **1 submission per 24-hour UTC window** (`00:00:00 UTC` reset). The graded artifact is `submission.zip` (unpacked size ceiling `3 GiB`; our adapter-less Track 1 baseline is `124,196` bytes across 14 files).

### 1.2 Container A vs. Container B Isolation
Each task executes in a two-phase hermetically isolated container pipeline:
1. **Container A (Agent Workspace Execution)**:
   - The target repository is checked out at the base commit inside `/workspace`.
   - The withheld evaluation tests (`test_patch`) are **absent** in Container A.
   - The agent runs until it calls `submit_patch()` or hits a hard budget ceiling (`max_tool_calls: 40`, `max_time_seconds: 270`, `max_llm_turns: 100`).
   - **Patch Extraction Trap**: At termination, the harness runs `git add -N . && git diff HEAD` inside `/workspace` to extract `agent.patch`. Any untracked scratch file left in `/workspace` is swept into `agent.patch`.
2. **Container B (Isolated Grading)**:
   - A fresh checkout of the repository is created, `agent.patch` is applied, and any modifications made by the agent to test files (`tests/*`) are **reverted/discarded** before the withheld `test_patch` (`FAIL_TO_PASS` and `PASS_TO_PASS` pytest nodes) is applied and executed.
   - **Scoring Metric**: Binary resolution (`resolved = True` iff `test_exit_code == 0`). Leaderboard score is `resolved_count / N`.

---

## 2. Production Track 1 Architecture: Single-Agent 5-Skill + 5-Tool Monolith

Our live production configuration (`submissions/track1_live/`) is a **single-agent monolith** (`name: main`, `model: gemma-4-31b-it-qat-w4a16-ct`) governed by `eval_config.yaml` (`max_tool_calls: 40`, `max_time_seconds: 270`, `max_llm_turns: 100`) and `configs/sampling.yaml` (`temperature: 0.15`, `top_p: 0.9`, `max_output_tokens: 4096`, `thinking_budget: 2048`, `include_thoughts: true`).

### 2.1 The 5 Direct Tools (`agent.yaml` `tools:`)
| Tool | Budget Cost | Role & Contract |
| :--- | :--- | :--- |
| `read_file` | 1 call | Targeted line-window inspection (`start_line`, `end_line`, typically `±30` lines around an anchor). |
| `edit_file` | 1 call | Surgical exact-string replacement (`old_str` -> `new_str`) on existing source files. |
| `write_file` | 1 call | Creation of brand-new source files when explicitly required by the issue specification. |
| `get_status` | **0 calls (Free)** | Lightweight `git status` check to confirm workspace cleanliness. |
| `submit_patch` | **0 calls (Free)** | Terminal action that locks in the `/workspace` diff and ends the episode. |

### 2.2 The 5 Pre-Installed Structured Skills (Invoked via `run_skill_script`)
Rather than exposing raw `run_command`, `get_code_neighbors`, `search_similar_code`, or `get_code_subgraph`, the agent invokes five hardened, crash-immune Python skills via the ADK `SkillToolset` meta-tool `run_skill_script` (`1 call` per invocation):

| Skill Name | Script (`file_path`) | Architectural Function & Safety Guarantees |
| :--- | :--- | :--- |
| **`fast-grep`** | `"grep.py"` | Tokenized, sliding-window regex/literal code search with AST fuzzy suggestions, stopword filtering, and automatic `/workspace` path resolution. |
| **`code-map`** | `"map.py"` | AST structural outline, class inheritance hierarchy, and inbound/outbound symbol call-graph mapper with cycle-safe inode traversal. |
| **`code-oracle`** | `"oracle.py"` | Sandboxed 2-second timer-guarded runtime evaluator (`--eval`, `--hex`, `--width`, `--html-esc`, `--schema`, `--syntax`) for verifying Python semantics without writing files. |
| **`repro-check`** | `"check.py"` | Isolated `/tmp` reproduction runner (`15s` `killpg` process-group timeout, `1 GB` RAM cap, markdown fence stripping, mandatory assertion enforcement returning exit code `1` on assertion-free scripts, and deep string/repr/hex/dict diff diagnostics). **Zero `/workspace` pollution.** |
| **`test-gate`** | `"gate.py"` | Unified verification gate: runs distance-1 neighbor regression `pytest` with hard timeouts, inspects read-only `git diff`, distinguishes pre-fix test conflicts from true regressions, and blocks mutations to `tests/*` files. |

### 2.3 Unified 40-Call Monotone Budget Ladder (`prompts/main.md`)
Because `max_tool_calls: 40` is a hard task-global ceiling, `prompts/main.md` enforces a strict monotone phase ladder together with an in-turn 3-bullet thought scratchpad (`FILES EXAMINED`, `ROOT CAUSE FOUND`, `DO NOT RE-READ`):
- **Turns 1–6 (Localize & Map)**: Use `fast-grep` and `code-map` to locate target symbols, then `read_file` on focused line windows (`±30` lines). Never paginate an entire file in 20-line chunks ("Anti-Mouse Reading Rule").
- **Turn 7 (Mandatory Initial Edit)**: Apply the surgical fix via `edit_file` (or `write_file` if creating a new module).
- **Turns 8–15 (Verify & Refine)**: Execute `repro-check` (`check.py`) to verify the bug reproduction and fix assertion in `/tmp`, followed by `test-gate` (`gate.py`) to confirm zero neighbor regressions and a clean `git diff`.
- **Emergency Reserve (`tool_calls_remaining <= 5`)**: Immediately cease exploration, verify workspace cleanliness via `get_status`, and call `submit_patch()`.

---

## 3. Complete Historical Score & Run Provenance

Every local and cloud run in this repository has been forensically audited against trace `model_name` fields, `submission.zip` SHA-256 digests, and Kaggle API submission records:

| Run / Submission ID | Date | Environment & Served Model | Configuration & Adapter State | Score / Resolution | Verified Forensic Takeaway |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Kaggle Ref `56744693`** | Oct 1 | Kaggle Leaderboard (`gemma-4-31b-it-qat-w4a16-ct`) | Early v1 monolith (`thinking_budget: 0`, `include_thoughts: false`). | Unscored initial | Superseded by v2. |
| **Kaggle Ref `56765397`** | Oct 2 | Kaggle Leaderboard (`gemma-4-31b-it-qat-w4a16-ct`) | Pre-hardening tree (`667472e`) prior to skill CLI omnivorous hardening and prompt kwarg scrub. | **`0.03`** | Early baseline before 5-skill hardening and gate enforcement. |
| **Kaggle Ref `56810465`** | Oct 4 | Kaggle Leaderboard (`gemma-4-31b-it-qat-w4a16-ct`) | Shipped 90 MB Rank-8 LoRA trained on **`unsloth/gemma-4-31B-it-unsloth-bnb-4bit`** (BitsAndBytes NF4). | **`0.00`** (`0/129` in cloud trace mirror) | **Lineage Mismatch Crash**: BnB NF4 adapter weights applied to `w4a16-ct` (`compressed-tensors` INT4 packed) caused logit/generation collapse (`111/129` tasks had `tool_calls == 0`, `77/95` traces had `0` completion tokens; `18/95` ran before mid-run server degradation ~7.15h later). Zero `run_command` errors occurred. |
| **Kaggle Ref `56883026`** | Oct 6 | Kaggle Leaderboard (`gemma-4-31b-it-qat-w4a16-ct`) | **Locked Track 1 Baseline** (`submissions/track1_live/`, SHA-256 `10e32ceb9b...`, `124,196` bytes): **Adapter-less**, 5 tools + 5 skills via `run_skill_script`, **ZERO `run_command`**, `thinking_budget: 2048`. | **`0.13`** (Locked Whitelist Baseline) | Proves our 5-Skill + 5-Tool adapter-less monolith works cleanly on real Gemma 4 and beats `0.08`–`0.12` public starter baselines (`ryanholbrook` `0.12`, sample S2 `0.08`). |
| **Local `run_B39`** | Oct 3 | Local Harness + LiteRouter Proxy (`stealth/space-bunny-alpha`) | 5-Skill + 5-Tool Monolith across all 129 tasks (`5,137` steps audited). | `56/129` (`43.41%`) | **Proxy Teacher Run Only**: Served frontier proxy (`stealth/space-bunny-alpha`), **never** Gemma 4. Validates 5-skill sufficiency and supplies teacher trajectories. |
| **Local `run_B40`** | Oct 4 | Local Harness + LiteRouter Proxy (`stealth/space-bunny-alpha`) | 5-Skill + 5-Tool Monolith on the 77 Tier-1 task subset. | `50/77` (`64.94%`) | **Proxy Teacher Run Only**: Confirms 5-skill ceiling on Tier-1 single-file tasks; distilled with `run_B39` into the 40 deduplicated teacher trajectories in `training/sft_data/`. |

---

## 4. 129-Task Benchmark Stratification & Track 2 Strategic Target

A census of all 129 tasks in `tasks.jsonl` across repository domains (`fastapi`: 67, `rich`: 48, `requests`: 13, `httpx`: 1) reveals a sharp three-tier difficulty distribution:

| Tier | Task Count (% of 129) | Structural Profile | Examples & Characteristics | Strategic Role |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1 (Core Capture Target)** | **77 tasks (`59.7%`)** | Single-file surgical fixes (`<= 60` lines churn). Splits into **Shard A** (`47` tasks, `<= 6` lines churn) and **Shard B** (`30` tasks, `7–60` lines churn). | Median fix lines: `requests` = 4, `rich` = 9, `fastapi` = 18 (e.g., `rich_4076` ANSI newline split, `rich_4077` `FileProxy.isatty`, `requests_7328` redirect history slice, `requests_6589` `super_len`). | **Primary Track 2 Target**: Solving `31` of these `77` Tier-1 tasks (`40.3%` Tier-1 conversion) reaches `31/129 = 0.24` (1st place on the public leaderboard). |
| **Tier 2 (Stretch Target)** | **15 tasks (`11.6%`)** | Coordinated 2-file changes with moderate diff size. | E.g., `fastapi_14986` (`fastapi/applications.py` + `fastapi/openapi/docs.py` Swagger escaping). | Secondary capture via `code-map` cross-file symbol tracing + `test-gate` neighbor verification. |
| **Tier 3 (Poison Pills)** | **37 tasks (`28.7%`)** | Massive multi-file refactors, release script generators, or async lock re-architectures that cannot be solved reliably within 40 calls / 270s on a 4-bit model. | `rich_3930` (`12,000+` lines generated data), `fastapi_14609` (`2,000+` lines), `fastapi_15661` (brand-new Typer release CLI generator), `fastapi_15280` (April Fools joke), `httpx_3672` (HTTP/2 async lock). | **Exclude from SFT training**: Attempting to train a Rank-8 LoRA on Tier-3 diffs causes catastrophic gradient distortion. At inference time, the agent still attempts every task (budgets do not roll over across tasks). |

### Why Track 2 LoRA Adaptation Is Needed Beyond Track 1 (`0.13` -> `0.24`)
While Track 1 (`0.13` = ~17/129 tasks) proves that the base `gemma-4-31b-it-qat-w4a16-ct` model can operate our 5-Skill + 5-Tool harness zero-shot, base 4-bit Gemma 4 exhibits three concrete behavioral bottlenecks that prompt engineering alone cannot fully eliminate:
1. **Gemma 4 Native Tool Call Syntax Drift**: Under long contexts, the 4-bit base model occasionally drifts from Gemma 4's `<|tool_call>call:fn{key:<|"|>val<|"|>}<tool_call|>` format or leaks markdown code fences into tool arguments.
2. **Turn 2+ Reasoning & Verification Skipping**: After receiving a `tool_response`, the base model sometimes skips `repro-check` / `test-gate` verification or stalls in repetitive `read_file` calls instead of executing the `edit_file` -> `repro-check` -> `test-gate` -> `submit_patch` closure loop.
3. **Budget Discipline**: Distilling compact, high-signal 5-skill decision windows (`<= 3072` tokens) into a Rank-8 attention LoRA (`q_proj, v_proj, o_proj`) directly reinforces surgical localization and verification closure within 12–20 tool calls.
