---
name: gcp-train
description: Autonomous playbook for launching, monitoring, and harvesting Gemma 4 31B LoRA fine-tuning runs on Google Cloud Platform (GCP). Uses yapcheeleong@gmail.com account credentials, manages ephemeral GPU VMs (A100/L4) with zero-leak self-destruct traps, and enforces strict base-model quantization alignment.
---

# Google Cloud Platform (GCP) Gemma 4 LoRA Training Playbook (`gcp-train`)

This skill documents the end-to-end operational procedure for fine-tuning **Gemma 4 31B IT** LoRA adapters on Google Cloud Platform (GCP) infrastructure for the Kaggle Gemma 4 Developer Agent competition.

---

## 1. The Critical Nuance: "Why We Must Train Against the Exact Same Model"

During the forensic autopsy of the canary runs and the external consultant audits (`consultant1.md`, `consultant2.md`, `consultant3.md`), Consultant 2 identified a critical structural misalignment between the development and production stacks:

### The Quantization Mismatch Trap (QAT vs. BNB-NF4)
* **The Competition Runtime:** Kaggle's evaluation environment strictly runs **`gemma-4-31b-it-qat-w4a16-ct`**. This model was produced using **Quantization-Aware Training (QAT)** by Google DeepMind, where weights were quantized to INT4 during training with FP16 activations.
* **The Common Development Trap:** In Unsloth and standard notebooks, developers typically load **`unsloth/gemma-4-31B-it-unsloth-bnb-4bit`**, which uses post-training **bitsandbytes NormalFloat4 (NF4)** quantization.
* **Why This Matters ("The Quality Tax"):**
  1. Post-training NF4 and QAT-w4a16 yield **fundamentally different numeric distributions across the base linear layers**.
  2. A Rank-8 LoRA adapter learns small low-rank weight updates $\Delta W = A \cdot B$ calibrated specifically to compensate for the base layer activations it sees during training.
  3. When an adapter trained on bitsandbytes-NF4 is plugged into the competition's QAT runtime, the learned deltas do not cleanly align with the QAT layer weights. While the model may load without crashing, it suffers a **"quality tax"**—degrading instruction following, tool-call syntax precision, and reasoning stability.
* **The Rule for Track 2:** 
  Always train the adapter against the exact base model distribution that matches production:
  - Either train against the official Google bfloat16 base (`google/gemma-4-31b-it`) or the exact QAT-compatible weights.
  - Set `base_model_name_or_path: "google/gemma-4-31b-it"` in `adapter_config.json`.
  - GCP A100 GPUs (40GB/80GB VRAM) have the memory capacity to load full precision or uncompressed base layers with Unsloth gradient checkpointing, eliminating the aggressive NF4 distortion forced on low-memory 24GB GPUs.

### The Target Modules Nuance (`k_proj` Dropping Bug)
* Past configurations used a regex like `(?i).*(q_proj|v_proj|o_proj).*` which silently **dropped `k_proj`**.
* Attention query-key interaction requires reciprocal adaptation. For Track 2, target modules must be explicitly defined as an explicit array:
  ```python
  target_modules = ["q_proj", "k_proj", "v_proj", "o_proj"]
  ```

### Chat Template and Special Token Isolation
* Gemma 4 uses strict turn tokens: `<start_of_turn>user\n...<end_of_turn>\n<start_of_turn>model\n...`.
* The tokenizer used during training must match the Google Gemma 4 IT tokenizer exactly. Any synthetic prompt formatting must remove the leading `<bos>` token if the chat template injects it automatically, preventing double BOS corruption.

---

## 2. Infrastructure & Account Configuration

All GCP assets and billing quotas are already configured under the user's dedicated GCP account:

* **User Account:** `yapcheeleong@gmail.com`
* **Google Cloud Project ID:** `gen-lang-client-0266946478`
* **Default Region & Zones:** `us-central1` (`us-central1-b` or `us-central1-c` for G2/A100)
* **Storage Bucket:** `gs://gen-lang-client-0266946478-gemma4-checkpoints`
* **Local Credentials File:** `.env.gcp` (in repository root)

### Machine Types & Hardware Sizing

| Machine Type | Accelerators | VRAM | Typical Use Case | Cost Profile |
|:---|:---|:---|:---|:---|
| `g2-standard-32` | 1x NVIDIA L4 | 24 GB | Fast 4-bit SFT, 3072 context | ~$0.35/hr (Spot) / ~$1.20/hr (Std) |
| `a2-highgpu-1g` | 1x NVIDIA A100 | 40 GB | 16-bit / High-Seq SFT, 6144+ context | ~$1.10/hr (Spot) / ~$3.67/hr (Std) |
| `a2-ultragpu-1g` | 1x NVIDIA A100 | 80 GB | Full 16384 context training | ~$1.80/hr (Spot) / ~$5.00/hr (Std) |

---

## 3. Zero-Leak Guardrail: The Ephemeral VM Lifecycle

To guarantee **zero accidental credit leakage**, the deployment script implements an autonomous self-destruct trap inside the VM startup script:

```bash
cleanup_and_destroy() {
    EXIT_CODE=$?
    ZONE=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/zone" | awk -F/ '{print $NF}')
    VM_NAME=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/name")
    
    if [[ "${TRAINING_SUCCESS}" -eq 1 ]]; then
        # Succeeded: Destroy VM immediately
        gcloud compute instances delete "${VM_NAME}" --zone="${ZONE}" --quiet || sudo poweroff
    else
        # Failed: Keep alive for 300s to allow remote log inspection, then self-destruct
        sleep 300
        gcloud compute instances delete "${VM_NAME}" --zone="${ZONE}" --quiet || sudo poweroff
    fi
}
trap cleanup_and_destroy EXIT
```

* **Result:** Even if your local machine loses internet or you disconnect, the VM automatically uploads the trained adapter to GCS and permanently deletes itself upon completion.

---

## 4. Step-by-Step Training Execution Runbook

### Quick Reference: Canonical Deployment Workflow

When you are ready to train on GCP, execute this exact workflow:

```bash
# Step 1: Preflight Verification (Dry-Run — zero cost, verifies all 7 gates)
./gcp/deploy_gemma4_lora.sh --dry-run

# Step 2: Deploy to GCP
# Option A: NVIDIA L4 GPU (Fastest, lowest cost ~$0.35/hr spot)
./gcp/deploy_gemma4_lora.sh -m g2-standard-32 -z us-central1-a

# Option B: NVIDIA A100 40GB GPU (Higher precision, larger context ~$1.10/hr spot)
./gcp/deploy_gemma4_lora.sh -m a2-highgpu-1g -z us-central1-a

# Step 3: Monitor Telemetry & Auto-Download Weights
./scripts/monitor_gcp_train.sh wait

# (Optional) Stream Live GPU Logs
./scripts/monitor_gcp_train.sh tail
```

* **Cost Protection:** The VM automatically self-destructs upon completion or error, syncing weights to `gs://gen-lang-client-0266946478-gemma4-checkpoints/output/main_lora/`.
* **Track 1 Baseline:** `submission.zip` has passed 100% of all 9 pre-submission gates and is ready to submit to Kaggle when your quota resets.

---

### Step 1: Pre-flight Verification & Local Environment
Ensure you are authenticated against `yapcheeleong@gmail.com` and your `.env.gcp` is loaded:

```bash
# Check active GCP account and project
gcloud auth list
gcloud config set project gen-lang-client-0266946478

# Ensure training data is generated and non-empty
ls -lh data/unsloth_sft_train.jsonl data/unsloth_sft_val.jsonl
```

### Step 2: Deploy the Training Job
Execute the production-grade deployment launcher. The script runs a 7-gate preflight check (validating `gcloud`, account identity, project quotas, GCS bucket access, dataset formatting, and target modules) before launching:

```bash
# 1. Run Preflight Verification without launching (Dry-Run Mode)
./gcp/deploy_gemma4_lora.sh --dry-run

# 2. Deploy Option A: Standard L4 GPU (Fastest provisioning, lowest cost ~$0.35/hr spot)
./gcp/deploy_gemma4_lora.sh -m g2-standard-32 -z us-central1-a

# 3. Deploy Option B: A100 40GB GPU (High precision, full context headroom ~$1.10/hr spot)
./gcp/deploy_gemma4_lora.sh -m a2-highgpu-1g -z us-central1-a
```

**What the deployment script does automatically:**
1. Runs 7 preflight check gates: system binaries, `yapcheeleong@gmail.com` identity, GCS bucket write test, dataset formatting (1,107 samples), training script target modules (`q_proj, k_proj, v_proj, o_proj`), and zone GPU availability.
2. Uploads `data/unsloth_sft_train.jsonl`, `data/unsloth_sft_val.jsonl`, and `scripts/train_gemma4_unsloth_cloud.py` to `gs://${BUCKET}/input/`.
3. Injects the self-destruct startup script into VM metadata.
4. Boots the ephemeral Spot VM with Deep Learning VM image (`pytorch-2-9-cu129-ubuntu-2204-nvidia-580`).

### Stale Artifact Guardrail (Pre-Clearing Output Bucket)
To prevent stale weights from previous runs triggering premature harvest, `deploy_gemma4_lora.sh` automatically purges `gs://${BUCKET}/output/main_lora/**` prior to VM launch.

### Step 3: Monitor Training Telemetry (Anti-Token Waste Protocol)
**CRITICAL PROTOCOL:** NEVER execute interactive polling loops (such as running repetitive SSH/status commands) in LLM chat turns. Doing so burns conversation context and model tokens.

Always use the autonomous background watcher, which polls every 5 minutes (300 seconds) in bash and logs clean timestamps to `/tmp/gemma4_gcp_monitor.log`:

```bash
# Canonical Monitoring: Detached 5-Minute Background Watcher & Auto-Harvest
./scripts/monitor_gcp_train.sh wait &
# Or launched directly via deployment flag:
# ./gcp/deploy_gemma4_lora.sh -m g2-standard-32 -z us-central1-a --wait

# View live background monitor log:
tail -f /tmp/gemma4_gcp_monitor.log

# (Optional) One-shot inspection commands (run once when needed, never in loops):
# Mode 2: Live SSH log tail (interactive terminal only)
./scripts/monitor_gcp_train.sh tail

# Mode 3: Single status snapshot
./scripts/monitor_gcp_train.sh status
```

### Step 4: Verification of Harvested Weights
Once `monitor_gcp_train.sh wait` finishes, verify the adapter artifacts downloaded to `my_submission/adapters/main_lora/`:

```bash
ls -lh my_submission/adapters/main_lora/
```
Expected output:
* `adapter_model.safetensors` (~70 MB – 150 MB)
* `adapter_config.json` (~600 bytes)
* `special_tokens_map.json`
* `tokenizer_config.json`
* `tokenizer.json`

### Step 5: Sanitize `adapter_config.json`
Inspect `adapter_config.json` to ensure no Unsloth private serialization artifacts or wrong base paths leaked:

```bash
python3 -c '
import json
with open("my_submission/adapters/main_lora/adapter_config.json", "r") as f:
    cfg = json.load(f)

assert cfg["r"] == 8, f"Expected rank 8, got {cfg.get(\"r\")}"
assert "k_proj" in cfg["target_modules"], "k_proj missing from target_modules!"
print("✅ Adapter config is valid and matches competition standards!")
'
```

---

## 5. Promotion Gate: Deploying to Submission

**CRITICAL RULE:** Do NOT blindly mount the newly trained adapter into `my_submission/agent.yaml` for a Kaggle submission.

Follow the **Track 2 Promotion Gate**:
1. Run local validation using `./start.sh` across the 14-task gauntlet.
2. The adapter run **must score $\ge 43.4\%$** (surpassing the Track 1 baseline).
3. The adapter **must cleanly resolve the two canary traps**:
   - `fastapi_14479` (zero JSON syntax splicing / loop).
   - `requests_7205` (zero repeated uninformative probes).
4. Only when both criteria pass:
   ```yaml
   # my_submission/agent.yaml
   model: gemma-4-31b-it-qat-w4a16-ct
   adapter: main_lora
   ```
5. Repackage and verify using the 9-gate audit:
   ```bash
   python3 scripts/verify_submission.py
   ```

---

## 6. Emergency Operations & Manual Teardown

If a run hangs or needs to be killed manually:

```bash
# List all running training instances
gcloud compute instances list --project=gen-lang-client-0266946478

# Manually delete an instance
gcloud compute instances delete <INSTANCE_NAME> --zone=<ZONE> --project=gen-lang-client-0266946478 --quiet

# Inspect bucket contents
gcloud storage ls --project=gen-lang-client-0266946478 gs://gen-lang-client-0266946478-gemma4-checkpoints/output/
```

---

## 7. Modular References (Lazy-Loaded)

For deep forensic troubleshooting, container environment traps, and library compatibility issues, load the modular reference:
* **Package Mismatches & Container Traps:** Read `references/environment-package-traps.md` for in-depth documentation on:
  - Missing test fixtures in Container A (`inline-snapshot`, `executing`) and the Container B test-discard policy.
  - Python import path collisions (`PYTHONPATH=/workspace/src:/workspace` and `PYTHONSAFEPATH=1`).
  - Organizer wheelhouse clashing and offline constraint manifests (`runtime-overlay-constraints.txt`).
  - Host bridge bugs (`LiteLLM` thinking budget translation and `ADK` SkillToolset invocation conventions).
  - GCP DLVM kernel quirks (`num_items_in_batch`, response loss masking tokenizer differences).
  - The cross-quantization mismatch trap (QAT-w4a16 vs BNB-NF4) and the 0.03 score post-mortem.

