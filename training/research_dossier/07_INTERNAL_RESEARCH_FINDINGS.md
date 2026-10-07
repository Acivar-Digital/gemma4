# 07. Internal Research Findings (`workflowz` Deep-Dive Audit)

While preparing this packet for external consultant review, our internal 4-subagent research pool audited the repository's existing dataset (`training/sft_data/unsloth_sft_train.jsonl`), dataset builder (`scripts/build_unsloth_dataset.py`), training notebook (`training/notebooks/train_gemma4_lora_minimal.ipynb`), and local model checkpoint (`models/gemma-4-31b-it-qat-w4a16-ct/`).

Below are the empirical findings across **Method** and **Data**.

---

## Part 1: How to Make LoRA Training Effective via METHOD

### 1. Fix the Fatal Chat-Template & Special-Token Mismatch
- **Discovery:** `models/gemma-4-31b-it-qat-w4a16-ct/tokenizer_config.json` defines Gemma 4's native special tokens:
  - Turn delimiters: `sot_token = "<|turn>"`, `eot_token = "<turn|>"`
  - Tool call delimiters (asymmetric): `stc_token = "<|tool_call>"`, `etc_token = "<tool_call|>"`
  - Tool response delimiters (asymmetric): `str_token = "<|tool_response>"`, `etr_token = "<tool_response|>"`
- **Current Defect:** `scripts/build_unsloth_dataset.py:306-324` hardcodes Gemma 2/3 tags (`<start_of_turn>user\n...<end_of_turn>`, `<start_of_turn>model\n...<end_of_turn>`) and symmetric `<|tool_call|>...<|tool_call|>`. **0 of 885 rows** in `unsloth_sft_train.jsonl` contain valid Gemma 4 `<tool_call|>` closing tokens.
- **Required Fix:** Render all trajectories via the official Gemma 4 `tokenizer.apply_chat_template(...)` and mask loss strictly on the final assistant turn (`<|turn>model\n`).

### 2. Exact Unsloth QAT Loading & Key-Prefix Contract on 1× 24GB L4
- **Two Validated Loading Paths:**
  1. **Path A (`google/gemma-4-31B-it-qat-q4_0-unquantized`):** De-quantized BF16 weights (62.55 GB on disk) whose values lie on Google's symmetric `group_size=32` INT4 QAT grid. Requires `load_in_4bit=True` on a 24GB L4 (~16.5 GB base VRAM).
  2. **Path B (`google/gemma-4-31b-it-qat-w4a16-ct` with `transformers >= 5.8` + `compressed-tensors`):** Unsloth's `Int4PackedLinear` loads the 23.27 GB packed INT4 checkpoint directly and decodes via Triton kernels with **zero NF4 re-quantization** and zero `base_model_name_or_path` mismatch.
- **Mandatory Flags (`FastLanguageModel.from_pretrained` & `FastModel.get_peft_model`):**
  - `use_exact_model_name=True`: Blocks Unsloth's `mapper.py` from remapping to non-QAT `unsloth/gemma-4-31B-it-unsloth-bnb-4bit`.
  - `dtype=torch.bfloat16`: Mandatory on L4 (SM 8.9); `float16` overflows Gemma 4's activation dynamic range.
  - `text_only=False` in `from_pretrained` + `finetune_vision_layers=False` in `get_peft_model`:
    - Setting `text_only=True` strips `.language_model.` from weight keys, breaking vLLM.
    - Leaving `finetune_vision_layers=True` attaches LoRA to `model.vision_tower.*` (81 modules, 1.49M params), crashing vLLM at startup.

### 3. Capacity Math & Regularized Hyperparameters
- **Architecture:** Gemma 4 31B has 60 layers (50 sliding-attention layers + 10 full-attention layers where `attention_k_eq_v=True`, meaning those 10 layers have no `v_proj` tensor).
- **Trainable Parameters (`r=8` on `q_proj, v_proj, o_proj`):** Exactly **18,124,800 parameters** (34.57 MiB in BF16; 340 weight tensors across 170 modules).
- **Overfitting Ratio:** In the current 885-sample dataset, there are only **90,853 supervised assistant tokens** (~200.8 trainable parameters per supervised token). Training for $>1$ epoch over 22.1× repeated task windows rapidly memorizes the 40 task prompts.
- **Recommended Schedule:**
  - `max_seq_length = 3072` (covers 100% of $\le 2,822$-token windows; ~18.8 GB peak VRAM on 24GB L4, leaving 5.2 GB headroom).
  - `per_device_train_batch_size = 1`, `gradient_accumulation_steps = 8` (effective batch size 8).
  - `learning_rate = 1e-4` (safer than `2e-4` for preserving base Python syntax), `lr_scheduler_type = "cosine"`, `warmup_ratio = 0.05`, `weight_decay = 0.05`, `lora_dropout = 0.05`.
  - **1.0 to 1.5 epochs** (~85–130 optimization steps; remove the `max_steps=25` truncation bug).

### 4. vLLM Adapter Packaging Contract
- **Exclude All Tokenizer Files:** Do **NOT** call `tokenizer.save_pretrained(ADAPTER_DIR)`.
  - `ALLOWED_SUBMISSION_EXTENSIONS` rejects `.model` files.
  - vLLM loads the tokenizer strictly from `--model`, never `--lora-modules`.
  - Ryan Holbrook's working 0.12 LB `main_lora` directory contains **only 2 files**: `adapter_config.json` and `adapter_model.safetensors`.
- **Sanitize `adapter_config.json`:**
  - `base_model_name_or_path`: `"google/gemma-4-31b-it-qat-w4a16-ct"`
  - `target_modules`: `["q_proj", "v_proj", "o_proj"]` (clean JSON list, never regex string; if Unsloth uses a regex internally to exclude vision layers, convert or post-filter vision tensors before saving).

---

## Part 2: How to Make LoRA Training Effective via DATA

### 1. Purge the 289 Tool-Less Assistant Turns (32.7% of Current Train Set)
- **Discovery:** `extract_raw_trajectory` in `scripts/build_unsloth_dataset.py` separated reasoning messages from tool-call messages. As a result, **289 of 885 training rows (32.66%)** have `target_tools: []` (text-only assistant thoughts followed immediately by `<end_of_turn>`).
- **Impact:** Nearly a third of the dataset trains Gemma 4 to emit a single thought sentence and **terminate its turn without calling any tool**—explaining why fine-tuned models stop acting.
- **Fix:** Merge consecutive assistant thought + tool call steps into a single assistant turn (`<|thought>\n...<thought|><|tool_call>call:...<tool_call|><turn|>`), and drop all terminal/intermediate rows that lack a valid tool call.

### 2. Cure the 0% `run_command` & 64.3% `run_skill_script` Imbalance
- **Discovery:** Because `run_B39`/`run_B40` ran without `run_command`, the current 596 tool-bearing training rows contain:
  - `run_skill_script`: 383 (64.3%)
  - `read_file`: 113 (19.0%)
  - `edit_file`: 66 (11.1%)
  - `submit_patch`: 32 (5.4%)
  - `run_command`: **0 (0.0%)**
- **Fix:** Synthesize and validate **150–200 multi-turn decision windows** across the **37 unrepresented Tier-1 single-file tasks** (expanding coverage from 40 to all **77 Tier-1 solvable tasks**) demonstrating:
  1. `run_command`: heredoc `/tmp/repro.py` reproducing the issue.
  2. `edit_file`: minimal surgical fix.
  3. `run_command`: targeted `pytest <test_file> -k <pattern> -x -q` passing.
  4. `submit_patch`: clean submission after `git diff` verification.

### 3. Fix the 100% Train/Val Task Leakage
- **Discovery:** `scripts/build_unsloth_dataset.py:483-490` splits 80/20 across sliced windows rather than by `task_id`. All **40 unique tasks appear in both `unsloth_sft_train.jsonl` and `unsloth_sft_val.jsonl`**, making `eval_loss` blind to task memorization.
- **Fix:** Group strictly by `task_id` before splitting (e.g., 62 train tasks / 15 val tasks with **0% task overlap**).
