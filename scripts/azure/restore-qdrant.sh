#!/bin/bash
# ============================================================================
# UBIS Qdrant Restore Script
# ============================================================================
# Restores Qdrant vector database from backup
#
# Usage:
#   ./scripts/azure/restore-qdrant.sh                    # List available backups
#   ./scripts/azure/restore-qdrant.sh 20260323_020000   # Restore specific backup
# ============================================================================

set -e

# Configuration
RESOURCE_GROUP="${RESOURCE_GROUP:-ubis-production-rg}"
STORAGE_ACCOUNT="${STORAGE_ACCOUNT:-}"
BACKUP_CONTAINER="${BACKUP_CONTAINER:-backups}"
APP_NAME="${APP_NAME:-}"

TIMESTAMP=$1
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOCAL_BACKUP_DIR="${LOCAL_BACKUP_DIR:-$PROJECT_ROOT/backups}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; exit 1; }
info() { echo -e "${BLUE}[i]${NC} $1"; }

# ─── VALIDATION ────────────────────────────────────────────────────────────────
if [ -z "$STORAGE_ACCOUNT" ]; then
    STORAGE_ACCOUNT=$(az storage account list \
        --resource-group "$RESOURCE_GROUP" \
        --query "[0].name" -o tsv 2>/dev/null || echo "")
fi

if [ -z "$STORAGE_ACCOUNT" ]; then
    error "STORAGE_ACCOUNT not set"
fi

STORAGE_KEY=$(az storage account keys list \
    --resource-group "$RESOURCE_GROUP" \
    --account-name "$STORAGE_ACCOUNT" \
    --query "[0].value" -o tsv)

# ─── LIST BACKUPS ──────────────────────────────────────────────────────────────
if [ -z "$TIMESTAMP" ]; then
    echo ""
    echo "Available Qdrant backups:"
    echo "========================="
    
    az storage blob list \
        --container-name "$BACKUP_CONTAINER" \
        --prefix "qdrant/" \
        --account-name "$STORAGE_ACCOUNT" \
        --account-key "$STORAGE_KEY" \
        --query "[].{Name:name, Size:properties.contentLength, Modified:properties.lastModified}" \
        --output table
    
    echo ""
    echo "Usage: $0 <timestamp>"
    echo "Example: $0 20260323_020000"
    exit 0
fi

# ─── CONFIRMATION ──────────────────────────────────────────────────────────────
BACKUP_FILE="qdrant_backup_$TIMESTAMP.tar.gz"
BLOB_NAME="qdrant/$BACKUP_FILE"

# Check if backup exists
if ! az storage blob exists \
    --container-name "$BACKUP_CONTAINER" \
    --name "$BLOB_NAME" \
    --account-name "$STORAGE_ACCOUNT" \
    --account-key "$STORAGE_KEY" \
    --query "exists" -o tsv | grep -q "true"; then
    error "Backup not found: $BLOB_NAME"
fi

echo ""
warn "⚠️  WARNING: This will REPLACE all current Qdrant data!"
warn "⚠️  Backup to restore: $BACKUP_FILE"
echo ""
read -p "Are you sure you want to proceed? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

# ─── STOP APP SERVICE ──────────────────────────────────────────────────────────
if [ -z "$APP_NAME" ]; then
    APP_NAME=$(az webapp list \
        --resource-group "$RESOURCE_GROUP" \
        --query "[0].name" -o tsv 2>/dev/null || echo "")
fi

if [ -n "$APP_NAME" ]; then
    log "Stopping App Service: $APP_NAME"
    az webapp stop --resource-group "$RESOURCE_GROUP" --name "$APP_NAME" --output none
fi

# ─── DOWNLOAD BACKUP ───────────────────────────────────────────────────────────
mkdir -p "$LOCAL_BACKUP_DIR"
log "Downloading backup: $BACKUP_FILE"

az storage blob download \
    --container-name "$BACKUP_CONTAINER" \
    --name "$BLOB_NAME" \
    --file "$LOCAL_BACKUP_DIR/$BACKUP_FILE" \
    --account-name "$STORAGE_ACCOUNT" \
    --account-key "$STORAGE_KEY" \
    --output none

# ─── CLEAR EXISTING DATA ───────────────────────────────────────────────────────
log "Clearing existing Qdrant data..."

# Delete all files in the file share
az storage file delete-batch \
    --source "qdrant-data" \
    --account-name "$STORAGE_ACCOUNT" \
    --account-key "$STORAGE_KEY" \
    --output none 2>/dev/null || true

# ─── RESTORE DATA ──────────────────────────────────────────────────────────────
log "Extracting backup..."
mkdir -p "$LOCAL_BACKUP_DIR/qdrant_restore"
tar -xzf "$LOCAL_BACKUP_DIR/$BACKUP_FILE" -C "$LOCAL_BACKUP_DIR/qdrant_restore"

log "Uploading to Azure File Share..."
az storage file upload-batch \
    --destination "qdrant-data" \
    --source "$LOCAL_BACKUP_DIR/qdrant_restore" \
    --account-name "$STORAGE_ACCOUNT" \
    --account-key "$STORAGE_KEY" \
    --output none

# Cleanup temp files
rm -rf "$LOCAL_BACKUP_DIR/qdrant_restore"

# ─── START APP SERVICE ─────────────────────────────────────────────────────────
if [ -n "$APP_NAME" ]; then
    log "Starting App Service: $APP_NAME"
    az webapp start --resource-group "$RESOURCE_GROUP" --name "$APP_NAME" --output none
fi

# ─── DONE ──────────────────────────────────────────────────────────────────────
echo ""
log "Restore complete!"
log "Qdrant data restored from: $BACKUP_FILE"

if [ -n "$APP_NAME" ]; then
    info "App Service is restarting. Check health at:"
    info "https://$APP_NAME.azurewebsites.net/api/health"
fi
echo ""
