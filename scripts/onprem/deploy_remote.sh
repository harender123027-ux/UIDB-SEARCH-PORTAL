#!/usr/bin/env bash
# Sync the local UBIS tree to a remote Linux host over SSH and rebuild the stack.
#
# Usage (from repo root):
#   export UBIS_SSH_USER=clam24101
#   export UBIS_SSH_HOST=103.114.153.213
#   export UBIS_SSH_PORT=4422                                # optional, default 22
#   export UBIS_REMOTE_DIR=/opt/ubis/UBIS_Gurugram_Handover  # optional, full path; avoid ~/
#   export UBIS_SSH_KEY=~/.ssh/id_ed25519                    # optional, default ~/.ssh/id_ed25519
#   export UBIS_PROFILE=lite                                 # optional, default lite (lite|full)
#   bash scripts/onprem/deploy_remote.sh
#
# What it does:
#   1. Rsyncs the working tree over SSH (preserves remote .env and ./data/).
#   2. Detects the container runtime on the remote (docker / podman) and whether
#      sudo is required to talk to it.
#   3. Runs:  compose build && compose up -d  on the remote.
#   4. Polls /api/health until the backend is up.
#
# Requirements on the local side:
#   - rsync, ssh
#   - SSH key auth to the server (run `ssh-copy-id -p <port> -i <key>.pub user@host` once).
#
# Requirements on the remote side:
#   - docker + compose plugin, or podman + podman-compose
#   - either: the remote user is in the docker group, OR sudo is passwordless
#     (the script auto-falls-back to `sudo` when direct access is denied).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
: "${UBIS_SSH_USER:?Set UBIS_SSH_USER (e.g. export UBIS_SSH_USER=clam24101)}"
: "${UBIS_SSH_HOST:?Set UBIS_SSH_HOST (e.g. export UBIS_SSH_HOST=103.114.153.213)}"
UBIS_SSH_PORT="${UBIS_SSH_PORT:-22}"
UBIS_REMOTE_DIR="${UBIS_REMOTE_DIR:-/opt/ubis/UBIS_Gurugram_Handover}"
UBIS_SSH_KEY="${UBIS_SSH_KEY:-${HOME}/.ssh/id_ed25519}"
UBIS_PROFILE="${UBIS_PROFILE:-lite}"

SSH_OPTS=(-i "${UBIS_SSH_KEY}" -p "${UBIS_SSH_PORT}" -o BatchMode=yes -o StrictHostKeyChecking=accept-new)
SSH=(ssh "${SSH_OPTS[@]}" "${UBIS_SSH_USER}@${UBIS_SSH_HOST}")
RSYNC_SSH="ssh ${SSH_OPTS[*]}"

echo "==> Sync ${ROOT}/ -> ${UBIS_SSH_USER}@${UBIS_SSH_HOST}:${UBIS_REMOTE_DIR}/"
rsync -avz --delete \
    --exclude '.git' \
    --exclude 'node_modules' \
    --exclude 'backend/.venv' \
    --exclude '__pycache__' \
    --exclude '.pytest_cache' \
    --exclude '.ruff_cache' \
    --exclude 'playwright-report' \
    --exclude 'test-results' \
    --exclude 'dist' \
    --exclude '.DS_Store' \
    --exclude '.env' \
    --exclude '.env.production' \
    --exclude '.env.local' \
    --exclude 'data/' \
    --exclude 'uploads/' \
    --exclude 'tmp/' \
    --exclude 'backups/' \
    --exclude 'backend/ubis.db' \
    --exclude 'backend/qdrant_data' \
    --exclude 'backend/qdrant_storage' \
    --exclude 'backend/uploads' \
    --exclude 'backend/models/buffalo_l.zip' \
    --exclude 'backend/models/buffalo_l/' \
    -e "${RSYNC_SSH}" \
    "${ROOT}/" "${UBIS_SSH_USER}@${UBIS_SSH_HOST}:${UBIS_REMOTE_DIR}/"

echo
echo "==> Detect container runtime + sudo requirement on remote"
# We probe in a single SSH call to keep things snappy and emit a single
# canonical compose invocation back to us as the last line of stdout.
DETECT_SCRIPT='
set -e
need_sudo() {
  # Return 0 if sudo is needed to talk to the container engine.
  local engine="$1"
  if "$engine" info >/dev/null 2>&1; then return 1; fi
  if sudo -n "$engine" info >/dev/null 2>&1; then return 0; fi
  echo "ERROR: cannot run $engine directly and passwordless sudo is not available." >&2
  exit 2
}

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  ENGINE=docker; COMPOSE_SUBCMD="compose"
elif command -v podman >/dev/null 2>&1 && podman compose version >/dev/null 2>&1; then
  ENGINE=podman; COMPOSE_SUBCMD="compose"
elif command -v podman-compose >/dev/null 2>&1; then
  ENGINE=podman-compose; COMPOSE_SUBCMD=""
elif command -v docker-compose >/dev/null 2>&1; then
  ENGINE=docker-compose; COMPOSE_SUBCMD=""
else
  echo "ERROR: no docker / podman compose found on remote." >&2
  exit 3
fi

PROBE_ENGINE="$ENGINE"
case "$PROBE_ENGINE" in
  docker-compose) PROBE_ENGINE=docker ;;
  podman-compose) PROBE_ENGINE=podman ;;
esac

PREFIX=""
if need_sudo "$PROBE_ENGINE"; then PREFIX="sudo "; fi

if [ -n "$COMPOSE_SUBCMD" ]; then
  echo "${PREFIX}${ENGINE} ${COMPOSE_SUBCMD}"
else
  echo "${PREFIX}${ENGINE}"
fi
'

COMPOSE_CMD="$("${SSH[@]}" "${DETECT_SCRIPT}" | tail -n 1)"
if [[ -z "${COMPOSE_CMD}" ]]; then
    echo "ERROR: could not detect a compose command on remote." >&2
    exit 1
fi
echo "    remote compose: ${COMPOSE_CMD}"

echo
echo "==> Build images on remote"
"${SSH[@]}" "cd '${UBIS_REMOTE_DIR}' && ${COMPOSE_CMD} -f docker-compose.onprem.yml --profile '${UBIS_PROFILE}' build"

echo
echo "==> Bring stack up (force-recreate so new images are used)"
"${SSH[@]}" "cd '${UBIS_REMOTE_DIR}' && ${COMPOSE_CMD} -f docker-compose.onprem.yml --profile '${UBIS_PROFILE}' up -d --force-recreate"

echo
echo "==> Wait for backend health"
"${SSH[@]}" '
HTTP_PORT="$(grep "^UBIS_HTTP_PORT=" '"${UBIS_REMOTE_DIR}"'/.env 2>/dev/null | cut -d= -f2-)"
HTTP_PORT="${HTTP_PORT:-8080}"
for attempt in $(seq 1 60); do
  if curl -fsS "http://localhost:${HTTP_PORT}/api/health" >/dev/null 2>&1; then
    echo "  backend healthy on http://localhost:${HTTP_PORT}"
    exit 0
  fi
  sleep 5
done
echo "  WARNING: backend did not become healthy within 5 minutes" >&2
exit 2
'

echo
echo "==> Done."
echo "    Open in a browser on the police LAN:"
echo "        http://${UBIS_SSH_HOST}:8080  (or the UBIS_HTTP_PORT set in remote .env)"
