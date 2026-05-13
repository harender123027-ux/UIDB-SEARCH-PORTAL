import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ─── BASE PATHS ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# ─── ENVIRONMENT ───────────────────────────────────────────────────────────────
# "development" (local SQLite, local files) or "production" (Azure PostgreSQL, Blob, Qdrant Cloud)
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
IS_PRODUCTION = ENVIRONMENT == "production"

# ─── DATABASE ──────────────────────────────────────────────────────────────────
# SQLite (development) or PostgreSQL (production)
SQLITE_PATH = os.getenv("SQLITE_PATH", str(BASE_DIR / "ubis.db"))

# PostgreSQL connection (production)
DATABASE_URL = os.getenv("DATABASE_URL", "")  # e.g., postgresql://user:pass@host:5432/dbname
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "ubis")
POSTGRES_USER = os.getenv("POSTGRES_USER", "")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

# ─── FILE STORAGE ──────────────────────────────────────────────────────────────
# Local paths (development) or Azure Blob Storage (production)
SUBMISSIONS_STORAGE_PATH = Path(os.getenv("SUBMISSIONS_STORAGE_PATH", str(BASE_DIR / "uploads")))
REFERENCE_PHOTOS_PATH = Path(os.getenv("REFERENCE_PHOTOS_PATH", str(BASE_DIR / "reference_photos")))

# Azure Blob Storage (production)
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
AZURE_STORAGE_CONTAINER_UPLOADS = os.getenv("AZURE_STORAGE_CONTAINER_UPLOADS", "uploads")
AZURE_STORAGE_CONTAINER_REFERENCES = os.getenv("AZURE_STORAGE_CONTAINER_REFERENCES", "references")
AZURE_STORAGE_ACCOUNT_URL = os.getenv("AZURE_STORAGE_ACCOUNT_URL", "")  # e.g., https://account.blob.core.windows.net

# Use Azure Blob if connection string is provided
USE_AZURE_BLOB = bool(AZURE_STORAGE_CONNECTION_STRING)

# ─── QDRANT (VECTOR DATABASE) ──────────────────────────────────────────────────
# Options:
#   - Local path (e.g., "qdrant_data/") → persistent local storage (development)
#   - ":memory:" → in-memory only (testing, NOT for production)
#   - "http://localhost:6333" → local Docker Qdrant
#   - "https://your-cluster.qdrant.io" → Qdrant Cloud (production)
QDRANT_DATA_PATH = BASE_DIR / "qdrant_data"
QDRANT_URL = os.getenv("QDRANT_URL", str(QDRANT_DATA_PATH))
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")  # Required for Qdrant Cloud
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "face_embeddings")

# ─── JWT AUTHENTICATION ────────────────────────────────────────────────────────
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))  # 24h default

# ─── AI MODEL SETTINGS ─────────────────────────────────────────────────────────
EMBEDDING_DIM = 512  # Both InsightFace and AdaFace ir_101 use 512 dimensions
ADAFACE_MODEL_PATH = os.getenv("ADAFACE_MODEL_PATH", "models/adaface_ir101.ckpt")
ADAFACE_GDRIVE_ID = "1m757p4-tUU5xlSHLaO04sqnhvqankimN"
FACE_DETECTION_THRESHOLD = float(os.getenv("FACE_DETECTION_THRESHOLD", "0.3"))
FACE_MATCH_THRESHOLD_STRONG = float(os.getenv("FACE_MATCH_THRESHOLD_STRONG", "0.45"))
FACE_MATCH_THRESHOLD_MEDIUM = float(os.getenv("FACE_MATCH_THRESHOLD_MEDIUM", "0.35"))

# Skip weak query views: do not search from submission vectors below this detection confidence (UI bodies).
# Set to 0 to disable. Missing embedding_confidence on the stored payload does not skip.
FACE_QUERY_MIN_EMBEDDING_CONFIDENCE = float(os.getenv("FACE_QUERY_MIN_EMBEDDING_CONFIDENCE", "0.22"))

# Per additional supporting Qdrant hit (same ref id, another angle), multiply best score by (1 + boost * (n-1)), capped at 1.0.
FACE_MULTIVIEW_SCORE_BOOST = float(os.getenv("FACE_MULTIVIEW_SCORE_BOOST", "0.07"))

# Embed at most this many detected faces per image, highest det_score first.
FACE_EMBEDDINGS_PER_IMAGE_MAX = int(os.getenv("FACE_EMBEDDINGS_PER_IMAGE_MAX", "3"))

# ─── ENSURE LOCAL DIRECTORIES EXIST (development only) ─────────────────────────
if not USE_AZURE_BLOB:
    SUBMISSIONS_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
    REFERENCE_PHOTOS_PATH.mkdir(parents=True, exist_ok=True)

# Persistent Qdrant storage (when QDRANT_URL is a local path)
if "://" not in QDRANT_URL and QDRANT_URL != ":memory:":
    Path(QDRANT_URL).mkdir(parents=True, exist_ok=True)

# ─── LOGGING ───────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ─── CORS ──────────────────────────────────────────────────────────────────────
# Comma-separated list of allowed origins
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# ─── ANONYMOUS FEEDBACK ─────────────────────────────────────────────────────────
# Max anonymous feedback POSTs per client IP per window (logged-in users are not limited).
FEEDBACK_ANONYMOUS_RATE_LIMIT = int(os.getenv("FEEDBACK_ANONYMOUS_RATE_LIMIT", "10"))
FEEDBACK_ANONYMOUS_RATE_WINDOW_SEC = int(os.getenv("FEEDBACK_ANONYMOUS_RATE_WINDOW_SEC", "60"))

