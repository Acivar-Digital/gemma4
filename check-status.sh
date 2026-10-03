#!/usr/bin/env bash
# ==============================================================================
# check-status.sh — Real-time telemetry for Kaggle Cloud Eval & Submission Timer
# ==============================================================================

set -euo pipefail

# ANSI Color Codes
BOLD="\033[1m"
GREEN="\033[0;32m"
CYAN="\033[0;36m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
MAGENTA="\033[0;35m"
RESET="\033[0m"

KERNEL_SLUG="${2:-francisclyap/gemma4-canary-eval}"
SUBMISSION_ZIP="submission.zip"
OUTPUT_DIR="cloud_results/canary_test_results"

print_header() {
    clear
    echo -e "${BOLD}${CYAN}======================================================================${RESET}"
    echo -e "${BOLD}${CYAN}      GEMMA 4 DEVELOPER AGENT — MISSION FLIGHT TELEMETRY              ${RESET}"
    echo -e "${BOLD}${CYAN}======================================================================${RESET}"
    echo -e "System Time: $(date -u '+%Y-%m-%d %H:%M:%S UTC')\n"
}

check_countdown() {
    # Calculate seconds until next 00:00:00 UTC
    local now_epoch
    local next_midnight_epoch
    local diff_seconds
    local hours
    local minutes
    local seconds

    now_epoch=$(date -u +%s)
    # macOS / BSD date compatibility: compute midnight of next day
    next_midnight_epoch=$(date -u -v+1d -v0H -v0M -v0S +%s 2>/dev/null || date -u -d "tomorrow 00:00:00" +%s)
    diff_seconds=$(( next_midnight_epoch - now_epoch ))

    hours=$(( diff_seconds / 3600 ))
    minutes=$(( (diff_seconds % 3600) / 60 ))
    seconds=$(( diff_seconds % 60 ))

    echo -e "${BOLD}⏳ Next Leaderboard Quota Reset (00:00:00 UTC):${RESET}"
    printf "   ${YELLOW}%02dh %02dm %02ds remaining${RESET} until Track 1 submission window opens\n\n" "$hours" "$minutes" "$seconds"
}

check_submission_archive() {
    echo -e "${BOLD}📦 Track 1 Submission Archive (${SUBMISSION_ZIP}):${RESET}"
    if [[ -f "${SUBMISSION_ZIP}" ]]; then
        local size_bytes
        size_bytes=$(stat -f %z "${SUBMISSION_ZIP}" 2>/dev/null || stat -c %s "${SUBMISSION_ZIP}")
        local size_kb
        size_kb=$(( size_bytes / 1024 ))
        local mtime
        mtime=$(date -r "${SUBMISSION_ZIP}" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date -d "@$(stat -c %Y ${SUBMISSION_ZIP})" '+%Y-%m-%d %H:%M:%S')
        echo -e "   Status:   ${GREEN}READY ON DISK${RESET}"
        echo -e "   Size:     ${size_kb} KB (${size_bytes} bytes, limit: 3 GiB)"
        echo -e "   Modified: ${mtime}"
    else
        echo -e "   Status:   ${RED}MISSING! Run build/verify first.${RESET}"
    fi
    echo ""
}

check_kaggle_kernel() {
    echo -e "${BOLD}☁️  Kaggle Cloud Eval Marathon (${KERNEL_SLUG}):${RESET}"
    
    if ! command -v kaggle >/dev/null 2>&1; then
        echo -e "   ${RED}Error: kaggle CLI is not installed or not in PATH.${RESET}"
        return 1
    fi

    local raw_status
    raw_status=$(kaggle kernels status "${KERNEL_SLUG}" 2>&1 || true)

    if [[ "${raw_status}" =~ RUNNING ]]; then
        echo -e "   Status:   ${GREEN}${BOLD}RUNNING 🟢${RESET} (tasks evaluating on 4x L4 GPUs)"
    elif [[ "${raw_status}" =~ COMPLETE ]]; then
        echo -e "   Status:   ${CYAN}${BOLD}COMPLETE 🏁${RESET} (all tasks finished evaluation)"
    elif [[ "${raw_status}" =~ ERROR|FAILED ]]; then
        echo -e "   Status:   ${RED}${BOLD}FAILED / ERROR 🔴${RESET}"
    else
        echo -e "   Raw:      ${raw_status}"
    fi
    echo -e "   Kernel:   https://www.kaggle.com/code/${KERNEL_SLUG}"
    echo ""
}

run_once() {
    print_header
    check_kaggle_kernel
    check_submission_archive
    check_countdown
    echo -e "${CYAN}----------------------------------------------------------------------${RESET}"
    echo -e "Tip: Run '${BOLD}./check-status.sh --watch${RESET}' to monitor continuously."
    echo -e "${CYAN}======================================================================${RESET}"
}

wait_mode() {
    echo -e "${BOLD}${CYAN}Entering silent wait mode for kernel: ${KERNEL_SLUG}${RESET}"
    echo -e "Waiting for completion without consuming LLM tokens..."
    mkdir -p "${OUTPUT_DIR}"

    local attempt=0
    while true; do
        attempt=$((attempt + 1))
        local raw_status
        raw_status=$(kaggle kernels status "${KERNEL_SLUG}" 2>&1 || true)
        local timestamp
        timestamp=$(date -u '+%Y-%m-%d %H:%M:%S UTC')

        if [[ "${raw_status}" =~ COMPLETE ]]; then
            echo -e "\n[${timestamp}] ${GREEN}${BOLD}Kernel ${KERNEL_SLUG} has COMPLETED successfully! 🏁${RESET}"
            echo -e "Fetching kernel outputs to ${OUTPUT_DIR}..."
            kaggle kernels output "${KERNEL_SLUG}" -p "${OUTPUT_DIR}" || true
            echo -e "Outputs saved to ${OUTPUT_DIR}. Exiting wait mode."
            return 0
        elif [[ "${raw_status}" =~ ERROR|FAILED ]]; then
            echo -e "\n[${timestamp}] ${RED}${BOLD}Kernel ${KERNEL_SLUG} encountered an ERROR or FAILED! 🔴${RESET}"
            echo -e "Status: ${raw_status}"
            echo -e "Attempting to fetch logs to ${OUTPUT_DIR}..."
            kaggle kernels output "${KERNEL_SLUG}" -p "${OUTPUT_DIR}" || true
            return 1
        elif [[ "${raw_status}" =~ RUNNING ]]; then
            echo -ne "\r[${timestamp}] Check #${attempt}: Still RUNNING... (sleeping 30s)    "
            sleep 30
        else
            echo -ne "\r[${timestamp}] Check #${attempt}: ${raw_status} (sleeping 30s)    "
            sleep 30
        fi
    done
}

if [[ "${1:-}" == "--wait" || "${1:-}" == "-wait" ]]; then
    wait_mode
elif [[ "${1:-}" == "--watch" || "${1:-}" == "-w" ]]; then
    watch_mode
else
    run_once
fi
