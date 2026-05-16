import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth import require_case_creator, require_police_portal_user
from app.database import audit_log_insert, get_db
from app.services import qdrant_client
from app.services.face_embedding import extract_embeddings_from_bytes
from app.storage import get_url_path, save_upload

router = APIRouter()

# Image types where the photo is not expected to contain a face. For these
# slots the embedding pipeline still produces a weak/full-image vector that
# powers the visual-search shortlist, but the strict "must contain a face"
# gate below is bypassed.
_RELAXED_FACE_DETECTION_TYPES = frozenset({"belonging", "clothing", "tattoo", "other"})

# Face conditions where the body's face genuinely may not be detectable
# (decomposed, burnt, partially missing, etc.). On these submissions we
# accept face-slot uploads even if the detector finds nothing, so the
# operator is not blocked from registering legitimate cases.
_FACE_DETECTION_REQUIRED_CONDITIONS = frozenset({"normal"})


def _slot_label(image_type: str) -> str:
    return image_type.replace("_", " ")


def process_images(
    submission_id: str,
    files: list,
    image_types: list,
    face_condition: str = "normal",
):
    """Save files, run face embedding per image, upsert to Qdrant.

    Two-pass design: first read every upload and run face embedding, validating
    that face-slot photos actually contain a detectable face when
    ``face_condition == "normal"``. Only after every file passes do we write
    anything to disk or Qdrant, so a single bogus face photo cannot leave
    half-saved files or stale Qdrant points behind.
    """
    enforce_for_condition = face_condition in _FACE_DETECTION_REQUIRED_CONDITIONS

    prepared: list[dict] = []
    for f, img_type in zip(files, image_types, strict=False):
        content = f.file.read()
        ext = (f.filename or "jpg").split(".")[-1].lower() or "jpg"
        face_required = (
            img_type not in _RELAXED_FACE_DETECTION_TYPES and enforce_for_condition
        )
        embeddings = extract_embeddings_from_bytes(
            content, img_type, enforce_detection=face_required
        )
        if face_required and not embeddings:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"No face could be detected in the uploaded "
                    f"'{_slot_label(img_type)}' image. Please retake the "
                    f"photo with the face clearly visible, or set the "
                    f"face condition to 'partial', 'bloated', or "
                    f"'damaged' if the body's face is not recoverable."
                ),
            )
        prepared.append({"content": content, "ext": ext, "img_type": img_type, "embeddings": embeddings})

    images = []
    all_points = []
    for item in prepared:
        content = item["content"]
        img_type = item["img_type"]
        ext = item["ext"]
        embeddings = item["embeddings"]

        rel_path = save_upload(content, submission_id, img_type, ext)
        image_id = str(uuid.uuid4())
        point_ids: list[str] = []
        for emb_data in embeddings:
            emb = emb_data["embedding"]
            conf = emb_data["confidence"]
            qual = emb_data["quality"]
            point_id = str(uuid.uuid4())
            point_ids.append(point_id)
            all_points.append({
                "id": point_id,
                "vector": emb.tolist() if hasattr(emb, "tolist") else emb,
                "payload": {
                    "submission_id": submission_id,
                    "image_id": image_id,
                    "image_type": img_type,
                    "is_missing_person": False,
                    "embedding_confidence": conf,
                    "quality_score": qual,
                },
            })
        qdrant_point_id = point_ids[0] if point_ids else None
        images.append({
            "id": image_id,
            "submission_id": submission_id,
            "image_type": img_type,
            "path": rel_path,
            "embedding_confidence": embeddings[0]["confidence"] if embeddings else None,
            "quality_score": embeddings[0]["quality"] if embeddings else None,
            "qdrant_point_id": qdrant_point_id,
        })
    if all_points:
        qdrant_client.upsert_points(all_points)
    return images


@router.post("/submissions")
async def create_submission(
    files: list[UploadFile] = File(...),
    image_types: str = Form(default="[]"),  # JSON array of strings
    attributes_ai: str = Form(default="{}"),
    attributes_manual: str = Form(default="{}"),
    face_condition: str = Form(default="normal"),
    current_user: Annotated[dict, Depends(require_case_creator)] = None,
):
    try:
        image_types_list = json.loads(image_types) if image_types else []
    except json.JSONDecodeError:
        image_types_list = ["face_frontal"] * len(files)
    if len(files) != len(image_types_list):
        raise HTTPException(400, "files and image_types length must match")
    submission_id = str(uuid.uuid4())
    try:
        att_ai = json.loads(attributes_ai) if attributes_ai else {}
        att_man = json.loads(attributes_manual) if attributes_manual else {}
    except json.JSONDecodeError:
        att_ai, att_man = {}, {}
    images = process_images(submission_id, files, image_types_list, face_condition)
    with get_db() as conn:
        conn.execute(
            "INSERT INTO submissions (id, attributes_ai, attributes_manual, face_condition) VALUES (?, ?, ?, ?)",
            (submission_id, json.dumps(att_ai), json.dumps(att_man), face_condition),
        )
        for im in images:
            conn.execute(
                "INSERT INTO images (id, submission_id, image_type, path, embedding_confidence, quality_score, qdrant_point_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (im["id"], im["submission_id"], im["image_type"], im["path"], im.get("embedding_confidence"), im.get("quality_score"), im.get("qdrant_point_id")),
            )
        audit_log_insert(conn, "submission.create", "submission", submission_id, user_id=current_user["id"])
    return {"submission_id": submission_id, "images": [{"id": im["id"], "image_type": im["image_type"], "path": get_url_path(im["path"], is_reference=False), "is_primary": im.get("is_primary", False)} for im in images]}


@router.get("/submissions")
def list_submissions(_: Annotated[dict, Depends(require_police_portal_user)]):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT s.id, s.created_at, s.status, (SELECT path FROM images WHERE submission_id = s.id LIMIT 1) as first_image_path FROM submissions s ORDER BY s.created_at DESC LIMIT 100"
        ).fetchall()
    return [{"id": row["id"], "created_at": row["created_at"], "status": row["status"], "first_image_path": get_url_path(row["first_image_path"], is_reference=False) if row["first_image_path"] else None} for row in rows]


@router.get("/submissions/{submission_id}")
def get_submission(
    submission_id: str,
    _: Annotated[dict, Depends(require_police_portal_user)],
):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Submission not found")
        images = conn.execute("SELECT id, image_type, path, embedding_confidence FROM images WHERE submission_id = ? ORDER BY created_at ASC", (submission_id,)).fetchall()
    
    # Mark first tattoo image as primary (or first of any image type for consistency)
    processed_images = []
    tattoo_images = [r for r in images if r["image_type"].startswith("tattoo")]
    other_images = [r for r in images if not r["image_type"].startswith("tattoo")]
    
    for idx, r in enumerate(tattoo_images):
        is_primary = (idx == 0) if tattoo_images else False
        processed_images.append({
            "id": r["id"],
            "image_type": r["image_type"],
            "path": get_url_path(r["path"], is_reference=False),
            "embedding_confidence": r["embedding_confidence"],
            "is_primary": is_primary
        })
    
    for r in other_images:
        processed_images.append({
            "id": r["id"],
            "image_type": r["image_type"],
            "path": get_url_path(r["path"], is_reference=False),
            "embedding_confidence": r["embedding_confidence"],
            "is_primary": False
        })
    
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "attributes_ai": json.loads(row["attributes_ai"] or "{}"),
        "attributes_manual": json.loads(row["attributes_manual"] or "{}"),
        "face_condition": row["face_condition"],
        "status": row["status"],
        "images": processed_images,
    }
