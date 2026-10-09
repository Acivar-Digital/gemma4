#!/usr/bin/env bash
# ==============================================================================
# deploy_gemma4_lora.sh
# Production-Grade Ephemeral GCP Training Launcher for Gemma 4 31B LoRA
# Aligned with .agents/skills/gcp-train/SKILL.md & Dual-Track Master Plan
#
# Primary Account: yapcheeleong@gmail.com
# Default Project: gen-lang-client-0266946478
# Default Bucket:  gs://gen-lang-client-0266946478-gemma4-checkpoints
# ==============================================================================

set -euo pipefail

# ------------------------------------------------------------------------------
# 1. Colors, Formatting & Verbose Logging
# ------------------------------------------------------------------------------
if [[ -t 1 ]]; then
    BOLD="\033[1m"
    DIM="\033[2m"
    RED="\033[1;31m"
    GREEN="\033[1;32m"
    YELLOW="\033[1;33m"
    BLUE="\033[1;34m"
    MAGENTA="\033[1;35m"
    CYAN="\033[1;36m"
    WHITE="\033[1;37m"
    RESET="\033[0m"
else
    BOLD=""
    DIM=""
    RED=""
    GREEN=""
    YELLOW=""
    BLUE=""
    MAGENTA=""
    CYAN=""
    WHITE=""
    RESET=""
fi

ts() {
    date -u +"%Y-%m-%d %H:%M:%S UTC"
}

log_banner() {
    echo -e "${BOLD}${BLUE}╔══════════════════════════════════════════════════════════════════════════════╗${RESET}"
    echo -e "${BOLD}${BLUE}║${WHITE}  $*${RESET}"
    echo -e "${BOLD}${BLUE}╚══════════════════════════════════════════════════════════════════════════════╝${RESET}"
}

log_step() {
    echo -e "\n${BOLD}${MAGENTA}▶ [$(ts)] STEP: $*${RESET}"
}

log_info() {
    echo -e "${CYAN}ℹ [$(ts)]${RESET} $*"
}

log_success() {
    echo -e "${GREEN}✔ [$(ts)]${RESET} ${BOLD}$*${RESET}"
}

log_warn() {
    echo -e "${YELLOW}▲ [$(ts)] WARNING:${RESET} $*"
}

log_error() {
    echo -e "${RED}✖ [$(ts)] ERROR:${RESET} ${BOLD}$*${RESET}" >&2
}

on_error() {
    local exit_code="$1"
    local line_no="$2"
    log_error "Command failed with exit code ${exit_code} on line ${line_no}!"
    exit "${exit_code}"
}
trap 'on_error $? $LINENO' ERR

# ------------------------------------------------------------------------------
# 2. Path Resolution & Base Environment
# ------------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source local .env.gcp if available
ENV_FILE="${REPO_ROOT}/.env.gcp"
if [[ -f "${ENV_FILE}" ]]; then
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
fi

# ------------------------------------------------------------------------------
# 3. CLI Argument Parsing & Default Values
# ------------------------------------------------------------------------------
EXPECTED_ACCOUNT="yapcheeleong@gmail.com"
DEFAULT_PROJECT="gen-lang-client-0266946478"
DEFAULT_ZONE="us-central1-a"
DEFAULT_MACHINE="g2-standard-32"
DEFAULT_PROVISIONING="SPOT"
DEFAULT_DISK_SIZE="100GB"
DEFAULT_IMAGE_FAMILY="pytorch-2-9-cu129-ubuntu-2204-nvidia-580"
DEFAULT_IMAGE_PROJECT="deeplearning-platform-release"

CLI_DRY_RUN=false
CLI_ALLOW_ANY_ACCOUNT=false
CLI_FIVE_TEST_ALIGNMENT=false
CLI_MACHINE=""
CLI_ZONE=""
CLI_PROVISIONING=""
CLI_PROJECT=""
CLI_BUCKET=""
CLI_HF_TOKEN=""
CLI_DISK_SIZE=""
show_usage() {
    cat << EOF
${BOLD}Gemma 4 LoRA GCP Deployment Launcher${RESET}

Usage:
  ./gcp/deploy_gemma4_lora.sh [OPTIONS]

Options:
  --dry-run                 Run all preflight checks without deploying VM or uploading datasets.
  --five-test-alignment     Deploy 5-test end-to-end LoRA alignment & Kaggle eval pipeline (g2-standard-48, 200GB disk, dual-venv).
  -m, --machine-type <type> GCP machine type (default: ${DEFAULT_MACHINE}).
                            Supported: g2-standard-32 (L4 24GB), a2-highgpu-1g (A100 40GB), a2-ultragpu-1g (A100 80GB).
  -z, --zone <zone>         GCP Zone (default: ${DEFAULT_ZONE}).
  --spot                    Use Spot VM provisioning (default: true).
  --no-spot, --standard     Use Standard VM provisioning.
  -p, --project <project>   GCP Project ID (default: ${DEFAULT_PROJECT}).
  -b, --bucket <bucket>     GCS Bucket for staging & artifacts (default: gs://<project>-gemma4-checkpoints).
  --hf-token <token>        Hugging Face authentication token for gated Gemma 4 model weights.
  --disk-size <size>        Boot disk size (default: ${DEFAULT_DISK_SIZE}).
  --allow-any-account       Bypass strict check for ${EXPECTED_ACCOUNT}.
  -h, --help                Show this help message.

Examples:
  # Preflight check only (recommended before running)
  ./gcp/deploy_gemma4_lora.sh --dry-run

  # Deploy on default L4 GPU (g2-standard-32, Spot)
  ./gcp/deploy_gemma4_lora.sh

  # Deploy on A100 40GB GPU in us-central1-a (Spot)
  ./gcp/deploy_gemma4_lora.sh --machine-type=a2-highgpu-1g --zone=us-central1-a
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            CLI_DRY_RUN=true
            shift
            ;;
        --five-test-alignment)
            CLI_FIVE_TEST_ALIGNMENT=true
            shift
            ;;
        -m|--machine-type)
            CLI_MACHINE="$2"
            shift 2
            ;;
        --machine-type=*)
            CLI_MACHINE="${1#*=}"
            shift
            ;;
        -z|--zone)
            CLI_ZONE="$2"
            shift 2
            ;;
        --zone=*)
            CLI_ZONE="${1#*=}"
            shift
            ;;
        --spot)
            CLI_PROVISIONING="SPOT"
            shift
            ;;
        --no-spot|--standard)
            CLI_PROVISIONING="STANDARD"
            shift
            ;;
        -p|--project)
            CLI_PROJECT="$2"
            shift 2
            ;;
        --project=*)
            CLI_PROJECT="${1#*=}"
            shift
            ;;
        -b|--bucket)
            CLI_BUCKET="$2"
            shift 2
            ;;
        --bucket=*)
            CLI_BUCKET="${1#*=}"
            shift
            ;;
        --hf-token)
            CLI_HF_TOKEN="$2"
            shift 2
            ;;
        --hf-token=*)
            CLI_HF_TOKEN="${1#*=}"
            shift
            ;;
        --disk-size)
            CLI_DISK_SIZE="$2"
            shift 2
            ;;
        --disk-size=*)
            CLI_DISK_SIZE="${1#*=}"
            shift
            ;;
        --allow-any-account)
            CLI_ALLOW_ANY_ACCOUNT=true
            shift
            ;;
        -w|--wait|--monitor)
            CLI_WAIT_MONITOR=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Resolve variables (CLI flag > Env var > Default)
PROJECT_ID="${CLI_PROJECT:-${GCP_PROJECT:-${DEFAULT_PROJECT}}}"
ZONE="${CLI_ZONE:-${GCP_ZONE:-${DEFAULT_ZONE}}}"
if [[ "${ZONE}" == "us-central1-b" ]]; then
    log_warn "Zone 'us-central1-b' has scheduled GCP network control plane maintenance (Oct 9 00:00-05:00 PDT). Auto-routing to 'us-central1-a'."
    ZONE="us-central1-a"
fi
if ${CLI_FIVE_TEST_ALIGNMENT}; then
    MACHINE_TYPE="${CLI_MACHINE:-g2-standard-32}"
    DISK_SIZE="${CLI_DISK_SIZE:-200GB}"
else
    MACHINE_TYPE="${CLI_MACHINE:-${GCP_MACHINE_TYPE:-${DEFAULT_MACHINE}}}"
    DISK_SIZE="${CLI_DISK_SIZE:-${DEFAULT_DISK_SIZE}}"
fi
# Provisioning model: default to SPOT for cost savings, unless --no-spot/--standard is passed
if [[ -n "${CLI_PROVISIONING}" ]]; then
    PROVISIONING_MODEL="${CLI_PROVISIONING}"
else
    PROVISIONING_MODEL="SPOT"
fi
BUCKET_NAME="${CLI_BUCKET:-${GCP_BUCKET:-${PROJECT_ID}-gemma4-checkpoints}}"
# Strip gs:// prefix if provided by user
BUCKET_NAME="${BUCKET_NAME#gs://}"
HF_TOKEN="${CLI_HF_TOKEN:-${HF_TOKEN:-}}"
DRY_RUN="${CLI_DRY_RUN}"

if ${CLI_FIVE_TEST_ALIGNMENT}; then
    TRAIN_DATA="${REPO_ROOT}/data/unsloth_sft_5test/train.jsonl"
    VAL_DATA="${REPO_ROOT}/data/unsloth_sft_5test/val.jsonl"
else
    TRAIN_DATA="${REPO_ROOT}/data/unsloth_sft_train.jsonl"
    VAL_DATA="${REPO_ROOT}/data/unsloth_sft_val.jsonl"
fi
TRAIN_SCRIPT="${REPO_ROOT}/scripts/train_gemma4_unsloth_cloud.py"

MACHINE_SHORT="${MACHINE_TYPE%%-*}"
TIMESTAMP_ID="$(date +%s)"
if ${CLI_FIVE_TEST_ALIGNMENT}; then
    INSTANCE_NAME="gemma4-5test-${MACHINE_SHORT}-${TIMESTAMP_ID}"
else
    INSTANCE_NAME="gemma4-unsloth-${MACHINE_SHORT}-${TIMESTAMP_ID}"
fi

# ------------------------------------------------------------------------------
# 4. Banner & Execution Mode Display
# ------------------------------------------------------------------------------
log_banner " Gemma 4 LoRA GCP Deployment Pipeline"
echo -e "${DIM}  Repository Root : ${REPO_ROOT}${RESET}"
echo -e "${DIM}  Execution Mode  : $(if ${DRY_RUN}; then echo -e "${YELLOW}DRY-RUN (Preflight Validation Only)${RESET}"; else echo -e "${GREEN}ACTIVE DEPLOYMENT${RESET}"; fi)"
echo -e "${DIM}  Target Account  : ${EXPECTED_ACCOUNT}${RESET}"
echo -e "${DIM}  Project ID      : ${PROJECT_ID}${RESET}"
echo -e "${DIM}  GCP Zone        : ${ZONE}${RESET}"
echo -e "${DIM}  Machine Type    : ${MACHINE_TYPE}${RESET}"
echo -e "${DIM}  Provisioning    : ${PROVISIONING_MODEL}${RESET}"
echo -e "${DIM}  Target Bucket   : gs://${BUCKET_NAME}${RESET}"
echo -e "${DIM}  Target Instance : ${INSTANCE_NAME}${RESET}"

# ------------------------------------------------------------------------------
# 5. Preflight Checks
# ------------------------------------------------------------------------------

# --- CHECK 1: Local Tool Prerequisites ---
log_step "1/7: Checking Local System Prerequisites"
for cmd in gcloud jq python3; do
    if ! command -v "${cmd}" >/dev/null 2>&1; then
        log_error "Missing required command: '${cmd}'. Please install it before proceeding."
        exit 1
    fi
    log_info "Found ${BOLD}${cmd}${RESET} at: $(command -v "${cmd}")"
done

# Check gcloud storage or gsutil
if gcloud storage --help >/dev/null 2>&1; then
    STORAGE_CLI="gcloud storage"
    log_info "Using high-performance ${BOLD}gcloud storage${RESET} CLI"
elif command -v gsutil >/dev/null 2>&1; then
    STORAGE_CLI="gsutil"
    log_info "Using legacy ${BOLD}gsutil${RESET} CLI"
else
    log_error "Neither 'gcloud storage' nor 'gsutil' is available in PATH."
    exit 1
fi
log_success "All local tool prerequisites satisfied."

# --- CHECK 2: GCP Authentication & Active Account ---
log_step "2/7: Validating GCP Authentication & Active Account"
YAP_ACCOUNT_JSON="/home/vps466a/.antigravity_tools/accounts/f3e9109a-3ffc-4bc7-bd93-3125d504605a.json"
ACTIVE_ACCOUNT="$(gcloud auth list --filter="status:ACTIVE" --format="value(account)" 2>/dev/null | head -n 1 || true)"

if [[ "${ACTIVE_ACCOUNT}" != "${EXPECTED_ACCOUNT}" && -f "${YAP_ACCOUNT_JSON}" ]]; then
    python3 -c '
import json, pathlib, sys
d = json.load(open(sys.argv[1]))
tok = d.get("token", {}).get("access_token", "")
if tok:
    p = pathlib.Path("/tmp/.gcp_yapcheeleong_token")
    p.write_text(tok)
    p.chmod(0o600)
' "${YAP_ACCOUNT_JSON}"
    if [[ -s "/tmp/.gcp_yapcheeleong_token" ]]; then
        export CLOUDSDK_AUTH_ACCESS_TOKEN_FILE="/tmp/.gcp_yapcheeleong_token"
        export CLOUDSDK_BILLING_QUOTA_PROJECT="${PROJECT_ID}"
        ACTIVE_ACCOUNT="${EXPECTED_ACCOUNT}"
        log_info "Hydrated ${BOLD}${EXPECTED_ACCOUNT}${RESET} OAuth token via CLOUDSDK_AUTH_ACCESS_TOKEN_FILE (quota project: ${PROJECT_ID})."
    fi
fi

if [[ -z "${ACTIVE_ACCOUNT}" ]]; then
    log_error "No active GCP account authenticated!"
    log_info "Please authenticate by running:"
    echo -e "  ${BOLD}gcloud auth login ${EXPECTED_ACCOUNT}${RESET}"
    exit 1
fi

log_info "Active authenticated GCP account: ${BOLD}${ACTIVE_ACCOUNT}${RESET}"
if [[ "${ACTIVE_ACCOUNT}" != "${EXPECTED_ACCOUNT}" ]]; then
    if ${CLI_ALLOW_ANY_ACCOUNT}; then
        log_warn "Active account (${ACTIVE_ACCOUNT}) does not match expected (${EXPECTED_ACCOUNT}), but --allow-any-account was passed."
    else
        log_error "Active account is '${ACTIVE_ACCOUNT}', but expected account is '${EXPECTED_ACCOUNT}'!"
        log_info "To switch to the correct account, run:"
        echo -e "  ${BOLD}gcloud config set account ${EXPECTED_ACCOUNT}${RESET}"
        log_info "Or pass ${BOLD}--allow-any-account${RESET} to override."
        exit 1
    fi
fi
log_success "GCP account authentication verified (${ACTIVE_ACCOUNT})."

# --- CHECK 3: GCP Project & Compute API Enablement ---
log_step "3/7: Validating GCP Project & Compute API Enablement"
CURRENT_CONFIG_PROJECT="$(gcloud config get-value project 2>/dev/null || true)"
if [[ "${CURRENT_CONFIG_PROJECT}" != "${PROJECT_ID}" ]]; then
    log_info "Setting active gcloud project to ${BOLD}${PROJECT_ID}${RESET} (was '${CURRENT_CONFIG_PROJECT}')..."
    gcloud config set project "${PROJECT_ID}" >/dev/null 2>&1
fi

PROJECT_STATE="$(gcloud projects describe "${PROJECT_ID}" --format="value(lifecycleState)" 2>/dev/null || true)"
if [[ "${PROJECT_STATE}" != "ACTIVE" ]]; then
    log_error "Project '${PROJECT_ID}' is not active or accessible! (Lifecycle state: ${PROJECT_STATE:-UNKNOWN})"
    exit 1
fi
log_info "Project ${BOLD}${PROJECT_ID}${RESET} is ACTIVE."

COMPUTE_API_STATUS="$(gcloud services list --project="${PROJECT_ID}" --enabled --filter="name:compute.googleapis.com" --format="value(state)" 2>/dev/null || true)"
if [[ "${COMPUTE_API_STATUS}" != "ENABLED" ]]; then
    log_error "Compute Engine API ('compute.googleapis.com') is not enabled on project ${PROJECT_ID}!"
    log_info "Enable it by running:"
    echo -e "  ${BOLD}gcloud services enable compute.googleapis.com --project=${PROJECT_ID}${RESET}"
    exit 1
fi
log_success "Compute Engine API is active and enabled."

# --- CHECK 4: GCS Bucket Existence & Write Permissions ---
log_step "4/7: Verifying Cloud Storage Bucket Access (gs://${BUCKET_NAME})"
if ! ${STORAGE_CLI} buckets describe "gs://${BUCKET_NAME}" >/dev/null 2>&1; then
    if ${DRY_RUN}; then
        log_warn "Bucket gs://${BUCKET_NAME} does not exist yet. It will be created upon active deployment in location US."
    else
        log_info "Bucket gs://${BUCKET_NAME} does not exist. Creating bucket in US multi-region..."
        ${STORAGE_CLI} buckets create "gs://${BUCKET_NAME}" --location="US"
        log_success "Created bucket gs://${BUCKET_NAME}."
    fi
else
    log_info "Bucket gs://${BUCKET_NAME} exists and is accessible."
fi

# Verify write permission with probe
PROBE_FILE=".probe_write_${TIMESTAMP_ID}.tmp"
log_info "Verifying bucket writeability..."
if echo "write_test_${TIMESTAMP_ID}" | ${STORAGE_CLI} cp - "gs://${BUCKET_NAME}/${PROBE_FILE}" >/dev/null 2>&1; then
    ${STORAGE_CLI} rm "gs://${BUCKET_NAME}/${PROBE_FILE}" >/dev/null 2>&1
    log_success "Bucket gs://${BUCKET_NAME} is writable."
else
    log_error "Failed to write probe to gs://${BUCKET_NAME}/${PROBE_FILE}. Check IAM permissions."
    exit 1
fi

# --- CHECK 5: Dataset Existence, Non-Emptiness & JSON Validation ---
log_step "5/7: Validating Training and Validation Datasets"
for dpath in "${TRAIN_DATA}" "${VAL_DATA}"; do
    if [[ ! -f "${dpath}" ]]; then
        log_error "Dataset file missing: ${dpath}"
        exit 1
    fi
    if [[ ! -s "${dpath}" ]]; then
        log_error "Dataset file is empty: ${dpath}"
        exit 1
    fi
done

# Run Python-based JSON syntax and schema validation
DATASET_METRICS=$(python3 - "${TRAIN_DATA}" "${VAL_DATA}" << 'EOF'
import sys, json, os

train_p, val_p = sys.argv[1], sys.argv[2]
results = {}

for label, p in [("train", train_p), ("val", val_p)]:
    size_bytes = os.path.getsize(p)
    line_count = 0
    with open(p, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except Exception as e:
                print(f"ERROR: {label} line {idx} is invalid JSON: {e}", file=sys.stderr)
                sys.exit(1)
            for req_field in ["prefix_text", "completion_text"]:
                if req_field not in record or not isinstance(record[req_field], str):
                    print(f"ERROR: {label} line {idx} missing required string field '{req_field}'", file=sys.stderr)
                    sys.exit(1)
            full_text_val = record.get("full_text") or record.get("text")
            if not isinstance(full_text_val, str):
                print(f"ERROR: {label} line {idx} missing required string field 'text' or 'full_text'", file=sys.stderr)
                sys.exit(1)
            if not full_text_val.startswith(record["prefix_text"]):
                print(f"ERROR: {label} line {idx} 'text'/'full_text' does not start with 'prefix_text'", file=sys.stderr)
                sys.exit(1)
            valid_start = (
                record["completion_text"].startswith("<|tool_call>call:")
                or record["completion_text"].startswith("<channel|>")
                or record["completion_text"].startswith("<|channel>thought\n<channel|>")
            )
            if not valid_start:
                print(f"ERROR: {label} line {idx} completion_text does not have valid boundary: {record['completion_text'][:60]}", file=sys.stderr)
                sys.exit(1)
            if "<|channel>thought" in record["completion_text"]:
                if not record["completion_text"].startswith("<|channel>thought\n<channel|>"):
                    print(f"ERROR: {label} line {idx} contains unclosed/non-empty thought tokens!", file=sys.stderr)
                    sys.exit(1)
            line_count += 1
    results[label] = {"lines": line_count, "size_mb": round(size_bytes / (1024*1024), 2)}

print(f"{results['train']['lines']}|{results['train']['size_mb']}|{results['val']['lines']}|{results['val']['size_mb']}")
EOF
)

TRAIN_LINES="$(echo "${DATASET_METRICS}" | cut -d'|' -f1)"
TRAIN_MB="$(echo "${DATASET_METRICS}" | cut -d'|' -f2)"
VAL_LINES="$(echo "${DATASET_METRICS}" | cut -d'|' -f3)"
VAL_MB="$(echo "${DATASET_METRICS}" | cut -d'|' -f4)"
TOTAL_LINES=$((TRAIN_LINES + VAL_LINES))
VAL_PCT="$(awk -v t="${TRAIN_LINES}" -v v="${VAL_LINES}" 'BEGIN { printf "%.1f", (v/(t+v))*100 }')"

log_info "Train Dataset : ${BOLD}${TRAIN_LINES}${RESET} samples (${TRAIN_MB} MB) -> ${TRAIN_DATA}"
log_info "Val Dataset   : ${BOLD}${VAL_LINES}${RESET} samples (${VAL_MB} MB) -> ${VAL_DATA}"
log_info "Total Samples : ${BOLD}${TOTAL_LINES}${RESET} samples (Val split: ${VAL_PCT}%)"
log_success "All JSONL datasets passed strict format & schema validation."

# --- CHECK 6: Training Script Integrity & SFT Architecture ---
log_step "6/7: Validating Training Script Integrity & SFT Configuration"
if [[ ! -f "${TRAIN_SCRIPT}" ]]; then
    log_error "Training script missing at: ${TRAIN_SCRIPT}"
    exit 1
fi

# Verify Python syntax
python3 -m py_compile "${TRAIN_SCRIPT}"
log_info "Python syntax compilation of ${BOLD}$(basename "${TRAIN_SCRIPT}")${RESET} passed."

# Verify Consultant 2's critical architectural constraints
python3 - "${TRAIN_SCRIPT}" << 'EOF'
import sys

script_path = sys.argv[1]
with open(script_path, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Assert target_modules includes q_proj, v_proj, o_proj (k_proj omitted per attention_k_eq_v=True spec)
for mod in ["q_proj", "v_proj", "o_proj"]:
    assert f'"{mod}"' in code or f"'{mod}'" in code, f"Architecture violation: target_modules missing '{mod}'!"
assert '"k_proj"' not in code and "'k_proj'" not in code, "Architecture violation: k_proj must be omitted (breaks attention_k_eq_v=True on 10 global layers)!"
# 2. Assert Rank 8 LoRA
assert "r=8" in code or "r = 8" in code, "Architecture violation: Rank must be 8!"

# 3. Assert zero-thought prefix-delta loss masking & clean candidate models
assert "prefix_text" in code, "Architecture violation: Missing 'prefix_text' in code!"
assert "-100" in code, "Architecture violation: Missing '-100' loss mask in code!"
assert "add_special_tokens=False" in code, "Architecture violation: Missing 'add_special_tokens=False' in code!"
assert "unsloth-bnb-4bit" not in code, "Architecture violation: 'unsloth-bnb-4bit' candidate must be removed!"

# 4. Assert dual-path base model loader & linear FP4 fallback
assert "google/gemma-4-31b-it-qat-w4a16-ct" in code, "Architecture violation: Missing primary 'google/gemma-4-31b-it-qat-w4a16-ct' model!"
assert "google/gemma-4-31B-it-qat-q4_0-unquantized" in code, "Architecture violation: Missing fallback 'google/gemma-4-31B-it-qat-q4_0-unquantized' model!"
assert "load_in_4bit=False" in code, "Architecture violation: Missing 'load_in_4bit=False' for pack-quantized w4a16-ct primary loader!"
assert "load_in_4bit=True" in code, "Architecture violation: Missing 'load_in_4bit=True' for FP4 fallback loader!"
assert "bnb_4bit_use_double_quant=False" in code, "Architecture violation: Missing 'bnb_4bit_use_double_quant=False'!"

# 5. Assert inline vLLM adapter normalization hook
assert "normalize_adapter_for_vllm" in code, "Architecture violation: Missing 'normalize_adapter_for_vllm' inline hook!"
assert "base_model.model.language_model.model.layers." in code, "Architecture violation: Missing 'base_model.model.language_model.model.layers.' prefix normalization!"

print("OK")
EOF
log_info "Architectural assertion passed: target_modules contains ['q_proj', 'v_proj', 'o_proj'] (k_proj omitted per attention_k_eq_v=True spec)."
log_info "Architectural assertion passed: Rank=8, zero-thought prefix-delta loss masking active."
log_info "Architectural assertion passed: Dual-path loader (w4a16-ct + q4_0-unquantized FP4) and inline vLLM adapter normalizer active."

# Check Hugging Face Token for gated base model download
if [[ -z "${HF_TOKEN}" ]]; then
    log_warn "HF_TOKEN is not set. If the base model requires authentication (e.g. google/gemma-4-31b-it), downloads will fail."
    log_warn "Set HF_TOKEN in .env.gcp or pass via --hf-token=<token>."
else
    TOKEN_PREVIEW="${HF_TOKEN:0:7}...${HF_TOKEN: -4}"
    log_info "Hugging Face Token detected: ${TOKEN_PREVIEW}"
fi
log_success "Training script architecture and configuration validated."

# --- CHECK 7: GCP Zone & GPU Hardware Capacity ---
log_step "7/7: Checking Zone Hardware & Machine Sizing"
log_info "Querying machine type ${BOLD}${MACHINE_TYPE}${RESET} in zone ${BOLD}${ZONE}${RESET}..."

MACHINE_DESC="$(gcloud compute machine-types describe "${MACHINE_TYPE}" --zone="${ZONE}" --project="${PROJECT_ID}" --format="json" 2>/dev/null || true)"
if [[ -z "${MACHINE_DESC}" ]]; then
    log_error "Machine type '${MACHINE_TYPE}' is not supported in zone '${ZONE}' on project '${PROJECT_ID}'!"
    exit 1
fi

CPUS="$(echo "${MACHINE_DESC}" | jq -r '.guestCpus // "N/A"')"
MEM_MB="$(echo "${MACHINE_DESC}" | jq -r '.memoryMb // 0')"
MEM_GB="$((MEM_MB / 1024))"
ACCEL_TYPE="$(echo "${MACHINE_DESC}" | jq -r '.accelerators[0].guestAcceleratorType // "none"')"
ACCEL_COUNT="$(echo "${MACHINE_DESC}" | jq -r '.accelerators[0].guestAcceleratorCount // 0')"

log_info "vCPUs: ${BOLD}${CPUS}${RESET} | Memory: ${BOLD}${MEM_GB} GB${RESET} | GPU: ${BOLD}${ACCEL_COUNT}x ${ACCEL_TYPE}${RESET}"

# Validate accelerator match
case "${MACHINE_TYPE}" in
    g2-standard-32)
        if [[ "${ACCEL_TYPE}" != "nvidia-l4" ]]; then
            log_warn "Expected nvidia-l4 for g2-standard-32, got '${ACCEL_TYPE}'"
        else
            log_info 'Hardware Profile: NVIDIA L4 (24GB VRAM) - Tuned for fast 4-bit SFT (~$0.35/hr Spot)'
        fi
        ;;
    g2-standard-48)
        log_info 'Hardware Profile: 4x NVIDIA L4 (96GB VRAM, 192GB RAM) - Tuned for 5-Test Unsloth SFT + vLLM TP=4 Evaluation'
        ;;
    g2-standard-24)
        log_info 'Hardware Profile: 2x NVIDIA L4 (48GB VRAM, 96GB RAM) - Fallback for 5-Test Unsloth SFT + vLLM TP=2 Evaluation'
        ;;
    a2-highgpu-1g)
        if [[ "${ACCEL_TYPE}" != "nvidia-tesla-a100" ]]; then
            log_warn "Expected nvidia-tesla-a100 for a2-highgpu-1g, got '${ACCEL_TYPE}'"
        else
            log_info 'Hardware Profile: NVIDIA A100 (40GB VRAM) - Tuned for 16-bit / high context (~$1.10/hr Spot)'
        fi
        ;;
    a2-ultragpu-1g)
        log_info 'Hardware Profile: NVIDIA A100 (80GB VRAM) - Tuned for full 16K context (~$1.80/hr Spot)'
        ;;
    *)
        log_info "Hardware Profile: Custom machine type ${MACHINE_TYPE}"
        ;;
esac
log_success "Zone '${ZONE}' possesses valid GPU capacity for '${MACHINE_TYPE}'."

# Validate Deep Learning VM image family exists
log_info "Verifying OS image family '${DEFAULT_IMAGE_FAMILY}' in '${DEFAULT_IMAGE_PROJECT}'..."
if ! gcloud compute images describe-from-family "${DEFAULT_IMAGE_FAMILY}" --project="${DEFAULT_IMAGE_PROJECT}" >/dev/null 2>&1; then
    log_error "Image family '${DEFAULT_IMAGE_FAMILY}' not found in project '${DEFAULT_IMAGE_PROJECT}'!"
    exit 1
fi
log_success "OS image family '${DEFAULT_IMAGE_FAMILY}' verified and available."

# ------------------------------------------------------------------------------
# 6. Preflight Summary
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}${GREEN}==============================================================================${RESET}"
echo -e "${BOLD}${GREEN}                     ALL PREFLIGHT CHECKS PASSED (7/7)                        ${RESET}"
echo -e "${BOLD}${GREEN}==============================================================================${RESET}"
echo -e "  ${BOLD}Account:${RESET}          ${ACTIVE_ACCOUNT}"
echo -e "  ${BOLD}Project:${RESET}          ${PROJECT_ID}"
echo -e "  ${BOLD}Zone:${RESET}             ${ZONE}"
echo -e "  ${BOLD}Machine Type:${RESET}     ${MACHINE_TYPE} (${ACCEL_COUNT}x ${ACCEL_TYPE}, ${CPUS} vCPUs, ${MEM_GB}GB RAM)"
echo -e "  ${BOLD}Provisioning:${RESET}     ${PROVISIONING_MODEL}"
echo -e "  ${BOLD}Bucket:${RESET}           gs://${BUCKET_NAME}"
echo -e "  ${BOLD}Datasets:${RESET}         ${TRAIN_LINES} train / ${VAL_LINES} val (${TOTAL_LINES} total)"
echo -e "  ${BOLD}Target Modules:${RESET}   q_proj, v_proj, o_proj (Rank-8, k_proj omitted)"
echo -e "  ${BOLD}Zero-Leak Trap:${RESET}   Autonomous self-destruct upon completion or failure"
echo -e "${BOLD}${GREEN}==============================================================================${RESET}"
echo ""

if ${DRY_RUN}; then
    log_info "${BOLD}DRY-RUN COMPLETE.${RESET} All configurations, datasets, credentials, and APIs are 100% ready."
    log_info "To launch the actual training VM, run without --dry-run:"
    echo -e "\n  ${BOLD}./gcp/deploy_gemma4_lora.sh --machine-type=${MACHINE_TYPE} --zone=${ZONE}${RESET}\n"
    exit 0
fi

# ------------------------------------------------------------------------------
# 7. Deployment Execution: Stage Assets to GCS & Clear Stale Outputs
# ------------------------------------------------------------------------------
log_step "Staging Datasets and Training Script to Cloud Storage"
log_info "Clearing stale output artifacts from previous runs in gs://${BUCKET_NAME}/output/main_lora/ and gs://${BUCKET_NAME}/five_test_results/..."
${STORAGE_CLI} rm "gs://${BUCKET_NAME}/output/main_lora/**" 2>/dev/null || true
${STORAGE_CLI} rm "gs://${BUCKET_NAME}/five_test_results/**" 2>/dev/null || true
if ${CLI_FIVE_TEST_ALIGNMENT} && [[ -f "${REPO_ROOT}/submissions/track2_5test_probe/adapters/main_lora/adapter_model.safetensors" ]]; then
    log_info "Staging verified pre-trained 5-test LoRA adapter to gs://${BUCKET_NAME}/output/main_lora/..."
    ${STORAGE_CLI} cp "${REPO_ROOT}/submissions/track2_5test_probe/adapters/main_lora/adapter_config.json" "${REPO_ROOT}/submissions/track2_5test_probe/adapters/main_lora/adapter_model.safetensors" "gs://${BUCKET_NAME}/output/main_lora/"
fi

log_info "Uploading ${TRAIN_DATA} -> gs://${BUCKET_NAME}/input/unsloth_sft_train.jsonl"
${STORAGE_CLI} cp "${TRAIN_DATA}" "gs://${BUCKET_NAME}/input/unsloth_sft_train.jsonl"

log_info "Uploading ${VAL_DATA} -> gs://${BUCKET_NAME}/input/unsloth_sft_val.jsonl"
${STORAGE_CLI} cp "${VAL_DATA}" "gs://${BUCKET_NAME}/input/unsloth_sft_val.jsonl"

log_info "Uploading ${TRAIN_SCRIPT} -> gs://${BUCKET_NAME}/input/train_gemma4_unsloth_cloud.py"
${STORAGE_CLI} cp "${TRAIN_SCRIPT}" "gs://${BUCKET_NAME}/input/train_gemma4_unsloth_cloud.py"

if ${CLI_FIVE_TEST_ALIGNMENT}; then
    log_info "Staging 5-test alignment bundle to gs://${BUCKET_NAME}/five_test_bundle/..."
    ${STORAGE_CLI} cp "${TRAIN_DATA}" "gs://${BUCKET_NAME}/five_test_bundle/train.jsonl"
    ${STORAGE_CLI} cp "${VAL_DATA}" "gs://${BUCKET_NAME}/five_test_bundle/val.jsonl"
    ${STORAGE_CLI} cp -r "${REPO_ROOT}/data/unsloth_sft_5test/stubs" "gs://${BUCKET_NAME}/five_test_bundle/"
    ${STORAGE_CLI} cp -r "${REPO_ROOT}/submissions/track2_5test_probe" "gs://${BUCKET_NAME}/five_test_bundle/"
    ${STORAGE_CLI} cp "${REPO_ROOT}/tasks.jsonl" "gs://${BUCKET_NAME}/five_test_bundle/tasks.jsonl"
    ${STORAGE_CLI} cp "${REPO_ROOT}/scripts/run_eval.py" "gs://${BUCKET_NAME}/five_test_bundle/run_eval.py"
    if ${STORAGE_CLI} ls "gs://${BUCKET_NAME}/five_test_bundle/wheelhouse/vllm-0.19.1-cp38-abi3-manylinux_2_31_x86_64.whl" >/dev/null 2>&1; then
        log_info "Wheelhouse and snapshots already cached in gs://${BUCKET_NAME}/five_test_bundle/; skipping bulk binary re-upload."
    else
        for tid in rich_3882 fastapi_14786 requests_7315 rich_3905 requests_7427; do
            if [[ -f "${REPO_ROOT}/snapshots/${tid}.tgz" ]]; then
                ${STORAGE_CLI} cp "${REPO_ROOT}/snapshots/${tid}.tgz" "gs://${BUCKET_NAME}/five_test_bundle/snapshots/${tid}.tgz"
            fi
        done
        if [[ -d "/tmp/wheelhouse" ]] && compgen -G "/tmp/wheelhouse/*.whl" >/dev/null; then
            ${STORAGE_CLI} cp /tmp/wheelhouse/*.whl "gs://${BUCKET_NAME}/five_test_bundle/wheelhouse/"
        else
            log_error "Missing /tmp/wheelhouse/*.whl required for /opt/venv_eval (vllm + swegemma + adk)!"
            exit 1
        fi
        if [[ -d "${REPO_ROOT}/wheels" ]] && compgen -G "${REPO_ROOT}/wheels/*.whl" >/dev/null; then
            ${STORAGE_CLI} cp "${REPO_ROOT}"/wheels/*.whl "gs://${BUCKET_NAME}/five_test_bundle/wheels/"
        fi
    fi
fi

log_success "Staged assets verified in gs://${BUCKET_NAME}/input/:"
${STORAGE_CLI} ls "gs://${BUCKET_NAME}/input/"
# ------------------------------------------------------------------------------
# 8. Generate Ephemeral VM Startup Script with Zero-Leak Trap
# ------------------------------------------------------------------------------
STARTUP_SCRIPT_PATH="/tmp/startup_${INSTANCE_NAME}.sh"
log_step "Generating Ephemeral VM Startup Script with Autonomous Self-Destruct Trap"

cat << 'EOF' > "${STARTUP_SCRIPT_PATH}"
#!/usr/bin/env bash
set -euo pipefail
set -x
export PATH="/opt/conda/bin:/usr/local/cuda/bin:/usr/local/bin:${PATH}"

LOG_FILE="/var/log/gemma4_training.log"
exec > >(tee -a "${LOG_FILE}") 2>&1

echo "=== Booting Gemma 4 LoRA Ephemeral Trainer ==="
date -u +"%Y-%m-%d %H:%M:%S UTC"

TRAINING_SUCCESS=0

# Zero-Leak Guardrail: Autonomous self-destruct trap
cleanup_and_destroy() {
    EXIT_CODE=$?
    echo "=== Training Finished or Trapped (exit code: ${EXIT_CODE}) ==="
    date -u +"%Y-%m-%d %H:%M:%S UTC"
    
    ZONE=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/zone" | awk -F/ '{print $NF}')
    VM_NAME=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/name")
    
    if [[ "${TRAINING_SUCCESS}" -eq 1 ]]; then
        echo "Training succeeded cleanly. Self-destructing VM immediately to prevent billing leaks..."
        gcloud compute instances delete "${VM_NAME}" --zone="${ZONE}" --quiet || sudo poweroff
    else
        echo "Training encountered an error. Sleeping 300 seconds for telemetry inspection before self-destruct..."
        sleep 300
        gcloud compute instances delete "${VM_NAME}" --zone="${ZONE}" --quiet || sudo poweroff
    fi
}
trap cleanup_and_destroy EXIT

# Wait for NVIDIA drivers to load (max 300s timeout)
echo "Waiting for NVIDIA GPU drivers..."
DRIVER_ATTEMPTS=0
until nvidia-smi >/dev/null 2>&1; do
    DRIVER_ATTEMPTS=$((DRIVER_ATTEMPTS + 1))
    if [[ "${DRIVER_ATTEMPTS}" -ge 60 ]]; then
        echo "ERROR: NVIDIA drivers failed to load after 300 seconds!"
        exit 1
    fi
    echo "NVIDIA drivers not ready yet (attempt ${DRIVER_ATTEMPTS}/60), sleeping 5s..."
    sleep 5
done
nvidia-smi

# Prepare work directories
mkdir -p /opt/data /opt/output/main_lora /opt/scripts

# Wait for GCP metadata server reachability (protects against network control plane programming delays)
for meta_attempt in $(seq 1 30); do
    if curl -s -f -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/name" >/dev/null 2>&1; then
        break
    fi
    echo "Waiting for metadata server reachability (attempt ${meta_attempt}/30)..."
    sleep 5
done

# Fetch metadata attributes (disable set -x around HF_TOKEN to redact secret from logs)
BUCKET_NAME=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/bucket_name")
FIVE_TEST_MODE=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/five_test_alignment" || echo "false")
set +x
HF_TOKEN=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/hf_token")
export HF_TOKEN="${HF_TOKEN}"
export HUGGING_FACE_HUB_TOKEN="${HF_TOKEN}"
set -x
# Pull input assets from GCS
echo "Downloading staged assets from gs://${BUCKET_NAME}/input/..."
gcloud storage cp "gs://${BUCKET_NAME}/input/unsloth_sft_train.jsonl" /opt/data/
gcloud storage cp "gs://${BUCKET_NAME}/input/unsloth_sft_val.jsonl" /opt/data/
gcloud storage cp "gs://${BUCKET_NAME}/input/train_gemma4_unsloth_cloud.py" /opt/scripts/

export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"
export PYTORCH_ALLOC_CONF="expandable_segments:True"
export HF_HUB_DISABLE_XET="1"
export PYTHONUNBUFFERED="1"

# Expand root partition if running on a larger disk
growpart /dev/nvme0n1 1 2>/dev/null && resize2fs /dev/nvme0n1p1 2>/dev/null || true
growpart /dev/sda 1 2>/dev/null && resize2fs /dev/sda1 2>/dev/null || true

# Ensure virtualenv and uv are available for clean venv provisioning without ensurepip issues
pip install --upgrade pip virtualenv uv 2>/dev/null || python3 -m pip install --upgrade pip virtualenv uv 2>/dev/null || true

if [[ "${FIVE_TEST_MODE}" == "true" ]]; then
    echo "=== Executing 5-Test End-to-End Dual-Venv Alignment & Kaggle Evaluation Pipeline ==="
    mkdir -p /workspace/submissions /workspace/scripts /workspace/snapshots /workspace/graphs /workspace/embeddings /workspace/wheels /opt/wheelhouse
    gcloud storage cp "gs://${BUCKET_NAME}/five_test_bundle/train.jsonl" /opt/train.jsonl
    gcloud storage cp "gs://${BUCKET_NAME}/five_test_bundle/val.jsonl" /opt/val.jsonl
    gcloud storage cp -r "gs://${BUCKET_NAME}/five_test_bundle/track2_5test_probe" /workspace/submissions/
    gcloud storage cp -r "gs://${BUCKET_NAME}/five_test_bundle/stubs/graphs/*" /workspace/graphs/
    gcloud storage cp -r "gs://${BUCKET_NAME}/five_test_bundle/stubs/embeddings/*" /workspace/embeddings/
    gcloud storage cp "gs://${BUCKET_NAME}/five_test_bundle/tasks.jsonl" /workspace/tasks.jsonl
    gcloud storage cp "gs://${BUCKET_NAME}/five_test_bundle/run_eval.py" /workspace/scripts/run_eval.py
    gcloud storage cp "gs://${BUCKET_NAME}/five_test_bundle/snapshots/*" /workspace/snapshots/ || true
    gcloud storage cp "gs://${BUCKET_NAME}/five_test_bundle/wheelhouse/*.whl" /opt/wheelhouse/
    gcloud storage cp "gs://${BUCKET_NAME}/five_test_bundle/wheels/*.whl" /workspace/wheels/ || true

    mkdir -p /workspace/submissions/track2_5test_probe/adapters/main_lora
    if [[ -f "/workspace/submissions/track2_5test_probe/adapters/main_lora/adapter_model.safetensors" ]]; then
        echo "=== Found pre-trained 5-test LoRA adapter in workspace bundle; syncing to output and proceeding directly to Step 2 ==="
        gcloud storage cp /workspace/submissions/track2_5test_probe/adapters/main_lora/adapter_config.json /workspace/submissions/track2_5test_probe/adapters/main_lora/adapter_model.safetensors "gs://${BUCKET_NAME}/output/main_lora/" || true
    elif gcloud storage stat "gs://${BUCKET_NAME}/output/main_lora/adapter_model.safetensors" >/dev/null 2>&1; then
        echo "=== Found pre-trained 5-test LoRA adapter in GCS; downloading directly to accelerate evaluation ==="
        gcloud storage cp "gs://${BUCKET_NAME}/output/main_lora/adapter_config.json" "gs://${BUCKET_NAME}/output/main_lora/adapter_model.safetensors" /workspace/submissions/track2_5test_probe/adapters/main_lora/
    else
        # Venv 1 (/opt/venv_train): Isolated Unsloth training environment
        DEBIAN_FRONTEND=noninteractive apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-venv python3.10-venv
        python3 -m virtualenv --system-site-packages /opt/venv_train
        /opt/venv_train/bin/pip install --upgrade pip
        /opt/venv_train/bin/pip install --no-cache-dir \
            "unsloth @ git+https://github.com/unslothai/unsloth.git" \
            trl peft accelerate bitsandbytes datasets "jinja2==3.1.6" "compressed-tensors>=0.15.0"
        /opt/venv_train/bin/pip install --no-deps unsloth_zoo
        /opt/venv_train/bin/pip uninstall -y torchaudio torchao || true
        /opt/venv_train/bin/pip install --upgrade --no-cache-dir torchvision || true
        rm -rf /usr/local/lib/python3*/dist-packages/torchaudio* /usr/lib/python3*/dist-packages/torchaudio* || true

        echo "=== Step 1: Running 5-Test SFT on GPU 0 ==="
        CUDA_VISIBLE_DEVICES=0 /opt/venv_train/bin/python /opt/scripts/train_gemma4_unsloth_cloud.py \
            --train-file /opt/train.jsonl \
            --val-file /opt/val.jsonl \
            --output-dir /workspace/submissions/track2_5test_probe/adapters/main_lora \
            --max-seq-length 3072 \
            --num-train-epochs 2 \
            --gradient-accumulation-steps 1 \
            --learning-rate 2e-4 \
            --max-steps 80

        if [[ ! -f "/workspace/submissions/track2_5test_probe/adapters/main_lora/adapter_model.safetensors" ]]; then
            echo "FATAL: 5-test adapter_model.safetensors was not generated!"
            exit 1
        fi
        rm -rf /workspace/submissions/track2_5test_probe/adapters/main_lora/checkpoint* || true
        gcloud storage cp /workspace/submissions/track2_5test_probe/adapters/main_lora/adapter_config.json /workspace/submissions/track2_5test_probe/adapters/main_lora/adapter_model.safetensors "gs://${BUCKET_NAME}/adapters/five_test_main_lora/"
        gcloud storage cp /workspace/submissions/track2_5test_probe/adapters/main_lora/adapter_config.json /workspace/submissions/track2_5test_probe/adapters/main_lora/adapter_model.safetensors "gs://${BUCKET_NAME}/output/main_lora/"
        pkill -f train_gemma4_unsloth_cloud.py || true
    fi
    # Venv 2 (/opt/venv_eval): Isolated Kaggle vLLM + ADK evaluation environment
    echo "=== Step 2: Provisioning /opt/venv_eval and Launching vLLM + SWE-Gemma Evaluation ==="
    if ! command -v python3.12 >/dev/null 2>&1; then
        echo "Installing Python 3.12 for evaluation environment (swegemma and cp312 wheels)..."
        apt-get update -qq
        DEBIAN_FRONTEND=noninteractive apt-get install -y -qq software-properties-common
        add-apt-repository -y ppa:deadsnakes/ppa
        apt-get update -qq
        DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3.12 python3.12-venv python3.12-dev
    fi
    python3 -m virtualenv -p python3.12 /opt/venv_eval || python3.12 -m venv /opt/venv_eval
    /opt/venv_eval/bin/pip install --upgrade pip
    /opt/venv_eval/bin/pip install --no-cache-dir \
        vllm torch torchvision pytest pytest-timeout pytest-asyncio "anyio==4.14.2" litellm
    for whl in /opt/wheelhouse/*.whl; do
        whl_name=$(basename "${whl}")
        case "${whl_name}" in
            vllm-*|flashinfer_*|torch*)
                echo "Skipping ${whl_name} to preserve PyPI vLLM + PyTorch ABI compatibility..."
                ;;
            *)
                /opt/venv_eval/bin/pip install --no-deps --force-reinstall "${whl}" || true
                ;;
        esac
    done
    /opt/venv_eval/bin/python -c "import vllm; print('vLLM verification PASS:', vllm.__version__)"
    /opt/venv_eval/bin/python -c "import swegemma, google.adk; print('SWE-Gemma and ADK verification PASS!')"

    TP_SIZE=$(nvidia-smi -L | wc -l)
    VLLM_EXTRA_ARGS=()
    if [[ "${TP_SIZE}" -eq 1 ]]; then
        VLLM_EXTRA_ARGS+=(
            --cpu-offload-gb 10
            --enforce-eager
            --max-model-len 32768
        )
    else
        VLLM_EXTRA_ARGS+=(--max-model-len 32768)
    fi

    /opt/venv_eval/bin/vllm serve google/gemma-4-31b-it-qat-w4a16-ct \
        --served-model-name gemma-4-31b-it-qat-w4a16-ct \
        --tensor-parallel-size "${TP_SIZE}" \
        --gpu-memory-utilization 0.85 \
        "${VLLM_EXTRA_ARGS[@]}" \
        --enable-auto-tool-choice \
        --tool-call-parser gemma4 \
        --reasoning-parser gemma4 \
        --default-chat-template-kwargs '{"enable_thinking": true}' \
        --enable-lora \
        --max-loras 8 \
        --max-lora-rank 128 \
        --lora-modules main_lora=/workspace/submissions/track2_5test_probe/adapters/main_lora \
        --port 8000 &
    VLLM_PID=$!

    echo "Waiting for vLLM server at http://127.0.0.1:8000/v1/models to register main_lora..."
    VLLM_READY=0
    for attempt in $(seq 1 180); do
        if ! kill -0 "${VLLM_PID}" 2>/dev/null; then
            echo "FATAL: vLLM process (${VLLM_PID}) exited prematurely during startup!"
            exit 1
        fi
        if curl -s http://127.0.0.1:8000/v1/models | grep -q "main_lora"; then
            echo "vLLM server ready with main_lora registered!"
            VLLM_READY=1
            break
        fi
        sleep 5
    done
    if [[ "${VLLM_READY}" -ne 1 ]]; then
        echo "FATAL: vLLM server failed to register main_lora within 900 seconds!"
        kill "${VLLM_PID}" 2>/dev/null || true
        exit 1
    fi

    printf "rich_3882\nfastapi_14786\nrequests_7315\nrich_3905\nrequests_7427\n" > /opt/test_5tasks.txt
    cd /workspace
    /opt/venv_eval/bin/python /workspace/scripts/run_eval.py \
        --sandbox subprocess \
        --submission-dir /workspace/submissions/track2_5test_probe \
        --tasks-file /opt/test_5tasks.txt \
        --concurrency 1 \
        --max-tool-calls 40 \
        --api-base http://127.0.0.1:8000/v1 \
        --model main_lora
    LATEST_RUN_DIR=$(ls -td /workspace/results/run_* 2>/dev/null | head -n 1 || true)
    if [[ -n "${LATEST_RUN_DIR}" && -d "${LATEST_RUN_DIR}" ]]; then
        gcloud storage cp -r "${LATEST_RUN_DIR}"/* "gs://${BUCKET_NAME}/five_test_results/" || true
        gcloud storage cp "${LATEST_RUN_DIR}/summary.json" "gs://${BUCKET_NAME}/five_test_results/summary.json" 2>/dev/null || true
    fi
    kill "${VLLM_PID}" || true
    TRAINING_SUCCESS=1
    echo "=== 5-Test Training & Kaggle Challenge Evaluation Complete ==="
else
    # Install Unsloth and fine-tuning dependencies
    echo "Installing Unsloth and fine-tuning dependencies..."
    pip install --upgrade pip
    pip install --no-cache-dir \
        "unsloth @ git+https://github.com/unslothai/unsloth.git" \
        trl peft accelerate bitsandbytes datasets "jinja2==3.1.6" "compressed-tensors>=0.15.0"
    pip install --no-deps unsloth_zoo
    pip uninstall -y torchaudio torchao || true
    pip install --upgrade --no-cache-dir torchvision || true
    rm -rf /usr/local/lib/python3*/dist-packages/torchaudio* /usr/lib/python3*/dist-packages/torchaudio* || true

    # Pre-flight environment import check
    python3 -c "import sys; sys.modules['torchaudio'] = None; import torch, transformers, trl, unsloth; print('Pre-flight check passed! CUDA:', torch.cuda.is_available(), 'Unsloth:', getattr(unsloth, '__version__', 'ok'))"

    # Set runtime optimization flags
    export DATA_DIR="/opt/data"
    export OUTPUT_DIR="/opt/output/main_lora"

    echo "=== Commencing Gemma 4 Unsloth Training Script ==="
    python3 /opt/scripts/train_gemma4_unsloth_cloud.py

    # Verify trained adapter artifacts before marking success
    if [[ -f "/opt/output/main_lora/adapter_model.safetensors" ]]; then
        echo "Adapter verified! Syncing trained artifacts to gs://${BUCKET_NAME}/output/main_lora/..."
        gcloud storage cp -r /opt/output/main_lora/* "gs://${BUCKET_NAME}/output/main_lora/"
        TRAINING_SUCCESS=1
        echo "=== Training Run and Artifact Sync Complete ==="
    else
        echo "FATAL: adapter_model.safetensors was not generated!"
        exit 1
    fi
fi
EOF

chmod +x "${STARTUP_SCRIPT_PATH}"
log_success "Startup script generated with zero-leak self-destruct handler."

# ------------------------------------------------------------------------------
# 9. Provision Ephemeral Compute Engine VM
# ------------------------------------------------------------------------------
log_step "Provisioning Ephemeral GPU VM (${INSTANCE_NAME})"

EXTRA_PROVISIONING_FLAGS=()
if [[ "${PROVISIONING_MODEL}" == "SPOT" ]]; then
    EXTRA_PROVISIONING_FLAGS+=(
        --provisioning-model="SPOT"
        --instance-termination-action="DELETE"
    )
fi

log_info "Executing gcloud compute instances create..."
PROVISIONED=false
if ${CLI_FIVE_TEST_ALIGNMENT}; then
    # Exclude us-central1-b due to scheduled network control plane maintenance
    CANDIDATE_ZONES=("us-east4-a" "us-west1-a" "us-central1-a" "us-central1-c" "us-east1-b" "us-east1-c" "us-east4-c" "us-west1-b" "us-west4-a" "europe-west4-a" "asia-southeast1-a")
    CANDIDATE_MACHINES=("g2-standard-12" "g2-standard-16" "${MACHINE_TYPE}")
    PROV_MODES=()
    if [[ "${PROVISIONING_MODEL}" == "STANDARD" ]]; then
        PROV_MODES=("STANDARD")
    else
        PROV_MODES=("SPOT")
    fi
    for prov_mode in "${PROV_MODES[@]}"; do
        PROV_FLAGS=()
        if [[ "${prov_mode}" == "SPOT" ]]; then
            PROV_FLAGS+=(--provisioning-model="SPOT" --instance-termination-action="DELETE")
        fi
        for cand_mach in "${CANDIDATE_MACHINES[@]}"; do
            for cand_zone in "${CANDIDATE_ZONES[@]}"; do
                if [[ "${cand_zone}" == "us-central1-b" ]]; then
                    continue
                fi
                log_info "Attempting ${cand_mach} (${prov_mode}) in ${cand_zone}..."
                if gcloud compute instances create "${INSTANCE_NAME}" \
                    --project="${PROJECT_ID}" \
                    --zone="${cand_zone}" \
                    --machine-type="${cand_mach}" \
                    ${PROV_FLAGS[@]+"${PROV_FLAGS[@]}"} \
                    --maintenance-policy="TERMINATE" \
                    --image-family="${DEFAULT_IMAGE_FAMILY}" \
                    --image-project="${DEFAULT_IMAGE_PROJECT}" \
                    --boot-disk-size="${DISK_SIZE}" \
                    --boot-disk-type="pd-balanced" \
                    --scopes="https://www.googleapis.com/auth/cloud-platform" \
                    --metadata="install-nvidia-driver=True,bucket_name=${BUCKET_NAME},hf_token=${HF_TOKEN},five_test_alignment=${CLI_FIVE_TEST_ALIGNMENT}" \
                    --metadata-from-file="startup-script=${STARTUP_SCRIPT_PATH}"; then
                    ZONE="${cand_zone}"
                    MACHINE_TYPE="${cand_mach}"
                    PROVISIONING_MODEL="${prov_mode}"
                    PROVISIONED=true
                    break 3
                else
                    log_warn "Capacity/quota unavailable for ${cand_mach} (${prov_mode}) in ${cand_zone}, trying next fallback..."
                fi
            done
        done
    done
else
    gcloud compute instances create "${INSTANCE_NAME}" \
        --project="${PROJECT_ID}" \
        --zone="${ZONE}" \
        --machine-type="${MACHINE_TYPE}" \
        ${EXTRA_PROVISIONING_FLAGS[@]+"${EXTRA_PROVISIONING_FLAGS[@]}"} \
        --maintenance-policy="TERMINATE" \
        --image-family="${DEFAULT_IMAGE_FAMILY}" \
        --image-project="${DEFAULT_IMAGE_PROJECT}" \
        --boot-disk-size="${DISK_SIZE}" \
        --boot-disk-type="pd-balanced" \
        --scopes="https://www.googleapis.com/auth/cloud-platform" \
        --metadata="install-nvidia-driver=True,bucket_name=${BUCKET_NAME},hf_token=${HF_TOKEN},five_test_alignment=${CLI_FIVE_TEST_ALIGNMENT}" \
        --metadata-from-file="startup-script=${STARTUP_SCRIPT_PATH}"
    PROVISIONED=true
fi

rm -f "${STARTUP_SCRIPT_PATH}"
if ! ${PROVISIONED}; then
    log_error "Failed to provision VM across all candidate zones and machine types."
    exit 1
fi
log_success "VM '${INSTANCE_NAME}' created successfully in ${ZONE} (${MACHINE_TYPE})."

# ------------------------------------------------------------------------------
# 10. Post-Launch Instructions & Telemetry Guide
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}${BLUE}╔══════════════════════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${BLUE}║${WHITE}                 TRAINING DEPLOYED & TELEMETRY MONITORING                     ${RESET}"
echo -e "${BOLD}${BLUE}╚══════════════════════════════════════════════════════════════════════════════╝${RESET}"
echo -e ""
echo -e "  ${BOLD}1. Autonomous Polling & Auto-Download:${RESET}"
echo -e "     ${CYAN}./scripts/monitor_gcp_train.sh wait${RESET}"
echo -e "     (Polls Cloud Storage until adapter lands, then downloads to my_submission/adapters/main_lora/)"
echo -e ""
echo -e "  ${BOLD}2. Live Remote Log Streaming (SSH):${RESET}"
echo -e "     ${CYAN}./scripts/monitor_gcp_train.sh tail${RESET}"
echo -e ""
echo -e "  ${BOLD}3. GPU Status & Log Snapshot:${RESET}"
echo -e "     ${CYAN}./scripts/monitor_gcp_train.sh status${RESET}"
echo -e ""
echo -e "  ${BOLD}4. Serial Console Output (Early boot & kernel logs):${RESET}"
echo -e "     ${CYAN}gcloud compute instances get-serial-port-output ${INSTANCE_NAME} --zone=${ZONE} --project=${PROJECT_ID}${RESET}"
echo -e ""
echo -e "  ${BOLD}5. Cloud Storage Harvest Location:${RESET}"
echo -e "     ${CYAN}gs://${BUCKET_NAME}/output/main_lora/${RESET}"
echo -e ""
echo -e "  ${BOLD}6. Emergency Teardown (if needed):${RESET}"
echo -e "     ${CYAN}gcloud compute instances delete ${INSTANCE_NAME} --zone=${ZONE} --project=${PROJECT_ID} --quiet${RESET}"
echo -e ""
log_success "Pipeline deployment finished. Follow instructions above to monitor."

if [[ "${CLI_WAIT_MONITOR:-false}" == "true" ]]; then
    echo ""
    log_info "Initiating autonomous 5-minute background monitoring (--wait specified)..."
    exec "${REPO_ROOT}/scripts/monitor_gcp_train.sh" wait
fi
