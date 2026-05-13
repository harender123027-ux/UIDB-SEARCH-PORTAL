# Dockerfile for Azure App Service - Production Ready
# Optimized for Azure PostgreSQL + Azure Blob Storage + Local Qdrant

# --- Build Stage ---
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies and clean up in one layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    libgl1 \
    libglib2.0-0 \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Build wheels for faster installation
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# Create models directory (to be used as mount point)
RUN mkdir -p /models

# --- Production Stage ---
FROM python:3.11-slim

LABEL maintainer="UBIS Team" \
      version="1.0" \
      description="UBIS Face Recognition Backend - Production"

WORKDIR /app

# Install runtime dependencies and clean up in one layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages from pre-built wheels
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

# Models will be mounted at /app/models from Azure Blob Storage
RUN mkdir -p /app/models

# Create non-root user and necessary directories in one layer
RUN groupadd --gid 1000 appgroup \
    && useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser \
    && mkdir -p /app/qdrant_storage /app/data /app/logs \
    && chown -R appuser:appgroup /app

# Copy only necessary application code (excluding tests, uploads, etc.)
COPY --chown=appuser:appgroup app/ ./app
COPY --chown=appuser:appgroup qdrant_data/ ./qdrant_data
COPY --chown=appuser:appgroup reference_photos/ ./reference_photos
COPY --chown=appuser:appgroup scripts/ ./scripts
COPY --chown=appuser:appgroup requirements.txt .

# Switch to non-root user
USER appuser

# Environment defaults (override in Azure App Service Configuration)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production \
    PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/health || exit 1

EXPOSE ${PORT}

# Use exec form for proper signal handling
CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "2", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--keep-alive", "5", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--capture-output", \
     "--enable-stdio-inheritance"]
