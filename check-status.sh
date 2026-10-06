#!/usr/bin/env bash
# ==============================================================================
# check-status.sh — Real-time telemetry for Kaggle Cloud Eval & Submission Timer
# ==============================================================================
#
# READ ONLY. This script never pushes a kernel and never submits to a
# competition. It only reports state.
#
#   Surface A  KERNEL      — `kaggle kernels status`      (a notebook on Kaggle
#                            GPUs: starting/running/complete/error)
#   Surface B  LEADERBOARD — `kaggle competitions submissions` (a scored or
#                            unscored leaderboard entry)
#
# These are different things and are reported under separate headers.
#
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

SUBMISSION_ZIP="submission.zip"
OUTPUT_DIR="cloud_results/canary_test_results"
COMPETITION="gemma-4-developer-agent"

# Known kernel slugs, offered as a hint when no slug is supplied or inferable.
KNOWN_SLUGS=(
  "francisclyap/gemma4-eval-40calls"
  "francisclyap/gemma4-canary-eval"
  "francisclyap/gemma4-lora-minimal-thinking"
  "francisclyap/gemma4-test-thinking-settings"
  "francisclyap/gemma4-baseline-v1"
)

# Triage source: the per-task results file whose `test_exit_code` field carries
# the infrastructure-vs-quality signal.
TRIAGE_FILE=""

# ------------------------------------------------------------------ defaults --
KERNEL_SLUG="${KAGGLE_KERNEL_SLUG:-}"
WATCH_INTERVAL=30
WATCH_TIMEOUT=7200      # bounded default: 2 hours, cannot poll forever
FETCH_OUTPUT=0          # --fetch-output downloads kernel artifacts
POSITIONAL_SLUG=""

# ----------------------------------------------------------------- utilities --
slug_hint() {
    echo -e "   ${YELLOW}No kernel slug supplied and none could be inferred.${RESET}"
    echo -e "   ${BOLD}Known kernel slugs — pass one explicitly:${RESET}"
    local s
    for s in "${KNOWN_SLUGS[@]}"; do
        echo -e "     ${s}"
    done
    echo -e "   ${BOLD}Usage:${RESET} $0 --kernel <owner>/<name>    (or: $0 <mode> <owner>/<name>)"
}

# Interruptible sleep.
#
# A plain foreground `sleep` blocks the shell, so a SIGINT arriving during it is
# not handled until the sleep returns — Ctrl+C would hang for up to one whole
# interval. Backgrounding the sleep and `wait`ing on it lets the INT/TERM trap
# fire immediately, so Ctrl+C always stops the poll loop at once.
interruptible_sleep() {
    sleep "$1" &
    local sleeper=$!
    wait "${sleeper}" 2>/dev/null || true
}

# Preconditions that must hold before any Kaggle surface is contacted.
# Returns 1 (without exiting) so callers can report a clean message.
preflight() {
    if ! command -v kaggle >/dev/null 2>&1; then
        echo -e "   ${RED}${BOLD}ERROR: kaggle CLI not found on PATH.${RESET}"
        echo -e "   ${BOLD}Fix:${RESET} pip install kaggle   (or: brew install kaggle)"
        echo -e "   ${BOLD}Then:${RESET} export KAGGLE_USERNAME=... KAGGLE_KEY=... (or write ~/.kaggle/kaggle.json)"
        return 1
    fi
    return 0
}

# Is a slug available? Echo it, or print the hint and return 1.
resolve_slug() {
    if [[ -n "${KERNEL_SLUG}" ]]; then
        echo "${KERNEL_SLUG}"
        return 0
    fi
    return 1
}

print_header() {
    clear 2>/dev/null || true
    echo -e "${BOLD}${CYAN}======================================================================${RESET}"
    echo -e "${BOLD}${CYAN}      GEMMA 4 DEVELOPER AGENT — MISSION FLIGHT TELEMETRY              ${RESET}"
    echo -e "${BOLD}${CYAN}======================================================================${RESET}"
    echo -e "System Time: $(date -u '+%Y-%m-%d %H:%M:%S UTC')\n"
}

print_footer() {
    echo -e "${CYAN}----------------------------------------------------------------------${RESET}"
    echo -e "Tip: Run '${BOLD}./check-status.sh --watch${RESET}' to monitor the kernel continuously."
    echo -e "     Run '${BOLD}./check-status.sh --help${RESET}' for every flag."
    echo -e "${CYAN}======================================================================${RESET}"
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

# ------------------------------------------------------------------- SURFACE A --
# KERNEL. Returns 0 always once attempted; sets KERNEL_STATE to the normalized
# state so callers (notably the watch loop) can branch on a terminal outcome.
KERNEL_STATE="unknown"
check_kaggle_kernel() {
    KERNEL_STATE="unknown"

    echo -e "${BOLD}☁️  KERNEL — Kaggle Cloud Eval Marathon${RESET}"
    if [[ -n "${KERNEL_SLUG}" ]]; then
        echo -e "   Slug:     ${BOLD}${KERNEL_SLUG}${RESET}"
    else
        echo -e "   Slug:     ${YELLOW}<none supplied>${RESET}"
    fi

    if ! resolve_slug >/dev/null; then
        slug_hint
        echo ""
        return 0
    fi

    if ! preflight; then
        echo ""
        return 1
    fi

    local raw_status
    local rc=0
    # Never swallow the real error: capture both output and exit code.
    raw_status=$(kaggle kernels status "${KERNEL_SLUG}" 2>&1) || rc=$?

    if [[ ${rc} -ne 0 ]]; then
        KERNEL_STATE="unavailable"
        echo -e "   Status:   ${RED}${BOLD}UNAVAILABLE 🔴${RESET} (kaggle exited ${rc})"
        echo -e "   ${BOLD}Real error from kaggle:${RESET}"
        local line
        while IFS= read -r line; do
            [[ -n "${line}" ]] && echo -e "     ${line}"
        done <<< "${raw_status}"
        echo -e "   ${BOLD}Hint:${RESET} missing/invalid credentials look like this."
        echo -e "         Set KAGGLE_USERNAME + KAGGLE_KEY, or write ~/.kaggle/kaggle.json."
        echo ""
        return 1
    fi

    if [[ "${raw_status}" =~ RUNNING ]]; then
        KERNEL_STATE="running"
        echo -e "   Status:   ${GREEN}${BOLD}RUNNING 🟢${RESET} (tasks evaluating on 4x L4 GPUs)"
    elif [[ "${raw_status}" =~ STARTING|QUEUED|PENDING|SUBMITTING ]]; then
        KERNEL_STATE="starting"
        echo -e "   Status:   ${YELLOW}${BOLD}STARTING 🟡${RESET} (accepted, not yet on a GPU)"
    elif [[ "${raw_status}" =~ COMPLETE ]]; then
        KERNEL_STATE="complete"
        echo -e "   Status:   ${CYAN}${BOLD}COMPLETE 🏁${RESET} (all tasks finished evaluation)"
    elif [[ "${raw_status}" =~ ERROR|FAILED ]]; then
        KERNEL_STATE="error"
        echo -e "   Status:   ${RED}${BOLD}FAILED / ERROR 🔴${RESET}"
    else
        KERNEL_STATE="unknown"
        echo -e "   Status:   ${YELLOW}UNRECOGNIZED${RESET}"
        echo -e "   Raw:      ${raw_status}"
    fi
    echo -e "   Kernel:   https://www.kaggle.com/code/${KERNEL_SLUG}"
    echo ""
    return 0
}

# ------------------------------------------------------------------- SURFACE B --
# LEADERBOARD. Distinct from the kernel surface: a competition submission entry
# is a scored/unscored row, not a running notebook.
check_leaderboard() {
    echo -e "${BOLD}📊 LEADERBOARD — Competition Submissions (${COMPETITION}):${RESET}"

    if ! preflight; then
        echo ""
        return 1
    fi

    local raw_out
    local rc=0
    raw_out=$(kaggle competitions submissions -c "${COMPETITION}" 2>&1) || rc=$?

    if [[ ${rc} -ne 0 ]]; then
        echo -e "   Status:   ${RED}${BOLD}UNAVAILABLE 🔴${RESET} (kaggle exited ${rc})"
        echo -e "   ${BOLD}Real error from kaggle:${RESET}"
        local line
        while IFS= read -r line; do
            [[ -n "${line}" ]] && echo -e "     ${line}"
        done <<< "${raw_out}"
        echo -e "   ${BOLD}Hint:${RESET} this needs Kaggle auth and access to the competition."
        echo ""
        return 1
    fi

    # Header row is: ref, fileName, date, description, status, publicScore,
    # privateScore (whitespace-aligned, not comma-separated).
    local header
    header=$(printf '%s\n' "${raw_out}" | head -1)
    echo -e "   ${BOLD}Columns:${RESET} ${header}"

    local data_lines
    data_lines=$(printf '%s\n' "${raw_out}" | tail -n +2 | grep -c . || true)

    if [[ "${data_lines}" -eq 0 ]]; then
        echo -e "   Status:   ${YELLOW}NO SUBMISSION ENTRIES FOUND${RESET} (nothing scored yet)"
        echo ""
        return 0
    fi

    # Kaggle prints this as a whitespace-aligned table, NOT CSV: the description
    # field contains both spaces and commas, so `awk -F','` misparses it.
    # Parse by anchoring on the `SubmissionStatus.` token and taking the token
    # after it as publicScore. This is immune to any description text.
    local shown=0
    while IFS= read -r line; do
        [[ -z "${line}" ]] && continue
        # Skip the dashed separator row Kaggle prints under the header.
        [[ "${line}" =~ ^-+[[:space:]]+-+ ]] && continue
        shown=$(( shown + 1 ))
        [[ "${shown}" -gt 10 ]] && continue

        local ref status_field score_field
        ref=$(printf '%s\n' "${line}" | awk '{print $1}')
        status_field=$(printf '%s\n' "${line}" | grep -oE 'SubmissionStatus\.[A-Z]+' | head -1 || true)
        score_field=$(printf '%s\n' "${line}" \
            | grep -oE 'SubmissionStatus\.[A-Z]+[[:space:]]+[-0-9.]+' \
            | head -1 | awk '{print $2}' || true)
        [[ -z "${score_field}" ]] && score_field="-"

        # Description = everything strictly between the date token
        # (YYYY-MM-DD) and the SubmissionStatus token. Anchor on the status
        # token first, then strip the leading ref/file/date fields.
        local description
        description=$(printf '%s\n' "${line}" \
            | sed -E 's/[[:space:]]+SubmissionStatus\.[A-Z]+.*$//' \
            | sed -E 's/^[^[:space:]]+[[:space:]]+[^[:space:]]+[[:space:]]+[0-9]{4}-[0-9]{2}-[0-9]{2}[[:space:]]+[0-9:.]+[[:space:]]+//' \
            | sed -E 's/[[:space:]]+/ /g; s/^ //; s/ $//' || true)

        if [[ "${status_field}" == *COMPLETE* ]]; then
            if [[ "${score_field}" != "-" ]]; then
                echo -e "   ${GREEN}${BOLD}SCORED  ${RESET} ref=${ref}  publicScore=${MAGENTA}${score_field}${RESET}"
            else
                echo -e "   ${YELLOW}UNSCORED${RESET} ref=${ref}  publicScore=${YELLOW}(none yet)${RESET}"
            fi
            echo -e "          ${description}"
        elif [[ -n "${status_field}" ]]; then
            echo -e "   ${YELLOW}PENDING ${RESET} ref=${ref}  status=${status_field}  score=${score_field}"
            echo -e "          ${description}"
        else
            echo -e "   ${YELLOW}UNKNOWN ${RESET} ${line}"
        fi
    done <<< "$(printf '%s\n' "${raw_out}" | tail -n +2)"

    if [[ "${data_lines}" -gt 10 ]]; then
        echo -e "   ${BOLD}... and $(( data_lines - 10 )) older entries not shown.${RESET}"
    fi
    echo -e "   ${BOLD}Total entries:${RESET} ${data_lines}"
    echo ""
    return 0
}

# -------------------------------------------------------------------- TRIAGE --
# The reason this script exists.
#
# A low score has two distinguishable causes, separated by the per-task
# `test_exit_code` distribution in the run's task_results.jsonl:
#
#   dominant -1  =>  INFRASTRUCTURE failure. No test result was ever produced
#                   (the run never got far enough to run tests). A model of any
#                   quality, however weak, cannot produce -1. So -1 dominant
#                   means the harness/kernel broke, NOT that the model is bad.
#   dominant  1  =>  MODEL-QUALITY failure. A patch WAS produced and applied and
#                   the tests actually ran and failed. That is a real verdict
#                   about the model's capability.
#
# Prints one explicit verdict line. If the data is absent, says so plainly and
# does not guess.
print_triage() {
    echo -e "${BOLD}🔍 TRIAGE — Infrastructure Failure vs Model Quality:${RESET}"

    if [[ -z "${TRIAGE_FILE}" ]]; then
        echo -e "   ${YELLOW}UNAVAILABLE — no exit-code data was located.${RESET}"
        echo -e "   ${BOLD}No verdict is being guessed.${RESET} Pass --triage <path/to/task_results.jsonl>"
        echo -e "   to triage a specific run once its results exist."
        echo ""
        return 0
    fi

    if [[ ! -f "${TRIAGE_FILE}" ]]; then
        echo -e "   ${YELLOW}UNAVAILABLE — triage file not found:${RESET} ${TRIAGE_FILE}"
        echo -e "   No verdict is being guessed."
        echo ""
        return 0
    fi

    local total="" minus_one=0 exit_one=0 zero=0 other=0
    # Parse with python3 for exact per-record `test_exit_code` semantics.
    local dist
    dist=$(python3 - "${TRIAGE_FILE}" <<'PYEOF' 2>/dev/null || true
import json, sys, collections
path = sys.argv[1]
counts = collections.Counter()
total = 0
try:
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            total += 1
            counts[rec.get("test_exit_code")] += 1
except OSError:
    sys.exit(1)
out = {"total": total}
for code, n in counts.items():
    out[str(code)] = n
print(json.dumps(out))
PYEOF
    )

    if [[ -z "${dist}" ]]; then
        echo -e "   ${YELLOW}UNAVAILABLE — could not parse exit codes from:${RESET} ${TRIAGE_FILE}"
        echo -e "   No verdict is being guessed."
        echo ""
        return 0
    fi

    total=$(printf '%s' "${dist}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("total",0))')
    minus_one=$(printf '%s' "${dist}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("-1",0))')
    exit_one=$(printf '%s' "${dist}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("1",0))')
    zero=$(printf '%s' "${dist}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("0",0))')

    if [[ "${total}" -eq 0 ]]; then
        echo -e "   ${YELLOW}UNAVAILABLE — ${TRIAGE_FILE} contained no usable records.${RESET}"
        echo -e "   No verdict is being guessed."
        echo ""
        return 0
    fi

    local other=$(( total - minus_one - zero - exit_one ))

    echo -e "   Source:   ${TRIAGE_FILE}"
    echo -e "   Tasks:    ${total} scored"
    echo -e "   Exit-code distribution:"
    echo -e "     ${RED}-1  (no test result produced): ${minus_one}${RESET}"
    echo -e "     ${GREEN}0   (passed):                    ${zero}${RESET}"
    echo -e "     ${YELLOW}1   (patch applied, tests ran and failed): ${exit_one}${RESET}"
    echo -e "     ${CYAN}other (timeouts 124, collection errors 2, …): ${BOLD}${other}${RESET}"
    echo ""

    # The verdict compares the two HYPOTHESES, so the denominator is the set of
    # tasks that failed to resolve — not every task. Passing tasks (exit 0) are
    # irrelevant to the question "was this an infrastructure break or a model
    # that could not solve the task?". Including them would dilute a genuine
    # signal; e.g. a healthy 56/129 run has 58 passes that would mask the
    # exit-1 failures that actually explain the other 43%.
    local failed=$(( minus_one + exit_one ))
    if [[ "${failed}" -eq 0 ]]; then
        if [[ "${other}" -eq 0 ]]; then
            echo -e "   ${GREEN}${BOLD}VERDICT: NO FAILURES 🟢${RESET} — every scored task passed."
        else
            echo -e "   ${YELLOW}${BOLD}VERDICT: MIXED / INCONCLUSIVE — no dominant exit code.${RESET}"
            echo -e "   No task exited -1 or 1; only other codes (${other}) appeared, which"
            echo -e "   match neither hypothesis. No verdict is being guessed."
        fi
        echo ""
        return 0
    fi

    local minus_one_pct=$(( minus_one * 100 / failed ))
    local exit_one_pct=$(( exit_one * 100 / failed ))

    echo -e "   ${BOLD}Of the ${failed} unresolved tasks:${RESET}"

    if [[ "${minus_one}" -gt 0 && "${minus_one}" -gt "${exit_one}" && "${minus_one_pct}" -ge 50 ]]; then
        echo -e "   ${RED}${BOLD}VERDICT: INFRASTRUCTURE FAILURE 🔴${RESET}"
        echo -e "   ${BOLD}Dominant exit code is -1 (${minus_one_pct}% of unresolved) — no test result was"
        echo -e "   ever produced. The kernel/harness broke before tests could run.${RESET}"
        echo -e "   ${BOLD}A weak model cannot produce -1, so this low score is NOT a model-quality"
        echo -e "   signal. Fix the run, then re-evaluate before tuning the model.${RESET}"
    elif [[ "${exit_one}" -gt 0 && "${exit_one}" -gt "${minus_one}" && "${exit_one_pct}" -ge 50 ]]; then
        echo -e "   ${GREEN}${BOLD}VERDICT: MODEL-QUALITY FAILURE 🟢${RESET}"
        echo -e "   ${BOLD}Dominant exit code is 1 (${exit_one_pct}% of unresolved) — a patch WAS produced"
        echo -e "   and applied, and the tests actually ran and failed.${RESET}"
        echo -e "   ${BOLD}Infrastructure is healthy; this score is a real signal about the model.${RESET}"
    else
        echo -e "   ${YELLOW}${BOLD}VERDICT: MIXED / INCONCLUSIVE — no dominant exit code.${RESET}"
        echo -e "   Neither -1 (infrastructure) nor 1 (quality) dominates, so neither explanation"
        echo -e "   is supported. No verdict is being guessed."
    fi
    echo ""
    return 0
}

# --------------------------------------------------------------------- MODES --
run_once() {
    print_header
    # Report BOTH surfaces regardless of the other's outcome: a failure on one
    # must not prevent the other from being reported. The exit code still
    # reflects failure so unattended callers can detect it.
    local rc=0
    check_kaggle_kernel || rc=1   # surface A
    check_leaderboard || rc=1     # surface B
    print_triage                  # verdict
    check_submission_archive
    check_countdown
    print_footer
    return "${rc}"
}

# Polls the kernel until it reaches a terminal state (complete/error), the
# timeout elapses, or the user interrupts. Honours --interval.
watch_mode() {
    if ! resolve_slug >/dev/null; then
        print_header
        echo -e "${BOLD}WATCH — KERNEL${RESET}"
        slug_hint
        return 2
    fi

    local start_ts
    local elapsed
    local polls=0

    trap 'echo ""; echo -e "${YELLOW}Interrupted by user. Stopping watch cleanly.${RESET}"; exit 130' INT TERM

    clear 2>/dev/null || true
    echo -e "${BOLD}${CYAN}======================================================================${RESET}"
    echo -e "${BOLD}${CYAN}  WATCH — KERNEL ${KERNEL_SLUG}${RESET}"
    echo -e "${BOLD}${CYAN}======================================================================${RESET}"
    echo -e "Interval: ${WATCH_INTERVAL}s   Timeout: ${WATCH_TIMEOUT}s   Ctrl+C to stop"
    echo ""

    start_ts=$(date -u +%s)

    while true; do
        polls=$(( polls + 1 ))
        local now_ts
        now_ts=$(date -u +%s)
        elapsed=$(( now_ts - start_ts ))
        local ts
        ts=$(date -u '+%H:%M:%S UTC')

        if [[ "${WATCH_TIMEOUT}" -ne 0 && "${elapsed}" -ge "${WATCH_TIMEOUT}" ]]; then
            echo -e "[${ts}] ${YELLOW}${BOLD}WATCH TIMEOUT after ${elapsed}s (${polls} polls).${RESET}"
            echo -e "Kernel did not reach a terminal status in time. Re-run with --timeout <seconds>."
            return 3
        fi

        local raw_status
        local rc=0
        raw_status=$(kaggle kernels status "${KERNEL_SLUG}" 2>&1) || rc=$?

        if [[ ${rc} -ne 0 ]]; then
            echo -e "[${ts}] ${RED}poll error (kaggle exited ${rc}): ${raw_status}${RESET}"
        elif [[ "${raw_status}" =~ COMPLETE ]]; then
            echo -e "[${ts}] ${GREEN}${BOLD}TERMINAL: COMPLETE 🏁${RESET} kernel ${KERNEL_SLUG} finished."
            if [[ ${FETCH_OUTPUT} -eq 1 ]]; then
                echo -e "Fetching kernel outputs to ${OUTPUT_DIR}..."
                mkdir -p "${OUTPUT_DIR}"
                kaggle kernels output "${KERNEL_SLUG}" -p "${OUTPUT_DIR}" || \
                    echo -e "   ${YELLOW}note: output fetch failed (see message above).${RESET}"
            fi
            echo -e "${BOLD}Exiting watch: kernel reached a terminal status.${RESET}"
            return 0
        elif [[ "${raw_status}" =~ ERROR|FAILED ]]; then
            echo -e "[${ts}] ${RED}${BOLD}TERMINAL: ERROR/FAILED 🔴${RESET} kernel ${KERNEL_SLUG} failed."
            if [[ ${FETCH_OUTPUT} -eq 1 ]]; then
                echo -e "Fetching kernel logs to ${OUTPUT_DIR}..."
                mkdir -p "${OUTPUT_DIR}"
                kaggle kernels output "${KERNEL_SLUG}" -p "${OUTPUT_DIR}" || \
                    echo -e "   ${YELLOW}note: log fetch failed (see message above).${RESET}"
            fi
            echo -e "${BOLD}Exiting watch: kernel reached a terminal status.${RESET}"
            return 1
        elif [[ "${raw_status}" =~ RUNNING ]]; then
            echo -e "[${ts}] poll #${polls} (${elapsed}s elapsed): ${GREEN}RUNNING${RESET}  [${raw_status}]"
        elif [[ "${raw_status}" =~ STARTING|QUEUED|PENDING|SUBMITTING ]]; then
            echo -e "[${ts}] poll #${polls} (${elapsed}s elapsed): ${YELLOW}STARTING${RESET}  [${raw_status}]"
        else
            echo -e "[${ts}] poll #${polls} (${elapsed}s elapsed): ${raw_status}"
        fi

        interruptible_sleep "${WATCH_INTERVAL}"
    done
}

# Legacy silent wait: polls until COMPLETE, then pulls outputs. Preserved.
wait_mode() {
    echo -e "${BOLD}${CYAN}Entering silent wait mode for kernel: ${KERNEL_SLUG:-<none>}${RESET}"
    if ! resolve_slug >/dev/null; then
        slug_hint
        return 2
    fi
    if ! preflight; then
        return 1
    fi
    echo -e "Waiting for completion without consuming LLM tokens..."
    mkdir -p "${OUTPUT_DIR}"

    trap 'echo ""; echo -e "${YELLOW}Interrupted by user. Stopping wait cleanly.${RESET}"; exit 130' INT TERM

    local start_ts
    start_ts=$(date -u +%s)
    local attempt=0
    while true; do
        attempt=$(( attempt + 1 ))
        local now_ts elapsed
        now_ts=$(date -u +%s)
        elapsed=$(( now_ts - start_ts ))
        local timestamp
        timestamp=$(date -u '+%Y-%m-%d %H:%M:%S UTC')

        if [[ "${WATCH_TIMEOUT}" -ne 0 && "${elapsed}" -ge "${WATCH_TIMEOUT}" ]]; then
            echo -e "\n[${timestamp}] ${YELLOW}Wait timeout after ${elapsed}s (${attempt} checks).${RESET}"
            return 3
        fi

        local raw_status
        local rc=0
        raw_status=$(kaggle kernels status "${KERNEL_SLUG}" 2>&1) || rc=$?

        if [[ ${rc} -eq 0 && "${raw_status}" =~ COMPLETE ]]; then
            echo -e "\n[${timestamp}] ${GREEN}${BOLD}Kernel ${KERNEL_SLUG} has COMPLETED successfully! 🏁${RESET}"
            echo -e "Fetching kernel outputs to ${OUTPUT_DIR}..."
            kaggle kernels output "${KERNEL_SLUG}" -p "${OUTPUT_DIR}" || true
            echo -e "Outputs saved to ${OUTPUT_DIR}. Exiting wait mode."
            return 0
        elif [[ ${rc} -eq 0 && "${raw_status}" =~ ERROR|FAILED ]]; then
            echo -e "\n[${timestamp}] ${RED}${BOLD}Kernel ${KERNEL_SLUG} encountered an ERROR or FAILED! 🔴${RESET}"
            echo -e "Status: ${raw_status}"
            echo -e "Attempting to fetch logs to ${OUTPUT_DIR}..."
            kaggle kernels output "${KERNEL_SLUG}" -p "${OUTPUT_DIR}" || true
            return 1
        elif [[ ${rc} -eq 0 && "${raw_status}" =~ RUNNING ]]; then
            echo -ne "\r[${timestamp}] Check #${attempt}: Still RUNNING... (sleeping ${WATCH_INTERVAL}s)    "
            interruptible_sleep "${WATCH_INTERVAL}"
        else
            echo -ne "\r[${timestamp}] Check #${attempt}: ${raw_status} (sleeping ${WATCH_INTERVAL}s)    "
            interruptible_sleep "${WATCH_INTERVAL}"
        fi
    done
}

# ---------------------------------------------------------------------- HELP --
usage() {
    cat <<EOF
${BOLD}${CYAN}check-status.sh${RESET} — Kaggle kernel + leaderboard telemetry (READ ONLY)

${BOLD}USAGE${RESET}
  $0 [MODE] [OPTIONS] [SLUG]
  $0 <owner>/<kernel-name>        # shorthand: treats slug as positional

${BOLD}MODES${RESET}
  (default)        One-shot report: KERNEL + LEADERBOARD + TRIAGE + local state.
  --watch, -w      Poll the kernel every --interval seconds until it reaches a
                   terminal status (COMPLETE or ERROR), the --timeout elapses,
                   or you press Ctrl+C. Exits early on a terminal status.
  --wait, -wait    Legacy silent wait: poll until COMPLETE, then download
                   kernel outputs to ${OUTPUT_DIR}.
  --help, -h       Show this help.

${BOLD}OPTIONS${RESET}
  --kernel SLUG, -k SLUG   Kaggle kernel to inspect (owner/name).
  --interval N             Seconds between polls in --watch/--wait. Default: ${WATCH_INTERVAL}.
  --timeout N              Maximum seconds --watch/--wait may run before giving
                           up. Bounded so polling cannot run forever.
                           Default: ${WATCH_TIMEOUT} (2h). Use 0 for no limit.
  --fetch-output           In --watch, download kernel artifacts to
                           ${OUTPUT_DIR} on a terminal status.
  --competition NAME       Leaderboard competition to query.
                           Default: ${COMPETITION}.
  --triage PATH            Path to a run's task_results.jsonl; prints the
                           infrastructure-vs-quality verdict. If omitted, the
                           most recent run under results/run_*/ is used when one
                           exists, otherwise the verdict reports that no
                           exit-code data is available (it never guesses).
  --no-color               Disable ANSI colour output.
  --help, -h               Show this help and exit.

${BOLD}TRIAGE${RESET}
  A low score has two distinguishable causes, read from the per-task
  test_exit_code distribution in a run's task_results.jsonl:
    dominant -1  =>  INFRASTRUCTURE failure. No test result was ever produced.
                   A model of any quality, however weak, cannot produce -1.
    dominant  1  =>  MODEL-QUALITY failure. A patch was produced and applied
                   and the tests actually ran and failed.

${BOLD}ENVIRONMENT${RESET}
  KAGGLE_KERNEL_SLUG   Default kernel slug, overridable by --kernel.
  KAGGLE_USERNAME / KAGGLE_KEY, or ~/.kaggle/kaggle.json   Kaggle credentials.

${BOLD}EXAMPLES${RESET}
  $0 --kernel francisclyap/gemma4-canary-eval
  $0 --watch --interval 60 --timeout 3600 --fetch-output
  $0 --triage results/run_B39/task_results.jsonl
  $0 --kernel francisclyap/gemma4-baseline-v1 --no-color

${BOLD}READ ONLY${RESET}
  This script never pushes a kernel and never submits to a competition.
  It only reads status.
EOF
}

# ----------------------------------------------------------------- ARGPARSE --
MODE="once"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --watch|-w)       MODE="watch" ;;
        --wait|-wait)     MODE="wait" ;;
        --help|-h)        usage; exit 0 ;;
        --kernel|-k)      shift; KERNEL_SLUG="${1:-}" ;;
        --interval)       shift; WATCH_INTERVAL="${1:-30}" ;;
        --timeout)        shift; WATCH_TIMEOUT="${1:-7200}" ;;
        --fetch-output)   FETCH_OUTPUT=1 ;;
        --competition)    shift; COMPETITION="${1:-$COMPETITION}" ;;
        --triage)         shift; TRIAGE_FILE="${1:-}" ;;
        --no-color)
            BOLD=""; GREEN=""; CYAN=""; YELLOW=""; RED=""; MAGENTA=""; RESET="" ;;
        -*)               echo "Unknown option: $1" >&2; usage; exit 2 ;;
        *)                POSITIONAL_SLUG="$1" ;;
    esac
    shift
done

# Positional slug is the legacy invocation: `$0 <mode> <owner>/<name>`.
if [[ -n "${POSITIONAL_SLUG}" && -z "${KERNEL_SLUG}" ]]; then
    KERNEL_SLUG="${POSITIONAL_SLUG}"
fi

# Validate numeric flags up front: a bad value would otherwise surface later as
# an opaque arithmetic error deep inside the poll loop.
require_uint() {
    local name="$1" value="$2"
    if [[ ! "${value}" =~ ^[0-9]+$ ]]; then
        echo -e "${RED}ERROR: --${name} must be a non-negative integer, got: '${value}'${RESET}" >&2
        exit 2
    fi
}
require_uint "interval" "${WATCH_INTERVAL}"
require_uint "timeout"  "${WATCH_TIMEOUT}"
if [[ "${WATCH_INTERVAL}" -eq 0 ]]; then
    echo -e "${RED}ERROR: --interval must be at least 1 second (0 would busy-poll Kaggle).${RESET}" >&2
    exit 2
fi

if [[ -z "${TRIAGE_FILE}" ]]; then
    # Prefer the newest run that has results, else the primary cloud results.
    TRIAGE_FILE=$(ls -1d results/run_*/task_results.jsonl 2>/dev/null | sort -V | tail -1 || true)
    [[ -z "${TRIAGE_FILE}" ]] && TRIAGE_FILE="cloud_results/results/task_results.jsonl"
    [[ -f "${TRIAGE_FILE}" ]] || TRIAGE_FILE=""
fi

case "${MODE}" in
    watch) watch_mode ;;
    wait)  wait_mode ;;
    once)  run_once ;;
esac
