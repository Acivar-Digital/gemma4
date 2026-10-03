#!/usr/bin/env bash
# ==============================================================================
# Fetch, Validate, Install, and Package Fine-Tuned Gemma 4 LoRA Adapter
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source GCP environment configuration
ENV_GCP="${ROOT_DIR}/.env.gcp"
if [[ -f "${ENV_GCP}" ]]; then
    # shellcheck disable=SC1090
    source "${ENV_GCP}"
fi

PROJECT_ID="${PROJECT_ID:-gen-lang-client-0266946478}"
BUCKET_NAME="${BUCKET_NAME:-gen-lang-client-0266946478-gemma4-checkpoints}"
GCS_LORA_URI="gs://${BUCKET_NAME}/output/main_lora"
LOCAL_LORA_DIR="${ROOT_DIR}/checkpoints/main_lora"
SUBMISSION_DIR="${ROOT_DIR}/my_submission"
SUBMISSION_ZIP="${ROOT_DIR}/submission.zip"

echo "=== Fetching Fine-Tuned Gemma 4 LoRA Adapter from GCS ==="
echo "GCS Source: ${GCS_LORA_URI}"
echo "Local Target: ${LOCAL_LORA_DIR}"

mkdir -p "${LOCAL_LORA_DIR}"

# Download adapter artifacts
gcloud storage cp -r "${GCS_LORA_URI}/*" "${LOCAL_LORA_DIR}/"

echo "=== Running Deep Tensor and Config Validation ==="
python3 "${SCRIPT_DIR}/verify_and_install_adapter.py" --source "${LOCAL_LORA_DIR}"

echo "=== Purging Bytecode, Cache, and OS Metadata from my_submission ==="
find "${SUBMISSION_DIR}" -name "*.pyc" -delete || true
find "${SUBMISSION_DIR}" -name "__pycache__" -exec rm -rf {} + || true
find "${SUBMISSION_DIR}" -name ".DS_Store" -delete || true

echo "=== Packaging Verified submission.zip Archive ==="
rm -f "${SUBMISSION_ZIP}"
(
    cd "${SUBMISSION_DIR}"
    zip -q -r "${SUBMISSION_ZIP}" . -x "*.DS_Store" "*__pycache__*" "*.pyc"
)

echo "=== Verifying Packaged Archive Size and Constraints ==="
ARCHIVE_SIZE_BYTES=$(stat -f%z "${SUBMISSION_ZIP}" 2>/dev/null || stat -c%s "${SUBMISSION_ZIP}")
ARCHIVE_SIZE_MIB=$(python3 -c "print(f'{${ARCHIVE_SIZE_BYTES} / (1024 * 1024):.2f}')")
MAX_SIZE_BYTES=3221225472

echo "Archive File: ${SUBMISSION_ZIP}"
echo "Archive Size: ${ARCHIVE_SIZE_MIB} MiB (${ARCHIVE_SIZE_BYTES} bytes, limit: 3072 MiB)"

if (( ARCHIVE_SIZE_BYTES > MAX_SIZE_BYTES )); then
    echo "ERROR: submission.zip exceeds 3 GiB Kaggle ceiling!" >&2
    exit 1
fi

echo "=== All Steps Succeeded! submission.zip is Ready for Submission ==="
