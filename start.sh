#!/usr/bin/env bash
set -e

# Cleanly exit on Ctrl+C
trap 'echo -e "\n🛑 Exited by Ctrl+C."; exit 0' INT

# ==============================================================================
# SWE-Gemma Evaluator Launcher
# Runs evaluation inside a dedicated tmux window with a live Rich dashboard.
# By default, reads the list of tasks from test.txt (or pass --pilot / --all).
# ==============================================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

export PYTHONDONTWRITEBYTECODE=1
export SWEGEMMA_CONCURRENCY="${SWEGEMMA_CONCURRENCY:-15}"
export SWEGEMMA_MODEL="${SWEGEMMA_MODEL:-thinkingmachines/inkling:free}"
export SWEGEMMA_API_KEY="${SWEGEMMA_API_KEY:-lr-or-oa-ch-no}"

# Clean any stray bytecode cache in submission directory before ADK compilation
find "$PROJECT_DIR/my_submission" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$PROJECT_DIR/my_submission" -name "*.pyc" -delete 2>/dev/null || true

PYTHON_BIN="/tmp/brun/venv/bin/python"

if [ ! -x "$PYTHON_BIN" ]; then
    echo "❌ Error: Virtual environment python not found at $PYTHON_BIN"
    exit 1
fi

# ------------------------------------------------------------------------------
# Step 1: Preflight Check & Live Agent Declarations
# ------------------------------------------------------------------------------
echo "============================================================"
echo " [1/2] Running Preflight Verification Gate & Agent Diagnostics..."
echo "============================================================"
"$PYTHON_BIN" scripts/preflight_check.py

echo ""
echo "============================================================"
echo " Preflight Verification & Agent Declarations Complete."
echo " 🤖 Model Target : ${SWEGEMMA_MODEL}"
echo "============================================================"

# Display active tasks if test.txt is used
ARGS="$*"
if [ -z "$ARGS" ] && [ -f "test.txt" ]; then
    ACTIVE_COUNT=$(grep -v '^[[:space:]]*#' test.txt | grep -v '^[[:space:]]*$' | wc -l | tr -d ' ')
    echo "📄 Found test.txt with $ACTIVE_COUNT active task(s):"
    grep -v '^[[:space:]]*#' test.txt | grep -v '^[[:space:]]*$' | sed 's/^/   - /'
fi

# ------------------------------------------------------------------------------
# Step 2: User Menu (1 = Start test, 2 = Exit)
# ------------------------------------------------------------------------------
# Flush any pending keystrokes entered while preflight was running
if [ -t 0 ]; then
    while read -r -t 0.05 -n 100 discard 2>/dev/null; do :; done
fi

while true; do
    echo ""
    echo "Select an option:"
    echo "  1) Yes - Start tmux test (Default)"
    echo "  2) No  - Exit"
    echo ""

    if [ -t 0 ] && [ -r /dev/tty ]; then
        read -r -p "Enter choice [1 or 2] (Default: 1): " CHOICE </dev/tty || CHOICE=""
    else
        read -r -p "Enter choice [1 or 2] (Default: 1): " CHOICE || CHOICE=""
    fi

    # Treat empty input (pressing Enter) as default "1"
    CHOICE="${CHOICE:-1}"

    case "$CHOICE" in
        1|[yY]|[yY][eE][sS])
            echo ""
            echo "🚀 Starting tmux evaluation..."
            break
            ;;
        2|[nN]|[nN][oO]|[qQ]|exit|quit)
            echo ""
            echo "🛑 Exiting."
            exit 0
            ;;
        *)
            echo "⚠️  Invalid choice '$CHOICE'. Please enter 1 to start or 2 to exit."
            ;;
    esac
done

# ------------------------------------------------------------------------------
# Step 3: Launch SWE-Gemma Live Dashboard in Tmux
# ------------------------------------------------------------------------------
echo ""
echo "============================================================"
echo " [2/2] Launching SWE-Gemma Live Dashboard in Tmux..."
echo "============================================================"

WINDOW_NAME="swe-eval"

# Check if we are running inside an existing tmux session
if [ -n "$TMUX" ]; then
    SESSION_NAME=$(tmux display-message -p '#S')
    
    # Check if a window named swe-eval already exists
    if tmux list-windows -t "$SESSION_NAME" -F "#{window_name}" | grep -q "^${WINDOW_NAME}$"; then
        echo "⚠️  Window '$WINDOW_NAME' already exists. Closing old window..."
        tmux kill-window -t "${SESSION_NAME}:${WINDOW_NAME}" 2>/dev/null || true
    fi

    # Create new window in current session and switch to it
    echo "🚀 Spawning live dashboard window '$WINDOW_NAME' in tmux session '$SESSION_NAME'..."
    tmux new-window -t "${SESSION_NAME}:" -n "$WINDOW_NAME" \
        "cd '$PROJECT_DIR' && '$PYTHON_BIN' scripts/run_eval.py $ARGS; echo ''; echo 'Evaluation ended. Press Enter to exit...'; read"
    
    # Immediately switch the active tmux window so the user sees the live progress
    tmux select-window -t "${SESSION_NAME}:${WINDOW_NAME}"
    echo "✅ Switched to tmux window '$WINDOW_NAME'!"
    echo "💡 Hint: To return to OpenCode, press 'Ctrl+b 0' (or Ctrl+b p)."

else
    # Not inside tmux - start a new tmux session and attach
    SESSION_NAME="swe-eval-session"
    if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
        echo "⚠️  Session '$SESSION_NAME' already exists. Killing old session..."
        tmux kill-session -t "$SESSION_NAME"
    fi

    echo "🚀 Starting new tmux session '$SESSION_NAME'..."
    tmux new-session -s "$SESSION_NAME" \
        "cd '$PROJECT_DIR' && '$PYTHON_BIN' scripts/run_eval.py $ARGS; echo ''; echo 'Evaluation ended. Press Enter to exit...'; read"
fi
