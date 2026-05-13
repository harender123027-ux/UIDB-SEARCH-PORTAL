#!/usr/bin/env bash
# UBIS on-prem backup.
# Produces ONE tarball under ./backups/ containing:
#   - the relational DB (SQLite file or pg_dump)
#   - all uploaded case images
#   - reference photos
#   - the Qdrant vector index
#   - .env  (so a restore on a new machine keeps the same JWT secret)
#
# Backups are encrypted at rest if you symlink GnuPG and pass UBIS_BACKUP_GPG_RECIPIENT.
# By default the tarball is gzipped but NOT encrypted — store it on department-controlled media.

set -euo pipefail

COMPOSE_FILE="docker-compose.onprem.yml"
STAMP=$(date -u +'%Y%m%dT%H%M%SZ')
OUT_DIR="${UBIS_BACKUP_DIR:-./backups}"
TARBALL="${OUT_DIR}/ubis-backup-${STAMP}.tar.gz"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    COMPOSE=(docker compose)
elif command -v podman >/dev/null 2>&1 && podman compose version >/dev/null 2>&1; then
    COMPOSE=(podman compose)
elif command -v podman-compose >/dev/null 2>&1; then
    COMPOSE=(podman-compose)
else
    COMPOSE=(docker-compose)
fi

mkdir -p "$OUT_DIR"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

echo "[*] Staging files at $WORK"

# Postgres dump if running, otherwise copy the SQLite file as-is.
if "${COMPOSE[@]}" -f "$COMPOSE_FILE" ps --services 2>/dev/null | grep -qx postgres; then
    if "${COMPOSE[@]}" -f "$COMPOSE_FILE" ps postgres 2>/dev/null | grep -q "Up\|running"; then
        echo "[*] Dumping PostgreSQL"
        "${COMPOSE[@]}" -f "$COMPOSE_FILE" exec -T postgres \
            sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$WORK/postgres.sql"
    fi
fi

# Always copy SQLite (cheap and tiny) when present.
[[ -f ./data/db/ubis.db ]] && cp ./data/db/ubis.db "$WORK/ubis.db"

# Application data.
# Models (~600 MB of InsightFace + AdaFace weights) are re-downloadable on first
# run, so by default we EXCLUDE them to keep nightly backups small.  Set
# UBIS_BACKUP_INCLUDE_MODELS=1 (e.g. for the very first archival snapshot) to
# bundle them in.
mkdir -p "$WORK/data"
for d in uploads reference_photos qdrant; do
    if [[ -d "./data/$d" ]]; then
        cp -R "./data/$d" "$WORK/data/$d"
    fi
done
if [[ "${UBIS_BACKUP_INCLUDE_MODELS:-0}" == "1" && -d ./data/models ]]; then
    cp -R ./data/models "$WORK/data/models"
fi

# .env — only the file, NOT the directory it sits in.
[[ -f .env ]] && cp .env "$WORK/dot.env"

# Manifest for forensics / audit.
cat >"$WORK/MANIFEST.txt" <<EOF
UBIS backup
Created: $STAMP UTC
Hostname: $(hostname -f 2>/dev/null || hostname)
Compose file: $COMPOSE_FILE
Contents:
  $(cd "$WORK" && find . -maxdepth 2 -type f -printf '  %p (%s bytes)\n' 2>/dev/null || find . -maxdepth 2 -type f -exec ls -l {} \;)
EOF

echo "[*] Creating $TARBALL"
tar -C "$WORK" -czf "$TARBALL" .

if [[ -n "${UBIS_BACKUP_GPG_RECIPIENT:-}" ]] && command -v gpg >/dev/null 2>&1; then
    gpg --yes --batch --encrypt --recipient "$UBIS_BACKUP_GPG_RECIPIENT" "$TARBALL"
    rm -f "$TARBALL"
    echo "[*] Encrypted: ${TARBALL}.gpg"
fi

echo
echo "[✓] Backup complete."
ls -lh "$OUT_DIR"
