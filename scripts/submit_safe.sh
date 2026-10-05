#!/usr/bin/env bash
# submit_safe.sh — ordered, gated Kaggle submission wrapper.
#
# WHY THIS EXISTS
# ---------------
# The markdown checklist it replaces (.agents/skills/kaggle-submit/SKILL.md)
# packed the zip BEFORE any gate could validate it, hardcoded a dead
# interpreter path (/private/tmp/brun/venv/bin/python, which does not contain the
# harness packages), and permitted submitting an ungated artifact.
#
# This wrapper makes that ordering impossible to get wrong: each step gates the
# next, and no irreversible action (pack, submit) happens before every gate
# in front of it has passed.
#
# STRICT ORDER
# ------------
#   1. Gate the working tree   (check_submission.py --pre-pack) -> stop on non-zero
#   2. Pack my_submission/ -> submission.zip         (announced first)
#   3. Gate the FINISHED zip  (check_submission.py)  -> stop on non-zero
#   4. Summary + SHA-256 of the zip
#   5. Quota check (submission_quota.per_day from gate_policy.yaml)
#   6. Prompt; default is NO
#   7. kaggle competitions submit
#
# TWO PHASES, ON PURPOSE
# ----------------------
# Step 1 runs the checker in --pre-pack mode: it validates the SOURCE TREE and
# SKIPS the four gates that read submission.zip (g_submission_size_unpacked,
# g_zip_directory_drift, g_zip_root_layout, g_disallowed_extensions), each
# printed as an explicit `SKIPPED (pre-pack):` line. Judging a zip before the
# pack is a verdict about an artifact that does not exist yet -- and it was a
# real deadlock: g_zip_directory_drift is only FIXABLE by step 2, so a stale zip
# made step 1 refuse to proceed to the very step that would resolve the refusal.
#
# Step 3 runs the FULL check, all 15 gates, against the freshly built zip. That
# is step 3's entire purpose and it is deliberately NOT narrowed: the artifact
# that will actually be uploaded is judged by every gate, including all four
# zip-dependent ones, with full veto power.
#
# FLAGS
# -----
#   --dry-run        Run gates 1 and 3 and print what it WOULD do. Never packs,
#                    never submits. This is the safe mode to test with.
#   --yes            Skip the interactive prompt ONLY. Gates still must pass.
#   --override-quota Deliberate second-submit case; bypasses the daily quota
#                    refusal. Does NOT bypass any gate.
#   -h|--help        Show usage.
#
# Interpreter discovery: $PYTHON, then python3, then python. Nothing is
# hardcoded. A candidate must actually be able to run the gates, else we move on.
#
# Exit codes: 0 success (submitted) | 1 gate/trap failure | 2 usage error
#             3 user declined prompt   | 4 quota refusal   | 5 no interpreter

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

CHECKER="$SCRIPT_DIR/check_submission.py"
POLICY="$SCRIPT_DIR/gate_policy.yaml"
SUBMISSION_DIR="$REPO_ROOT/my_submission"
SUBMISSION_ZIP="$REPO_ROOT/submission.zip"
COMPETITION="gemma-4-developer-agent"

# --- Flags (default: prompt, no quota override, not a dry run) ---------------
DRY_RUN=0
ASSUME_YES=0
OVERRIDE_QUOTA=0

# --- Failure trap: report WHICH step failed ----------------------------------
CURRENT_STEP="startup"
on_error() {
  local rc=$?
  echo
  echo "============================================================"
  echo " ABORTED at step: ${CURRENT_STEP}  (exit ${rc})"
  echo "============================================================"
  exit "$rc"
}
trap on_error ERR

# --- Output helpers ----------------------------------------------------------
step()  { CURRENT_STEP="$1"; printf '\n>> [%s/7] %s\n' "$1" "$2"; }
note()  { printf '   %s\n' "$*"; }
warn()  { printf '   ! %s\n' "$*"; }
die()   { printf '\n   STOPPED: %s\n' "$*" >&2; exit 1; }

usage() {
  sed -n '2,40p' "$SCRIPT_PATH" | sed 's/^# \{0,1\}//'
}

# --- ONE exclusion vocabulary, straight from policy ---------------------------
# scripts/gate_policy.yaml -> packaging.excluded_globs is the SINGLE SOURCE OF
# TRUTH for what the packer excludes (see the MANDATORY CONSUMER CONTRACT in
# that file). Both the junk purge and the `zip -x` filter are derived from it,
# so the packer and the gate can never disagree about which files are junk.
#
# Parsing notes:
#   * The policy is FLAT YAML, so the value arrives as one plain comma-separated
#     STRING, not a list.
#   * A value may legitimately contain ':' (e.g. a path-ish glob), so we split
#     on the FIRST colon only -- never an unbounded split, which would truncate
#     the value at the first extra colon.
#   * A missing or empty key is a LOUD failure. There is deliberately NO
#     hardcoded fallback list: a silent fallback would reintroduce the exact
#     second-vocabulary divergence this contract exists to prevent.
EXCLUDE_GLOBS=()   # every glob, verbatim, for the `zip -x` filter
PRUNE_DIR_NAMES=() # directory names to prune (globs ending in "/*")
NAME_GLOBS=()      # globs with no '/'  -> `find -name`
PATH_GLOBS=()      # globs with a '/'    -> `find -path` (find's '*' spans '/')

parse_excluded_globs() {
  local raw="" line part g base name i
  # Extract the raw scalar. awk (not Python+yaml) so this works even without
  # PyYAML; the checker itself is stdlib-only. A first-colon split keeps any
  # embedded ':' in the value intact.
  if ! raw="$(awk '
      BEGIN { in_pack = 0; found = 0; val = "" }
      # A top-level "key:" at column 0 opens/closes a section.
      /^[A-Za-z_][A-Za-z0-9_]*[[:space:]]*:/ {
        k = $0; sub(/[[:space:]]*:.*$/, "", k)   # first-colon split
        in_pack = (k == "packaging"); next
      }
      # The nested key, only while we are inside the packaging: section.
      in_pack && /^[[:space:]]*excluded_globs[[:space:]]*:/ {
        line = $0
        sub(/^[[:space:]]*excluded_globs[[:space:]]*:[[:space:]]*/, "", line)  # first-colon split
        sub(/[[:space:]]+#.*$/, "", line)   # trailing YAML comment
        sub(/[[:space:]]+$/, "", line)
        val = line; found = 1; exit
      }
      END { if (found) print val }
    ' "$POLICY" 2>&1)"; then
    die "could not parse packaging.excluded_globs from $POLICY: ${raw:-<no output>}"
  fi

  # Split the comma-separated string, trim each item, drop empties -- matching
  # check_submission.py's resolve_excluded_globs() exactly.
  local parts=() raw_parts=()
  local oldifs="$IFS"
  IFS=','
  read -r -a raw_parts <<< "$raw" || true   # empty scalar -> read returns 1
  IFS="$oldifs"
  local i=0
  while [ "$i" -lt "${#raw_parts[@]}" ]; do
    part="${raw_parts[$i]}"
    i=$((i + 1))
    part="${part#"${part%%[![:space:]]*}"}"   # ltrim
    part="${part%"${part##*[![:space:]]}"}"   # rtrim
    if [ -n "$part" ]; then
      parts+=("$part")
    fi
  done

  if [ "${#parts[@]}" -eq 0 ]; then
    echo
    echo "============================================================"
    echo " STOPPED: packaging.excluded_globs is missing or empty in"
    echo "          $POLICY"
    echo " There is NO hardcoded fallback list by design -- a second,"
    echo " divergent vocabulary is the bug this policy key exists to"
    echo " prevent. Add a non-empty excluded_globs to the packaging"
    echo " section (comma-separated globs) and re-run."
    echo "============================================================"
    exit 1
  fi

  EXCLUDE_GLOBS=()
  PRUNE_DIR_NAMES=()
  NAME_GLOBS=()
  PATH_GLOBS=()
  for g in "${parts[@]}"; do
    EXCLUDE_GLOBS+=("$g")
    if [ "${g#*/}" = "$g" ]; then
      NAME_GLOBS+=("$g")                       # no '/' -> basename match
    elif [ "${g##*/}" = '*' ]; then
      # Ends in "/*" -> the preceding component names a directory to prune.
      base="${g%/*}"; name="${base##*/}"
      case "$name" in
        *[\*\?\[]*) PATH_GLOBS+=("$g") ;;      # metachars -> match by path
        *) PRUNE_DIR_NAMES+=("$name") ;;       # literal dir name -> prune
      esac
    else
      PATH_GLOBS+=("$g")                       # other path glob -> -path
    fi
  done
}

# --- Flag parsing ------------------------------------------------------------
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)        DRY_RUN=1 ;;
    --yes|-y)         ASSUME_YES=1 ;;
    --override-quota) OVERRIDE_QUOTA=1 ;;
    -h|--help)        usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

[ -f "$CHECKER" ] || die "gate script not found: $CHECKER"
[ -f "$POLICY"  ] || die "gate policy not found: $POLICY"
[ -d "$SUBMISSION_DIR" ] || die "submission directory not found: $SUBMISSION_DIR"

# Parse the one exclusion vocabulary now (before any irreversible step) so a
# missing/empty policy key fails loudly rather than silently falling back.
parse_excluded_globs

# --- Interpreter discovery: the bug this script exists to fix ---------------
# A candidate must be able to run the gates. check_submission.py is stdlib-only
# (yaml optional), so "can run it" means it is a working Python 3 that can at
# minimum import zipfile/hashlib and execute the module.
discover_python() {
  local candidates=() c resolved=""
  if [ -n "${PYTHON:-}" ]; then candidates+=("$PYTHON"); fi
  candidates+=("python3" "python")
  for c in "${candidates[@]}"; do
    command -v "$c" >/dev/null 2>&1 || continue
    resolved="$(command -v "$c")"
    if "$resolved" -c 'import sys,zipfile,hashlib; sys.exit(0 if sys.version_info[:2] >= (3,8) else 1)' 2>/dev/null; then
      printf '%s\n' "$resolved"
      return 0
    fi
  done
  return 1
}

# ============================================================================
# STEP 1 — Gate the working tree
# ============================================================================
step 1 "Gate the working tree (source-tree validation, before any pack)"
if ! PY_BIN="$(discover_python)"; then
  echo
  echo "   STOPPED: no usable Python interpreter found."
  echo "   Tried: \$PYTHON (if set), python3, python."
  echo "   None could run the gates. Set PYTHON=/path/to/python3 and retry."
  echo "   (The old checklist hardcoded a venv path that lacks the packages.)"
  exit 5
fi
note "interpreter: $PY_BIN"
note "gates:      $CHECKER"
note "phase:      pre-pack (the 4 zip-dependent gates run at step 3)"

if ! "$PY_BIN" "$CHECKER" --pre-pack; then
  echo
  echo "============================================================"
  echo " GATES FAILED on the working tree. STOPPING HERE."
  echo " Nothing was packed. Nothing was submitted."
  echo " Fix the FAILs above, then re-run this script."
  echo "============================================================"
  exit 1
fi
note "working tree: PASS (source tree validated; the zip itself is gated at step 3)"

# --- Dry run stops here for packing purposes, but still runs gate 3 ---------
if [ "$DRY_RUN" -eq 1 ]; then
  step 3 "Gate the FINISHED zip (existing artifact; --dry-run did not repack)"
  # FULL check, same as the real step 3: it validates an actual packed zip, so
  # the four zip-dependent gates are meaningful here and keep full veto power.
  if "$PY_BIN" "$CHECKER"; then
    note "existing zip: PASS"
  else
    echo
    echo "============================================================"
    echo " GATES FAILED on the existing submission.zip. STOPPING HERE."
    echo " Nothing was submitted. (--dry-run never packs or submits.)"
    echo "============================================================"
    exit 1
  fi

  step 4 "What a real run WOULD do (no changes made)"
  note "  - purge junk from my_submission/, then pack it into submission.zip"
  note "  - re-run the gates against that new zip"
  note "  - print its SHA-256, check the daily quota, then prompt you"
  note "  - exclusion vocabulary (packaging.excluded_globs from gate_policy.yaml):"
  note "      ${EXCLUDE_GLOBS[*]}"
  note "    purge: prune dirs [${PRUNE_DIR_NAMES[*]:-none}]"
  note "           by name   [${NAME_GLOBS[*]:-none}]"
  note "           by path   [${PATH_GLOBS[*]:-none}]"
  if [ -f "$SUBMISSION_ZIP" ]; then
    note "  current zip would be replaced: $SUBMISSION_ZIP"
    note "  current zip sha256: $(shasum -a 256 "$SUBMISSION_ZIP" | awk '{print $1}')"
  else
    note "  no submission.zip present yet"
  fi
  echo
  echo "DRY RUN OK — no pack, no submit."
  exit 0
fi

# ============================================================================
# STEP 2 — Pack (irreversible-ish: overwrites the real submission.zip)
# ============================================================================
step 2 "Pack my_submission/ -> submission.zip"

# ANNOUNCED BEFORE IT HAPPENS: this overwrites the real archive.
warn "ABOUT TO OVERWRITE: $SUBMISSION_ZIP"

# Purge junk PHYSICALLY, governed by packaging.excluded_globs from
# gate_policy.yaml (parsed at startup -- see the ONE exclusion vocabulary block).
# The drift gate (g_zip_directory_drift) honours that SAME shared exclusion list
# on BOTH sides of the comparison, so a correctly-excluded file is skipped by the
# gate rather than reported as "in dir not zip". We still purge physically
# because that also keeps the working tree clean and guarantees the junk is
# absent from the zip itself. The vocabulary below comes ONLY from policy --
# there is no hardcoded list here, so the packer and gate cannot diverge.
#
# Prune matching directories first (one rm -rf per tree), then delete matching
# files by basename and by path.
for name in "${PRUNE_DIR_NAMES[@]+"${PRUNE_DIR_NAMES[@]}"}"; do
  find "$SUBMISSION_DIR" -type d -name "$name" -prune -exec rm -rf {} + 2>/dev/null || true
done
for g in "${NAME_GLOBS[@]+"${NAME_GLOBS[@]}"}"; do
  find "$SUBMISSION_DIR" -type f -name "$g" -delete 2>/dev/null || true
done
for g in "${PATH_GLOBS[@]+"${PATH_GLOBS[@]}"}"; do
  find "$SUBMISSION_DIR" -type f -path "$SUBMISSION_DIR/$g" -delete 2>/dev/null || true
done
note "purged junk per packaging.excluded_globs (prune dirs: ${PRUNE_DIR_NAMES[*]:-none})"

# Zip from INSIDE the directory so paths sit at the archive root. A submission
# nested one level too deep is a silent failure. The -x filter uses the SAME
# policy-derived globs as the purge above -- one vocabulary, both places.
rm -f "$SUBMISSION_ZIP"
( cd "$SUBMISSION_DIR" && zip -r -q "$SUBMISSION_ZIP" . \
    -x "${EXCLUDE_GLOBS[@]+"${EXCLUDE_GLOBS[@]}"}" ) || die "zip failed"
[ -f "$SUBMISSION_ZIP" ] || die "zip did not produce $SUBMISSION_ZIP"
note "packed $(ls -lh "$SUBMISSION_ZIP" | awk '{print $5}')"

# ============================================================================
# STEP 3 — Gate the FINISHED zip
# ============================================================================
step 3 "Gate the FINISHED zip (validates the artifact that will be uploaded)"
# FULL check -- all 15 gates, no --pre-pack. The zip now exists, so the four
# gates step 1 deferred (g_submission_size_unpacked, g_zip_directory_drift,
# g_zip_root_layout, g_disallowed_extensions) run here with full veto power.
# This step is what makes the artifact trustworthy; narrowing it would defeat
# the entire two-phase split, so it is deliberately left unfiltered.
if ! "$PY_BIN" "$CHECKER"; then
  echo
  echo "============================================================"
  echo " GATES FAILED on the newly packed zip. STOPPING HERE."
  echo " Nothing was submitted."
  echo "============================================================"
  exit 1
fi
note "packed zip: PASS"

# ============================================================================
# STEP 4 — Summary + hash
# ============================================================================
step 4 "Submission summary"
note "competition: $COMPETITION"
note "file:        $(basename "$SUBMISSION_ZIP") ($(ls -lh "$SUBMISSION_ZIP" | awk '{print $5}'))"
ZIP_SHA="$(shasum -a 256 "$SUBMISSION_ZIP" | awk '{print $1}')"
note "sha256:      $ZIP_SHA"

# ============================================================================
# STEP 5 — Quota check
# ============================================================================
step 5 "Daily quota check"

# Read the quota from the policy file. Do NOT hardcode it.
read -r QUOTA_PER_DAY < <(
  "$PY_BIN" - "$POLICY" <<'PYEOF' 2>/dev/null || true
import sys
try:
    import yaml
    with open(sys.argv[1]) as fh:
        print(yaml.safe_load(fh)["submission_quota"]["per_day"])
except Exception:
    pass
PYEOF
)
QUOTA_PER_DAY="${QUOTA_PER_DAY:-unknown}"
if [ "$QUOTA_PER_DAY" = "unknown" ]; then
  warn "could not read submission_quota.per_day from gate_policy.yaml"
else
  note "policy allows: $QUOTA_PER_DAY submission(s) per day"
fi

TODAY_SUBMITS="unknown"
if command -v kaggle >/dev/null 2>&1; then
  HISTORY="$(kaggle competitions submissions -c "$COMPETITION" 2>/dev/null || true)"
  if [ -n "$HISTORY" ]; then
    TODAY_SUBMITS="$(printf '%s\n' "$HISTORY" \
      | awk -v today="$(date -u +%Y-%m-%d)" 'NR>1 && index($0, today) {n++} END {print n+0}')"
    note "kaggle CLI available; submissions dated today (UTC): $TODAY_SUBMITS"
  else
    warn "kaggle CLI present but submission history could not be read"
  fi
else
  warn "kaggle CLI not available; cannot determine today's submission count"
fi

if [ "$TODAY_SUBMITS" != "unknown" ] && [ "$TODAY_SUBMITS" -ge 1 ] 2>/dev/null; then
  if [ "$OVERRIDE_QUOTA" -eq 1 ]; then
    warn "quota: $TODAY_SUBMITS submit(s) already today; --override-quota given, continuing"
  else
    echo
    echo "============================================================"
    echo " QUOTA REFUSAL: already $TODAY_SUBMITS submission(s) today (UTC)."
    echo " Policy allows $QUOTA_PER_DAY per day."
    echo " Nothing was submitted."
    echo " Re-run with --override-quota ONLY if you mean it."
    echo "============================================================"
    exit 4
  fi
elif [ "$TODAY_SUBMITS" = "unknown" ]; then
  warn "quota state UNKNOWN — proceeding carefully, not assuming a free slot"
fi

# ============================================================================
# STEP 6 — Prompt (default NO)
# ============================================================================
if [ "$ASSUME_YES" -eq 1 ]; then
  step 6 "Prompt skipped (--yes given); gates above already passed"
  warn "submitting WITHOUT confirmation because --yes was passed"
else
  step 6 "Confirm submission"
  echo
  echo "   About to submit the artifact described above."
  echo "   Default is NO. Type 'y' to submit, anything else aborts."
  printf '   Proceed? [y/N]: '
  REPLY=""
  if ! IFS= read -r REPLY; then
    echo
    echo "   No input (EOF / non-interactive). Aborting. Nothing was submitted."
    exit 3
  fi
  case "$REPLY" in
    y|Y|yes|YES) ;;
    *)
      echo "   Answer was not 'y'. Aborting. Nothing was submitted."
      exit 3
      ;;
  esac
fi

# ============================================================================
# STEP 7 — Submit
# ============================================================================
step 7 "Submitting to Kaggle (irreversible — this consumes your daily slot)"
warn "SUBMITTING: $SUBMISSION_ZIP (sha256 $ZIP_SHA)"
command -v kaggle >/dev/null 2>&1 || die "kaggle CLI not found; cannot submit"

kaggle competitions submit \
  -c "$COMPETITION" \
  -f "$SUBMISSION_ZIP" \
  -m "Gated submission (sha256 ${ZIP_SHA:0:12}); gates passed via scripts/submit_safe.sh" \
  || die "kaggle submit failed"

echo
echo "============================================================"
echo " SUBMITTED. sha256=$ZIP_SHA"
echo "============================================================"
