#!/usr/bin/env bash
# Build the single sealed handover archive that goes to Gurugram Police IT.
#
# Output: dist/UBIS_Gurugram_Handover.zip
#
# Contents:
#   - Cleaned source tree (no .venv, .git, node_modules, models, uploaded data, *.db).
#   - docker-compose.onprem.yml + .env.onprem.example
#   - scripts/onprem/* (install, backup, restore, status, generate_secrets)
#   - docs/HANDOVER_GURUGRAM/* (the IT-facing handbook)
#   - docs/UBIS_Handover_Package.docx (Volume 1, executive / UAT)
#   - docs/UBIS_Gurugram_Handover_Package.docx (Volume 2, IT + training)
#   - sample_import_images/ + ui_body_template.xlsx + ui_body_template.csv
#   - INSTALL.txt — the 5-line quickstart at the root of the zip.

set -euo pipefail

DIST="dist"
ZIP="${DIST}/UBIS_Gurugram_Handover.zip"
mkdir -p "$DIST"

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
ROOT="$WORK/UBIS_Gurugram_Handover"
mkdir -p "$ROOT"

echo "[*] Staging clean source tree"
rsync -a \
    --exclude='.git/' \
    --exclude='.venv/' \
    --exclude='test_venv/' \
    --exclude='node_modules/' \
    --exclude='dist/' \
    --exclude='backups/' \
    --exclude='data/' \
    --exclude='backend/.venv/' \
    --exclude='backend/qdrant_data/' \
    --exclude='backend/qdrant_storage/' \
    --exclude='backend/uploads/' \
    --exclude='backend/reference_photos/' \
    --exclude='backend/models/' \
    --exclude='backend/ubis.db' \
    --exclude='backend/ubis.db.backup' \
    --exclude='.pytest_cache/' \
    --exclude='*.pyc' \
    --exclude='__pycache__/' \
    --exclude='playwright-report/' \
    --exclude='test-results/' \
    --exclude='.DS_Store' \
    --exclude='~$*' \
    --exclude='.env' \
    --exclude='.env.production' \
    --exclude='.env.local' \
    --exclude='aa.pdf' \
    --exclude='District PS master.xlsx' \
    --exclude='UBIS_Handover_Package.doc' \
    --exclude='~$IS_Handover_Package.docx' \
    --exclude='*.tar.gz' \
    --exclude='ubis-pwa.html' \
    --exclude='ubis-pwa-original.jsx' \
    --exclude='.cursor*/' \
    --exclude='.claude*/' \
    ./ "$ROOT/"

cat >"$ROOT/INSTALL.txt" <<'EOF'
UBIS — Quick install
====================

You will need:
  - one Linux server (Ubuntu 22.04 LTS recommended; RHEL/Rocky 9 also OK)
  - 4+ vCPU, 8+ GB RAM, 100+ GB SSD (see 01_INSTALL.md Chapter 01 for sizing)
  - root / sudo access on the server
  - the file UBIS_Gurugram_Handover.zip you just received

Run these commands on the server, in order:

  1. Copy the zip to the server, then unzip it:
        cd /opt && sudo mkdir -p ubis && sudo chown "$USER":"$USER" ubis && cd ubis
        unzip /path/to/UBIS_Gurugram_Handover.zip
        cd UBIS_Gurugram_Handover

  2. Install Docker Engine + docker-compose-plugin (or Podman 4.4+ with
     podman-compose). The full apt / dnf commands are spelled out in
     docs/HANDOVER_GURUGRAM/01_INSTALL.md (Chapter 01, sections 3 and 4).
     **On-prem install (one page):** docs/HANDOVER_GURUGRAM/README.md
     If you use Docker (not Podman), add yourself to the docker group:
        sudo usermod -aG docker "$USER" && newgrp docker

  3. Run the installer (idempotent — safe to re-run):
        bash scripts/onprem/install.sh

     The first run takes 5-10 minutes to build the container images.
     The installer generates a strong random JWT_SECRET and a strong random
     INITIAL_ADMIN_PASSWORD, writes both to .env at mode 600, seeds the
     database, and starts the stack.

  4. Confirm everything is healthy:
        bash scripts/onprem/ubis-status.sh
     You should see ubis-backend "Up ... (healthy)" and ubis-frontend "Up ...",
     and a backend-health line of {"status":"ok"}.

  5. From a workstation on the police LAN, open the URL:
        http://<server-hostname>:8080
     Log in as user "admin". The password is the value of
     INITIAL_ADMIN_PASSWORD in the .env file the installer just wrote:
        grep INITIAL_ADMIN_PASSWORD .env
     Change the admin password from the UI immediately (see 02_OPERATIONS.md
     Chapter 06, Security hardening).

  6. Schedule a nightly backup and complete the security hardening checklist
     in 02_OPERATIONS.md BEFORE letting officers use the system.

If anything goes wrong, open docs/HANDOVER_GURUGRAM/04_TRAINING_AND_SUPPORT.md
(Chapter 14, Troubleshooting & FAQ) first.

The handbook lives under docs/HANDOVER_GURUGRAM/:

  README.md                   — start here (on-prem install, one page)
  01_INSTALL.md               — long-form prerequisites, secrets, first-boot checklist
  02_OPERATIONS.md            — runbook, backup & restore, security hardening
  03_USER_GUIDES.md           — per-role guides + bulk-import SOP
  04_TRAINING_AND_SUPPORT.md  — half-day training, FAQ, support & escalation
  05_ACCEPTANCE.md            — sign-off forms + pre-handover verification
EOF

echo "[*] Creating $ZIP"
rm -f "$ZIP"
( cd "$WORK" && zip -qr "$OLDPWD/$ZIP" "UBIS_Gurugram_Handover" )
ls -lh "$ZIP"
echo "[✓] Handover archive ready: $ZIP"
