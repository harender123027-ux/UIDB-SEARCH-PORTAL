#!/usr/bin/env bash
# Sync local UBIS tree to a remote Linux host over SSH, then run the on-prem installer.
#
# Usage (from repo root):
#   export UBIS_SSH_USER=you
#   export UBIS_SSH_HOST=203.0.113.10
#   export UBIS_SSH_PORT=4422          # optional, default 22
#   export UBIS_REMOTE_DIR=/opt/ubis/UBIS_Gurugram_Handover   # optional (use full path; avoid ~/ — local shell may expand it)
#   bash scripts/onprem/deploy_remote.sh
#
# Requires:
#   - SSH key auth to the server (password auth will not work non-interactively)
#   - Docker or Podman + compose on the remote host (see docs/HANDOVER_GURUGRAM/01_INSTALL.md)
#
# First-time on the server (once):
#   sudo mkdir -p /opt/ubis && sudo chown "$USER:$USER" /opt/ubis
#
# Copy SSH public key (so this script can run unattended):
#   ssh-copy-id -p 4422 you@203.0.113.10

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
: "${UBIS_SSH_USER:?Set UBIS_SSH_USER (e.g. export UBIS_SSH_USER=myuser)}"
: "${UBIS_SSH_HOST:?Set UBIS_SSH_HOST (e.g. export UBIS_SSH_HOST=203.0.113.10)}"
UBIS_SSH_PORT="${UBIS_SSH_PORT:-22}"
UBIS_REMOTE_DIR="${UBIS_REMOTE_DIR:-/opt/ubis/UBIS_Gurugram_Handover}"

SSH=(ssh -p "${UBIS_SSH_PORT}" -o BatchMode=yes -o StrictHostKeyChecking=accept-new "${UBIS_SSH_USER}@${UBIS_SSH_HOST}")
RSYNC=(rsync -avz --delete
  --exclude '.git'
  --exclude 'node_modules'
  --exclude 'backend/.venv'
  --exclude '__pycache__'
  --exclude '.pytest_cache'
  --exclude 'playwright-report'
  --exclude 'test-results'
  --exclude 'backend/ubis.db'
  --exclude 'backend/qdrant_data'
  --exclude 'backend/qdrant_storage'
  --exclude 'backend/uploads'
  --exclude '.env'
  --exclude '.env.production'
  --exclude '.env.local'
  -e "ssh -p ${UBIS_SSH_PORT} -o BatchMode=yes -o StrictHostKeyChecking=accept-new"
)

echo "==> Sync ${ROOT}/ -> ${UBIS_SSH_USER}@${UBIS_SSH_HOST}:${UBIS_REMOTE_DIR}/"
"${RSYNC[@]}" "${ROOT}/" "${UBIS_SSH_USER}@${UBIS_SSH_HOST}:${UBIS_REMOTE_DIR}/"

echo "==> Run on-prem install on remote (idempotent)"
"${SSH[@]}" "cd '${UBIS_REMOTE_DIR}' && bash scripts/onprem/install.sh"

echo "==> Done. Check remote: bash scripts/onprem/ubis-status.sh (on server, from ${UBIS_REMOTE_DIR})"
