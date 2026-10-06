#!/usr/bin/env bash
# push_kernel_safe.sh — ordered, gated gateway for the two Kaggle WRITE actions
# that publish the baseline diagnostic kernel.
#
# WHY THIS EXISTS
# ---------------
# There are TWO divergent LoRA lineages in this repo, both of them named
# `main_lora`, and no other tool in the tree tells them apart. The one this
# script guards is identified by its content hash:
#
#   CORRECT  cb4347b1...  kaggle_adapter_dataset/adapter_model.safetensors
#   STALE    7d32d9e7...  what is currently published on Kaggle
#
# THE ORDER IS LOAD BEARING.
#
#   STEP 1  kaggle datasets version -p kaggle_adapter_dataset -m "<message>"
#             -> republishes the LoRA adapter as an INPUT DATASET (version bump)
#   STEP 2  kaggle kernels push -p kaggle_baseline_v1
#             -> pushes the 129-task diagnostic kernel
#
# A kernel push resolves its `dataset_sources` at PUSH TIME against whatever
# dataset version is live at that instant. So if the kernel is pushed BEFORE the
# dataset is republished, the kernel is permanently bound to the STALE adapter
# (sha256 prefix 7d32d9e7) instead of the correct one (cb4347b1) — and the next
# 30 hour GPU run then measures the WRONG LoRA. That failure is silent, costs a
# full day of quota, and cannot be detected from the kernel logs at a glance.
#
# Therefore: STEP 1 ALWAYS PRECEDES STEP 2, and this script REFUSES to run
# STEP 2 if STEP 1 was skipped, was declined, or failed. The only way past that
# refusal is `--force-stale-adapter`, which exists so the refusal is a decision
# the operator makes out loud rather than an accident.
#
# THIS SCRIPT IS NOT ON THE LEADERBOARD PATH.
# It never submits a competition entry and never touches leaderboard scoring.
# The kernel it pushes produces PER-TASK DIAGNOSTICS ONLY.
#
# GATES (all LOCAL — they run before any network action and abort on failure)
#   1. kaggle CLI is on PATH
#   2. kaggle_adapter_dataset/ exists and holds adapter_model.safetensors
#      plus adapter_config.json
#   3. THE CRITICAL GATE: sha256 of adapter_model.safetensors equals
#      cb4347b1824cad75d12e998b609defd6421c63e7b3d54e2d055aa6cbb3cb965d.
#      Full 64-character comparison. On mismatch the script prints the expected
#      and the observed hash in full and ABORTS. A truncated hash is never
#      printed as though it were a pass. This gate is the reason the script
#      exists: without it, the two `main_lora` lineages are indistinguishable.
#   4. kaggle_baseline_v1/kernel-metadata.json parses as JSON and its `id` is
#      exactly francisclyap/gemma4-baseline-v1
#   5. kaggle_baseline_v1/baseline_v1.ipynb parses as JSON and has a `cells`
#      array
#
# COST WARNING (printed before the confirmation prompt, not buried in a comment)
#   Pushing this kernel commits roughly 30 HOURS of GPU quota and yields NO
#   leaderboard score — per-task diagnostics only.
#
# SAFETY
#   * No `--yes`, no `-y`, no non-interactive path, no unattended path.
#   * The confirmation is typed by a human on the controlling terminal.
#   * Declining, EOF, Ctrl+C, or a non-interactive invocation all abort BEFORE
#     any Kaggle write.
#
# FLAGS
#   --dry-run              Run every local gate, print the full plan, execute
#                          ZERO kaggle commands of any kind (read-only ones
#                          included), and exit 0. This is the safe mode to test
#                          with; it is verified to work with kaggle absent from
#                          PATH.
#   --skip-dataset         Do not run STEP 1. STEP 2 is then REFUSED unless
#                          --force-stale-adapter is also given.
#   --force-stale-adapter  The documented override. Lets STEP 2 run when STEP 1
#                          did not publish, i.e. accepts that the kernel will
#                          bind the STALE adapter (7d32d9e7...) and that a
#                          30 hour GPU run would measure the wrong LoRA.
#                          Passing this is the ONLY way to reach STEP 2 without
#                          a fresh dataset publish. It bypasses the ORDER GUARD
#                          and nothing else — every local gate still runs.
#   -h|--help              Show usage and exit 0.
#
# Exit codes: 0 success (pushed) | 1 gate/trap failure | 2 usage error
#             3 declined / no human confirmation / Ctrl+C (130) — nothing done
#             4 order-guard refusal (STEP 2 without a fresh STEP 1)

set -euo pipefail

# --- Repo root resolved from THIS FILE, so any CWD works --------------------
SCRIPT_PATH="${BASH_SOURCE[0]}"
while [ -L "$SCRIPT_PATH" ]; do
  _link="$(readlink "$SCRIPT_PATH")"
  case "$_link" in
    /*) SCRIPT_PATH="$_link" ;;
    *)  SCRIPT_PATH="$(dirname "$SCRIPT_PATH")/$_link" ;;
  esac
done
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"

DATASET_DIR="$REPO_ROOT/kaggle_adapter_dataset"
DATASET_SLUG="kaggle_adapter_dataset"
ADAPTER_FILE="$DATASET_DIR/adapter_model.safetensors"
ADAPTER_CFG="$DATASET_DIR/adapter_config.json"
KERNEL_DIR="$REPO_ROOT/kaggle_baseline_v1"
KERNEL_METADATA="$KERNEL_DIR/kernel-metadata.json"
KERNEL_NOTEBOOK="$KERNEL_DIR/baseline_v1.ipynb"

# THE constant this whole script exists to enforce. Never edit it to "make it
# pass" — if it no longer matches, the adapter you are about to publish is a
# different lineage and the operator must be told.
EXPECTED_ADAPTER_SHA="cb4347b1824cad75d12e998b609defd6421c63e7b3d54e2d055aa6cbb3cb965d"
STALE_ADAPTER_SHA_PREFIX="7d32d9e7"
EXPECTED_KERNEL_ID="francisclyap/gemma4-baseline-v1"

# --- Flags (default: run BOTH steps, prompt, no override) ---------------------
DRY_RUN=0
SKIP_DATASET=0
FORCE_STALE=0

# --- Failure trap: report WHICH step failed ----------------------------------
CURRENT_STEP="startup"
on_error() {
  local rc=$?
  echo
  echo "============================================================"
  echo " ABORTED at step: ${CURRENT_STEP}  (exit ${rc})"
  echo " Nothing was published. Nothing was pushed."
  echo "============================================================"
  exit "$rc"
}
trap on_error ERR

# Ctrl+C at the prompt (or anywhere) must leave the world untouched.
trap 'echo; echo "   INTERRUPTED (Ctrl+C). Nothing was published. Nothing was pushed."; exit 130' INT

# --- Output helpers ----------------------------------------------------------
step()  { CURRENT_STEP="$1"; printf '\n>> [%s/6] %s\n' "$1" "$2"; }
note()  { printf '   %s\n' "$*"; }
warn()  { printf '   ! %s\n' "$*"; }
pass()  { printf '   PASS  %s\n' "$*"; }
skip()  { printf '   SKIP  %s\n' "$*"; }
fail()  { printf '   FAIL  %s\n' "$*"; }
die()   { printf '\n   STOPPED: %s\n' "$*" >&2; exit 1; }

usage() {
  # The header comment block only: line 2 through the `set -euo pipefail` line,
  # with that terminator dropped so the usage text is pure documentation.
  sed -n '2,/^set -euo pipefail$/p' "$SCRIPT_PATH" | sed -e '$d' -e 's/^# \{0,1\}//'
}

banner() {
  echo "============================================================"
  echo " push_kernel_safe.sh — gated Kaggle kernel publish gateway"
  echo "============================================================"
}

# --- Flag parsing ------------------------------------------------------------
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)             DRY_RUN=1 ;;
    --skip-dataset)        SKIP_DATASET=1 ;;
    --force-stale-adapter) FORCE_STALE=1 ;;
    -h|--help)             usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

# --- Local-only helpers ------------------------------------------------------

# sha256 of a file, FULL 64 hex chars. macOS ships shasum; Linux ships
# sha256sum. Prefer the one that is actually present.
sha256_of() {
  local f="$1"
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$f" | awk '{print $1}'
  elif command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$f" | awk '{print $1}'
  else
    echo ""
  fi
}

# A Python 3 that can at least import json — used only for the two JSON parse
# gates. Nothing here reaches the network.
discover_python() {
  local candidates=() c resolved=""
  if [ -n "${PYTHON:-}" ]; then candidates+=("$PYTHON"); fi
  candidates+=("python3" "python")
  for c in "${candidates[@]}"; do
    command -v "$c" >/dev/null 2>&1 || continue
    resolved="$(command -v "$c")"
    if "$resolved" -c 'import sys,json; sys.exit(0 if sys.version_info[:2] >= (3,6) else 1)' 2>/dev/null; then
      printf '%s\n' "$resolved"
      return 0
    fi
  done
  return 1
}

banner

# ============================================================================
# GATE 1 — kaggle CLI on PATH
# ============================================================================
step 1 "Gate: kaggle CLI availability"
KAGGLE_BIN=""
if KAGGLE_BIN="$(command -v kaggle 2>/dev/null)"; then
  KAGGLE_BIN="$(cd "$(dirname "$KAGGLE_BIN")" && pwd -P)/$(basename "$KAGGLE_BIN")"
  pass "kaggle CLI on PATH: $KAGGLE_BIN"
  note "credentials are NOT probed here; a missing token surfaces as a write failure"
else
  if [ "$DRY_RUN" -eq 1 ]; then
    # --dry-run performs ZERO kaggle commands, read-only ones included, so the
    # absence of the CLI cannot make a dry run fail. Reported, not fatal.
    skip "kaggle CLI not on PATH — NOT FATAL in --dry-run (zero kaggle commands run)"
  else
    fail "kaggle CLI not found on PATH"
    echo
    echo "============================================================"
    echo " GATE 1 FAILED. STOPPING BEFORE ANY NETWORK ACTION."
    echo " Nothing was published. Nothing was pushed."
    echo " Install/authenticate the kaggle CLI, then re-run."
    echo "============================================================"
    exit 1
  fi
fi

# ============================================================================
# GATE 2 — staging directory contents
# ============================================================================
step 2 "Gate: dataset staging directory"
[ -d "$DATASET_DIR" ] || { fail "missing directory: $DATASET_DIR"; die "gate 2 failed"; }
pass "directory present: $DATASET_DIR"
for f in "$ADAPTER_FILE" "$ADAPTER_CFG"; do
  if [ -f "$f" ]; then
    pass "present: $(basename "$f") ($(ls -lh "$f" | awk '{print $5}'))"
  else
    fail "missing: $f"
    die "gate 2 failed"
  fi
done

# ============================================================================
# GATE 3 — THE CRITICAL GATE: adapter identity
# ============================================================================
step 3 "Gate: adapter sha256 identity (this is the point of the script)"
OBSERVED_ADAPTER_SHA="$(sha256_of "$ADAPTER_FILE")"
if [ -z "$OBSERVED_ADAPTER_SHA" ]; then
  fail "no sha256 tool found (need shasum or sha256sum)"
  die "gate 3 could not be evaluated"
fi
if [ "$OBSERVED_ADAPTER_SHA" = "$EXPECTED_ADAPTER_SHA" ]; then
  pass "sha256 matches the CORRECT lineage exactly (64/64 chars compared)"
  note "expected: $EXPECTED_ADAPTER_SHA"
  note "observed: $OBSERVED_ADAPTER_SHA"
else
  fail "ADAPTER SHA256 MISMATCH — refusing to continue"
  note "expected: $EXPECTED_ADAPTER_SHA"
  note "observed: $OBSERVED_ADAPTER_SHA"
  if [ "${OBSERVED_ADAPTER_SHA:0:8}" = "$STALE_ADAPTER_SHA_PREFIX" ]; then
    warn "observed hash has the STALE lineage prefix (${STALE_ADAPTER_SHA_PREFIX}...)."
    warn "Publishing this would re-bind the kernel to the wrong LoRA."
  fi
  echo
  echo "============================================================"
  echo " GATE 3 FAILED. STOPPING BEFORE ANY NETWORK ACTION."
  echo " Nothing was published. Nothing was pushed."
  echo " Two LoRA lineages in this repo are both named main_lora."
  echo " This hash is the only thing that tells them apart."
  echo " Do NOT edit EXPECTED_ADAPTER_SHA in this script to force a pass."
  echo "============================================================"
  exit 1
fi

# ============================================================================
# GATE 4 — kernel metadata identity
# ============================================================================
step 4 "Gate: kernel-metadata.json"
[ -f "$KERNEL_METADATA" ] || { fail "missing: $KERNEL_METADATA"; die "gate 4 failed"; }
if ! PY_BIN="$(discover_python)"; then
  fail "no usable Python 3 found for the JSON gates"
  die "gate 4 could not be evaluated (set PYTHON=/path/to/python3)"
fi
note "interpreter: $PY_BIN"
KERNEL_ID_FOUND="$("$PY_BIN" - "$KERNEL_METADATA" <<'PYEOF' 2>/dev/null || echo "__PARSE_ERROR__"
import json, sys
try:
    with open(sys.argv[1]) as fh:
        print(json.load(fh)["id"])
except Exception:
    print("__PARSE_ERROR__")
PYEOF
)"
if [ "$KERNEL_ID_FOUND" = "__PARSE_ERROR__" ]; then
  fail "kernel-metadata.json does not parse as JSON, or has no 'id' key"
  die "gate 4 failed"
fi
if [ "$KERNEL_ID_FOUND" != "$EXPECTED_KERNEL_ID" ]; then
  fail "kernel id mismatch"
  note "expected: $EXPECTED_KERNEL_ID"
  note "observed: $KERNEL_ID_FOUND"
  die "gate 4 failed"
fi
pass "kernel-metadata.json parses; id is exactly $EXPECTED_KERNEL_ID"

# ============================================================================
# GATE 5 — notebook parses
# ============================================================================
step 5 "Gate: baseline_v1.ipynb"
[ -f "$KERNEL_NOTEBOOK" ] || { fail "missing: $KERNEL_NOTEBOOK"; die "gate 5 failed"; }
NOTEBOOK_CELLS="$("$PY_BIN" - "$KERNEL_NOTEBOOK" <<'PYEOF' 2>/dev/null || echo "__PARSE_ERROR__"
import json, sys
try:
    with open(sys.argv[1]) as fh:
        nb = json.load(fh)
    cells = nb["cells"]
    if not isinstance(cells, list):
        print("__PARSE_ERROR__")
    else:
        print(len(cells))
except Exception:
    print("__PARSE_ERROR__")
PYEOF
)"
if [ "$NOTEBOOK_CELLS" = "__PARSE_ERROR__" ]; then
  fail "baseline_v1.ipynb does not parse as JSON with a 'cells' array"
  die "gate 5 failed"
fi
pass "notebook parses as JSON with a cells array (${NOTEBOOK_CELLS} cells)"

# ============================================================================
# STEP 0 — Consequence, stated before any confirmation
# ============================================================================
step 6 "What proceeding actually costs"
cat <<EOF
   ---------------------------------------------------------------
   THE 30 HOUR WARNING

   Pushing this kernel spends roughly 30 HOURS of your GPU quota.
   It yields NO LEADERBOARD SCORE. It produces PER-TASK DIAGNOSTICS
   ONLY. It is not on the competition leaderboard path.
   ---------------------------------------------------------------
EOF

# ============================================================================
# PLAN + DRY RUN
# ============================================================================
echo
echo "   PLAN"
note "STEP 1  publish dataset : $DATASET_SLUG"
note "        adapter sha256  : ${OBSERVED_ADAPTER_SHA}"
if [ "$SKIP_DATASET" -eq 1 ]; then
  note "        SKIPPED by operator (--skip-dataset)"
else
  note "        kaggle datasets version -p ${DATASET_DIR} -m \"<message>\""
fi
note "STEP 2  push kernel     : $(basename "$KERNEL_DIR")"
note "        kernel id      : $EXPECTED_KERNEL_ID"
note "        kaggle kernels push -p ${KERNEL_DIR#"$REPO_ROOT"/}"
if [ "$SKIP_DATASET" -eq 1 ] || [ "$FORCE_STALE" -eq 1 ]; then
  warn "--skip-dataset / --force-stale-adapter given: STEP 1 will NOT publish."
  warn "STEP 2 therefore binds the STALE adapter (${STALE_ADAPTER_SHA_PREFIX}...),"
  warn "and a 30 hour GPU run would measure the WRONG LoRA."
fi
echo

if [ "$DRY_RUN" -eq 1 ]; then
  echo "DRY RUN OK — every local gate ran; ZERO kaggle commands were executed"
  echo "(including read-only ones) and nothing was written to Kaggle."
  note "the confirmation prompt was intentionally skipped in --dry-run"
  exit 0
fi

# ============================================================================
# ORDER GUARD — the refusal that makes the ordering unbreakable
# ============================================================================
# STEP 2 may only run if STEP 1 actually published in THIS run. Anything else
# (skipped, declined, failed) is refused unless --force-stale-adapter says so
# out loud.
if [ "$SKIP_DATASET" -eq 1 ] && [ "$FORCE_STALE" -ne 1 ]; then
  echo "============================================================"
  echo " ORDER GUARD REFUSAL: STEP 1 was skipped (--skip-dataset)."
  echo
  echo " Pushing the kernel now would attach the STALE adapter"
  echo " (sha256 prefix ${STALE_ADAPTER_SHA_PREFIX}...) instead of the"
  echo " correct one (${EXPECTED_ADAPTER_SHA:0:8}...)."
  echo " Nothing was published. Nothing was pushed."
  echo
  echo " Fix, in order:"
  echo "   1) re-run WITHOUT --skip-dataset, or"
  echo "   2) publish the dataset first on its own, then re-run, or"
  echo "   3) re-run WITH --force-stale-adapter if you truly accept that"
  echo "      this kernel measures the wrong LoRA."
  echo "============================================================"
  exit 4
fi

# ============================================================================
# Human check — this script is never unattended
# ============================================================================
HUMAN_OK=0
if [ -t 0 ] && [ -r /dev/tty ] && [ -w /dev/tty ]; then
  HUMAN_OK=1
elif [ -r /dev/tty ] && [ -w /dev/tty ]; then
  HUMAN_OK=1   # stdin redirected, but a real controlling terminal exists
fi
if [ "$HUMAN_OK" -ne 1 ]; then
  echo
  echo "============================================================"
  echo " NON-INTERACTIVE INVOCATION REFUSED."
  echo " This script requires a HUMAN to type the confirmation; there is"
  echo " deliberately no --yes, no -y, and no unattended path. Run it from"
  echo " an interactive terminal."
  echo " Nothing was published. Nothing was pushed."
  echo "============================================================"
  exit 3
fi

# ============================================================================
# Confirmation — one prompt, unambiguous, recommends BOTH
# ============================================================================
if [ "$SKIP_DATASET" -eq 1 ]; then
  DO_DATASET=0
else
  DO_DATASET=1
fi
DO_KERNEL=1

echo
echo "   CONFIRM"
if [ "$DO_DATASET" -eq 1 ]; then
  note "recommended: type  both   to publish the dataset THEN push the kernel"
  note "            type  dataset to publish the dataset ONLY (no kernel push)"
  note "            type  kernel  to push ONLY — REFUSED unless --force-stale-adapter"
else
  note "--skip-dataset is set, so only STEP 2 (kernel push) can be confirmed."
  note "type  kernel  to push the kernel against the STALE adapter"
  note "anything else aborts with nothing done"
fi
note "default is NO. anything other than a listed word aborts (exit 3)."
printf '   Proceed? [both|dataset|kernel]: '

REPLY=""
if ! IFS= read -r REPLY < /dev/tty; then
  echo
  echo "   No input (EOF / non-interactive). Aborting. Nothing was published."
  echo "   Nothing was pushed."
  exit 3
fi

case "$REPLY" in
  both|both*)            DO_DATASET=1; DO_KERNEL=1 ;;
  dataset|dataset*)      DO_DATASET=1; DO_KERNEL=0 ;;
  kernel|kernel*)        DO_DATASET=0; DO_KERNEL=1 ;;
  *)
    echo "   Answer was not a recognised word. Aborting. Nothing was published."
    echo "   Nothing was pushed."
    exit 3
    ;;
esac

echo
if [ "$DO_DATASET" -eq 1 ] && [ "$DO_KERNEL" -eq 1 ]; then
  note "confirmed: BOTH (publish dataset, then push kernel — in that order)"
elif [ "$DO_DATASET" -eq 1 ]; then
  note "confirmed: dataset publish ONLY (no kernel push)"
else
  note "confirmed: kernel push ONLY"
fi

# ============================================================================
# STEP 1 — publish the dataset. Irreversible: bumps the live dataset version.
# ============================================================================
DATASET_PUBLISHED=0
if [ "$DO_DATASET" -eq 1 ]; then
  CURRENT_STEP="STEP 1 kaggle datasets version"
  warn "PUBLISHING NOW: dataset '$DATASET_SLUG' (adapter ${OBSERVED_ADAPTER_SHA:0:8}...)"
  MESSAGE="main_lora adapter cb4347b1 (Rank-8 q/v/o), staged for baseline diagnostic kernel; published by push_kernel_safe.sh"
  if "$KAGGLE_BIN" datasets version -p "$DATASET_DIR" -m "$MESSAGE"; then
    DATASET_PUBLISHED=1
    pass "STEP 1 OK — dataset '$DATASET_SLUG' republished"
  else
    fail "STEP 1 FAILED — kaggle datasets version returned non-zero"
    note "the live dataset version was NOT advanced by this run"
  fi
else
  warn "STEP 1 NOT RUN (declined at the prompt or --skip-dataset)"
fi

# ============================================================================
# STEP 2 — push the kernel. BLOCKED unless STEP 1 published, or the operator
#          explicitly forced the stale binding with --force-stale-adapter.
# ============================================================================
if [ "$DO_KERNEL" -eq 1 ]; then
  if [ "$DATASET_PUBLISHED" -ne 1 ] && [ "$FORCE_STALE" -ne 1 ]; then
    echo
    echo "============================================================"
    echo " ORDER GUARD REFUSAL: STEP 1 did not publish in this run."
    if [ "$FORCE_STALE" -eq 0 ]; then
      echo
      echo " Pushing now would attach the STALE adapter"
      echo " (sha256 prefix ${STALE_ADAPTER_SHA_PREFIX}...) instead of the"
      echo " correct one (${EXPECTED_ADAPTER_SHA:0:8}...)."
    fi
    echo " Nothing was pushed."
    echo " Re-run and answer 'both' so the dataset publishes first, or pass"
    echo " --force-stale-adapter to accept the stale binding explicitly."
    echo "============================================================"
    exit 4
  fi

  if [ "$DATASET_PUBLISHED" -ne 1 ]; then
    warn "PROCEEDING ON --force-stale-adapter: this kernel binds the STALE adapter"
    warn "(${STALE_ADAPTER_SHA_PREFIX}...). A 30 hour GPU run will measure the WRONG LoRA."
  fi

  CURRENT_STEP="STEP 2 kaggle kernels push"
  warn "PUSHING NOW: kernel '$EXPECTED_KERNEL_ID' (binds dataset '$DATASET_SLUG')"
  if ! "$KAGGLE_BIN" kernels push -p "$KERNEL_DIR"; then
    die "kaggle kernels push failed"
  fi
  pass "STEP 2 OK — kernel pushed"

  echo
  echo "============================================================"
  echo " PUSHED. Kernel: $EXPECTED_KERNEL_ID"
  echo " Dataset bound at push time: $DATASET_SLUG"
  if [ "$DATASET_PUBLISHED" -eq 1 ]; then
    echo " Adapter measured: ${OBSERVED_ADAPTER_SHA}  (CORRECT lineage)"
  else
    echo " Adapter measured: STALE (${STALE_ADAPTER_SHA_PREFIX}...)  -- forced"
  fi
  echo " Reminder: ~30 HOURS of GPU quota, NO leaderboard score."
  echo "============================================================"
  echo
  echo "   NEXT COMMANDS (run these yourself):"
  echo
  echo "   kaggle kernels status gemma4-baseline-v1"
  echo "        one-shot server-side state of the kernel: queued/running/finished"
  echo
  echo "   ./check-status.sh --watch --kernel gemma4-baseline-v1"
  echo "        live-watch the run here, with log tailing, until it finishes"
  echo
  echo "   kaggle kernels output gemma4-baseline-v1 -p baseline_v1_results"
  echo "        after completion, downloads the notebook's output artifacts"
  echo "        into ./baseline_v1_results for the per-task diagnostics"
  echo
else
  echo
  note "STEP 2 declined at the prompt — no kernel push. Nothing further to do."
  if [ "$DO_DATASET" -eq 1 ]; then
    echo
    echo "   The dataset '$DATASET_SLUG' IS published. Push the kernel later with:"
    echo "   ./scripts/push_kernel_safe.sh"
  fi
fi