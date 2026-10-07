# 05. Executive Summary & External Consultant Review Packet

**Document Purpose:** This briefing packet contains the full technical context, architectural choices, data audit, and empirical constraints of the **Gemma 4 Developer Agent** project for external review and expert feedback.

---

## 1. Executive Summary & Objective

- **Competition:** Google Gemma 4 Developer Agent (Kaggle).
- **Benchmark:** 129 hidden SWE-bench-style tasks across real Python repositories (FastAPI 67, Rich 48, Requests 13, HTTPX 1).
- **Leaderboard Reality:**
  - Solo Leader (Rank 1): **0.24** (Yurnero — 31/129 tasks).
  - Dense Cluster (Ranks 2–20): **0.17 – 0.18** (22–23/129 tasks).
  - Official Baseline / Public Starter: **0.08 – 0.12** (10–16/129 tasks).
- **Core Diagnosis:** Pure declarative prompt and tool engineering tops out at **~0.17–0.18**. Un-finetuned Gemma 31B lacks domain familiarity with complex FastAPI lifespan protocols and Rich render hierarchies. To reach $\ge 0.20$ and contend for Rank 1, we must deploy a parameter-efficient adapter (**Track 2 LoRA**).

---

## 2. Confirmed Technical Decisions (Non-Negotiable Baseline)

1. **Framework:** **Unsloth** for low-memory, fast PEFT training.
2. **Base Model Checkpoint:** **`google/gemma-4-31B-it-qat-q4_0-unquantized`**
   - *Rationale:* Must match the exact weight lineage of Kaggle's served model (`gemma-4-31b-it-qat-w4a16-ct`). Using BitsAndBytes NF4 is strictly forbidden because quantization scale mismatch previously caused a 0.00 score and 0-completion crash.
3. **PEFT Configuration:**
   - **Rank 8, Alpha 16** on attention projections only: **`q_proj`, `v_proj`, `o_proj`**.
   - Freeze all MLPs (`gate_proj`, `up_proj`, `down_proj`) and `k_proj`.
   - Resulting adapter size: **~18 MB** (clean, fast loading in vLLM).
4. **Hardware Target:** Single **NVIDIA L4 GPU (24GB VRAM)** on Kaggle Compute or GCP.

---

## 3. Negative Constraints (What We Will NOT Do & Why)

1. **NO Heterogeneous / Multiple LLMs:** The Kaggle scoring container has zero internet connectivity and strictly serves one local vLLM instance of Gemma 31B across 4× L4 GPUs. Any router or secondary model is physically impossible.
2. **NO Omitting `run_command` in the Agent:** Our earlier Track 1 v2 run scored 0.03 because omitting `run_command` stripped the agent of dynamic verification. The agent must have shell access to run `/tmp/repro.py`, `python -m py_compile`, and `pytest -k`.
3. **NO Single-Turn Diff Datasets:** The SWE-Gemma harness is an interactive multi-turn ADK agent loop. The model must learn structured tool calling and observation parsing, not static markdown diffs.
4. **NO Runaway Context / 16K Sequences on 1x L4:**
   - A 31B 4-bit model takes ~16.5 GB base VRAM.
   - At sequence length 16,384, activation memory exceeds 12 GB, causing guaranteed OOM on a 24GB L4 GPU.
   - We cap sequence length at **3,072 tokens**, which leaves 5.2 GB of safe VRAM headroom.

---

## 4. Empirical Data Audit (Current State of Training Data)

We audited the existing SFT dataset in `training/sft_data/`:
- **Volume:** **885 training samples** + **222 validation samples** (1,107 total decision windows).
- **Token Lengths:** Min 665, **Median 1,162**, P90 1,686, Max 2,822 tokens.
  - **100% of samples fit inside 3,072 tokens.**
- **Repository Domain:** 50.7% FastAPI, 35.0% Rich, 14.2% Requests.
- **Tool Invocations in Supervised Turns:**
  - `run_skill_script`: 383 turns (64.3%)
  - `read_file`: 113 turns (19.0%)
  - `edit_file`: 66 turns (11.1%)
  - `submit_patch`: 32 turns (5.4%)
  - `run_command`: **0 turns (0.0%)**
- **Data Origin:** Decision windows sliced from successful trajectories produced by LiteRouter proxy (`stealth/space-bunny-alpha`). This functions as **Teacher-Student Knowledge Distillation** into Gemma 31B.

---

## 5. Explicit Questions for External Consultants

We request your review and guidance on the following four strategic questions:

### Question 1: Data Augmentation vs. Baseline Adapter
The current 885 samples heavily emphasize `run_skill_script` (64.3%) and contain 0 turns of `run_command`. 
- **Option A:** Train immediately on the existing 885 samples to establish a working v1 LoRA pipeline and measure validation loss.
- **Option B:** Synthesize ~150–200 multi-turn trajectories demonstrating `run_command` (reproducing in `/tmp/repro.py`, checking syntax with `py_compile`, running `pytest -k`) and merge them before the first training run.
- **Your recommendation?**

### Question 2: Learning Rate & Hyperparameter Tuning for 31B PEFT
For a 31B base model using Rank 8 LoRA on attention projections across 885 high-density samples:
- Is a learning rate of **`2e-4`** (with cosine decay to `2e-5` and 5% warmup) appropriate, or is **`1e-4`** safer to prevent degradation of Python syntax generation?
- Are **2 to 3 epochs** (~220–330 optimization steps with effective batch size 8) optimal to avoid overfitting on 40 distinct tasks?

### Question 3: Sequence Length & VRAM Trade-off
We proved that on a single 24GB L4 GPU, training Gemma 31B with sequence length 16,384 will instantly OOM, whereas sequence length 3,072 consumes ~18.8 GB total and covers 100% of our training samples with zero truncation.
- Do you agree with locking `max_seq_length = 3072` for the training phase, or should we push to `4096` with paged 8-bit AdamW?

### Question 4: vLLM LoRA Serving Quirks
When Kaggle's evaluation runtime starts:
```bash
vllm serve google/gemma-4-31b-it-qat-w4a16-ct --enable-lora --lora-modules main_lora=/kaggle/working/submission/adapters/main_lora ...
```
- Are there known pitfalls in how vLLM handles LoRA adapters trained on `google/gemma-4-31B-it-qat-q4_0-unquantized`?
- Specifically, does the tokenizer or chat template embedded in the adapter directory override or clash with the base model's native template?
