# Seven Hard Negative Constraints: Engineering Proofs & Failure Post-Mortems

Every constraint in this document was derived from concrete empirical failures observed on Kaggle L4 evaluation runs, local container audits, or direct inspection of the `models/gemma-4-31b-it-qat-w4a16-ct/` checkpoint. Consultants reviewing this package **must not** recommend violating any of the seven rules below.

---

## Constraint 1: NO `run_command` or Raw Shell Execution (Strictly 5-Skill + 5-Tool Contract)

### The Rule
Never attach `run_command`, `get_code_neighbors`, `search_similar_code`, or `get_code_subgraph` in `submissions/track1_live/agent.yaml`, and never synthesize raw bash/shell trajectories (`run_command`) in Track 2 SFT data. The agent operates strictly with:
- **5 Direct Tools**: `read_file`, `edit_file`, `write_file`, `get_status`, `submit_patch`
- **5 Pre-Installed Skills** (via `run_skill_script`): `fast-grep` (`grep.py`), `code-map` (`map.py`), `code-oracle` (`oracle.py`), `repro-check` (`check.py`), and `test-gate` (`gate.py`)

### Three Fatal Failure Modes of Raw `run_command` on 4-Bit Gemma 4
1. **300-Second Full-Suite Pytest Hangs (Exit Code `124`)**:
   When given raw shell access (`run_command`), 4-bit quantized models routinely invoke bare `pytest` or broad test directories on large repositories (`fastapi`, `rich`), triggering `300s` subprocess timeouts (`exit_code = 124`) that exceed the `270s` task budget (`eval_config.yaml:max_time_seconds: 270`) and kill the entire episode.
2. **`/workspace` Untracked File `git diff` Corruption**:
   Container A extracts the final submission patch by executing `git add -N . && git diff HEAD` inside `/workspace`. Whenever an agent uses `run_command` to write a reproduction script (e.g., `cat << 'EOF' > repro.py`) inside `/workspace` and forgets to delete it before calling `submit_patch` (or hits the budget ceiling), `git add -N .` sweeps the untracked file into `agent.patch`, causing patch rejection or import pollution in Container B.
3. **Multi-Line Bash Heredoc & Quote Escaping Crashes**:
   Passing multi-line Python snippets inside `run_command(command="python3 -c \"...\"")` or bash heredocs forces the 4-bit model to double-escape quotes, backslashes, and newlines inside tool-call arguments. Unescaped newlines inside string arguments trigger upstream `json.loads` crashes in LiteLLM (`lite_llm.py:1730`), terminating the turn.

### How `repro-check` and `test-gate` Safely Replace Raw Shell
- **`repro-check` (`check.py`)**: Executes reproduction scripts exclusively inside an isolated `/tmp` directory (never `/workspace`), strips accidental markdown code fences, enforces a `15s` process-group timeout (`os.killpg`) and `1 GB` RAM cap, rejects assertion-free scripts with exit code `1` (`category = "missing_assertion"`), and prints structured character/hex/dict diffs.
- **`test-gate` (`gate.py`)**: Resolves and runs only distance-1 neighbor regression `pytest` nodes under a hard timeout, provides a read-only `git diff` viewer, distinguishes pre-fix baseline test conflicts from true regressions, and blocks edits to `tests/*`.

### Empirical Refutation of the "`run_command` Caused `0.03` / `0.00`" Fallacy
Earlier external commentary speculated that withholding `run_command` caused our historical `0.03` (Ref `56765397`) or `0.00` (Ref `56810465`) scores. That claim is **empirically false**:
1. Across all 95 surviving cloud traces (`cloud_results/results/traces/trace_*.json`), there are **zero** `run_command` missing-tool errors; `run_skill_script` executed natively and returned real skill stdout (`trace_fastapi_14962.json:36-60`).
2. Submission Ref **`56883026`** (Oct 6) shipped our exact 5-Skill + 5-Tool contract with **zero `run_command`** and scored **`0.13`** on the Kaggle Public Leaderboard, outperforming `0.08`–`0.12` starter baselines that attach all 9 tools.

---

## Constraint 2: NO Multi-Agent or Sub-Agent Delegation Chains

### The Rule
Never split the agent into multi-agent hierarchies (`Scout -> Coder -> Breaker`, `Supervisor -> Worker`, or a separate `code_analyzer` sub-agent). The submission must remain a single monolithic agent (`name: main`).

### Engineering Proof
In the Google ADK `swegemma` harness, `max_tool_calls: 40` (`submissions/track1_live/eval_config.yaml:4`) is a **single task-global counter** shared across all agents in the session, with **zero per-sub-agent rationing or call cap**. When we tested a multi-agent pipeline (commit `6868f24`, reverted in `c01058c`), the exploratory sub-agent consumed 30–40 tool calls before returning control, leaving the main agent with `0` calls to run `edit_file` or `submit_patch`.

---

## Constraint 3: NO BitsAndBytes NF4 (`unsloth-bnb-4bit` or `load_in_4bit=True` on `w4a16-ct`)

### The Rule
Never train a LoRA adapter on `unsloth/gemma-4-31B-it-unsloth-bnb-4bit`, and never pass `load_in_4bit=True` when loading `google/gemma-4-31b-it-qat-w4a16-ct`.

### Engineering Proof & Oct-4 `0.00` Post-Mortem
- The Kaggle evaluation server runs vLLM against **`google/gemma-4-31b-it-qat-w4a16-ct`**, whose `config.json` specifies:
  - `quant_method: "compressed-tensors"`
  - `format: "pack-quantized"`
  - `num_bits: 4`, `group_size: 32`, `symmetric: true`, `type: "int"` (Quantization-Aware Trained INT4 packed integer grid).
- By contrast, `unsloth/gemma-4-31B-it-unsloth-bnb-4bit` uses **BitsAndBytes NormalFloat4 (NF4)** asymmetric blockwise quantization derived from post-training quantization of BF16 weights.
- On Oct 4 (Submission Ref `56810465`), mounting a 90 MB LoRA trained on `unsloth-bnb-4bit` onto Kaggle's `w4a16-ct` vLLM server caused immediate activation scale mismatch and logit collapse (`111/129` tasks recorded `tool_calls == 0`, `77/95` traces produced `0` completion tokens, scoring `0.00`).
- Furthermore, passing `load_in_4bit=True` when loading `google/gemma-4-31b-it-qat-w4a16-ct` in Unsloth triggers a quantizer collision (`ValueError` or silent BitsAndBytes re-quantization of already `pack-quantized` tensors).
- **Mandatory Loading Contract**:
  - Primary: `FastModel.from_pretrained("google/gemma-4-31b-it-qat-w4a16-ct", max_seq_length=3072, dtype=torch.bfloat16, load_in_4bit=False, use_exact_model_name=True, text_only=False)`.
  - Fallback (only if PyTorch/Unsloth blocks gradient backpropagation through `Int4PackedLinear`): Load the official QAT unquantized twin `google/gemma-4-31B-it-qat-q4_0-unquantized` with `load_in_4bit=True`, and rewrite `base_model_name_or_path` to `"google/gemma-4-31b-it-qat-w4a16-ct"` in `adapter_config.json` on export.

---

## Constraint 4: NO Gemma 2/3 `<start_of_turn>` Tags, Symmetric `<|tool_call|>`, or `<|thought|>` Tokens

### The Rule
Never format SFT strings manually with `<start_of_turn>`, `<end_of_turn>`, symmetric `<|tool_call|>...<|tool_call|>`, or `<|thought|>` / `<thought|>` tags, and never use `train_on_responses_only("<|turn>model\n")`.

### Engineering Proof (`models/gemma-4-31b-it-qat-w4a16-ct/tokenizer.json` & `chat_template.jinja`)
Direct inspection of the local `tokenizer.json` (`vocab_size = 262,144`) proves that Gemma 4 uses an asymmetric control token vocabulary completely distinct from Gemma 2/3:

| Token ID | Literal String | Role in `tokenizer_config.json` / `chat_template.jinja` |
| :--- | :--- | :--- |
| `46` / `47` | `<|tool>` / `<tool|>` | Tool declaration block opener / closer (`sotd_token` / `eotd_token`) |
| `48` / `49` | `<|tool_call>` / `<tool_call|>` | Tool call opener / closer (`stc_token` / `etc_token` — **asymmetric!**) |
| `50` / `51` | `<|tool_response>` / `<tool_response|>` | Tool response opener / closer (`str_token` / `etr_token`) |
| `52` | `<|"|>` | String delimiter inside tool declarations and tool-call arguments (`escape_token`) |
| `98` | `<|think|>` | System prompt thinking-mode activation token (`think_token`) |
| `100` / `101` | `<|channel>` / `<channel|>` | Reasoning channel opener / closer (`soc_token` / `eoc_token`) |
| `105` / `106` | `<|turn>` / `<turn|>` | Turn opener / closer (`sot_token` / `eot_token`) |

- **No `<|thought|>` Token Exists**: Reasoning blocks are rendered strictly as `<|channel>thought\n...<channel|>`.
- **Single-Turn Multi-Step Continuation & Turn 2+ Prefix Asymmetry**: In `chat_template.jinja`, an entire multi-step tool loop stays inside a single open `<|turn>model\n` turn. On Turn 2+ (after `tool_response`), line 388 appends `<|channel>thought\n` to `prefix_text` (`add_generation_prompt=True`), so `completion_text` begins directly with the thought text. Substring splitting on `<|turn>model\n` fails on every Turn 2+ window; **prefix-delta masking** (`full_text[len(prefix_text):]`) with `enable_thinking=True, preserve_thinking=True` is mandatory.

---

## Constraint 5: NO `max_seq_length > 3072` or `eval_strategy="steps"` on a Single 24GB L4 GPU

### The Rule
Never set `max_seq_length > 3072`, and never enable mid-training evaluation (`eval_strategy="steps"` or `eval_strategy="epoch"`) on a single 24GB NVIDIA L4 (`22.494 GiB` usable VRAM). Lock `max_seq_length=3072` and `eval_strategy="no"`.

### Exact VRAM & Step-5 Logit OOM Math
- During training with `max_seq_length=3072`, `per_device_train_batch_size=1`, `gradient_accumulation_steps=8`, and `paged_adamw_8bit`, Unsloth uses fused chunked cross-entropy (`Apple Cut Cross-Entropy`), avoiding full logit materialization:
  - Base `w4a16-ct` weights (60 INT4 language layers + BF16 vision tower + embeddings): **`17.77 GiB`**
  - LoRA parameters (`18.12M` BF16) + BF16 gradients: **`0.07 GiB`**
  - 8-bit Paged AdamW optimizer states: **`0.04 GiB`**
  - Gradient-checkpointed activations + Cut Cross-Entropy workspace at `seq_len=3072`: **`1.60 GiB`**
  - PyTorch CUDA context & Triton kernel cache reserve: **`0.85 GiB`**
  - **Total Training Peak VRAM**: **`20.31 GiB`** (`+2.18 GiB` safety margin under `22.494 GiB`).
- If `eval_strategy="steps"` is enabled, Hugging Face `Trainer.evaluate()` bypasses Unsloth's training-only fused cross-entropy kernel and materializes the full FP32 logit tensor `[batch=1, seq_len=3072, vocab=262144]`:
  $$\text{Eval Logits VRAM} = 1 \times 3072 \times 262,144 \times 4\text{ bytes} = 3,221,225,472\text{ bytes} = 3.00\text{ GiB}$$
  Together with the FP16/BF16 lm_head output buffer (`1.50 GiB`) and `.float()` cast + reduction buffers (`3.00 GiB`), the evaluation forward pass spikes by **`+7.50 GiB`**, driving peak VRAM to **`27.81 GiB > 22.494 GiB`** and crashing with `CUDA out of memory` at Step 5.
- Because `100%` of our 885 training windows are `<= 2,822` tokens (`Max = 2,822`, `P90 = 1,686`), `max_seq_length=3072` achieves **zero truncation** while preserving `+2.18 GiB` of VRAM headroom.

---

## Constraint 6: NO MLP Layers, Vision Tower Layers, `k_proj`, or NEFTune in LoRA; Strictly 2-File Export

### The Rule
1. Lock LoRA targets to `target_modules=["q_proj", "v_proj", "o_proj"]` (`r=8, lora_alpha=16, lora_dropout=0.0, bias="none"`) with `finetune_vision_layers=False, finetune_language_layers=True, finetune_attention_modules=True, finetune_mlp_modules=False`.
2. Lock `neftune_noise_alpha=None`.
3. Export **only two files** into `submissions/track1_live/adapters/main_lora/`: `adapter_config.json` and `adapter_model.safetensors` (**zero tokenizer files**).

### Engineering Proofs
- **Why Omit `k_proj` (`attention_k_eq_v=True`)**: Binary header inspection of `models/gemma-4-31b-it-qat-w4a16-ct/model.safetensors` proves that across the 60 language layers, the 50 sliding-window attention layers have `q_proj, k_proj, v_proj, o_proj`, whereas the **10 global full-attention layers** set `attention_k_eq_v=True` (reusing `k_proj` as values $K=V$ and omitting `v_proj`). Targeting `["q_proj", "v_proj", "o_proj"]` adapts `60 (q_proj) + 50 (v_proj) + 60 (o_proj) = 170` linear modules (`340` LoRA A/B tensors, `18,124,800` trainable params = `34.57 MiB` BF16), leaving `k_proj` cleanly unperturbed on the 10 shared-$K/V$ global layers.
- **Why Freeze MLPs & Vision Tower**: Adapting `gate_proj, up_proj, down_proj` across 60 layers balloons trainable parameters by `>3.5x`, increases activation memory beyond the single-L4 ceiling, and causes catastrophic memorization of teacher repository text on small trajectory datasets ($N < 1,000$). Passing `text_only=False` + `finetune_vision_layers=False` preserves the `base_model.model.language_model.layers.{i}...` key hierarchy expected by vLLM while ensuring zero `vision_tower` LoRA keys are emitted.
- **Why Disable NEFTune (`neftune_noise_alpha=None`)**: Adding uniform embedding noise degrades exact control-token generation (`<|tool_call>`, `<|"|>`, `<tool_call|>`) on 4-bit quantized models where attention routing relies on sharp token boundaries.
- **Why Strip All Tokenizer Files on Export**: `scripts/check_submission.py` (`g_disallowed_extensions`) hard-fails if `tokenizer.model` or extraneous artifacts appear in `submission.zip`, and vLLM's LoRA loader only reads `adapter_config.json` + `adapter_model.safetensors`.

---

## Constraint 7: NO Training on `tasks.jsonl` Gold Patches (Contamination Firewall)

### The Rule
Never read, parse, or convert the `patch` or `test_patch` columns of `tasks.jsonl` into synthetic SFT training examples or prompt hints.

### Engineering Proof
The 129 tasks in `tasks.jsonl` are the public/local evaluation benchmark. Training a LoRA on gold patches extracted from `tasks.jsonl` teaches the adapter to memorize exact diff hunks for those 129 issues rather than generalizable 5-skill localization and verification behavior, causing immediate collapse on unseen private evaluation tasks. Furthermore, `scripts/build_unsloth_dataset.py` must split train and validation sets strictly by `task_id` (`set(train_tasks) & set(val_tasks) == set()`) so validation metrics measure true cross-issue generalization.
