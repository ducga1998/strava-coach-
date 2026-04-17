#!/usr/bin/env bash
# Start FastAPI backend (:8000) and Vite frontend (:5173) together.
# From repo root: ./scripts/run-local.sh
# Requires: Python deps in backend (uvicorn), Node deps in frontend (npm install).
# Optional: docker compose up -d for Postgres/Redis before running.

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PID=""
FRONTEND_PID=""

# Non-interactive scripts often miss Node (nvm/fnm/Volta only hook login shells).
load_node_tools() {
  local nvm_dir="${NVM_DIR:-${HOME}/.nvm}"
  if [[ -s "${nvm_dir}/nvm.sh" ]]; then
    # shellcheck source=/dev/null
    source "${nvm_dir}/nvm.sh"
  fi
  if command -v fnm >/dev/null 2>&1; then
    eval "$(fnm env 2>/dev/null)" || true
  fi
  if [[ -d "${HOME}/.volta" ]]; then
    export VOLTA_HOME="${HOME}/.volta"
    export PATH="${VOLTA_HOME}/bin:${PATH}"
  fi
  if [[ -f "${HOME}/.asdf/asdf.sh" ]]; then
    # shellcheck source=/dev/null
    source "${HOME}/.asdf/asdf.sh"
  fi
}

cleanup() {
  if [[ -n "${BACKEND_PID}" ]] && kill -0 "${BACKEND_PID}" 2>/dev/null; then
    kill "${BACKEND_PID}" 2>/dev/null || true
  fi
  if [[ -n "${FRONTEND_PID}" ]] && kill -0 "${FRONTEND_PID}" 2>/dev/null; then
    kill "${FRONTEND_PID}" 2>/dev/null || true
  fi
  wait 2>/dev/null || true
}

trap cleanup EXIT INT TERM

load_node_tools

if [[ -f "${ROOT}/backend/.venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "${ROOT}/backend/.venv/bin/activate"
fi

cd "${ROOT}/backend" || exit 1
echo "[run-local] Backend → http://127.0.0.1:8000 (reload on)"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

cd "${ROOT}/frontend" || exit 1
echo "[run-local] Frontend → http://127.0.0.1:5173"

VITE_BIN="${ROOT}/frontend/node_modules/.bin/vite"
VITE_JS="${ROOT}/frontend/node_modules/vite/bin/vite.js"
if [[ -f "${VITE_JS}" ]] && command -v node >/dev/null 2>&1; then
  # Most reliable: local Vite + node on PATH (after load_node_tools).
  node "${VITE_JS}" --host 127.0.0.1 --port 5173 &
  FRONTEND_PID=$!
elif [[ -x "${VITE_BIN}" ]]; then
  "${VITE_BIN}" --host 127.0.0.1 --port 5173 &
  FRONTEND_PID=$!
elif command -v npm >/dev/null 2>&1; then
  npm run dev &
  FRONTEND_PID=$!
else
  echo "[run-local] ERROR: Node tooling not found." >&2
  echo "  Install deps: cd frontend && npm install" >&2
  echo "  Or ensure node/npm is on PATH (open a login shell and retry)." >&2
  exit 1
fi

sleep 0.3
if ! kill -0 "${FRONTEND_PID}" 2>/dev/null; then
  echo "[run-local] ERROR: frontend exited immediately. Try: cd frontend && npm install" >&2
  exit 1
fi

echo "[run-local] Press Ctrl+C to stop both."
wait
