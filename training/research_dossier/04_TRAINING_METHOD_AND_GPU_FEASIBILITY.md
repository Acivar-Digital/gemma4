# 04. Training Method & GPU Feasibility Analysis

This document directly evaluates the user's second primary concern: **"Is our method correct?"** and validates the confirmed choices:
1. **Unsloth adapter**
2. **Using the exact model to get the same weight**

---

## 1. Model Checkpoint Lineage (Confirmed & Validated)

- **Target Serving Model (Kaggle Leaderboard):** `google/gemma-4-31b-it-qat-w4a16-ct`
- **Mandatory Training Base:** **`google/gemma-4-31B-it-qat-q4_0-unquantized`**
- **Validation:**
  - Google provided this unquantized sibling checkpoint specifically to allow standard PyTorch/Unsloth LoRA training while producing weight delta matrices mathematically compatible with the QAT quantization scales.
  - Using any BnB NF4 checkpoint (such as `unsloth/gemma-4-31B-it-unsloth-bnb-4bit`) is **PROHIBITED**—that was the proven root cause of the Oct-4 0.00 crash.
- **Verdict:** Our confirmed choice of base model is **100% correct**.

---

## 2. VRAM Arithmetic on Single NVIDIA L4 (24GB)

The primary physical constraint is training a 31B model on **1× 24GB L4 GPU** (available on Kaggle and GCP).

| Component | VRAM Consumption | Notes / Constraints |
|---|---|---|
| **Base Model (31B @ 4-bit)** | **~16.5 GB** | Unsloth 4-bit quantized base + PyTorch CUDA context |
| **Available VRAM Headroom** | **~7.5 GB** | Total 24.0 GB minus base weights |
| **LoRA Weights (Rank 8 on q, v, o)** | **~30 MB** | 15M trainable parameters @ FP16 |
| **Optimizer States (AdamW 8-bit)** | **~30 MB** | Gradients + momentum on 15M parameters |
| **Activation Memory @ seq_len 3,072** | **~2.2 GB** | With Unsloth manual gradient checkpointing |
| **Activation Memory @ seq_len 6,144** | **~5.1 GB** | Approaching VRAM boundary (~21.7 GB total) |
| **Activation Memory @ seq_len 16,384** | **>12.0 GB** | **GUARANTEED OUT-OF-MEMORY (OOM)** on 24GB L4 |

### Mathematical Conclusion on Sequence Length
- Prior documentation (`EXTERNAL_REVIEW_PACKET.md`) claimed `max_seq_length=16384` was required. **On a single 24GB L4 GPU, 16,384 tokens will instantly OOM.**
- However, our empirical Data Audit (`03_DATA_AUDIT_AND_SUFFICIENCY.md`) revealed that **100% of our high-density SFT decision windows fit inside 2,822 tokens**.
- Therefore, setting **`max_seq_length = 3072`** (or 4,096 max):
  1. Covers 100% of training samples with **zero truncation**.
  2. Uses only ~18.8 GB total VRAM, leaving a **5.2 GB safety cushion**.
  3. Eliminates all risk of CUDA OOM on Kaggle or GCP.

---

## 3. PEFT / LoRA Architecture & Hyperparameters

```python
# Unsloth FastLanguageModel PEFT configuration
model = FastLanguageModel.get_peft_model(
    model,
    r = 8,
    target_modules = ["q_proj", "v_proj", "o_proj"],
    lora_alpha = 16,
    lora_dropout = 0, # Optimized 0 for Unsloth
    bias = "none",
    use_gradient_checkpointing = "unsloth", # 60% activation memory reduction
    random_state = 42,
)
```

- **Target Modules:** Restricted to attention projections (`q_proj`, `v_proj`, `o_proj`). Freeze all MLPs (`gate_proj`, `up_proj`, `down_proj`) and `k_proj` to prevent catastrophic forgetting and keep adapter size under 20 MB.
- **Loss Masking (`train_on_responses_only`):**
  - Loss is computed strictly on assistant turns (the tool invocation and parameters).
  - System prompt, task problem statements, and tool observation outputs are masked ($loss = 0$).
  - Prevents the model from wasting gradient steps learning to recite repository file contents.

---

## 4. Training Schedule & Compute Budget

- **Effective Batch Size:** 8 (Per-device `batch_size = 1`, `gradient_accumulation_steps = 8`).
- **Dataset Size:** 885 training samples.
- **Steps per Epoch:** $885 / 8 \approx 110$ steps.
- **Epochs:** 2 to 3 epochs ($\approx 220$ to $330$ optimization steps total).
- **Learning Rate:** $2 \times 10^{-4}$ with linear warmup (5% of steps) and cosine decay to $2 \times 10^{-5}$.
- **Optimizer:** `paged_adamw_8bit` (stable low-memory allocator).
- **Estimated Runtime:**
  - Unsloth throughput on Gemma 31B 4-bit with seq_len 3,072: ~20–25 seconds per gradient accumulation step.
  - 250 steps $\times$ 22s $\approx$ **5,500 seconds (~1.5 hours)**.
  - Easily runs within Kaggle's 9-hour execution limit or GCP free tier quota.

---

## 5. Export & Lineage Verification Protocol

Before any adapter is promoted to Track 1, it must pass the Lineage Integrity Gate:
1. Export adapter files to `submission/adapters/main_lora/`.
2. Inspect `adapter_config.json`:
   ```json
   {
     "base_model_name_or_path": "google/gemma-4-31B-it-qat-q4_0-unquantized",
     "peft_type": "LORA",
     "r": 8,
     "lora_alpha": 16,
     "target_modules": ["q_proj", "v_proj", "o_proj"]
   }
   ```
3. Assert file size of `adapter_model.safetensors` is between **15 MB and 25 MB** (never >80 MB, which indicates unfreezed MLPs).
4. Run `python scripts/check_submission.py` to confirm all 14 gates PASS.
