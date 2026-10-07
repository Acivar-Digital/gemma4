# External Consultant Review Briefing: Track 2 Unsloth LoRA SFT Pipeline for Google Gemma 4 (31B QAT)

## 1. Purpose of This Review Package

You are reviewing our **Track 2 Supervised Fine-Tuning (SFT) & LoRA Adaptation Pipeline** for the Kaggle **Google Gemma 4 Developer Agent** competition (SWE-bench style autonomous Python bug-fixing benchmark across 129 tasks in `fastapi`, `rich`, `requests`, and `httpx`).

Our **Track 1 (Adapter-Less Prompt & 5-Skill Harness)** baseline is locked and verified on the Kaggle Public Leaderboard at **0.13** (Submission Ref `56883026`, SHA-256 `10e32ceb9b2ca6bf40b40c485d9279e837a1e4ce67fa2f4df5c3fcb5e4bc4a83`), outperforming standard `0.08`–`0.12` public starter baselines. To close the gap from `0.13` toward the leaderboard ceiling (`0.24`, ~31/129 resolved tasks), **Track 2** trains a lightweight, surgical Rank-8 LoRA adapter (`18.12M` parameters across `170` attention projection modules) on a single 24GB NVIDIA L4 GPU (`22.494 GiB` usable VRAM) to instill native Gemma 4 tool-calling syntax, Turn 2+ reasoning continuity, and strict 5-skill verification discipline.

Every architectural claim in this dossier has been verified directly against the local competition model checkpoint (`models/gemma-4-31b-it-qat-w4a16-ct/`, `23,265,352,448` bytes, `2,009` tensors, `tokenizer.json` vocab `262,144`, `chat_template.jinja`, and `config.json`), the production submission package (`submissions/track1_live/`), and our curated SFT dataset (`training/sft_data/unsloth_sft_train.jsonl`).

---

## 2. Four Non-Negotiable Architectural Invariants (LOCKED — DO NOT VIOLATE)

Before answering the review questions, you must treat the following four architectural invariants as **hard, immutable boundary conditions**. Do not propose designs, data synthesis recipes, or configuration changes that violate any of these four constraints:

### Invariant 1: Strictly 5-Skill + 5-Tool Contract (ZERO `run_command`)
- Our production agent (`submissions/track1_live/agent.yaml`) exposes **5 direct file/status tools** (`read_file`, `edit_file`, `write_file`, `get_status`, `submit_patch`) and **5 pre-installed structured skills** (`fast-grep`, `code-map`, `code-oracle`, `repro-check`, `test-gate`) invoked exclusively via the Google ADK `SkillToolset` meta-tool `run_skill_script`.
- Raw `run_command` (along with `get_code_neighbors`, `search_similar_code`, and `get_code_subgraph`) is **intentionally withheld by design**.
- On 4-bit quantized Gemma 4 (`w4a16-ct`), raw `run_command` introduces three catastrophic runtime failure modes:
  1. **Unbounded 300-second `pytest` sweeps** (exit code `124` timeouts that burn the entire `270s` task wall-clock budget).
  2. **`/workspace` untracked file pollution**: Container A extracts the final submission patch via `git add -N . && git diff HEAD`; any scratch script or reproduction artifact written inside `/workspace` via bash heredoc is swept into the graded diff, corrupting the patch in Container B.
  3. **Multi-line bash heredoc JSON escaping failures**: Unescaped quotes and newlines inside `python3 -c "..."` or `cat << 'EOF'` tool arguments trigger `json.loads` crashes in LiteLLM/vLLM tool parsers.
- All runtime execution and verification are safely handled by `repro-check` (`file_path: "check.py"`, isolated `/tmp` execution, 15s process-group timeout, 1GB RAM ceiling, mandatory assertion verification) and `test-gate` (`file_path: "gate.py"`, distance-1 neighbor regression pytest, read-only `git diff` inspection, and protected test-file guard).
- **Directive**: Do **NOT** recommend adding `run_command` to `agent.yaml`, and do **NOT** propose synthesizing raw bash/shell trajectories for SFT. All training windows must strictly adhere to the 5-Skill + 5-Tool surface (`0.0%` `run_command`).

### Invariant 2: Single-Agent Monolith (`max_tool_calls: 40`)
- The competition evaluation harness (`submissions/track1_live/eval_config.yaml:4`) enforces a single task-global budget (`max_tool_calls: 40`, `max_time_seconds: 270`, `max_llm_turns: 100`) with **zero per-sub-agent rationing**.
- Multi-agent or sub-agent delegation chains (e.g., Scout -> Coder -> Breaker or `code_analyzer` sub-agents) starve the global counter before `edit_file` and `submit_patch` can execute.
- **Directive**: Keep the single-agent monolith (`name: main`, `model: gemma-4-31b-it-qat-w4a16-ct`). Do **NOT** propose sub-agent architectures.

### Invariant 3: Zero Test-Set Contamination (`tasks.jsonl` Firewall)
- `tasks.jsonl` contains the 129 benchmark evaluation tasks (67 FastAPI, 48 Rich, 13 Requests, 1 HTTPX) along with gold `patch` and `test_patch` fields.
- Reverse-engineering, extracting, or training on `tasks.jsonl` gold patches constitutes training on the test set and causes severe overfitting that collapses on the private evaluation leaderboard.
- **Directive**: Never use `tasks.jsonl` gold patches as training targets or prompt hints.

### Invariant 4: Single 24GB NVIDIA L4 Training Envelope
- Training runs on a single NVIDIA L4 GPU (`22.494 GiB` usable VRAM; `NVIDIA_A100_GPUS` quota is `0.0`).
- To fit within `22.494 GiB` without out-of-memory (OOM) crashes against Gemma 4's `262,144` vocabulary, training is locked to `max_seq_length=3072`, `per_device_train_batch_size=1`, `gradient_accumulation_steps=8`, `optim="paged_adamw_8bit"`, `eval_strategy="no"` (avoiding the `7.50 GiB` `[1, 3072, 262144]` FP32 evaluation logit spike at Step 5), and Rank-8 LoRA (`r=8, lora_alpha=16, lora_dropout=0.0`) targeting `["q_proj", "v_proj", "o_proj"]` (`170` modules, `340` LoRA tensors, `18,124,800` trainable parameters = `34.57 MiB` BF16).

---

## 3. Four Focused Review Questions (Q1–Q4)

Please provide concrete, deeply technical, code-level answers to the following four questions:

### Q1: Gemma 4 Native Chat Template & Prefix-Delta Loss Masking
We verified directly against `models/gemma-4-31b-it-qat-w4a16-ct/chat_template.jinja` that Gemma 4 keeps an entire multi-step tool-calling loop inside a **single open `<|turn>model\n` block** without emitting `<turn|>` until the final text response. Furthermore:
- On **Turn 1** (immediately after `user`), `prefix_text` (`add_generation_prompt=True`) ends with `<|turn>model\n`, and `completion_text` starts with `<|channel>thought\n`.
- On **Turn 2+** (immediately after `tool`), `chat_template.jinja:388` (`{%- if ns.prev_message_type == 'tool' -%}{%- if enable_thinking -%}<|channel>thought\n{%- endif -%}`) appends `<|channel>thought\n` to `prefix_text` **before** the completion begins, while line 241 (`add_generation_prompt=False`) only emits `<|channel>thought\n...<channel|>` in `full_text` when `reasoning` / `reasoning_content` is non-empty.
- Consequently, standard substring splitters like Unsloth's `train_on_responses_only(response_part="<|turn>model\n")` fail on Turn 2+. We replaced it with **prefix-delta loss masking** (`full_text[len(prefix_text):]`) with `enable_thinking=True, preserve_thinking=True` and a hard assertion that every supervised Turn 2+ step has non-empty `reasoning` (`assert full_text.startswith(prefix_text)`).

**Questions for Q1**:
1. Audit our prefix-delta masking implementation against `chat_template.jinja`. Are there any BPE boundary token-merging ("token-healing") edge cases in Gemma 4's SentencePiece/BPE tokenizer (`vocab_size=262,144`) when slicing token IDs via `full_ids[len(prefix_ids):]` right after `<|channel>thought\n` (where `\n` is followed by plain-text reasoning)?
2. Should we compute the `-100` label mask using character-offset mapping (`tokenizer(full_text, return_offsets_mapping=True, add_special_tokens=False)`) against `len(prefix_text)` rather than `len(prefix_ids)`, and how should the boundary token be handled if BPE merges the trailing `\n` of `<|channel>thought\n` with the first character of the reasoning string?

### Q2: Unsloth `w4a16-ct` Int4PackedLinear Training vs `q4_0-unquantized` Fallback & vLLM Serving Parity
Kaggle serves `google/gemma-4-31b-it-qat-w4a16-ct` (`quant_method: "compressed-tensors"`, `format: "pack-quantized"`, INT4 group-32 symmetric on `model.language_model.layers.0..59`, BF16 on `model.vision_tower`) under vLLM (`tp=4`, `--enable-lora`). Our primary training load passes `FastModel.from_pretrained("google/gemma-4-31b-it-qat-w4a16-ct", max_seq_length=3072, dtype=torch.bfloat16, load_in_4bit=False, use_exact_model_name=True, text_only=False)` with `finetune_vision_layers=False`. If Unsloth/PyTorch blocks gradient backpropagation through `compressed-tensors` `Int4PackedLinear` kernels, our fallback loads the official unquantized QAT sibling `google/gemma-4-31B-it-qat-q4_0-unquantized` with `load_in_4bit=True` and rewrites `base_model_name_or_path` to `"google/gemma-4-31b-it-qat-w4a16-ct"` on export.

**Questions for Q2**:
1. Verify our Unsloth loading contract and fallback mechanics. When training on `q4_0-unquantized` with `load_in_4bit=True`, does the QAT-trained weight geometry align closely enough with `w4a16-ct` `pack-quantized` INT4 group-32 weights at `r=8, lora_alpha=16` to prevent the logit collapse observed when mounting a non-QAT `unsloth-bnb-4bit` adapter?
2. Verify our vLLM `--enable-lora` tensor-name and module-count parity: across 60 language layers (50 sliding-attention layers with `q/k/v/o_proj` and 10 global full-attention layers where `attention_k_eq_v=True` omits `v_proj`), targeting `["q_proj", "v_proj", "o_proj"]` yields `60 + 50 + 60 = 170` adapted modules (`340` LoRA A/B tensors) named `base_model.model.language_model.layers.{i}.self_attn.{q,v,o}_proj.lora_{A,B}.weight`. Are any additional key transformations or `adapter_config.json` fields required by vLLM's `Gemma4ForCausalLM` / multimodal wrapper?

### Q3: 5-Skill SFT Dataset Curation, Filtering, and Overfitting Prevention
Our teacher dataset (`training/sft_data/unsloth_sft_train.jsonl`, `885` train / `222` val windows across `40` resolved teacher trajectories from `run_B39`/`run_B40`) reduces to **`596` valid tool-calling train windows** (`639` tool calls: `run_skill_script` `64.3%`, `read_file` `17.2%`, `edit_file` `11.1%`, `submit_patch` `6.9%`, `write_file` `0.5%`, `run_command` `0.0%`) after merging the `289` (`32.66%`) `target_tools: []` dead-thought windows into subsequent action turns and splitting strictly by `task_id` (`0%` task overlap).

**Questions for Q3**:
1. With `18,124,800` trainable parameters and `596` decision windows (~`75,000`–`90,000` supervised completion tokens), what is the optimal sample-weighting or window-filtering strategy so the adapter masters high-leverage transition boundaries (`repro-check` -> `edit_file` -> `test-gate` -> `submit_patch`) rather than over-allocating capacity to repetitive early-turn `fast-grep` calls?
2. Audit our regularization and optimization hyperparameters (`lr=1e-4`, `1` epoch, `warmup_ratio=0.10`, `weight_decay=0.01`, `max_grad_norm=0.3`, `lora_dropout=0.0`, `neftune_noise_alpha=None`). How do we prevent the Rank-8 adapter from memorizing FastAPI/Rich/Requests file paths and repository-specific symbol names?

### Q4: Contamination-Free 5-Skill Trajectory Augmentation
Our 40 resolved teacher trajectories come from `fastapi` (`21` tasks), `rich` (`13` tasks), and `requests` (`6` tasks). Under Invariant 3, we will **never** extract or train on gold patches from `tasks.jsonl`. Under Invariant 1, we will **never** synthesize `run_command` calls.

**Questions for Q4**:
1. If `596` clean decision windows are insufficient or require augmentation, what is the highest-leverage, 100% contamination-free method to synthesize or harvest additional 5-skill trajectories (`fast-grep` -> `code-map` -> `read_file` -> `repro-check` -> `edit_file` -> `test-gate` -> `submit_patch`) — for example, using external open-source commits/PRs or negative-to-positive self-correction loops (`repro-check` assertion failure -> `edit_file` fix -> `test-gate` pass)?
2. What exact offline validation gate (e.g., held-out task exact-match tool syntax rate, `<|"|>` delimiter validity, `submit_patch` termination rate, and perplexity on held-out `task_id`s) should govern whether the trained Track 2 LoRA adapter is promoted to our Kaggle Compute staging kernel before touching the 1/day Leaderboard quota?

---

## 4. Dossier Reading Order

| File | Title | Contents & Scope |
| :--- | :--- | :--- |
| **`00_CONSULTANT_PROMPT.md`** | **Consultant Review Briefing** | Mission, 4 Non-Negotiable Architectural Invariants, Q1–Q4 Review Questions, and reading order. |
| **`01_CURRENT_SITUATION.md`** | **Current Situation & Architecture** | Kaggle 4x L4 vLLM environment, Container A/B grading split, 5-Skill + 5-Tool Monolith, 40-call budget ladder, score provenance (`0.13` baseline), and 129-task census. |
| **`02_NEGATIVE_CONSTRAINTS.md`** | **Seven Hard Negative Constraints** | Engineering proofs for NO `run_command`, NO sub-agents, NO BnB NF4 on `w4a16-ct`, NO `<start_of_turn>`, NO `eval_strategy="steps"` OOM, NO MLP/vision/`k_proj`/NEFTune, and NO `tasks.jsonl` gold-patch leakage. |
| **`03_DATA_AUDIT_AND_SUFFICIENCY.md`** | **SFT Data Audit & Builder Fixes** | Quantitative audit of `unsloth_sft_train.jsonl` (token percentiles, tool distribution, repo split) and exact fixes for all 4 bugs in `scripts/build_unsloth_dataset.py`. |
| **`04_MODEL_AND_CHAT_TEMPLATE_TRUTH.md`** | **Model & Chat Template Ground Truth** | Verified `models/gemma-4-31b-it-qat-w4a16-ct/` control token IDs (`46`–`52`, `98`, `100`–`101`, `105`–`106`), 6 `chat_template.jinja` invariants, and Turn 2+ prefix-delta masking math. |
| **`05_HARDWARE_AND_VRAM_BUDGET.md`** | **Hardware & L4 VRAM Budget** | Exact tensor breakdown (`2,009` tensors, `170` LoRA modules, `attention_k_eq_v=True`), single 24GB L4 `20.31 GiB` VRAM ledger, and Step-5 `7.50 GiB` logit OOM proof. |
| **`06_PROPOSED_TRAINING_PLAN.md`** | **End-to-End Track 2 Training Plan** | Complete implementation blueprint: fixed dataset builder, Unsloth loading + fallback, prefix-delta collator, hyperparameters, and 2-file vLLM adapter export gate. |
| **`07_INTERNAL_RESEARCH_FINDINGS.md`** | **Internal Research & Audit Ledger** | Empirical findings from local weight inspections, cloud trace post-mortems (`56810465` vs `56883026`), and reconciliation of prior consultant reviews. |
