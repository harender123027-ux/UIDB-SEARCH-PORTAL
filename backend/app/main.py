import os
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.config import (
    CORS_ORIGINS,
    REFERENCE_PHOTOS_PATH,
    SUBMISSIONS_STORAGE_PATH,
    USE_AZURE_BLOB,
)
from app.database import init_db
from app.routers import (
    admin,
    audit,
    auth,
    criminals,
    dashboard,
    feedback,
    geo,
    match,
    search,
    submissions,
)

# Startup initialization
print("--- STARTING UBIS BACKEND ---", flush=True)
try:
    print("Initializing database...", flush=True)
    init_db()
    print("Database initialization successful.", flush=True)
except Exception as e:
    print(f"CRITICAL ERROR during database initialization: {e}", flush=True)
    import traceback
    traceback.print_exc()
    if os.getenv("ENVIRONMENT") == "production":
        raise SystemExit(1) from e


app = FastAPI(title="UBIS API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve files from local or Azure
if not USE_AZURE_BLOB:
    uploads_path = Path(SUBMISSIONS_STORAGE_PATH)
    if uploads_path.exists():
        app.mount("/api/files", StaticFiles(directory=str(uploads_path)), name="files")
    if REFERENCE_PHOTOS_PATH.exists():
        app.mount("/api/reference_files", StaticFiles(directory=str(REFERENCE_PHOTOS_PATH)), name="reference_files")
else:
    # If using Azure, we need proxy endpoints because StaticFiles only works for local dirs
    from fastapi.responses import StreamingResponse

    from app.storage import get_file_content

    @app.get("/api/files/{path:path}")
    async def proxy_uploads(path: str):
        content = get_file_content(path, is_reference=False)
        if not content:
            from fastapi import HTTPException
            raise HTTPException(404, "File not found in storage")
        return StreamingResponse(BytesIO(content), media_type="image/jpeg")

    @app.get("/api/reference_files/{path:path}")
    async def proxy_references(path: str):
        # The storage layer might expect just the filename or the full path
        content = get_file_content(path, is_reference=True)
        if not content:
            from fastapi import HTTPException
            raise HTTPException(404, "Reference photo not found")
        return StreamingResponse(BytesIO(content), media_type="image/jpeg")

    # Also handle the 'references' prefix if used by some storage helpers
    @app.get("/api/references/{path:path}")
    async def proxy_references_alt(path: str):
        content = get_file_content(path, is_reference=True)
        if not content:
            from fastapi import HTTPException
            raise HTTPException(404, "Reference photo not found")
        return StreamingResponse(BytesIO(content), media_type="image/jpeg")

app.include_router(submissions.router, prefix="/api", tags=["submissions"])
app.include_router(match.router, prefix="/api", tags=["match"])
app.include_router(feedback.router, prefix="/api", tags=["feedback"])
app.include_router(audit.router, prefix="/api", tags=["audit"])
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
app.include_router(search.router, prefix="/api", tags=["search"])
app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(admin.router, prefix="/api", tags=["admin"])
app.include_router(geo.router, prefix="/api", tags=["geo"])
app.include_router(criminals.router, prefix="/api", tags=["criminals"])


@app.get("/api/health")
def health():
    return {"status": "ok"}
