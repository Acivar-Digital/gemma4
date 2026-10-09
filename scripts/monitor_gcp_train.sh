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

refresh_gcp_token() {
    local yap_json="/home/vps466a/.antigravity_tools/accounts/f3e9109a-3ffc-4bc7-bd93-3125d504605a.json"
    if [[ -f "${yap_json}" ]]; then
        python3 -c '
import json, pathlib, sys
d = json.load(open(sys.argv[1]))
tok = d.get("token", {}).get("access_token", "")
if tok:
    p = pathlib.Path("/tmp/.gcp_yapcheeleong_token")
    p.write_text(tok)
    p.chmod(0o600)
' "${yap_json}" 2>/dev/null || true
        if [[ -s "/tmp/.gcp_yapcheeleong_token" ]]; then
            export CLOUDSDK_AUTH_ACCESS_TOKEN_FILE="/tmp/.gcp_yapcheeleong_token"
            export CLOUDSDK_BILLING_QUOTA_PROJECT="${PROJECT}"
        fi
    fi
}
refresh_gcp_token

echo "=== Gemma 4 GCP LoRA Monitor ==="
echo "Project: ${PROJECT}"
echo "Bucket:  gs://${BUCKET}"
echo "Mode:    ${MODE}"
echo "================================="

find_active_vm() {
    refresh_gcp_token
    gcloud compute instances list \
        --project="${PROJECT}" \
        --filter="name ~ '^gemma4-(unsloth|5test)-' AND status = RUNNING" \
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
        INTERVAL_SECONDS="${POLL_INTERVAL:-300}"
        INTERVAL_MIN=$((INTERVAL_SECONDS / 60))
        echo "Monitoring training progress every ${INTERVAL_MIN} minutes until adapter weights land in GCS..."
        echo "Log file: /tmp/gemma4_gcp_monitor.log"
        ADAPTER_URI="gs://${BUCKET}/output/main_lora/adapter_model.safetensors"
        FIVE_TEST_SUMMARY_URI="gs://${BUCKET}/five_test_results/summary.json"
        START_TIME=$(date +%s)
        ADAPTER_DOWNLOADED=0

        while true; do
            refresh_gcp_token
            CURRENT_TIME=$(date +%s)
            ELAPSED=$((CURRENT_TIME - START_TIME))
            ELAPSED_MIN=$((ELAPSED / 60))
            TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S UTC")

            # Check if adapter safetensors has landed in GCS
            if [[ "${ADAPTER_DOWNLOADED}" -eq 0 ]] && gcloud storage ls "${ADAPTER_URI}" >/dev/null 2>&1; then
                echo "" | tee -a /tmp/gemma4_gcp_monitor.log
                echo "[${TIMESTAMP}] 🎉 Adapter found in Cloud Storage!" | tee -a /tmp/gemma4_gcp_monitor.log
                echo "Downloading to ${REPO_ROOT}/adapters_staging/main_lora/..." | tee -a /tmp/gemma4_gcp_monitor.log

                mkdir -p "${REPO_ROOT}/adapters_staging/main_lora"
                gcloud storage cp -r "gs://${BUCKET}/output/main_lora/*" "${REPO_ROOT}/adapters_staging/main_lora/"

                if [[ -d "${REPO_ROOT}/submissions/track2_5test_probe" ]]; then
                    mkdir -p "${REPO_ROOT}/submissions/track2_5test_probe/adapters/main_lora"
                    cp -rf "${REPO_ROOT}/adapters_staging/main_lora/"* "${REPO_ROOT}/submissions/track2_5test_probe/adapters/main_lora/"
                fi

                if [[ -f "${REPO_ROOT}/adapters_staging/main_lora/adapter_model.safetensors" ]]; then
                    SIZE_BYTES=$(wc -c < "${REPO_ROOT}/adapters_staging/main_lora/adapter_model.safetensors")
                    SIZE_MB=$((SIZE_BYTES / 1024 / 1024))
                    echo "✅ Download verified: adapter_model.safetensors (${SIZE_MB} MB)" | tee -a /tmp/gemma4_gcp_monitor.log
                    ADAPTER_DOWNLOADED=1
                else
                    echo "Error: adapter_model.safetensors missing from download!" | tee -a /tmp/gemma4_gcp_monitor.log
                    exit 1
                fi
            fi

            # Check if 5-test evaluation summary has landed in GCS
            if gcloud storage ls "${FIVE_TEST_SUMMARY_URI}" >/dev/null 2>&1; then
                echo "[${TIMESTAMP}] 🎯 5-Test evaluation results found in Cloud Storage!" | tee -a /tmp/gemma4_gcp_monitor.log
                mkdir -p "${REPO_ROOT}/results/five_test_eval"
                gcloud storage cp -r "gs://${BUCKET}/five_test_results/*" "${REPO_ROOT}/results/five_test_eval/"
                echo "5-Test evaluation summary:" | tee -a /tmp/gemma4_gcp_monitor.log
                cat "${REPO_ROOT}/results/five_test_eval/summary.json" | tee -a /tmp/gemma4_gcp_monitor.log
                ACTIVE_VM_INFO=$(find_active_vm)
                if [[ -n "${ACTIVE_VM_INFO}" ]]; then
                    VM_NAME=$(echo "${ACTIVE_VM_INFO}" | awk '{print $1}')
                    VM_ZONE=$(echo "${ACTIVE_VM_INFO}" | awk '{print $2}')
                    echo "Deleting completed VM ${VM_NAME} in ${VM_ZONE} to prevent billing leaks..." | tee -a /tmp/gemma4_gcp_monitor.log
                    gcloud compute instances delete "${VM_NAME}" --zone="${VM_ZONE}" --project="${PROJECT}" --quiet || true
                fi
                echo "Training harvest and 5-test verification COMPLETE." | tee -a /tmp/gemma4_gcp_monitor.log
                exit 0
            fi

            # If adapter downloaded and no 5-test VM is running, finish
            ACTIVE_VM_INFO=$(find_active_vm)
            if [[ "${ADAPTER_DOWNLOADED}" -eq 1 && -z "${ACTIVE_VM_INFO}" ]]; then
                if gcloud storage ls "${FIVE_TEST_SUMMARY_URI}" >/dev/null 2>&1; then
                    echo "🎯 5-Test evaluation results found in Cloud Storage!" | tee -a /tmp/gemma4_gcp_monitor.log
                    mkdir -p "${REPO_ROOT}/results/five_test_eval"
                    gcloud storage cp -r "gs://${BUCKET}/five_test_results/*" "${REPO_ROOT}/results/five_test_eval/"
                    echo "5-Test evaluation summary:" | tee -a /tmp/gemma4_gcp_monitor.log
                    cat "${REPO_ROOT}/results/five_test_eval/summary.json" | tee -a /tmp/gemma4_gcp_monitor.log
                    echo "Training harvest and 5-test verification COMPLETE." | tee -a /tmp/gemma4_gcp_monitor.log
                    exit 0
                else
                    echo "[WARN] VM has terminated, but 5-test evaluation summary was not found in GCS!" | tee -a /tmp/gemma4_gcp_monitor.log
                    echo "Fetching last 40 lines of serial console log for post-mortem diagnostics..." | tee -a /tmp/gemma4_gcp_monitor.log
                    LAST_VM=$(gcloud compute instances list --project="${PROJECT}" --sort-by="~creationTimestamp" --format="value(name,zone)" | head -n 1)
                    if [[ -n "${LAST_VM}" ]]; then
                        LAST_NAME=$(echo "${LAST_VM}" | awk '{print $1}')
                        LAST_ZONE=$(echo "${LAST_VM}" | awk '{print $2}')
                        gcloud compute instances get-serial-port-output "${LAST_NAME}" --zone="${LAST_ZONE}" --project="${PROJECT}" 2>&1 | tail -n 40 | tee -a /tmp/gemma4_gcp_monitor.log || true
                    fi
                    exit 1
                fi
            fi

            # Check VM state
            ACTIVE_VM_INFO=$(find_active_vm)
            if [[ -z "${ACTIVE_VM_INFO}" ]]; then
                echo "" | tee -a /tmp/gemma4_gcp_monitor.log
                echo "[${TIMESTAMP}] ⚠️ VM has terminated, but adapter_model.safetensors was not found in GCS!" | tee -a /tmp/gemma4_gcp_monitor.log
                echo "Fetching last 40 lines of serial console log for post-mortem diagnostics..." | tee -a /tmp/gemma4_gcp_monitor.log
                LAST_VM=$(gcloud compute instances list --project="${PROJECT}" --sort-by="~creationTimestamp" --format="value(name,zone)" | head -n 1)
                if [[ -n "${LAST_VM}" ]]; then
                    LAST_NAME=$(echo "${LAST_VM}" | awk '{print $1}')
                    LAST_ZONE=$(echo "${LAST_VM}" | awk '{print $2}')
                    gcloud compute instances get-serial-port-output "${LAST_NAME}" --zone="${LAST_ZONE}" --project="${PROJECT}" | tail -n 40 | tee -a /tmp/gemma4_gcp_monitor.log
                fi
                exit 1
            fi

            VM_NAME=$(echo "${ACTIVE_VM_INFO}" | awk '{print $1}')
            echo "[${TIMESTAMP}] Elapsed: ${ELAPSED_MIN}m | VM: ${VM_NAME} (RUNNING) | Polling GCS every ${INTERVAL_MIN}m..." | tee -a /tmp/gemma4_gcp_monitor.log
            sleep "${INTERVAL_SECONDS}"
        done
        ;;

    *)
        echo "Usage: $0 [wait|tail|status]"
        exit 1
        ;;
esac
