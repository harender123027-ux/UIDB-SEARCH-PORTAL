# Criminal records/arrest data upload and search
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.auth import require_police_portal_user
from app.database import get_db

router = APIRouter()

CRIMINALS_UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "criminals"
CRIMINALS_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def save_photos(files: list[UploadFile], record_id: str) -> list[str]:
    paths = []
    for i, file in enumerate(files):
        ext = os.path.splitext(file.filename)[-1] or ".jpg"
        fname = f"{record_id}_{i}{ext}"
        fpath = CRIMINALS_UPLOAD_DIR / fname
        with open(fpath, "wb") as f:
            f.write(file.file.read())
        paths.append(fname)
    return paths

@router.post("/criminals")
def upload_criminal(
    name: str = Form(...),
    fir: str = Form(""),
    district: str = Form(""),
    station: str = Form(""),
    arrest_date: str = Form(""),
    notes: str = Form(""),
    photos: list[UploadFile] = File([]),
    user: dict = Depends(require_police_portal_user),
):
    record_id = str(uuid.uuid4())
    photo_paths = save_photos(photos, record_id)
    with get_db() as conn:
        conn.execute(
            """INSERT INTO criminals (id, name, fir, district, station, arrest_date, notes, photo_paths, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (record_id, name, fir, district, station, arrest_date, notes, ",".join(photo_paths), user["id"]),
        )
    return {"id": record_id}

@router.get("/criminals")
def list_criminals(user: dict = Depends(require_police_portal_user)):
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM criminals ORDER BY arrest_date DESC, created_at DESC").fetchall()
    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "name": r["name"],
            "fir": r["fir"],
            "district": r["district"],
            "station": r["station"],
            "arrest_date": r["arrest_date"],
            "notes": r["notes"],
            "photos": r["photo_paths"].split(",") if r["photo_paths"] else [],
        })
    return result

@router.get("/criminals/photo/{fname}")
def get_criminal_photo(fname: str, user: dict = Depends(require_police_portal_user)):
    fpath = CRIMINALS_UPLOAD_DIR / fname
    if not fpath.exists():
        raise HTTPException(404)
    return FileResponse(str(fpath))
