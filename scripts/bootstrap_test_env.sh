#!/usr/bin/env bash
# bootstrap_test_env.sh — Idempotently provisions a persistent test environment (.venv)
# for Gemma 4 / SWE-Gemma test gates, and maintains /tmp/g4venv compatibility.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_VENV="${TEST_VENV_PATH:-${REPO_ROOT}/.venv}"
REQ_FILE="${REPO_ROOT}/requirements-test.txt"
TMP_COMPAT="/tmp/g4venv"

# Ensure standard CA bundle is used if mkcert is active in user environment
if [[ -f /etc/ssl/certs/ca-certificates.crt ]]; then
    export SSL_CERT_FILE="${SSL_CERT_FILE:-/etc/ssl/certs/ca-certificates.crt}"
fi

PYTHON_BIN="$(command -v python3.12 || command -v python3)"

echo "=== Gemma 4 Test Environment Bootstrap ==="
echo "Repo root:    ${REPO_ROOT}"
echo "Target venv:  ${TARGET_VENV}"
echo "Python bin:   ${PYTHON_BIN}"
echo "Requirements: ${REQ_FILE}"

if [[ ! -f "${REQ_FILE}" ]]; then
    echo "ERROR: Requirements file not found at ${REQ_FILE}" >&2
    exit 1
fi

# 1. Create virtual environment if missing or broken
if [[ ! -x "${TARGET_VENV}/bin/python3" ]]; then
    echo "Creating virtual environment at ${TARGET_VENV}..."
    if command -v uv >/dev/null 2>&1; then
        uv venv "${TARGET_VENV}" --python "${PYTHON_BIN}" --allow-existing
    elif "${PYTHON_BIN}" -m venv --help >/dev/null 2>&1; then
        "${PYTHON_BIN}" -m venv "${TARGET_VENV}"
    else
        echo "ERROR: Neither 'uv' nor 'venv' available to create venv." >&2
        exit 1
    fi
fi

# 2. Install pinned dependencies
echo "Installing pinned dependencies into ${TARGET_VENV}..."
if command -v uv >/dev/null 2>&1; then
    uv pip install --python "${TARGET_VENV}/bin/python3" -r "${REQ_FILE}"
elif [[ -x "${TARGET_VENV}/bin/pip" ]]; then
    "${TARGET_VENV}/bin/pip" install --no-cache-dir -r "${REQ_FILE}"
else
    echo "Bootstrapping pip via ensurepip..."
    "${TARGET_VENV}/bin/python3" -m ensurepip --default-pip
    "${TARGET_VENV}/bin/pip" install --no-cache-dir -r "${REQ_FILE}"
fi

# 3. Maintain /tmp/g4venv compatibility symlink
if [[ "${TARGET_VENV}" != "${TMP_COMPAT}" ]]; then
    echo "Ensuring compatibility symlink at ${TMP_COMPAT}..."
    if [[ -L "${TMP_COMPAT}" ]]; then
        rm -f "${TMP_COMPAT}"
        ln -s "${TARGET_VENV}" "${TMP_COMPAT}"
    elif [[ -d "${TMP_COMPAT}" ]]; then
        echo "Replacing legacy directory /tmp/g4venv with symlink to ${TARGET_VENV}..."
        rm -rf "${TMP_COMPAT}"
        ln -s "${TARGET_VENV}" "${TMP_COMPAT}"
    else
        ln -s "${TARGET_VENV}" "${TMP_COMPAT}"
    fi
fi

# 3b. Maintain my_submission -> submissions/track1_live compatibility symlink
if [[ ! -e "${REPO_ROOT}/my_submission" && -d "${REPO_ROOT}/submissions/track1_live" ]]; then
    echo "Creating my_submission compatibility symlink -> submissions/track1_live..."
    ln -s "submissions/track1_live" "${REPO_ROOT}/my_submission"
fi

# 4. Verify pytest functionality
echo "Verifying test interpreter..."
"${TARGET_VENV}/bin/pytest" --version
echo "Verifying Pydantic import..."
"${TARGET_VENV}/bin/python3" -c "import pydantic; print(f'Pydantic {pydantic.__version__} OK')"
echo "Verifying /tmp/g4venv symlink pytest..."
"${TMP_COMPAT}/bin/pytest" --version

echo "=== Bootstrap Complete: Environment Ready ==="
