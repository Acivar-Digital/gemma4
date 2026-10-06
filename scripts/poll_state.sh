#!/usr/bin/env bash
# poll_state.sh — change-detecting state watcher for the Gemma 4 submission effort.
#
# CONTRACT: emits output ONLY when a STABLE signature line changes, plus a
# heartbeat every HEARTBEAT_EVERY ticks. It is NOT a metronome: with no
# change it prints nothing at all.
#
# The signature deliberately EXCLUDES any monotonically-changing value.
# A previous version included `tick=` and `quota_min=` in the compared
# signature, so the equality test could never hold and it printed a full
# STATE CHANGED report every single run. Those values are rendered inside
# the report body and the heartbeat only — never compared.
#
# Read-only: never runs ./start.sh, never submits, never mutates tracked files.
#
# Usage:
#   ./scripts/poll_state.sh --once     # single check, print if changed, exit
#   ./scripts/poll_state.sh --watch    # loop forever, $INTERVAL between checks
#
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || exit 1

STATE_DIR="$REPO/.poll_state"
STATE_FILE="$STATE_DIR/last_seen"
TICK_FILE="$STATE_DIR/tick"
mkdir -p "$STATE_DIR"
[ -f "$TICK_FILE" ] || echo 0 > "$TICK_FILE"   # init on first run

INTERVAL=300          # 5 minutes
HEARTBEAT_EVERY=12    # heartbeat every 12 ticks (~1 hour)

# --- stable signature helpers ------------------------------------------------
# Each returns a value that only changes when the underlying fact changes.

sig_memory() {
  # Count of memories that re-assert a formally retracted claim. Must stay 0.
  bd memories 2>/dev/null \
    | grep -ciE 'process died|sequential phase|P2/P3|wrong-fix, not search|T2 include_thoughts'
}

sig_git() {
  # Exclude .poll_state/ — otherwise the poller's own writes dirty its own
  # signature and it reports a phantom change on every tick.
  git status --porcelain -- . ':!.poll_state' 2>/dev/null | sha256sum | cut -c1-16
}

sig_zip() {
  [ -f submission.zip ] && sha256sum submission.zip | cut -c1-16 || echo "NO-ZIP"
}

sig_gate() {
  python3 scripts/check_submission.py >/dev/null 2>&1 && echo "PASS" || echo "FAIL"
}

sig_tests() {
  # Static presence proxy only. NOT a test run — ./start.sh is user-only
  # per AGENTS.md.
  [ -f tests/test_check_submission.py ] && echo "present" || echo "missing"
}

sig_kaggle() {
  # Reachability only. Does NOT scrape, authenticate, or submit anything.
  curl -sS -m 8 -o /dev/null -w '%{http_code}' https://www.kaggle.com 2>/dev/null \
    || echo "unreachable"
}

# --- volatile helpers (report body / heartbeat only, NEVER compared) ---------

sig_quota() {
  local now next
  now=$(date -u +%s)
  next=$(date -u -d 'tomorrow 00:00' +%s 2>/dev/null) || { echo "unknown"; return; }
  echo $(( (next - now) / 60 ))
}

bump_tick() {
  local t
  t=$(cat "$TICK_FILE" 2>/dev/null || echo 0)
  [ -z "$t" ] && t=0
  echo $((t + 1)) > "$TICK_FILE"
}

read_tick() { cat "$TICK_FILE" 2>/dev/null || echo 0; }

# --- signature --------------------------------------------------------------
# STABLE LINES ONLY. tick and quota_min are deliberately absent.

collect() {
  echo "memory_retracted=$(sig_memory)"
  echo "git=$(sig_git)"
  echo "zip=$(sig_zip)"
  echo "gate=$(sig_gate)"
  echo "tests=$(sig_tests)"
  echo "kaggle=$(sig_kaggle)"
}

# --- reporting --------------------------------------------------------------

# $1 = current signature, $2 = previous signature. Returns 0 if CHANGED.
report() {
  local current="$1" previous="$2"
  [ "$current" = "$previous" ] && return 1

  echo "=== POLL: STATE CHANGED (tick $(read_tick), quota_min $(sig_quota)) ==="
  echo "--- diff ---"
  diff <(echo "$previous") <(echo "$current") | grep -E '^[<>]' || true
  echo "--- current ---"
  echo "$current"
  echo "=== END POLL ==="
  return 0
}

heartbeat() {
  echo "=== POLL: HEARTBEAT (no change, tick $(read_tick), quota_min $(sig_quota)) ==="
  echo "kaggle=$(sig_kaggle)"
  echo "=== END POLL ==="
}

# Decide-and-emit for one tick. Args: $1=current signature, $2=previous signature.
emit() {
  local current="$1" previous="$2" tick
  tick="$(read_tick)"

  if report "$current" "$previous"; then
    echo "$current" > "$STATE_FILE"
    bump_tick
    return 0
  fi

  if [ "$tick" -gt 0 ] && [ $((tick % HEARTBEAT_EVERY)) -eq 0 ]; then
    heartbeat
  fi
  bump_tick
  return 0
}

# --- main -------------------------------------------------------------------

CURRENT="$(collect)"

if [ ! -f "$STATE_FILE" ]; then
  echo "$CURRENT" > "$STATE_FILE"
  bump_tick
  echo "=== POLL: BASELINE INITIALISED (nothing to compare) ==="
  echo "$CURRENT"
  echo "=== END POLL ==="
  exit 0
fi

PREVIOUS="$(cat "$STATE_FILE")"

if [ "${1:-}" = "--watch" ]; then
  emit "$CURRENT" "$PREVIOUS"
  while true; do
    sleep "$INTERVAL"
    emit "$(collect)" "$(cat "$STATE_FILE")"
  done
else
  emit "$CURRENT" "$PREVIOUS"
fi
