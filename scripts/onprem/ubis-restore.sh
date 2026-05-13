#!/usr/bin/env bash
# Restore a UBIS backup tarball produced by ubis-backup.sh.
#
# Usage:
#   bash scripts/onprem/ubis-restore.sh ./backups/ubis-backup-YYYYMMDDThhmmssZ.tar.gz
#
# WARNING: This wipes ./data and replaces it with the contents of the tarball.
# The script asks for explicit confirmation unless UBIS_RESTORE_YES=1.

set -euo pipefail

TARBALL="${1:-}"
[[ -n "$TARBALL" && -f "$TARBALL" ]] || {
    echo "Usage: $0 <path-to-tarball>" >&2
    exit 1
}

COMPOSE_FILE="docker-compose.onprem.yml"
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    COMPOSE=(docker compose)
elif command -v podman >/dev/null 2>&1 && podman compose version >/dev/null 2>&1; then
    COMPOSE=(podman compose)
elif command -v podman-compose >/dev/null 2>&1; then
    COMPOSE=(podman-compose)
else
    COMPOSE=(docker-compose)
fi

if [[ "${UBIS_RESTORE_YES:-}" != "1" ]]; then
    cat <<EOF
This will:
  1. Stop the running UBIS containers.
  2. Move the existing ./data directory aside (./data.before-restore-<timestamp>).
  3. Restore files from $TARBALL.
  4. Restart the containers.

Type the word RESTORE to continue:
EOF
    read -r ANSWER
    [[ "$ANSWER" == "RESTORE" ]] || { echo "Aborted."; exit 1; }
fi

echo "[*] Stopping containers"
# podman-compose 1.5 sometimes refuses to remove pods with running containers,
# so stop first (best effort), then down --remove-orphans.
"${COMPOSE[@]}" -f "$COMPOSE_FILE" --profile "${UBIS_PROFILE:-lite}" stop -t 30 >/dev/null 2>&1 || true
"${COMPOSE[@]}" -f "$COMPOSE_FILE" --profile "${UBIS_PROFILE:-lite}" down --remove-orphans >/dev/null 2>&1 || true
# Final safety: kill anything still running.
for c in ubis-backend ubis-frontend ubis-postgres; do
    if command -v podman >/dev/null 2>&1; then
        podman rm -f "$c" >/dev/null 2>&1 || true
    elif command -v docker >/dev/null 2>&1; then
        docker rm -f "$c" >/dev/null 2>&1 || true
    fi
done

if [[ -d ./data ]]; then
    SAFE="./data.before-restore-$(date -u +'%Y%m%dT%H%M%SZ')"
    echo "[*] Moving existing ./data to $SAFE"
    mv ./data "$SAFE"
fi
mkdir -p ./data

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
echo "[*] Extracting $TARBALL"
tar -C "$WORK" -xzf "$TARBALL"

# Restore data tree.
if [[ -d "$WORK/data" ]]; then
    cp -R "$WORK/data/." ./data/
fi
mkdir -p ./data/db

# SQLite file goes back to its mount path.
[[ -f "$WORK/ubis.db" ]] && cp "$WORK/ubis.db" ./data/db/ubis.db

# Optional .env restore (rename so we never silently overwrite a different secret).
if [[ -f "$WORK/dot.env" && ! -f .env ]]; then
    cp "$WORK/dot.env" .env
    chmod 600 .env
    echo "[*] Restored .env from backup"
fi

echo "[*] Bringing the stack back up"
"${COMPOSE[@]}" -f "$COMPOSE_FILE" --profile "${UBIS_PROFILE:-lite}" up -d

# Some podman + virtiofs combos cache the inode of the original ./data
# directory.  Recreate the containers explicitly so they re-bind to the
# fresh inode of the restored ./data tree.  Idempotent on docker.
sleep 2
for c in ubis-backend ubis-frontend; do
    if command -v podman >/dev/null 2>&1; then
        podman rm -f "$c" >/dev/null 2>&1 || true
    fi
done
"${COMPOSE[@]}" -f "$COMPOSE_FILE" --profile "${UBIS_PROFILE:-lite}" up -d >/dev/null 2>&1 || true

# Restore Postgres if the dump exists and the postgres service is in this profile.
if [[ -f "$WORK/postgres.sql" ]]; then
    echo "[*] Waiting 20s for Postgres to come up before importing dump"
    sleep 20
    "${COMPOSE[@]}" -f "$COMPOSE_FILE" exec -T postgres \
        sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$WORK/postgres.sql"
fi

echo "[✓] Restore complete.  Run ./scripts/onprem/ubis-status.sh to verify."
