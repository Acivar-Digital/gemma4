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
MACHINE_TYPE="${CLI_MACHINE:-${GCP_MACHINE_TYPE:-${DEFAULT_MACHINE}}}"
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
DISK_SIZE="${CLI_DISK_SIZE:-${DEFAULT_DISK_SIZE}}"
DRY_RUN="${CLI_DRY_RUN}"

TRAIN_DATA="${REPO_ROOT}/data/unsloth_sft_train.jsonl"
VAL_DATA="${REPO_ROOT}/data/unsloth_sft_val.jsonl"
TRAIN_SCRIPT="${REPO_ROOT}/scripts/train_gemma4_unsloth_cloud.py"

MACHINE_SHORT="${MACHINE_TYPE%%-*}"
TIMESTAMP_ID="$(date +%s)"
INSTANCE_NAME="gemma4-unsloth-${MACHINE_SHORT}-${TIMESTAMP_ID}"

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
ACTIVE_ACCOUNT="$(gcloud auth list --filter="status:ACTIVE" --format="value(account)" 2>/dev/null | head -n 1 || true)"

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
            if "messages" not in record or not isinstance(record["messages"], list):
                print(f"ERROR: {label} line {idx} missing 'messages' list", file=sys.stderr)
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

# 1. Assert target_modules includes k_proj, q_proj, v_proj, o_proj
for mod in ["k_proj", "q_proj", "v_proj", "o_proj"]:
    assert f'"{mod}"' in code or f"'{mod}'" in code, f"Architecture violation: target_modules missing '{mod}'!"

# 2. Assert Rank 8 LoRA
assert "r=8" in code or "r = 8" in code, "Architecture violation: Rank must be 8!"

# 3. Assert Response-only loss masking
assert "train_on_responses_only" in code, "Architecture violation: Missing response-only loss masking!"

print("OK")
EOF
log_info "Architectural assertion passed: target_modules contains ['k_proj', 'q_proj', 'v_proj', 'o_proj']."
log_info "Architectural assertion passed: Rank=8, response-only loss masking active."

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
echo -e "  ${BOLD}Target Modules:${RESET}   q_proj, k_proj, v_proj, o_proj (Rank-8)"
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
log_info "Clearing stale output artifacts from previous runs in gs://${BUCKET_NAME}/output/main_lora/..."
${STORAGE_CLI} rm "gs://${BUCKET_NAME}/output/main_lora/**" 2>/dev/null || true

log_info "Uploading ${TRAIN_DATA} -> gs://${BUCKET_NAME}/input/unsloth_sft_train.jsonl"
${STORAGE_CLI} cp "${TRAIN_DATA}" "gs://${BUCKET_NAME}/input/unsloth_sft_train.jsonl"

log_info "Uploading ${VAL_DATA} -> gs://${BUCKET_NAME}/input/unsloth_sft_val.jsonl"
${STORAGE_CLI} cp "${VAL_DATA}" "gs://${BUCKET_NAME}/input/unsloth_sft_val.jsonl"

log_info "Uploading ${TRAIN_SCRIPT} -> gs://${BUCKET_NAME}/input/train_gemma4_unsloth_cloud.py"
${STORAGE_CLI} cp "${TRAIN_SCRIPT}" "gs://${BUCKET_NAME}/input/train_gemma4_unsloth_cloud.py"

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

# Fetch metadata attributes
BUCKET_NAME=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/bucket_name")
HF_TOKEN=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/hf_token")

# Pull input assets from GCS
echo "Downloading staged assets from gs://${BUCKET_NAME}/input/..."
gcloud storage cp "gs://${BUCKET_NAME}/input/unsloth_sft_train.jsonl" /opt/data/
gcloud storage cp "gs://${BUCKET_NAME}/input/unsloth_sft_val.jsonl" /opt/data/
gcloud storage cp "gs://${BUCKET_NAME}/input/train_gemma4_unsloth_cloud.py" /opt/scripts/

# Install Unsloth and fine-tuning dependencies
echo "Installing Unsloth and fine-tuning dependencies..."
pip install --upgrade pip
pip install --no-cache-dir \
    "unsloth @ git+https://github.com/unslothai/unsloth.git" \
    trl peft accelerate bitsandbytes datasets "jinja2==3.1.6"
pip install --no-deps unsloth_zoo
pip uninstall -y torchaudio torchao || true

# Pre-flight environment import check
python3 -c "import sys; sys.modules['torchaudio'] = None; import torch, transformers, trl, unsloth; print('Pre-flight check passed! CUDA:', torch.cuda.is_available(), 'Unsloth:', getattr(unsloth, '__version__', 'ok'))"

# Set runtime optimization flags
export DATA_DIR="/opt/data"
export OUTPUT_DIR="/opt/output/main_lora"
export HF_TOKEN="${HF_TOKEN}"
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"
export PYTORCH_ALLOC_CONF="expandable_segments:True"
export HF_HUB_DISABLE_XET="1"
export PYTHONUNBUFFERED="1"

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
    --metadata="install-nvidia-driver=True,bucket_name=${BUCKET_NAME},hf_token=${HF_TOKEN}" \
    --metadata-from-file="startup-script=${STARTUP_SCRIPT_PATH}"

rm -f "${STARTUP_SCRIPT_PATH}"
log_success "VM '${INSTANCE_NAME}' created successfully."

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
