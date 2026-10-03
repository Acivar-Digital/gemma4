#!/usr/bin/env bash
# ==============================================================================
# scripts/monitor_gcp_train.sh
# Autonomous local watcher for Gemma 4 LoRA fine-tuning on GCP.
# Avoids conversational LLM token waste by polling and syncing locally in bash.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source GCP configuration
if [[ -f "${REPO_ROOT}/.env.gcp" ]]; then
    # shellcheck disable=SC1091
    source "${REPO_ROOT}/.env.gcp"
fi

PROJECT="${GCP_PROJECT:-gen-lang-client-0266946478}"
BUCKET="${GCP_BUCKET:-gen-lang-client-0266946478-gemma4-checkpoints}"
ZONE="${GCP_ZONE:-us-central1-c}"

MODE="${1:-wait}" # "wait", "tail", or "status"

echo "=== Gemma 4 GCP LoRA Monitor ==="
echo "Project: ${PROJECT}"
echo "Bucket:  gs://${BUCKET}"
echo "Mode:    ${MODE}"
echo "================================="

find_active_vm() {
    gcloud compute instances list \
        --project="${PROJECT}" \
        --filter="name ~ gemma4-unsloth-g2- AND status = RUNNING" \
        --format="value(name,zone)" | head -n 1
}

case "${MODE}" in
    tail|-t|--tail)
        ACTIVE_VM_INFO=$(find_active_vm)
        if [[ -z "${ACTIVE_VM_INFO}" ]]; then
            echo "No active running training VM found."
            exit 1
        fi
        VM_NAME=$(echo "${ACTIVE_VM_INFO}" | awk '{print $1}')
        VM_ZONE=$(echo "${ACTIVE_VM_INFO}" | awk '{print $2}')
        echo "Streaming logs from ${VM_NAME} (${VM_ZONE})... (Ctrl+C to stop)"
        gcloud compute ssh "${VM_NAME}" \
            --zone="${VM_ZONE}" \
            --project="${PROJECT}" \
            --command="tail -f /var/log/gemma4_training.log"
        ;;

    status|-s|--status)
        ACTIVE_VM_INFO=$(find_active_vm)
        if [[ -n "${ACTIVE_VM_INFO}" ]]; then
            VM_NAME=$(echo "${ACTIVE_VM_INFO}" | awk '{print $1}')
            VM_ZONE=$(echo "${ACTIVE_VM_INFO}" | awk '{print $2}')
            echo "Active VM: ${VM_NAME} in ${VM_ZONE}"
            gcloud compute ssh "${VM_NAME}" \
                --zone="${VM_ZONE}" \
                --project="${PROJECT}" \
                --command="nvidia-smi && tail -n 15 /var/log/gemma4_training.log" -- -o BatchMode=yes
        else
            echo "No active VM running."
            echo "Checking GCS bucket for completed output:"
            gcloud storage ls "gs://${BUCKET}/output/main_lora/" 2>/dev/null || echo "No output artifacts found."
        fi
        ;;

    wait|-w|--wait)
        echo "Monitoring training progress until adapter weights land in GCS..."
        ADAPTER_URI="gs://${BUCKET}/output/main_lora/adapter_model.safetensors"
        START_TIME=$(date +%s)

        while true; do
            CURRENT_TIME=$(date +%s)
            ELAPSED=$((CURRENT_TIME - START_TIME))
            ELAPSED_MIN=$((ELAPSED / 60))
            TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S UTC")

            # Check if adapter safetensors has landed in GCS
            if gcloud storage ls "${ADAPTER_URI}" >/dev/null 2>&1; then
                echo ""
                echo "[${TIMESTAMP}] 🎉 Adapter found in Cloud Storage!"
                echo "Downloading to ${REPO_ROOT}/my_submission/adapters/main_lora/..."
                
                mkdir -p "${REPO_ROOT}/my_submission/adapters/main_lora"
                gcloud storage cp -r "gs://${BUCKET}/output/main_lora/*" "${REPO_ROOT}/my_submission/adapters/main_lora/"

                # Verify files
                if [[ -f "${REPO_ROOT}/my_submission/adapters/main_lora/adapter_model.safetensors" ]]; then
                    SIZE_BYTES=$(wc -c < "${REPO_ROOT}/my_submission/adapters/main_lora/adapter_model.safetensors")
                    SIZE_MB=$((SIZE_BYTES / 1024 / 1024))
                    echo "✅ Download verified: adapter_model.safetensors (${SIZE_MB} MB)"

                    # Update agent.yaml with adapter reference if not present
                    if ! grep -q "adapter: main_lora" "${REPO_ROOT}/my_submission/agent.yaml"; then
                        echo "Mounting 'adapter: main_lora' in my_submission/agent.yaml..."
                        sed -i '' 's/^model: gemma-4-31b-it-qat-w4a16-ct/model: gemma-4-31b-it-qat-w4a16-ct\nadapter: main_lora/' "${REPO_ROOT}/my_submission/agent.yaml"
                    fi

                    # Package submission_lora.zip
                    echo "Packaging submission_lora.zip..."
                    (cd "${REPO_ROOT}/my_submission" && zip -q -r "${REPO_ROOT}/submission_lora.zip" . -x "*.pyc" -x "__pycache__/*")
                    
                    LORA_ZIP_SIZE=$(wc -c < "${REPO_ROOT}/submission_lora.zip")
                    LORA_ZIP_MB=$((LORA_ZIP_SIZE / 1024 / 1024))
                    echo "🏆 Packaged ${REPO_ROOT}/submission_lora.zip (${LORA_ZIP_MB} MB)"
                    echo "Training and submission preparation COMPLETE."
                    exit 0
                else
                    echo "Error: adapter_model.safetensors missing from download!"
                    exit 1
                fi
            fi

            # Check VM state
            ACTIVE_VM_INFO=$(find_active_vm)
            if [[ -z "${ACTIVE_VM_INFO}" ]]; then
                echo ""
                echo "[${TIMESTAMP}] ⚠️ VM has terminated, but adapter_model.safetensors was not found in GCS!"
                echo "Fetching last 40 lines of serial console log for post-mortem diagnostics..."
                LAST_VM=$(gcloud compute instances list --project="${PROJECT}" --sort-by="~creationTimestamp" --format="value(name,zone)" | head -n 1)
                if [[ -n "${LAST_VM}" ]]; then
                    LAST_NAME=$(echo "${LAST_VM}" | awk '{print $1}')
                    LAST_ZONE=$(echo "${LAST_VM}" | awk '{print $2}')
                    gcloud compute instances get-serial-port-output "${LAST_NAME}" --zone="${LAST_ZONE}" --project="${PROJECT}" | tail -n 40
                fi
                exit 1
            fi

            VM_NAME=$(echo "${ACTIVE_VM_INFO}" | awk '{print $1}')
            printf "\r[%s] Elapsed: %dm | VM: %s (RUNNING) | Waiting for adapter weights..." "${TIMESTAMP}" "${ELAPSED_MIN}" "${VM_NAME}"
            sleep 30
        done
        ;;

    *)
        echo "Usage: $0 [wait|tail|status]"
        exit 1
        ;;
esac
