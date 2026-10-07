# 00. Consultant Prompt — Track 2 LoRA Effectiveness Review

> **INSTRUCTIONS FOR EXTERNAL CONSULTANTS:**
> Please read all files in this `training/research_dossier/` directory (`00` through `06`). This directory is a self-contained ~15K-token briefing packet containing our architecture, empirical constraints, data audit, training code, and sample trajectories for the **Google Gemma 4 Developer Agent** Kaggle competition.
>
> Do NOT propose switching models, adding a second LLM, using BitsAndBytes NF4 checkpoints, or omitting `run_command`. Those boundaries are physically locked by the offline Kaggle evaluation harness (documented in `02_NEGATIVE_CONSTRAINTS.md`).
>
> **We ask you to answer ONLY the following TWO core questions with concrete, implementation-ready engineering recommendations:**

---

## Question 1: How do we make LoRA training effective via METHOD?

We are fine-tuning **`google/gemma-4-31B-it-qat-q4_0-unquantized`** using **Unsloth** on a **single 24GB NVIDIA L4 GPU**, exporting a PEFT LoRA adapter (`main_lora`) to be served by **vLLM** on **`google/gemma-4-31b-it-qat-w4a16-ct`** (4× L4 GPUs in the offline scoring container).

During our internal audit of our existing training script (`06_ESSENTIAL_CODE_AND_SAMPLES.md`), we identified several critical methodological questions and potential defects:
1. **Chat Template & Loss Masking Alignment:**
   - Our current dataset builder (`scripts/build_unsloth_dataset.py`) renders turns using Gemma 2/3 markers (`<start_of_turn>user\n...<end_of_turn>`, `<start_of_turn>model\n...<end_of_turn>`) and `<|tool_call|>call:fn{args}<|tool_call|>`, and masks loss using `train_on_responses_only(instruction_part='<start_of_turn>user\n', response_part='<start_of_turn>model\n')`.
   - However, native Gemma 4 tokenizers and vLLM's Gemma 4 tool parser use `<|turn>user\n...<turn|>`, `<|turn>model\n<|thought>\n...<turn|>`, and `<|tool_call>call:fn{...}<tool_call|>`.
   - **How should we structure the exact chat template rendering and response-only loss masking in Unsloth so the trained LoRA weights align 100% with vLLM's runtime prompt formatting and tool call parser?**
2. **Quantization & Base Model Loading in Unsloth:**
   - Our current notebook falls back to `google/gemma-4-31b-it` with `load_in_4bit=True` (which triggers BitsAndBytes NF4 quantization, the exact root cause of our Oct-4 `0.00` crash).
   - **What are the exact `FastLanguageModel.from_pretrained(...)` arguments and precision flags required to load `google/gemma-4-31B-it-qat-q4_0-unquantized` on a 24GB L4 GPU so that the exported LoRA adapter tensors match the QAT `w4a16-ct` serving weights without scale distortion?**
3. **PEFT Hyperparameters & Regularization:**
   - Current config: Rank `r=8`, `lora_alpha=16` (or `8`), `target_modules=['q_proj', 'v_proj', 'o_proj']` (or including `k_proj`), `max_seq_length=3072`, `learning_rate=2e-4`, `optim='paged_adamw_8bit'`, `neftune_noise_alpha=5`.
   - Note: Our current notebook had `max_steps=25` (which only trains on 200 samples out of 885!).
   - **What exact rank, alpha, target modules, learning rate, step/epoch count, and sequence length should we lock in to maximize SWE tool-calling accuracy without overfitting or degrading Python code syntax?**
4. **vLLM Adapter Packaging:**
   - Our current notebook calls `tokenizer.save_pretrained(ADAPTER_DIR)` alongside `model.save_pretrained(ADAPTER_DIR)`.
   - **Should tokenizer files be stripped from `submission/adapters/main_lora/` so vLLM uses the base model's native tokenizer, and what exact fields in `adapter_config.json` must be set/sanitized before packaging?**

---

## Question 2: How do we make LoRA training effective via DATA?

We audited our current SFT dataset (`training/sft_data/unsloth_sft_train.jsonl`, 885 train / 222 val samples across 40 solved tasks, 100% $\le 2,822$ tokens; see `03_DATA_AUDIT_AND_SUFFICIENCY.md` and `06_ESSENTIAL_CODE_AND_SAMPLES.md`).

Our audit exposed four critical data imbalances:
- **Zero `run_command` Coverage (0%):** The 885 samples were sliced from earlier proxy runs (`run_B39`/`run_B40`) that had only 5 tools + 5 skills (`run_command` was disabled). Thus, `run_command` appears **0 times** in the training set, and the embedded system prompt in the training data does not even list `run_command` or the 3 graph tools (`get_code_neighbors`, `search_similar_code`, `get_code_subgraph`).
- **Heavy Skew Toward `run_skill_script` (64.3%):** 383 of 594 tool calls invoke `run_skill_script`, compared to only 113 `read_file`, 66 `edit_file`, and 32 `submit_patch`.
- **Unactionable Reasoning Turns (32.7%):** 289 of the 885 training windows end on an assistant turn with `target_tools: []` (pure text reasoning without a tool call).
- **Limited Task Breadth (40 / 129 tasks):** All 885 decision windows come from 40 tasks solved by the teacher model (`stealth/space-bunny-alpha`), leaving 89 benchmark tasks unrepresented.

**Please advise on our exact Data Protocol:**
1. **System Prompt & Tool Alignment:** How should we rewrite the SFT `SYSTEM_PROMPT` and trajectories so the trained LoRA matches our live 9-tool + 5-skill production prompt (`submissions/track1_live/prompts/main.md`)?
2. **Bridging the `run_command` Gap:** How should we construct or synthesize multi-turn trajectories that teach the agent the winning verification loop (`run_command` with `/tmp/repro.py` + `pytest -k` before `submit_patch`)? How many `run_command` trajectories do we need?
3. **Filtering & Rebalancing the 885 Samples:** Should we drop the 289 tool-less assistant turns (`target_tools == []`) and downsample `run_skill_script` so that surgical `read_file` $\rightarrow$ `edit_file` $\rightarrow$ `run_command` (`pytest`) $\rightarrow$ `submit_patch` sequences dominate the loss gradient?
4. **Preventing Task Memorization:** Since each of the 40 tasks yields ~22 overlapping 4-turn windows in `unsloth_sft_train.jsonl` (and the same 40 tasks appear in `unsloth_sft_val.jsonl`!), how should we re-split train/val by `task_id` and expand coverage using the gold patches in `tasks.jsonl` without data leakage?
