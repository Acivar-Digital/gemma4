# Google Cloud Platform (GCP) Gemma 4 LoRA Training Pipeline

This directory contains the production-grade deployment infrastructure for fine-tuning **Gemma 4 31B IT** LoRA adapters on Google Cloud Platform (GCP).

It directly implements the operational runbook and safety guardrails defined in `.agents/skills/gcp-train/SKILL.md` for Track 2 of the Gemma 4 Developer Agent project.

---

## 1. Architectural Guardrails & Critical Nuances

Fine-tuning for SWE-bench-style developer agents requires strict alignment between the training distribution and Kaggle's evaluation runtime:

1. **Quantization Alignment (Preventing the "Quality Tax"):**
   - **Production Runtime:** Kaggle strictly evaluates against `gemma-4-31b-it-qat-w4a16-ct` (Google DeepMind Quantization-Aware Training INT4 with FP16 activations).
   - **Development Trap:** Training against post-training bitsandbytes NormalFloat4 (`bnb-4bit`) distorts base linear activations, degrading tool call syntax precision and reasoning stability.
   - **GCP Infrastructure:** Provisioning L4 (24 GB) or A100 (40 GB/80 GB) instances allows training against official base distributions with Unsloth gradient checkpointing, eliminating quantization mismatch.

2. **The Attention Geometry & `k_proj` Omission Rule (`attention_k_eq_v=True`):**
   - Gemma 4 31B features 50 sliding-window layers and 10 global full-attention layers.
   - The 10 global layers configure `attention_k_eq_v=True`, where `k_proj` physically serves as both the RoPE-rotated Key and unrotated Value ($K=V$), while `v_proj` is physically omitted in `model.safetensors`.
   - Adapting `k_proj` alters RoPE long-range positional routing and disrupts tool syntax across long contexts. LoRA target modules are strictly locked to:
     ```python
     target_modules = ["q_proj", "v_proj", "o_proj"]
     ```
3. **Response-Only Loss Masking & Tokenizer Isolation:**
   - Training masks user prompts and applies loss exclusively to model response turns (`<start_of_turn>model\n...<end_of_turn>\n`).
   - The tokenizer removes leading `<bos>` prefixes when chat templates inject them to prevent double-BOS sequence corruption.

4. **Zero-Leak Autonomous Self-Destruct:**
   - Ephemeral VMs implement an automated cleanup trap upon exit.
   - **On Success:** Uploads trained adapter weights to Cloud Storage and immediately executes instance deletion.
   - **On Error:** Preserves the VM for 300 seconds (allowing SSH/serial log diagnostics) before automatically deleting itself or executing `sudo poweroff`.
   - Result: Zero lingering idle instances, zero accidental billing leaks.

---

## 2. Infrastructure & Account Specifications

* **Primary Account:** `yapcheeleong@gmail.com`
* **GCP Project ID:** `gen-lang-client-0266946478`
* **Default Bucket:** `gs://gen-lang-client-0266946478-gemma4-checkpoints`
* **Default Zones:** `us-central1-a` / `us-central1-b`
* **Deep Learning VM Image:** `pytorch-2-9-cu129-ubuntu-2204-nvidia-580` (`deeplearning-platform-release`)
* **Environment File:** `.env.gcp` (in repository root)

### Supported Hardware Configurations

| Machine Type | Accelerator | VRAM | Context Window | Use Case | Estimated Cost |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `g2-standard-32` | 1x NVIDIA L4 | 24 GB | 3,072 tokens | Fast 4-bit SFT, cost-effective | ~$0.35/hr (Spot) / ~$1.20/hr (Std) |
| `a2-highgpu-1g` | 1x NVIDIA A100 | 40 GB | 6,144+ tokens | 16-bit precision, high sequence length | ~$1.10/hr (Spot) / ~$3.67/hr (Std) |
| `a2-ultragpu-1g` | 1x NVIDIA A100 | 80 GB | 16,384 tokens | Full-context uncompressed fine-tuning | ~$1.80/hr (Spot) / ~$5.00/hr (Std) |

---

## 3. Preflight Verification Suite (7 Automated Checks)

Before staging any files or launching cloud compute instances, `deploy_gemma4_lora.sh` executes 7 non-destructive preflight checks:

1. **System Tool Prerequisites:** Confirms `gcloud`, `jq`, `python3`, and `gcloud storage` (or `gsutil`) are installed and functional.
2. **GCP Authentication:** Validates that the active authenticated account is `yapcheeleong@gmail.com` (prompts/fails if unauthenticated or misconfigured).
3. **Project & API Enablement:** Ensures project `gen-lang-client-0266946478` is active and that `compute.googleapis.com` is enabled.
4. **Cloud Storage Writeability:** Verifies bucket `gs://gen-lang-client-0266946478-gemma4-checkpoints` exists, is accessible, and passes write/delete probes.
5. **Dataset Integrity & JSONL Schema:** Verifies `data/unsloth_sft_train.jsonl` and `data/unsloth_sft_val.jsonl` exist, are non-empty, parse cleanly line-by-line, and contain valid `messages` lists. Reports line counts and train/val split ratio.
6. **Training Script Integrity:** Syntax-checks `scripts/train_gemma4_unsloth_cloud.py`, asserts `target_modules` contains `["q_proj", "v_proj", "o_proj"]` (with `k_proj` omitted), checks Rank-8 configuration, verifies response-only loss masking, and checks `HF_TOKEN`.
7. **Zone Hardware Capacity:** Verifies that the requested zone supports the target machine type and GPU accelerator.

---

## 4. Usage Guide

### A. Run Preflight Dry-Run (Recommended First Step)
Runs all 7 preflight checks without spinning up any cloud compute instances or staging assets:
```bash
./gcp/deploy_gemma4_lora.sh --dry-run
```

Test dry-run with A100 40GB GPU:
```bash
./gcp/deploy_gemma4_lora.sh --dry-run --machine-type=a2-highgpu-1g --zone=us-central1-a
```

### B. Launch Training on Spot L4 GPU (Default)
Deploys on a Spot `g2-standard-32` instance in `us-central1-a`:
```bash
./gcp/deploy_gemma4_lora.sh
```

### C. Launch Training on Spot A100 GPU (High VRAM Headroom)
Deploys on a Spot `a2-highgpu-1g` instance in `us-central1-a`:
```bash
./gcp/deploy_gemma4_lora.sh --machine-type=a2-highgpu-1g --zone=us-central1-a
```

### CLI Options Reference

```text
Usage:
  ./gcp/deploy_gemma4_lora.sh [OPTIONS]

Options:
  --dry-run                 Run all preflight checks without deploying VM or uploading datasets.
  -m, --machine-type <type> GCP machine type (default: g2-standard-32).
                            Supported: g2-standard-32 (L4 24GB), a2-highgpu-1g (A100 40GB), a2-ultragpu-1g (A100 80GB).
  -z, --zone <zone>         GCP Zone (default: us-central1-a).
  --spot                    Use Spot VM provisioning (default: true).
  --no-spot, --standard     Use Standard VM provisioning.
  -p, --project <project>   GCP Project ID (default: gen-lang-client-0266946478).
  -b, --bucket <bucket>     GCS Bucket for staging & artifacts (default: gs://<project>-gemma4-checkpoints).
  --hf-token <token>        Hugging Face authentication token for gated Gemma 4 model weights.
  --disk-size <size>        Boot disk size (default: 100GB).
  --allow-any-account       Bypass strict check for yapcheeleong@gmail.com.
  -h, --help                Show help message.
```

---

## 5. Monitoring & Artifact Harvesting

Once the VM is launched, use the automated watcher script to monitor progress and harvest the trained weights:

### Mode 1: Autonomous Watcher & Auto-Download (Recommended)
Polls Cloud Storage every 30 seconds until `adapter_model.safetensors` lands, then automatically downloads artifacts to `my_submission/adapters/main_lora/`, updates `my_submission/agent.yaml`, and packages `submission_lora.zip`:
```bash
./scripts/monitor_gcp_train.sh wait
```

### Mode 2: Live Remote SSH Log Streaming
Streams training output live from `/var/log/gemma4_training.log` on the ephemeral VM:
```bash
./scripts/monitor_gcp_train.sh tail
```

### Mode 3: Instant GPU & Process Status Snapshot
Displays current GPU utilization and the last 15 lines of training logs:
```bash
./scripts/monitor_gcp_train.sh status
```

### Mode 4: Early Boot & Kernel Console Logs
If the VM has not finished booting or SSH is not yet ready:
```bash
gcloud compute instances get-serial-port-output <INSTANCE_NAME> --zone=<ZONE> --project=gen-lang-client-0266946478
```

---

## 6. Verification & Promotion Gate

Before mounting any newly trained LoRA adapter into the production submission:

1. **Verify Harvested Artifacts:**
   Ensure the following files exist in `my_submission/adapters/main_lora/`:
   - `adapter_model.safetensors` (~70 MB – 150 MB)
   - `adapter_config.json` (~600 bytes)
   - `tokenizer_config.json`, `tokenizer.json`, `special_tokens_map.json`

2. **Sanitize `adapter_config.json`:**
   ```bash
   python3 -c '
   import json
   with open("my_submission/adapters/main_lora/adapter_config.json", "r") as f:
       cfg = json.load(f)
   assert cfg["r"] == 8, f"Expected rank 8, got {cfg.get(\"r\")}"
   assert "k_proj" in cfg["target_modules"], "k_proj missing from target_modules!"
   print("Adapter configuration verified.")
   '
   ```

3. **Kaggle Promotion Rule:**
   - Local validation via `./start.sh` must beat the Track 1 declarative baseline **measured on
     `gemma-4-31b-it-qat-w4a16-ct` itself**. The historical `43.4%` is **not** a usable
     threshold — the runs behind it (`run_B35`/`B37`/`B39`) recorded
     `model_name: stealth/space-bunny-alpha`, a LiteRouter proxy rather than Gemma 4.
   - Must cleanly resolve canary tasks `fastapi_14479` and `requests_7205` without looping.
   - Validate and submit through the single supported path:
     ```bash
     bash scripts/submit_safe.sh --dry-run   # gates only; packs and submits nothing
     bash scripts/submit_safe.sh             # gate -> pack -> gate -> hash -> quota -> prompt
     ```
     The legacy packaging check script was deleted; `scripts/submit_safe.sh` +
     `scripts/check_submission.py` replaced it.

---

## 7. Emergency Teardown

If a run must be aborted immediately:
```bash
# List all active training instances
gcloud compute instances list --project=gen-lang-client-0266946478 --filter="name ~ gemma4-unsloth-"

# Force delete an instance
gcloud compute instances delete <INSTANCE_NAME> --zone=<ZONE> --project=gen-lang-client-0266946478 --quiet
```
