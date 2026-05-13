#!/usr/bin/env bash
# Generate strong random secrets for an on-prem UBIS install.
#
# We deliberately do NOT write to .env automatically.
# The operator copies the values into .env by hand, so the secrets stay under
# their control and are never echoed into shell history or log files.
#
# Usage:
#   bash scripts/onprem/generate_secrets.sh

set -euo pipefail

if ! command -v openssl >/dev/null 2>&1; then
    echo "ERROR: openssl is required.  Install with:  sudo apt-get install -y openssl" >&2
    exit 1
fi

cat <<EOF
# ──────────────────────────────────────────────────────────────────────────
# UBIS — generated secrets ($(date -u +'%Y-%m-%dT%H:%M:%SZ'))
# Copy the lines below into your .env file, replacing the placeholders.
# These values are NOT stored anywhere by this script.
# ──────────────────────────────────────────────────────────────────────────

JWT_SECRET=$(openssl rand -hex 32)

# Use only when running with --profile full (PostgreSQL)
POSTGRES_PASSWORD=$(openssl rand -base64 24 | tr -d '/=+' | head -c 32)

# A first-time admin password.  After first login, force change in the UI.
# This is shown ONCE.  Save it in your password manager and clear your screen.
INITIAL_ADMIN_PASSWORD=$(openssl rand -base64 18 | tr -d '/=+' | head -c 18)

EOF
