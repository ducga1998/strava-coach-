#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
RAILWAY_ENVIRONMENT="${RAILWAY_ENVIRONMENT:-production}"
RAILWAY_SERVICE="${RAILWAY_SERVICE:-backend}"

require_command() {
  local command_name="$1"
  if command -v "${command_name}" >/dev/null 2>&1; then
    return
  fi
  echo "[railway-deploy] Missing required command: ${command_name}" >&2
  exit 1
}

assert_logged_in() {
  if railway whoami >/dev/null 2>&1; then
    return
  fi
  echo "[railway-deploy] Railway auth not found. Run: railway login" >&2
  exit 1
}

assert_linked_project() {
  cd "${BACKEND_DIR}"
  if railway status >/dev/null 2>&1; then
    return
  fi
  cat >&2 <<'MSG'
[railway-deploy] Railway project is not linked.
Run once:
  cd backend && railway link --project strava-coach --environment production --service backend
MSG
  exit 1
}

deploy_backend() {
  cd "${BACKEND_DIR}"
  echo "[railway-deploy] Deploying backend from: ${BACKEND_DIR}"
  railway up --service "${RAILWAY_SERVICE}" --environment "${RAILWAY_ENVIRONMENT}" --detach
}

main() {
  require_command railway
  assert_logged_in
  assert_linked_project
  deploy_backend
}

main "$@"
