#!/bin/bash
# ============================================================================
# UBIS Qdrant Backup Script
# ============================================================================
# Backs up Qdrant vector database from Azure File Share
#
# Usage:
#   ./scripts/azure/backup-qdrant.sh
#
# Cron (daily at 2 AM):
#   0 2 * * * /path/to/scripts/azure/backup-qdrant.sh >> /var/log/ubis-backup.log 2>&1
# ============================================================================

set -e

# Configuration
RESOURCE_GROUP="${RESOURCE_GROUP:-ubis-production-rg}"
STORAGE_ACCOUNT="${STORAGE_ACCOUNT:-}"
BACKUP_CONTAINER="${BACKUP_CONTAINER:-backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOCAL_BACKUP_DIR="${LOCAL_BACKUP_DIR:-$PROJECT_ROOT/backups}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"; }
error() { echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"; exit 1; }

# ─── VALIDATION ────────────────────────────────────────────────────────────────
if [ -z "$STORAGE_ACCOUNT" ]; then
    # Try to get from Azure
    STORAGE_ACCOUNT=$(az storage account list \
        --resource-group "$RESOURCE_GROUP" \
        --query "[0].name" -o tsv 2>/dev/null || echo "")
fi

if [ -z "$STORAGE_ACCOUNT" ]; then
    error "STORAGE_ACCOUNT not set. Set it via environment variable or ensure Azure CLI is configured."
fi

log "Starting Qdrant backup..."
log "Storage Account: $STORAGE_ACCOUNT"

# Get storage key
STORAGE_KEY=$(az storage account keys list \
    --resource-group "$RESOURCE_GROUP" \
    --account-name "$STORAGE_ACCOUNT" \
    --query "[0].value" -o tsv)

if [ -z "$STORAGE_KEY" ]; then
    error "Failed to get storage account key"
fi

# ─── CREATE BACKUP CONTAINER ───────────────────────────────────────────────────
az storage container create \
    --name "$BACKUP_CONTAINER" \
    --account-name "$STORAGE_ACCOUNT" \
    --account-key "$STORAGE_KEY" \
    --output none 2>/dev/null || true

# ─── CREATE LOCAL BACKUP ───────────────────────────────────────────────────────
mkdir -p "$LOCAL_BACKUP_DIR"
BACKUP_FILE="qdrant_backup_$TIMESTAMP.tar.gz"

log "Downloading Qdrant data from Azure File Share..."

# Download from file share
az storage file download-batch \
    --destination "$LOCAL_BACKUP_DIR/qdrant_temp" \
    --source "qdrant-data" \
    --account-name "$STORAGE_ACCOUNT" \
    --account-key "$STORAGE_KEY" \
    --output none

# Compress
log "Compressing backup..."
tar -czf "$LOCAL_BACKUP_DIR/$BACKUP_FILE" -C "$LOCAL_BACKUP_DIR/qdrant_temp" .
rm -rf "$LOCAL_BACKUP_DIR/qdrant_temp"

log "Local backup created: $LOCAL_BACKUP_DIR/$BACKUP_FILE"

# ─── UPLOAD TO BLOB STORAGE ────────────────────────────────────────────────────
log "Uploading backup to Azure Blob Storage..."

az storage blob upload \
    --container-name "$BACKUP_CONTAINER" \
    --file "$LOCAL_BACKUP_DIR/$BACKUP_FILE" \
    --name "qdrant/$BACKUP_FILE" \
    --account-name "$STORAGE_ACCOUNT" \
    --account-key "$STORAGE_KEY" \
    --output none

log "Backup uploaded to: $STORAGE_ACCOUNT/$BACKUP_CONTAINER/qdrant/$BACKUP_FILE"

# ─── CLEANUP OLD BACKUPS ───────────────────────────────────────────────────────
log "Cleaning up backups older than $RETENTION_DAYS days..."

# Local cleanup
find "$LOCAL_BACKUP_DIR" -name "qdrant_backup_*.tar.gz" -mtime +$RETENTION_DAYS -delete 2>/dev/null || true

# Azure cleanup (list old blobs and delete)
CUTOFF_DATE=$(date -v-${RETENTION_DAYS}d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -d "$RETENTION_DAYS days ago" +%Y-%m-%dT%H:%M:%SZ)

OLD_BLOBS=$(az storage blob list \
    --container-name "$BACKUP_CONTAINER" \
    --prefix "qdrant/" \
    --account-name "$STORAGE_ACCOUNT" \
    --account-key "$STORAGE_KEY" \
    --query "[?properties.lastModified<'$CUTOFF_DATE'].name" -o tsv 2>/dev/null || echo "")

for blob in $OLD_BLOBS; do
    az storage blob delete \
        --container-name "$BACKUP_CONTAINER" \
        --name "$blob" \
        --account-name "$STORAGE_ACCOUNT" \
        --account-key "$STORAGE_KEY" \
        --output none 2>/dev/null || true
    log "Deleted old backup: $blob"
done

# ─── SUMMARY ───────────────────────────────────────────────────────────────────
BACKUP_SIZE=$(ls -lh "$LOCAL_BACKUP_DIR/$BACKUP_FILE" | awk '{print $5}')
log "Backup complete!"
log "  File: $BACKUP_FILE"
log "  Size: $BACKUP_SIZE"
log "  Location: Azure Blob ($STORAGE_ACCOUNT/$BACKUP_CONTAINER/qdrant/)"

echo ""
