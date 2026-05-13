#!/bin/bash
# ============================================================================
# UBIS Azure Production Deployment Script
# ============================================================================
# This script sets up:
#   1. Azure Resource Group
#   2. Azure Container Registry (ACR)
#   3. Azure Database for PostgreSQL
#   4. Azure Storage Account (Blob Storage)
#   5. Azure File Share (for Qdrant persistence)
#   6. Azure App Service (Container)
#
# Prerequisites:
#   - Azure CLI installed: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli
#   - Docker installed
#   - Logged in to Azure: az login
#
# Usage:
#   chmod +x scripts/azure/deploy.sh
#   ./scripts/azure/deploy.sh
# ============================================================================

set -e

# ─── CONFIGURATION ─────────────────────────────────────────────────────────────
# Edit these values for your deployment
RESOURCE_GROUP="${RESOURCE_GROUP:-ubis-production-rg}"
LOCATION="${LOCATION:-eastus}"
ACR_NAME="${ACR_NAME:-ubisacr$(openssl rand -hex 4)}"  # Must be globally unique
POSTGRES_SERVER_NAME="${POSTGRES_SERVER_NAME:-ubis-postgres-$(openssl rand -hex 4)}"
STORAGE_ACCOUNT_NAME="${STORAGE_ACCOUNT_NAME:-ubisstorage$(openssl rand -hex 4)}"
APP_SERVICE_PLAN="${APP_SERVICE_PLAN:-ubis-app-plan}"
APP_NAME="${APP_NAME:-ubis-backend-$(openssl rand -hex 4)}"

# Database credentials
POSTGRES_ADMIN_USER="${POSTGRES_ADMIN_USER:-ubisadmin}"
POSTGRES_ADMIN_PASSWORD="${POSTGRES_ADMIN_PASSWORD:-$(openssl rand -base64 24)}"
POSTGRES_DB_NAME="ubis"

# JWT Secret
JWT_SECRET="${JWT_SECRET:-$(openssl rand -hex 32)}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; exit 1; }
info() { echo -e "${BLUE}[i]${NC} $1"; }

# ─── PRE-FLIGHT CHECKS ─────────────────────────────────────────────────────────
echo ""
echo "=============================================="
echo "  UBIS Azure Production Deployment"
echo "=============================================="
echo ""

# Check Azure CLI
if ! command -v az &> /dev/null; then
    error "Azure CLI not installed. Install from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
fi

# Check Docker
if ! command -v docker &> /dev/null; then
    error "Docker not installed."
fi

# Check Azure login
if ! az account show &> /dev/null; then
    warn "Not logged in to Azure. Running 'az login'..."
    az login
fi

SUBSCRIPTION=$(az account show --query name -o tsv)
info "Using Azure subscription: $SUBSCRIPTION"

# ─── STEP 1: CREATE RESOURCE GROUP ─────────────────────────────────────────────
echo ""
log "Step 1: Creating Resource Group..."
az group create \
    --name "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --output none
log "Resource Group '$RESOURCE_GROUP' created in '$LOCATION'"

# ─── STEP 2: CREATE AZURE CONTAINER REGISTRY ───────────────────────────────────
echo ""
log "Step 2: Creating Azure Container Registry..."
az acr create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$ACR_NAME" \
    --sku Basic \
    --admin-enabled true \
    --output none
log "Container Registry '$ACR_NAME' created"

# Get ACR credentials
ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)
ACR_USERNAME=$(az acr credential show --name "$ACR_NAME" --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv)

# ─── STEP 3: CREATE AZURE DATABASE FOR POSTGRESQL ──────────────────────────────
echo ""
log "Step 3: Creating Azure Database for PostgreSQL (Flexible Server)..."
az postgres flexible-server create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$POSTGRES_SERVER_NAME" \
    --location "$LOCATION" \
    --admin-user "$POSTGRES_ADMIN_USER" \
    --admin-password "$POSTGRES_ADMIN_PASSWORD" \
    --sku-name Standard_B1ms \
    --tier Burstable \
    --storage-size 32 \
    --version 15 \
    --public-access 0.0.0.0 \
    --output none
log "PostgreSQL Server '$POSTGRES_SERVER_NAME' created"

# Create database
az postgres flexible-server db create \
    --resource-group "$RESOURCE_GROUP" \
    --server-name "$POSTGRES_SERVER_NAME" \
    --database-name "$POSTGRES_DB_NAME" \
    --output none
log "Database '$POSTGRES_DB_NAME' created"

POSTGRES_HOST="${POSTGRES_SERVER_NAME}.postgres.database.azure.com"
DATABASE_URL="postgresql://${POSTGRES_ADMIN_USER}:${POSTGRES_ADMIN_PASSWORD}@${POSTGRES_HOST}:5432/${POSTGRES_DB_NAME}?sslmode=require"

# ─── STEP 4: CREATE AZURE STORAGE ACCOUNT ──────────────────────────────────────
echo ""
log "Step 4: Creating Azure Storage Account..."
az storage account create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$STORAGE_ACCOUNT_NAME" \
    --location "$LOCATION" \
    --sku Standard_LRS \
    --kind StorageV2 \
    --output none
log "Storage Account '$STORAGE_ACCOUNT_NAME' created"

# Get storage connection string
STORAGE_CONNECTION_STRING=$(az storage account show-connection-string \
    --resource-group "$RESOURCE_GROUP" \
    --name "$STORAGE_ACCOUNT_NAME" \
    --query connectionString -o tsv)

STORAGE_KEY=$(az storage account keys list \
    --resource-group "$RESOURCE_GROUP" \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --query "[0].value" -o tsv)

# Create blob containers
az storage container create \
    --name "uploads" \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --account-key "$STORAGE_KEY" \
    --output none
az storage container create \
    --name "references" \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --account-key "$STORAGE_KEY" \
    --output none
log "Blob containers 'uploads' and 'references' created"

# Create file share for Qdrant persistence
az storage share create \
    --name "qdrant-data" \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --account-key "$STORAGE_KEY" \
    --quota 10 \
    --output none
log "File share 'qdrant-data' created for Qdrant persistence"

# ─── STEP 5: BUILD AND PUSH DOCKER IMAGE ───────────────────────────────────────
echo ""
log "Step 5: Building and pushing Docker image..."

# Login to ACR
az acr login --name "$ACR_NAME"

# Build and push
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

docker build \
    -t "$ACR_LOGIN_SERVER/ubis-backend:latest" \
    -f "$PROJECT_ROOT/backend/Dockerfile" \
    "$PROJECT_ROOT/backend"

docker push "$ACR_LOGIN_SERVER/ubis-backend:latest"
log "Docker image pushed to $ACR_LOGIN_SERVER/ubis-backend:latest"

# ─── STEP 6: CREATE APP SERVICE ────────────────────────────────────────────────
echo ""
log "Step 6: Creating App Service..."

# Create App Service Plan
az appservice plan create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_SERVICE_PLAN" \
    --is-linux \
    --sku P1V2 \
    --output none
log "App Service Plan '$APP_SERVICE_PLAN' created"

# Create Web App
az webapp create \
    --resource-group "$RESOURCE_GROUP" \
    --plan "$APP_SERVICE_PLAN" \
    --name "$APP_NAME" \
    --deployment-container-image-name "$ACR_LOGIN_SERVER/ubis-backend:latest" \
    --output none
log "Web App '$APP_NAME' created"

# Configure container settings
az webapp config container set \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_NAME" \
    --docker-custom-image-name "$ACR_LOGIN_SERVER/ubis-backend:latest" \
    --docker-registry-server-url "https://$ACR_LOGIN_SERVER" \
    --docker-registry-server-user "$ACR_USERNAME" \
    --docker-registry-server-password "$ACR_PASSWORD" \
    --output none

# Mount Azure File Share for Qdrant persistence
az webapp config storage-account add \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_NAME" \
    --custom-id "qdrant-storage" \
    --storage-type AzureFiles \
    --share-name "qdrant-data" \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --access-key "$STORAGE_KEY" \
    --mount-path "/app/qdrant_storage" \
    --output none
log "Azure File Share mounted at /app/qdrant_storage"

# ─── STEP 7: CONFIGURE APP SETTINGS ────────────────────────────────────────────
echo ""
log "Step 7: Configuring App Settings..."

az webapp config appsettings set \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_NAME" \
    --settings \
        ENVIRONMENT="production" \
        PORT="8000" \
        WEBSITES_PORT="8000" \
        DATABASE_URL="$DATABASE_URL" \
        POSTGRES_HOST="$POSTGRES_HOST" \
        POSTGRES_PORT="5432" \
        POSTGRES_DB="$POSTGRES_DB_NAME" \
        POSTGRES_USER="$POSTGRES_ADMIN_USER" \
        POSTGRES_PASSWORD="$POSTGRES_ADMIN_PASSWORD" \
        AZURE_STORAGE_CONNECTION_STRING="$STORAGE_CONNECTION_STRING" \
        AZURE_STORAGE_CONTAINER_UPLOADS="uploads" \
        AZURE_STORAGE_CONTAINER_REFERENCES="references" \
        QDRANT_URL="/app/qdrant_storage" \
        QDRANT_COLLECTION="face_embeddings" \
        JWT_SECRET="$JWT_SECRET" \
        JWT_EXPIRE_MINUTES="1440" \
        CORS_ORIGINS="*" \
    --output none
log "App Settings configured"

# ─── STEP 8: ENABLE LOGGING ────────────────────────────────────────────────────
echo ""
log "Step 8: Enabling logging..."

az webapp log config \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_NAME" \
    --docker-container-logging filesystem \
    --output none
log "Container logging enabled"

# ─── SUMMARY ───────────────────────────────────────────────────────────────────
APP_URL="https://${APP_NAME}.azurewebsites.net"

echo ""
echo "=============================================="
echo "  DEPLOYMENT COMPLETE!"
echo "=============================================="
echo ""
echo "Resources Created:"
echo "  - Resource Group:    $RESOURCE_GROUP"
echo "  - Container Registry: $ACR_NAME ($ACR_LOGIN_SERVER)"
echo "  - PostgreSQL Server: $POSTGRES_SERVER_NAME"
echo "  - Storage Account:   $STORAGE_ACCOUNT_NAME"
echo "  - App Service:       $APP_NAME"
echo ""
echo "Application URL: $APP_URL"
echo "Health Check:    $APP_URL/api/health"
echo ""
echo "=============================================="
echo "  SAVE THESE CREDENTIALS SECURELY!"
echo "=============================================="
echo ""
echo "PostgreSQL:"
echo "  Host:     $POSTGRES_HOST"
echo "  Database: $POSTGRES_DB_NAME"
echo "  Username: $POSTGRES_ADMIN_USER"
echo "  Password: $POSTGRES_ADMIN_PASSWORD"
echo ""
echo "JWT Secret: $JWT_SECRET"
echo ""
echo "ACR Credentials:"
echo "  Server:   $ACR_LOGIN_SERVER"
echo "  Username: $ACR_USERNAME"
echo "  Password: $ACR_PASSWORD"
echo ""

# Save credentials to file
CREDS_FILE="$PROJECT_ROOT/.azure-credentials-$(date +%Y%m%d-%H%M%S).txt"
cat > "$CREDS_FILE" << EOF
# UBIS Azure Deployment Credentials
# Generated: $(date)
# KEEP THIS FILE SECURE!

RESOURCE_GROUP=$RESOURCE_GROUP
LOCATION=$LOCATION

# Container Registry
ACR_NAME=$ACR_NAME
ACR_LOGIN_SERVER=$ACR_LOGIN_SERVER
ACR_USERNAME=$ACR_USERNAME
ACR_PASSWORD=$ACR_PASSWORD

# PostgreSQL
POSTGRES_SERVER_NAME=$POSTGRES_SERVER_NAME
POSTGRES_HOST=$POSTGRES_HOST
POSTGRES_DB=$POSTGRES_DB_NAME
POSTGRES_USER=$POSTGRES_ADMIN_USER
POSTGRES_PASSWORD=$POSTGRES_ADMIN_PASSWORD
DATABASE_URL=$DATABASE_URL

# Storage
STORAGE_ACCOUNT_NAME=$STORAGE_ACCOUNT_NAME
AZURE_STORAGE_CONNECTION_STRING=$STORAGE_CONNECTION_STRING

# App Service
APP_SERVICE_PLAN=$APP_SERVICE_PLAN
APP_NAME=$APP_NAME
APP_URL=$APP_URL

# Auth
JWT_SECRET=$JWT_SECRET
EOF

chmod 600 "$CREDS_FILE"
warn "Credentials saved to: $CREDS_FILE"
warn "Add this file to .gitignore and store securely!"

echo ""
log "Deployment complete! Your app should be available at: $APP_URL"
log "Note: Initial startup may take 2-3 minutes for model loading."
echo ""
