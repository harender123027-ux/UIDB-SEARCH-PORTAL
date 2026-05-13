#!/usr/bin/env bash
# UBIS on-prem installer for police IT.
# Idempotent: safe to re-run.
#
# What this script does:
#   1. Verifies prerequisites (docker / podman + compose, openssl, curl).
#   2. Creates ./data subdirectories with sane permissions.
#   3. Creates a .env from .env.onprem.example if one is missing,
#      and fills it with freshly generated random secrets.
#   4. Builds the backend + frontend images.
#   5. Brings up the stack (default profile = "lite").
#   6. Waits for the backend to report healthy.
#   7. Seeds the default admin user and the Haryana district master data.
#   8. Prints the URL the operator should hand to police users.
#
# Re-running the script after a successful install will:
#   - skip secret generation (your .env is preserved)
#   - re-build images and restart containers
#   - re-run seeders (they detect existing rows and exit cleanly)

set -euo pipefail

PROFILE="${UBIS_PROFILE:-lite}"
HTTP_PORT="${UBIS_HTTP_PORT:-8080}"
COMPOSE_FILE="docker-compose.onprem.yml"

bold()  { printf "\033[1m%s\033[0m\n" "$*"; }
info()  { printf "  • %s\n" "$*"; }
warn()  { printf "  ! %s\n" "$*" >&2; }
die()   { printf "ERROR: %s\n" "$*" >&2; exit 1; }

bold "UBIS on-prem installer"
echo "Profile  : ${PROFILE}"
echo "HTTP port: ${HTTP_PORT}"
echo

# ── 1. Prerequisites ────────────────────────────────────────────────────────
bold "Step 1/7  Checking prerequisites"

# Pick docker / podman.
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    COMPOSE=(docker compose)
elif command -v podman >/dev/null 2>&1 && podman compose version >/dev/null 2>&1; then
    COMPOSE=(podman compose)
elif command -v podman-compose >/dev/null 2>&1; then
    COMPOSE=(podman-compose)
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE=(docker-compose)
else
    die "Neither 'docker compose' nor 'podman compose' is installed. Install Podman and compose (see docs/HANDOVER_GURUGRAM/01_INSTALL.md Chapter 01, section 3)."
fi
info "Using container runtime: ${COMPOSE[*]}"

for tool in openssl curl tar; do
    command -v "$tool" >/dev/null 2>&1 || die "$tool is required but not installed."
done
info "openssl, curl, tar — present."
echo

# ── 2. Data directories ─────────────────────────────────────────────────────
bold "Step 2/7  Preparing data directories"
for d in db uploads reference_photos qdrant models logs postgres; do
    mkdir -p "./data/$d"
    info "ready: ./data/$d"
done
echo

# ── 3. .env ─────────────────────────────────────────────────────────────────
bold "Step 3/7  Configuring .env"
if [[ -f .env ]]; then
    info ".env already exists — keeping it as-is."
else
    [[ -f .env.onprem.example ]] || die ".env.onprem.example is missing.  Did you unzip the package fully?"
    cp .env.onprem.example .env
    JWT_SECRET=$(openssl rand -hex 32)
    PG_PASSWORD=$(openssl rand -base64 24 | tr -d '/=+' | head -c 32)
    ADMIN_PW=$(openssl rand -base64 18 | tr -d '/=+' | head -c 20)
    # Cross-platform sed
    if sed --version >/dev/null 2>&1; then
        SED=(sed -i)
    else
        SED=(sed -i '')
    fi
    "${SED[@]}" "s|JWT_SECRET=.*|JWT_SECRET=${JWT_SECRET}|" .env
    # Append the initial admin password — seed_admin.py reads INITIAL_ADMIN_PASSWORD on first run.
    cat >>.env <<EOF

# Initial admin password — only used the very first time the database is seeded.
# Operator MUST change it immediately after first login from the UI.
INITIAL_ADMIN_PASSWORD=${ADMIN_PW}
EOF
    if [[ "$PROFILE" == "full" ]]; then
        cat >>.env <<EOF

DATABASE_URL=postgresql://ubis:${PG_PASSWORD}@postgres:5432/ubis
POSTGRES_DB=ubis
POSTGRES_USER=ubis
POSTGRES_PASSWORD=${PG_PASSWORD}
EOF
    fi
    chmod 600 .env
    info "wrote .env with freshly generated JWT_SECRET and INITIAL_ADMIN_PASSWORD (mode 600)."
fi
echo

# ── 3b. Validate required env values ────────────────────────────────────────
# shellcheck disable=SC1091
set -a; source ./.env; set +a
[[ -n "${JWT_SECRET:-}" && "$JWT_SECRET" != "REPLACE_WITH_64_HEX_CHARACTERS" ]] || \
    die "JWT_SECRET in .env is empty or still the placeholder.  Re-run installer to regenerate or run scripts/onprem/generate_secrets.sh."
if [[ "$PROFILE" == "full" ]]; then
    [[ -n "${POSTGRES_PASSWORD:-}" ]] || die "POSTGRES_PASSWORD must be set in .env for --profile full."
fi
info "Required secrets present in .env."
echo

# ── 4. Build images ─────────────────────────────────────────────────────────
bold "Step 4/7  Building container images (this can take 5–10 minutes the first time)"
"${COMPOSE[@]}" -f "$COMPOSE_FILE" --profile "$PROFILE" build
echo

# ── 5. Start stack ──────────────────────────────────────────────────────────
bold "Step 5/7  Starting containers"
"${COMPOSE[@]}" -f "$COMPOSE_FILE" --profile "$PROFILE" up -d
echo

# ── 6. Wait for health ──────────────────────────────────────────────────────
bold "Step 6/7  Waiting for the backend to become healthy"
for attempt in $(seq 1 60); do
    if curl -fsS "http://localhost:${HTTP_PORT}/api/health" >/dev/null 2>&1; then
        info "Backend is healthy."
        break
    fi
    sleep 5
    if [[ $attempt -eq 60 ]]; then
        warn "Backend did not become healthy within 5 minutes."
        warn "Check logs with: ${COMPOSE[*]} -f $COMPOSE_FILE logs backend"
        exit 2
    fi
done
echo

# ── 7. Seed admin and Haryana district master ───────────────────────────────
bold "Step 7/7  Seeding admin user and Haryana district / police-station master data"
# `podman compose exec` requires --profile so the service is in scope; `docker compose exec` accepts it without.
"${COMPOSE[@]}" -f "$COMPOSE_FILE" --profile "$PROFILE" exec -T backend python -m scripts.seed_admin || \
    warn "seed_admin reported a non-zero exit; this is harmless if the admin user already exists."

# Optional: import the full Haryana district / police-station master from Excel if it
# was bundled with the source tree.  The Excel file is large and is intentionally NOT
# part of the public repo / handover zip; if it is present, use it, otherwise stay
# silent and rely on the basic seed above.
if "${COMPOSE[@]}" -f "$COMPOSE_FILE" --profile "$PROFILE" exec -T backend test -f "/District PS master.xlsx" 2>/dev/null; then
    "${COMPOSE[@]}" -f "$COMPOSE_FILE" --profile "$PROFILE" exec -T backend python -m scripts.migrate_districts_stations 2>/dev/null || \
        warn "Could not import the full district master from Excel — basic seed will be used."
else
    info "Full district master Excel not bundled — basic 15-district seed is in use (sufficient for pilot)."
fi
echo

bold "✓ UBIS on-prem install complete."
cat <<EOF

  Open in a browser on the police LAN:
        http://$(hostname -f 2>/dev/null || hostname):${HTTP_PORT}

  Default admin login (CHANGE IT ON FIRST LOGIN):
        username : admin
        password : (see INITIAL_ADMIN_PASSWORD in .env)
                   $ grep INITIAL_ADMIN_PASSWORD .env

  Useful next steps:
        ./scripts/onprem/ubis-status.sh                     # one-shot health
        ${COMPOSE[*]} -f $COMPOSE_FILE logs -f backend       # tail backend logs
        ./scripts/onprem/ubis-backup.sh                     # take a backup

  On-prem guide: docs/HANDOVER_GURUGRAM/README.md
EOF
