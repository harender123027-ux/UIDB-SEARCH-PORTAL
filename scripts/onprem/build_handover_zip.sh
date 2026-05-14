#!/usr/bin/env bash
# Build the single sealed handover archive that goes to Gurugram Police IT.
#
# Output: dist/UBIS_Gurugram_Handover.zip
#
# Contents:
#   - Cleaned source tree (no .venv, .git, node_modules, uploaded data, *.db).
#   - docker-compose.onprem.yml + .env.onprem.example
#   - scripts/onprem/* (install, backup, restore, status, generate_secrets)
#   - docs/HANDOVER_GURUGRAM/* (the IT-facing handbook)
#   - docs/UBIS_Handover_Package.docx (Volume 1, executive / UAT)
#   - docs/UBIS_Gurugram_Handover_Package.docx (Volume 2, IT + training)
#   - data/models/buffalo_l/*.onnx — InsightFace pack (~329 MB), pre-staged for the
#     /app/models bind-mount so the first install has zero model-download steps.
#   - sample_import_images/ + ui_body_template.xlsx + ui_body_template.csv
#   - INSTALL.txt — the 5-line quickstart at the root of the zip.
#
# Everything else under data/ (DB, uploads, qdrant store, logs, postgres) is left
# out so the operator's machine starts with a clean slate.

set -euo pipefail

DIST="dist"
ZIP="${DIST}/UBIS_Gurugram_Handover.zip"
mkdir -p "$DIST"

# Verify the InsightFace model pack is staged at data/models/buffalo_l/.
# These are the two files the on-prem backend actually loads at runtime.
REQUIRED_MODELS=(
    "data/models/buffalo_l/det_10g.onnx"
    "data/models/buffalo_l/w600k_r50.onnx"
)
MISSING_MODELS=0
for f in "${REQUIRED_MODELS[@]}"; do
    if [[ ! -f "$f" ]]; then
        echo "[!] Missing required model file: $f" >&2
        MISSING_MODELS=1
    fi
done
if [[ $MISSING_MODELS -ne 0 ]]; then
    cat >&2 <<'EOF'
[!] The InsightFace buffalo_l pack is not present under data/models/buffalo_l/.
[!] The handover ZIP would ship without face recognition models and the install
[!] would have no way to match faces. Place the pack at data/models/buffalo_l/
[!] (at minimum det_10g.onnx and w600k_r50.onnx) and re-run.
EOF
    exit 1
fi

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
    --exclude='data/db/' \
    --exclude='data/uploads/' \
    --exclude='data/reference_photos/' \
    --exclude='data/qdrant/' \
    --exclude='data/postgres/' \
    --exclude='data/logs/' \
    --exclude='data/models/buffalo_l.zip' \
    --exclude='data/models/buffalo_l.tar.gz' \
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

# Make sure the bind-mount target directories that install.sh expects all exist
# inside the archive, so the operator does not have to mkdir them manually.
mkdir -p \
    "$ROOT/data/db" \
    "$ROOT/data/uploads" \
    "$ROOT/data/reference_photos" \
    "$ROOT/data/qdrant" \
    "$ROOT/data/postgres" \
    "$ROOT/data/logs"
# Keep these directories present in the zip even though they are empty.
for d in db uploads reference_photos qdrant postgres logs; do
    touch "$ROOT/data/$d/.gitkeep"
done

echo "[*] Staged InsightFace pack: $(du -sh "$ROOT/data/models/buffalo_l" | cut -f1)"

cat >"$ROOT/INSTALL.txt" <<'EOF'
UBIS — Quick install
====================

You will need:
  - one Linux server (Ubuntu 22.04 LTS recommended; RHEL/Rocky 9 also OK)
  - 4+ vCPU, 8+ GB RAM, 100+ GB SSD (see 01_INSTALL.md Chapter 01 for sizing)
  - root / sudo access on the server
  - the file UBIS_Gurugram_Handover.zip you just received

The zip is self-contained: the InsightFace face-recognition model pack
(~330 MB) is already inside, under data/models/buffalo_l/. The on-prem
backend mounts that directory as /app/models, so there is NO model download
step during install.

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
     database, and starts the stack. The bundled face-recognition models are
     picked up automatically from data/models/buffalo_l/.

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

Bulk import:
  - Sample CSV with 5 worked examples : ui_body_template.csv (zip root)
  - Excel template with dropdowns      : ui_body_template.xlsx (zip root)
  - Step-by-step guide                 : docs/BULK_IMPORT_GUIDE.md
  - 10k-50k record runs                : docs/BULK_IMPORT_AT_SCALE.md
  - One-page cheat-sheet               : docs/BULK_IMPORT_QUICK_REFERENCE.md

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
