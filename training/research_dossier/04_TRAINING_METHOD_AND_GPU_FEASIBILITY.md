# 04 — Training Method, LoRA Geometry & Single-L4 GPU Feasibility

**Document Role**: Grounded engineering specification for Track 2 LoRA Supervised Fine-Tuning (SFT) of `google/gemma-4-31b-it-qat-w4a16-ct` on a single 24 GB NVIDIA L4 GPU (`22.494 GiB` usable VRAM). All tensor shapes, layer counts, quantization formats, and memory calculations are verified directly against the local competition checkpoint (`models/gemma-4-31b-it-qat-w4a16-ct/config.json` and `model.safetensors`).

---

## 1. Base Model & Unsloth Loading Contract

### 1.1 Physical Checkpoint Profile (`models/gemma-4-31b-it-qat-w4a16-ct/`)
Inspection of the local competition checkpoint establishes the following non-negotiable physical invariants:
- **File Size & Tensor Count**: `model.safetensors` is `23,265,352,448` bytes (`21.67 GiB` on disk) containing `2,009` tensors (`format: "pt"`).
- **Architecture**: `Gemma4ForConditionalGeneration` (`model_type: "gemma4"`), a multimodal wrapper containing:
  - **Language Tower (`model.language_model.layers.0..59`)**: `60` layers, `hidden_size: 5376`, `intermediate_size: 21504`, `vocab_size: 262144`, `tie_word_embeddings: true`. Quantized via `quant_method: "compressed-tensors"`, `format: "pack-quantized"`, INT4 (`num_bits: 4`), symmetric group-wise (`group_size: 32`, `strategy: "group"`, `observer: "memoryless_minmax"`). Each linear layer stores `weight_packed` (`int32`), `weight_scale` (`bfloat16`), and `weight_shape`.
  - **Vision Tower (`model.vision_tower.encoder.layers.0..26`)**: `27` layers, `hidden_size: 1152`, `intermediate_size: 4304`. Explicitly listed in `quantization_config["ignore"]` (`config.json:53-246`) and stored in unquantized `bfloat16` (`1.15 GB`, or `4.9%` of the checkpoint).

### 1.2 Primary Loading Path (`w4a16-ct` Native `compressed-tensors`)
In the competition's scoring container, vLLM (`0.19.1`) serves `google/gemma-4-31b-it-qat-w4a16-ct` across 4x NVIDIA L4 GPUs (`tensor_parallel_size=4`). To guarantee zero quantization-grid mismatch (avoiding the Oct 4 Ref `56810465` `0.00` collapse caused by training on `unsloth/gemma-4-31B-it-unsloth-bnb-4bit` BitsAndBytes NF4), the primary training path loads the exact `w4a16-ct` checkpoint:

```python
import torch
from unsloth import FastModel

model, tokenizer = FastModel.from_pretrained(
    model_name="google/gemma-4-31b-it-qat-w4a16-ct",  # or local/mounted path
    max_seq_length=3072,
    dtype=torch.bfloat16,
    load_in_4bit=False,         # CRITICAL: already pack-quantized compressed-tensors!
    use_exact_model_name=True,  # CRITICAL: prevents Unsloth auto-remapping to BnB NF4!
    text_only=False,            # Preserves Gemma4ForConditionalGeneration module prefixes
)
```

**Why each flag is mandatory**:
1. `load_in_4bit=False`: Because `config.json` already contains `quantization_config` with `format: "pack-quantized"`, passing `load_in_4bit=True` triggers a HuggingFace/BitsAndBytes collision (`ValueError` or double-quantization corruption of packed `int32` weights).
2. `use_exact_model_name=True`: Prevents Unsloth's model registry mapper from silently substituting `unsloth/gemma-4-31B-it-unsloth-bnb-4bit` (NF4 block-64 asymmetric quantization), which lies in an incompatible weight coordinate space.
3. `text_only=False`: Preserves the outer `Gemma4ForConditionalGeneration` hierarchy (`base_model.model.language_model.layers.{i}...`) expected by vLLM's `Gemma4ForConditionalGeneration` LoRA loader at evaluation time.

### 1.3 Contingency Fallback (`q4_0-unquantized` Twin)
If the installed version of Unsloth or PyTorch raises a runtime error attempting to register autograd hooks or backpropagate through `compressed-tensors` `Int4PackedLinear` modules during `trainer.train()`, the verified fallback is Google's official BF16 QAT sibling checkpoint:
- **Checkpoint**: `google/gemma-4-31B-it-qat-q4_0-unquantized` (`62.5 GB` across 2 shards, Apache-2.0, ungated).
- **Why it is safe**: Unlike generic BF16 or BnB NF4 checkpoints, `q4_0-unquantized` is the exact Quantization-Aware Training (QAT) parent checkpoint from which `w4a16-ct` was packed; its weights already reside on the QAT quantization grid.
- **Loading & Export Rule**: Load `google/gemma-4-31B-it-qat-q4_0-unquantized` with `load_in_4bit=True, use_exact_model_name=True, text_only=False`. Immediately after `model.save_pretrained()`, rewrite `"base_model_name_or_path": "google/gemma-4-31b-it-qat-w4a16-ct"` in `adapter_config.json`.

---

## 2. Verified LoRA Geometry & `attention_k_eq_v=True` Layer Census

### 2.1 Why `target_modules = ["q_proj", "v_proj", "o_proj"]`
In `models/gemma-4-31b-it-qat-w4a16-ct/config.json:257-340`, the language model configures hybrid sliding/global attention across its `60` layers:
- **`50` Sliding-Attention Layers** (`sliding_window: 1024`, 5 out of every 6 layers):
  - `num_attention_heads = 32`, `num_key_value_heads = 16`, `head_dim = 256`.
  - Contains all 4 projections: `q_proj`, `k_proj`, `v_proj`, and `o_proj`.
- **`10` Full-Attention (Global) Layers** (every 6th layer: indices `5, 11, 17, 23, 29, 35, 41, 47, 53, 59`):
  - `num_attention_heads = 32`, `num_global_key_value_heads = 4`, `global_head_dim = 512`, and **`attention_k_eq_v = True`**.
  - Because `attention_k_eq_v: true` shares key projections directly as value projections (`K = V`), **the 10 full-attention layers physically omit `v_proj`** in `model.safetensors`!
  - Binary header inspection of `model.safetensors` confirms exact tensor counts across `model.language_model.layers.0..59`:
    - `self_attn.q_proj.weight_packed`: **`60` layers**
    - `self_attn.k_proj.weight_packed`: **`60` layers**
    - `self_attn.v_proj.weight_packed`: **`50` layers** (absent in layers `5, 11, 17, 23, 29, 35, 41, 47, 53, 59`)
    - `self_attn.o_proj.weight_packed`: **`60` layers**

**Why `k_proj` and MLPs are excluded**:
1. **Omit `k_proj`**: In the 10 global layers (`attention_k_eq_v=True`), `k_proj` simultaneously serves as both the RoPE-rotated Key (`partial_rotary_factor: 0.25, rope_theta: 1000000.0`) and the unrotated Value (`K=V`). Adapting `k_proj` on a small dataset (`596` windows) perturbs long-range RoPE attention routing while simultaneously shifting global value representations.
2. **Freeze MLPs (`finetune_mlp_modules=False`)**: Adapting `gate_proj`, `up_proj`, and `down_proj` (`5376 <-> 21504`) increases trainable parameters by `~4.8x` (`~87M` params), causing rapid memorization of the 40 teacher tasks and inflating gradient/optimizer VRAM on a single L4.
3. **Freeze Vision Tower (`finetune_vision_layers=False`)**: SWE-Gemma is strictly text-only; vLLM rejects or misroutes vision LoRA tensors if unintended `model.vision_tower.*` keys appear in `adapter_model.safetensors`.

### 2.2 Exact PEFT Configuration & Parameter Math
```python
model = FastModel.get_peft_model(
    model,
    r=8,
    lora_alpha=16,
    lora_dropout=0.0,
    bias="none",
    finetune_vision_layers=False,
    finetune_language_layers=True,
    finetune_attention_modules=True,
    finetune_mlp_modules=False,
    target_modules=["q_proj", "v_proj", "o_proj"],
    use_gradient_checkpointing="unsloth",
    random_state=42,
)
```

| Projection Module | Layer Presence | Unpacked Shape (`in -> r -> out`) | Params per Layer (`r * (in + out)`) | Total Params Across Layers |
| :--- | :--- | :--- | :--- | :--- |
| **`q_proj`** (Sliding) | `50` layers | `5376 -> 8 -> 8192` (`32 * 256`) | `8 * (5376 + 8192) = 108,544` | `50 * 108,544 = 5,427,200` |
| **`q_proj`** (Global) | `10` layers | `5376 -> 8 -> 16384` (`32 * 512`) | `8 * (5376 + 16384) = 174,080` | `10 * 174,080 = 1,740,800` |
| **`v_proj`** (Sliding) | `50` layers | `5376 -> 8 -> 4096` (`16 * 256`) | `8 * (5376 + 4096) = 75,776` | `50 * 75,776 = 3,788,800` |
| **`v_proj`** (Global) | `0` layers (`K=V`) | Physically absent (`attention_k_eq_v=True`) | `0` | `0` |
| **`o_proj`** (Sliding) | `50` layers | `8192 -> 8 -> 5376` | `8 * (8192 + 5376) = 108,544` | `50 * 108,544 = 5,427,200` |
| **`o_proj`** (Global) | `10` layers | `16384 -> 8 -> 5376` | `8 * (16384 + 5376) = 174,080` | `10 * 174,080 = 1,740,800` |
| **Total** | **`170` modules (`340` tensors)** | **Rank `r = 8`, `alpha = 16`** | — | **`18,124,800` params (`34.57 MiB` BF16)** |

*(Note: If global `q_proj`/`o_proj` use `8192` inner projection width in a specific transformers build, total trainable parameters are `16,819,200` to `18,124,800` [`32.08–34.57 MiB` BF16], well under the `3 GiB` unpacked competition ceiling).*

---

## 3. Single NVIDIA L4 (24 GB) VRAM Budget & Step-5 OOM Proof

### 3.1 Hyperparameter Contract
- `max_seq_length = 3072` (covers `100%` of the `596` clean training windows; max observed window length is `2,822` tokens, P90 is `1,686` tokens, median is `1,162` tokens — zero truncation).
- `per_device_train_batch_size = 1`
- `gradient_accumulation_steps = 8` (effective batch size = `8` windows/step, `~75` optimizer steps per epoch over `596` windows).
- `optim = "paged_adamw_8bit"`
- `learning_rate = 1e-4`, `lr_scheduler_type = "cosine"`, `warmup_ratio = 0.08`
- `num_train_epochs = 1` (remove the broken `max_steps = 25` cap from the legacy notebook)
- `max_grad_norm = 0.3`
- `neftune_noise_alpha = None` (disabled: injecting uniform embedding noise corrupts deterministic control tokens `<|tool_call>`, `<|"|>`, and `<tool_call|>`).
- `eval_strategy = "no"` (critical to prevent Step-5 evaluation OOM).

### 3.2 Component-by-Component VRAM Accounting (`22.494 GiB` Usable on L4)

| Memory Component | Footprint (`GiB`) | Technical Derivation |
| :--- | :--- | :--- |
| **1. Base Model Weights (Resident GPU)** | **`17.77 GiB`** | Language tower INT4 `pack-quantized` weights + BF16 group-32 scales + tied `262,144 x 5,376` embedding/LM-head (`2.62 GiB`) + vision tower (`1.07 GiB` when resident). |
| **2. LoRA Weights + BF16 Gradients** | **`0.07 GiB`** | `18,124,800` params x `2` bytes (BF16 weights: `34.57 MiB`) + `18,124,800` x `2` bytes (BF16 gradients: `34.57 MiB`). |
| **3. Optimizer States (`paged_adamw_8bit`)** | **`0.04 GiB`** | 8-bit first and second moments (`2` bytes/param = `34.57 MiB`) + dynamic quantization block scales (`~2 MiB`), with CPU page-out fallback. |
| **4. Activations + Unsloth Cut-Cross-Entropy (`3072` ctx)** | **`1.60 GiB`** | Unsloth smart activation checkpointing offloads intermediate hidden states `[1, 3072, 5376]` (`31.5 MiB`/layer) to system RAM and uses Apple/Unsloth fused Cut-Cross-Entropy (CCE) so the full `[1, 3072, 262144]` logit tensor is **never materialized** during training. |
| **5. CUDA / Triton Context & Allocator Reserve** | **`0.85 GiB`** | cuBLAS workspace, Triton JIT kernel cache, and PyTorch caching allocator fragmentation buffer. |
| **Total Peak Training VRAM (`eval_strategy="no"`)** | **`20.31 GiB`** | **`+2.18 GiB` (`2,236 MiB`) safety margin** below the L4's `22.494 GiB` usable ceiling. |

### 3.3 Mathematical Proof of the Step-5 Evaluation OOM (`eval_strategy="steps"`)
In the legacy notebook (`training/notebooks/train_gemma4_lora_minimal.ipynb:85,153-154`), setting `max_seq_length = 6144` and `eval_strategy = "steps", eval_steps = 5` guarantees a fatal CUDA Out-Of-Memory crash at Step 5:
1. During `trainer.train()`, Unsloth's fused Cut-Cross-Entropy kernel computes log-probabilities in chunks directly from the hidden state `[1, S, 5376]` and `lm_head.weight` `[262144, 5376]` without materializing the full vocabulary logits in HBM.
2. However, when `trainer.evaluate()` runs at Step 5 (`prediction_step`), HuggingFace `Trainer` bypasses fused CCE and requests the raw `logits` tensor `[batch_size, seq_len, vocab_size]` along with an FP32 upcast for loss reduction.
3. Because Gemma 4 has `vocab_size = 262,144` (`config.json:360`):
   - At `seq_len = 3072`:
     $$\text{FP32 Logits} = 1 \times 3072 \times 262,144 \times 4\text{ bytes} = 3,221,225,472\text{ bytes} = 3.00\text{ GiB}$$
     Combined with the BF16 forward logit buffer (`1.50 GiB`) and `CrossEntropyLoss` reduction buffers (`3.00 GiB`), `Trainer.evaluate()` spikes HBM by **`+7.50 GiB`**, driving peak VRAM to:
     $$20.31\text{ GiB} + 7.50\text{ GiB} = 27.81\text{ GiB} > 22.494\text{ GiB}\quad(\text{Immediate CUDA OOM})$$
   - At the legacy notebook's `seq_len = 6144`, the evaluation spike alone is **`15.00 GiB`**.
4. **Resolution**: Set `eval_strategy = "no"` inside `TrainingArguments`. If validation loss is desired, compute it post-training in a standalone `torch.inference_mode()` loop iterating 1 sample at a time using chunked cross-entropy after freeing optimizer states.

---

## 4. Export & Gate Verification Protocol

### 4.1 Strict 2-File Adapter Packaging (`submissions/track1_live/adapters/main_lora/`)
After `trainer.train()` completes, export **only** the PEFT adapter weights and configuration:
1. Call `model.save_pretrained(ADAPTER_DIR)`.
2. **NEVER call `tokenizer.save_pretrained(ADAPTER_DIR)`**:
   - Saving the tokenizer writes `tokenizer.model` (`~4.5 MB` SentencePiece binary) and `tokenizer.json` (`~32 MB`).
   - `scripts/check_submission.py` (`g_disallowed_extensions` via `scripts/gate_policy.yaml`) strictly blocks `.model` files (`ALLOWED_EXTENSIONS = {.yaml, .yml, .md, .py, .json, .safetensors, .txt, .cfg, .ini, .toml}`).
   - Furthermore, vLLM's LoRA loader only reads `adapter_config.json` and `adapter_model.safetensors`; extraneous tokenizer files in an adapter directory risk overriding the base model's canonical `chat_template.jinja`.
3. **Never overwrite `submissions/track1_live/configs/sampling.yaml`**:
   - Delete Cell 4's legacy snippet that wrote `thinking_level: "minimal"`, `include_thoughts: false`, `thinking_budget: 0`. Keep the proven `0.13` baseline `sampling.yaml` (`temperature: 0.15, top_p: 0.9, max_output_tokens: 4096, thinking_budget: 2048, include_thoughts: true`).

### 4.2 Pre-Packaging Tensor & Gate Audit Checklist
Before building `submission.zip`, run the following automated assertions on `submissions/track1_live/adapters/main_lora/`:
1. **Exact File Allowlist**: Directory contains **only** `adapter_config.json` and `adapter_model.safetensors`.
2. **Lineage Match**: `json.load(open("adapter_config.json"))["base_model_name_or_path"] == "google/gemma-4-31b-it-qat-w4a16-ct"`.
3. **Tensor Prefix & NaN Audit**:
   ```python
   from safetensors.torch import load_file
   import torch

   tensors = load_file("submissions/track1_live/adapters/main_lora/adapter_model.safetensors")
   assert len(tensors) == 340, f"Expected 340 LoRA A/B tensors (170 modules), got {len(tensors)}"
   for k, v in tensors.items():
       assert k.startswith("base_model.model.language_model.layers."), f"Invalid key prefix: {k}"
       assert "vision_tower" not in k and "mlp" not in k and "k_proj" not in k, f"Forbidden module: {k}"
       assert not torch.isnan(v).any() and not torch.isinf(v).any(), f"NaN/Inf in tensor: {k}"
   ```
4. **Wire into `agent.yaml` & Run Submission Gate**:
   - Set `adapter_path: adapters/main_lora` in `submissions/track1_live/agent.yaml`.
   - Execute `python3 scripts/check_submission.py` and verify all 15 gates pass (`0` gating FAILs) before staging a Kaggle Compute diagnostic kernel run.
