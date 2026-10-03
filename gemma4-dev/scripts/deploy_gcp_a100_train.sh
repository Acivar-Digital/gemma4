#!/usr/bin/env bash
# ==============================================================================
# deploy_gcp_a100_train.sh
# Ephemeral Spot A100 Unsloth Gemma 4 31B Training Launcher
# Project: gen-lang-client-0266946478 (yapcheeleong@gmail.com)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

CLI_ZONE="${GCP_ZONE:-}"
CLI_MACHINE="${GCP_MACHINE_TYPE:-}"
CLI_PROVISIONING="${GCP_PROVISIONING_MODEL:-}"

if [[ -f "${ROOT_DIR}/.env.gcp" ]]; then
    source "${ROOT_DIR}/.env.gcp"
fi

PROJECT_ID="${GCP_PROJECT:-gen-lang-client-0266946478}"
ZONE="${CLI_ZONE:-${GCP_ZONE:-us-central1-b}}"
MACHINE_TYPE="${CLI_MACHINE:-${GCP_MACHINE_TYPE:-g2-standard-32}}"
PROVISIONING_MODEL="${CLI_PROVISIONING:-${GCP_PROVISIONING_MODEL:-STANDARD}}"
BUCKET_NAME="${GCP_BUCKET:-${PROJECT_ID}-gemma4-checkpoints}"
INSTANCE_NAME="gemma4-unsloth-${MACHINE_TYPE%%-*}-$(date +%s)"
HF_TOKEN="${HF_TOKEN:-}"

echo "=== GCP Training Pipeline Initialization ==="
echo "Project:            ${PROJECT_ID}"
echo "Zone:               ${ZONE}"
echo "Machine Type:       ${MACHINE_TYPE}"
echo "Provisioning Model: ${PROVISIONING_MODEL}"
echo "Instance:           ${INSTANCE_NAME}"
echo "Bucket:             gs://${BUCKET_NAME}"

# Ensure gcloud is configured to target project
gcloud config set project "${PROJECT_ID}"

# Create storage bucket if it does not exist
if ! gcloud storage buckets describe "gs://${BUCKET_NAME}" >/dev/null 2>&1; then
    echo "Creating Cloud Storage bucket gs://${BUCKET_NAME}..."
    gcloud storage buckets create "gs://${BUCKET_NAME}" --location="US"
fi

# Upload datasets and training script to GCS
echo "Staging training assets to Cloud Storage..."
gcloud storage cp "${ROOT_DIR}/data/unsloth_sft_train.jsonl" "gs://${BUCKET_NAME}/input/unsloth_sft_train.jsonl"
gcloud storage cp "${ROOT_DIR}/data/unsloth_sft_val.jsonl" "gs://${BUCKET_NAME}/input/unsloth_sft_val.jsonl"
gcloud storage cp "${SCRIPT_DIR}/train_gemma4_unsloth_cloud.py" "gs://${BUCKET_NAME}/input/train_gemma4_unsloth_cloud.py"

echo "Staged assets in gs://${BUCKET_NAME}/input/:"
gcloud storage ls "gs://${BUCKET_NAME}/input/"

# Generate ephemeral VM startup script
STARTUP_SCRIPT="/tmp/startup_${INSTANCE_NAME}.sh"
cat << 'EOF' > "${STARTUP_SCRIPT}"
#!/usr/bin/env bash
set -euo pipefail
set -x

LOG_FILE="/var/log/gemma4_training.log"
exec > >(tee -a "${LOG_FILE}") 2>&1

echo "=== Booting Gemma 4 A100 Trainer ==="
date

TRAINING_SUCCESS=0

# Self-destruct cleanup trap to ensure zero credit leakage
cleanup_and_destroy() {
    EXIT_CODE=$?
    echo "=== Training Finished or Trapped (exit code: ${EXIT_CODE}) ==="
    date
    ZONE=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/zone" | awk -F/ '{print $NF}')
    VM_NAME=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/name")
    
    if [[ "${TRAINING_SUCCESS}" -eq 1 ]]; then
        echo "Training succeeded cleanly. Self-destructing VM immediately..."
        gcloud compute instances delete "${VM_NAME}" --zone="${ZONE}" --quiet || sudo poweroff
    else
        echo "Training encountered an error. Sleeping 300 seconds for telemetry inspection before self-destruct..."
        sleep 300
        gcloud compute instances delete "${VM_NAME}" --zone="${ZONE}" --quiet || sudo poweroff
    fi
}
trap cleanup_and_destroy EXIT

# Wait for NVIDIA drivers
until nvidia-smi; do
    echo "Waiting for NVIDIA GPU drivers..."
    sleep 5
done

# Prepare directories
mkdir -p /opt/data /opt/output/main_lora /opt/scripts

# Fetch metadata attributes
BUCKET_NAME=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/bucket_name")
HF_TOKEN=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/hf_token")

# Pull input assets from GCS
echo "Downloading assets from gs://${BUCKET_NAME}/input/..."
gcloud storage cp "gs://${BUCKET_NAME}/input/unsloth_sft_train.jsonl" /opt/data/
gcloud storage cp "gs://${BUCKET_NAME}/input/unsloth_sft_val.jsonl" /opt/data/
gcloud storage cp "gs://${BUCKET_NAME}/input/train_gemma4_unsloth_cloud.py" /opt/scripts/

# Install Unsloth and dependencies
echo "Installing Unsloth and training dependencies..."
pip install --upgrade pip
pip install --no-cache-dir \
    "unsloth @ git+https://github.com/unslothai/unsloth.git" \
    trl peft accelerate bitsandbytes datasets "jinja2==3.1.6"
pip install --no-deps unsloth_zoo
pip uninstall -y torchaudio torchao || true

# Smoke test Unsloth import before launch
python3 -c "import sys; sys.modules['torchaudio'] = None; import torch, transformers, trl, unsloth; print('Pre-flight check passed! CUDA:', torch.cuda.is_available(), 'Unsloth:', getattr(unsloth, '__version__', 'ok'))"

# Execute training run
export DATA_DIR="/opt/data"
export OUTPUT_DIR="/opt/output/main_lora"
export HF_TOKEN="${HF_TOKEN}"
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"
export PYTORCH_ALLOC_CONF="expandable_segments:True"
export HF_HUB_DISABLE_XET="1"
export PYTHONUNBUFFERED="1"

echo "Commencing Unsloth training script..."
python3 /opt/scripts/train_gemma4_unsloth_cloud.py

# Verify adapter weights exist before claiming success
if [[ -f "/opt/output/main_lora/adapter_model.safetensors" ]]; then
    echo "Syncing trained adapter weights to gs://${BUCKET_NAME}/output/main_lora/..."
    gcloud storage cp -r /opt/output/main_lora/* "gs://${BUCKET_NAME}/output/main_lora/"
    TRAINING_SUCCESS=1
    echo "=== Training Run and Artifact Sync Complete ==="
else
    echo "ERROR: adapter_model.safetensors was not generated!"
    exit 1
fi
EOF

chmod +x "${STARTUP_SCRIPT}"

# Provision the Ephemeral VM
echo "Provisioning Ephemeral VM (${INSTANCE_NAME}) with ${MACHINE_TYPE} (${PROVISIONING_MODEL})..."

EXTRA_PROVISIONING_FLAGS=()
if [[ "${PROVISIONING_MODEL}" == "SPOT" ]]; then
    EXTRA_PROVISIONING_FLAGS+=(
        --provisioning-model="SPOT"
        --instance-termination-action="DELETE"
    )
fi

gcloud compute instances create "${INSTANCE_NAME}" \
    --project="${PROJECT_ID}" \
    --zone="${ZONE}" \
    --machine-type="${MACHINE_TYPE}" \
    ${EXTRA_PROVISIONING_FLAGS[@]+"${EXTRA_PROVISIONING_FLAGS[@]}"} \
    --maintenance-policy="TERMINATE" \
    --image-family="pytorch-2-9-cu129-ubuntu-2204-nvidia-580" \
    --image-project="deeplearning-platform-release" \
    --boot-disk-size="100GB" \
    --boot-disk-type="pd-balanced" \
    --scopes="https://www.googleapis.com/auth/cloud-platform" \
    --metadata="install-nvidia-driver=True,bucket_name=${BUCKET_NAME},hf_token=${HF_TOKEN}" \
    --metadata-from-file="startup-script=${STARTUP_SCRIPT}"

rm -f "${STARTUP_SCRIPT}"

echo "=== VM Created Successfully ==="
echo "Stream console logs with:"
echo "gcloud compute instances get-serial-port-output ${INSTANCE_NAME} --zone=${ZONE} --project=${PROJECT_ID}"
echo ""
echo "When finished, download the trained adapter with:"
echo "gcloud storage cp -r gs://${BUCKET_NAME}/output/main_lora/ ${ROOT_DIR}/my_submission/adapters/main_lora/"
