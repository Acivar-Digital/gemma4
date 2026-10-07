# 05 — Executive Summary for External Consultants

**Competition**: Kaggle — *Gemma 4 Developer Agent* (SWE-bench style autonomous Python bug-fixing on 129 tasks across FastAPI, Rich, Requests, and HTTPX)  
**Current Standing**: **`0.13` Verified Public Leaderboard Baseline** (Submission Ref `56883026`, Oct 6 — Track 1 adapter-less 5-skill single-agent monolith; outperforms the `0.08`–`0.12` public starter baselines). Top of leaderboard is `0.24` (`~31/129` tasks).  
**Objective of This Review**: Validate our **Track 2 Rank-8 LoRA Supervised Fine-Tuning (SFT)** architecture on `google/gemma-4-31b-it-qat-w4a16-ct` (single 24 GB NVIDIA L4 GPU) to lift our verified `0.13` (`~17/129`) baseline into the `0.20`–`0.25+` (`26–32/129`) leaderboard tier without regressing tool-call syntax or triggering quantization/VRAM failures.

---

## 1. Production Architecture Invariant: 5 Tools + 5 Skills (ZERO `run_command`)

Our production agent (`submissions/track1_live/agent.yaml`) is a **single-agent monolith** (`name: main`, `model: gemma-4-31b-it-qat-w4a16-ct`) operating under a strict **40-tool-call task-global ceiling** (`eval_config.yaml`: `max_tool_calls: 40`, `max_time_seconds: 270`, `max_llm_turns: 100`).

1. **Why Single-Agent Monolith**: The Google ADK SWE-Gemma harness enforces a single task-global `max_tool_calls` counter with zero per-subagent rationing. Sub-agent chains (`Scout -> Coder -> Breaker`) starve the budget before `edit_file` or `submit_patch` can run.
2. **Direct Native Tools (5)**:
   - `read_file` (150-line window; omit `end_line`)
   - `edit_file` (exact line replacement)
   - `write_file` (new file creation when required)
   - `get_status` (100% FREE — 0 budget cost)
   - `submit_patch` (100% FREE — final diff extraction)
3. **Pre-Installed Structured Skills (5, invoked exclusively via `run_skill_script`)**:
   - `fast-grep` (`file_path: "grep.py"`) — AST-aware token/regex search with 0-match fallback diagnostics.
   - `code-map` (`file_path: "map.py"`) — AST call graph, class hierarchy, and file outline mapper.
   - `code-oracle` (`file_path: "oracle.py"`) — isolated Python expression (`--eval`), ANSI/hex (`--hex`), terminal cell width (`--width`), HTML escaping (`--html-esc`), JSON Schema (`--schema`), and AST syntax (`--syntax`) verifier.
   - `repro-check` (`file_path: "check.py"`) — isolated `/tmp` reproduction runner (`15s` process-group timeout, `1 GB` RAM guard, mandatory assertion verification, string/repr/hex/dict diff breakdown).
   - `test-gate` (`file_path: "gate.py"`) — distance-1 neighbor regression `pytest` runner, read-only `git diff` viewer (`--diff`), and protected test-file guard (`--status`).
4. **Why `run_command` is Withheld by Design**:
   - Raw `run_command` (along with `get_code_neighbors`, `search_similar_code`, `get_code_subgraph`) is intentionally excluded from `agent.yaml`, `prompts/main.md`, and all SFT data.
   - On 4-bit Gemma 4, raw shell commands cause three fatal failure modes: (a) 300-second full-repo `pytest` hangs (`exit 124`), (b) untracked scratch files in `/workspace` swept into `git add -N . && git diff HEAD` (corrupting the graded patch in Container B), and (c) multi-line bash heredoc JSON escaping crashes.
   - **Empirical Proof**: Omitting `run_command` NEVER caused the historical `0.03` or `0.00` scores (`0` `run_command` errors across all 95 Kaggle cloud traces), and our locked `0.13` leaderboard baseline (`56883026`) uses this exact 5-tool + 5-skill (`0` `run_command`) architecture.

---

## 2. Forensic Provenance of All Historical Runs

| Run / Submission ID | Date | Model Served | Adapter State | Score / Resolution | Verified Root Cause |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Kaggle Ref `56883026`** | Oct 6 | `gemma-4-31b-it-qat-w4a16-ct` (4x L4 vLLM) | **None** (Track 1 baseline) | **`0.13` Public LB** (`~17/129`) | **Locked Production Baseline**: 5 direct tools + 5 skills via `run_skill_script`, zero `run_command`, `temperature: 0.15, top_p: 0.9, max_output_tokens: 4096, thinking_budget: 2048, include_thoughts: true`. |
| **Kaggle Ref `56765397`** | Oct 2 | `gemma-4-31b-it-qat-w4a16-ct` (4x L4 vLLM) | Early prototype | **`0.03` Public LB** (`~4/129`) | Early pre-hardening tree (`667472e`) prior to skill/prompt hardening and `repro-check` missing-assertion exit-code fix. |
| **Kaggle Ref `56810465`** | Oct 4 | `gemma-4-31b-it-qat-w4a16-ct` (4x L4 vLLM) | **90 MB Broken LoRA** (`unsloth-bnb-4bit`) | **`0.00` Public LB** (`0/129`) | **Quantization Lineage + Template Mismatch**: Adapter trained on BitsAndBytes NF4 (`unsloth-bnb-4bit`) with Gemma 2/3 `<start_of_turn>` tags and mounted onto vLLM's `compressed-tensors` INT4 (`w4a16-ct`) engine. Caused immediate generation collapse (`111/129` tasks had `tool_calls == 0`, `77/95` traces had `0` completion tokens; `18/95` ran tool loops before server degradation). |
| **Local `run_B39` / `run_B40`** | Oct 3–5 | `stealth/space-bunny-alpha` (LiteRouter proxy) | None | `56/129` (`43.4%`) / `50/77` (`64.9%`) | **Teacher Proxy Trajectories**: Executed on a frontier proxy model, **not** Gemma 4. Used strictly as a teacher corpus to distill 5-skill protocol trajectories. |

---

## 3. Verified Gemma 4 SFT & LoRA Ground Truth (`models/gemma-4-31b-it-qat-w4a16-ct/`)

Direct inspection of the local competition checkpoint (`tokenizer.json`, `chat_template.jinja`, `config.json`, `model.safetensors`) established four critical engineering truths:

1. **Native Gemma 4 Control Tokens (`vocab_size = 262,144`)**:
   - Turn delimiters are `<|turn>` (`105`) and `<turn|>` (`106`) — **Gemma 2/3 `<start_of_turn>` does not exist**.
   - Reasoning delimiters are `<|channel>thought\n...<channel|>` (`<|channel>` = `100`, `<channel|>` = `101`, system header `<|think|>` = `98`) — **there is NO `<|thought|>` token in Gemma 4**.
   - Tool calls use asymmetric tags `<|tool_call>` (`48`) and `<tool_call|>` (`49`) with unquoted sorted keys and `<|"|>` (`52`) string delimiters: `<|tool_call>call:run_skill_script{args:[<|"|>pattern<|"|>],file_path:<|"|>grep.py<|"|>,skill_name:<|"|>fast-grep<|"|>}<tool_call|><|tool_response>`.
2. **Turn 2+ Prefix Asymmetry & Prefix-Delta Loss Masking (`chat_template.jinja:232-243, 381-390`)**:
   - Gemma 4 keeps an entire multi-step tool loop inside a **single open `<|turn>model\n` block** without emitting `<turn|>` until the final text response.
   - On Turn 1 (after `user`), `prefix_text` (`add_generation_prompt=True`) ends with `<|turn>model\n` and completion starts with `<|channel>thought\n`.
   - On Turn 2+ (after `tool`), `chat_template.jinja:388` **already appends `<|channel>thought\n` to the end of `prefix_text`**! Therefore, `train_on_responses_only("<|turn>model\n")` fails on Turn 2+.
   - **Solution**: Supervise each decision window via **Prefix-Delta Token Masking** (`labels = [-100] * len(prefix_ids) + full_ids[len(prefix_ids):]`) with `enable_thinking=True, preserve_thinking=True`, and enforce non-empty `reasoning` on every Turn 2+ target step (`assert full_text.startswith(prefix_text)`).
3. **Dataset Remediation (`scripts/build_unsloth_dataset.py`)**:
   - The current `885` train / `222` val windows (`100% <= 2,822` tokens, `0%` `run_command`, `64.3%` `run_skill_script`) suffer from 4 bugs: (a) Gemma 2/3 `<start_of_turn>` formatting, (b) `289/885` (`32.66%`) `target_tools: []` dead-thought rows teaching premature stopping, (c) `100%` `task_id` overlap between train and val (`40/40` tasks leaked), and (d) a 3-line stub system prompt instead of `submissions/track1_live/prompts/main.md`.
   - Merging thought-only turns into the subsequent tool-calling turn's `reasoning` and dropping trailing orphans yields **`596` clean 100%-tool-calling windows**, split strictly by `task_id` (`34` train tasks / `6` val tasks = `0%` task leakage).
4. **170-Module LoRA Geometry & Single-L4 VRAM (`20.31 GiB` Peak)**:
   - Because the `10` global full-attention layers set `attention_k_eq_v=True` (`K=V`) and physically omit `v_proj`, targeting `["q_proj", "v_proj", "o_proj"]` (`r=8, lora_alpha=16`) adapts **`60 q_proj + 50 v_proj + 60 o_proj = 170` linear modules** (`340` LoRA A/B tensors, `18,124,800` trainable params = `34.57 MiB` BF16).
   - At `max_seq_length=3072, batch_size=1, grad_accum=8, paged_adamw_8bit, eval_strategy="no"`, peak VRAM is **`20.31 GiB`** (`+2.18 GiB` headroom on a 24 GB L4). Setting `eval_strategy="steps"` materializes `[1, 3072, 262144]` FP32 logits (`+7.50 GiB`) and OOMs (`27.81 GiB > 22.494 GiB`).

---

## 4. Dossier Map & Specific Questions for Consultants

### 4.1 Dossier Structure (`training/research_dossier/00`–`07`)
- **`00_README_FOR_CONSULTANTS.md`**: Review charter, ground-truth invariants, and key questions.
- **`01_SYSTEM_ARCHITECTURE_AND_HARNESS.md`**: Container A/B lifecycle, 5-tool + 5-skill contract, and 15-gate verification pipeline.
- **`02_NEGATIVE_CONSTRAINTS.md`**: Hard physical, token, and tool boundaries (why `run_command` and sub-agents are forbidden).
- **`03_DATA_AND_TRAJECTORY_ANALYSIS.md`**: 129-task Tier 1/2/3 stratification (`77` single-file target) and `885 -> 596` SFT window audit.
- **`04_TRAINING_METHOD_AND_GPU_FEASIBILITY.md`**: `w4a16-ct` loading contract, 170-module LoRA math, and `20.31 GiB` L4 VRAM budget.
- **`05_EXECUTIVE_SUMMARY_FOR_CONSULTANTS.md`**: This executive overview.
- **`06_ESSENTIAL_CODE_AND_SAMPLES.md`**: Exact production configs, `build_unsloth_dataset.py` & notebook bug annotations, and replacement code.
- **`07_INTERNAL_RESEARCH_FINDINGS.md`**: Deep technical reference of all verified Gemma 4 (`w4a16-ct`) tokenizer, Jinja, and safetensors invariants.

### 4.2 Consultant Deliverables Requested (`Q1`–`Q4`)
- **Q1 (Autograd on `compressed-tensors` `w4a16-ct` vs `q4_0-unquantized` Fallback)**: Verify whether any additional Triton/PEFT hook is needed when training LoRA directly on `pack-quantized` `compressed-tensors` in Unsloth, or if we should default immediately to the `q4_0-unquantized` twin with `base_model_name_or_path` rewrite.
- **Q2 (Prefix-Delta Loss Masking & Thought Weighting)**: Validate our `build_supervised_step_sample()` prefix-delta masking on Turn 1 vs Turn 2+ and advise whether `<|channel>thought\n...<channel|>` tokens should receive full (`1.0`) cross-entropy weight or reduced weight relative to `<|tool_call>...<tool_call|><|tool_response>`.
- **Q3 (Small-Sample Regularization on `596` Windows / `34` Train Tasks)**: Validate `r=8, lora_alpha=16, lr=1e-4, 1 epoch, max_grad_norm=0.3, neftune_noise_alpha=None` on `["q_proj", "v_proj", "o_proj"]` (`170` modules) to prevent overfitting to teacher repo identifiers while instilling strict 5-skill discipline.
- **Q4 (Inference Sampling Interaction with LoRA)**: Advise whether `temperature: 0.15, top_p: 0.9, thinking_budget: 2048` should remain unchanged once the Rank-8 LoRA adapter is attached in vLLM.
