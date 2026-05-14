import json
import uuid
from typing import Annotated

import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth import get_current_user_optional
from app.config import (
    FACE_MATCH_THRESHOLD_MEDIUM,
    FACE_MATCH_THRESHOLD_STRONG,
    FACE_QUERY_MIN_EMBEDDING_CONFIDENCE,
)
from app.database import audit_log_insert, get_db
from app.services import qdrant_client
from app.services.face_embedding import extract_embeddings_from_bytes
from app.services.match_logic import aggregate_ref_hits
from app.storage import get_url_path, save_upload

router = APIRouter()

# Ephemeral rows created by face search / upload-and-match must not appear as gallery hits.
SEARCH_PROBE_MARKER = "_search_probe"


def _submission_ids_flagged_search_probe(conn) -> set[str]:
    rows = conn.execute(
        """
        SELECT id FROM submissions
        WHERE COALESCE(json_extract(attributes_manual, '$._search_probe'), 0) = 1
        """
    ).fetchall()
    return {r["id"] for r in rows}


def _run_match_impl(submission_id: str, audit_user_id: str | None = None, search_target: str = "all"):
    with get_db() as conn:
        row = conn.execute("SELECT id FROM submissions WHERE id = ?", (submission_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Submission not found")
        probe_submission_ids = _submission_ids_flagged_search_probe(conn)
    points = qdrant_client.get_vectors_by_submission(submission_id)
    if not points:
        return {"submission_id": submission_id, "matches": [], "message": "No face embeddings found for this submission."}

    candidate_rows: list[tuple[str, float, dict]] = []
    for p in points:
        qpayload = p.get("payload") or {}
        qconf = qpayload.get("embedding_confidence")
        if (
            FACE_QUERY_MIN_EMBEDDING_CONFIDENCE > 0
            and qconf is not None
            and float(qconf) < FACE_QUERY_MIN_EMBEDDING_CONFIDENCE
        ):
            continue
        vector = p["vector"]
        if isinstance(vector, list):
            vector = np.array(vector, dtype=np.float32)
        results = qdrant_client.search_all(vector, limit=15)
        for r in results:
            payload = r.get("payload") or {}
            is_miss = payload.get("is_missing_person", False)
            if search_target == "criminal" and not is_miss:
                continue
            if search_target == "ui_body" and is_miss:
                continue
            ref_id = payload.get("reference_person_id")
            if not ref_id:
                ref_id = payload.get("submission_id")
            if (
                ref_id
                and ref_id != submission_id
                and ref_id not in probe_submission_ids
                and r.get("score") is not None
            ):
                score = float(r["score"])
                if score >= FACE_MATCH_THRESHOLD_MEDIUM:
                    candidate_rows.append((ref_id, score, payload))

    aggregated = aggregate_ref_hits(candidate_rows)

    with get_db() as conn:
        refs = {}
        for ref_id, _score, _bp, _sup in aggregated[:20]:
            row = conn.execute(
                "SELECT id, label, photo_path, attributes FROM reference_persons WHERE id = ?",
                (ref_id,),
            ).fetchone()
            if row:
                refs[ref_id] = {
                    "id": row["id"],
                    "label": row["label"],
                    "photo_path": get_url_path(row["photo_path"], is_reference=True),
                    "attributes": json.loads(row["attributes"] or "{}")
                    if isinstance(row["attributes"], str)
                    else (row["attributes"] or {}),
                    "result_type": "reference",
                }
            else:
                sub_row = conn.execute("SELECT id, attributes_manual FROM submissions WHERE id = ?", (ref_id,)).fetchone()
                if sub_row:
                    img_row = conn.execute(
                        """SELECT path FROM images WHERE submission_id = ? ORDER BY CASE image_type
                        WHEN 'face_frontal' THEN 0 WHEN 'face_left' THEN 1 WHEN 'face_right' THEN 2
                        WHEN 'full_body' THEN 3 ELSE 4 END, created_at ASC LIMIT 1""",
                        (ref_id,),
                    ).fetchone()
                    photo_path = get_url_path(img_row["path"], is_reference=False) if img_row else None
                    att = (
                        json.loads(sub_row["attributes_manual"] or "{}")
                        if isinstance(sub_row["attributes_manual"], str)
                        else (sub_row["attributes_manual"] or {})
                    )
                    display_attrs = {k: v for k, v in att.items() if not str(k).startswith("_")}
                    dd_no = display_attrs.get("dd_no")
                    label = f"UI Body — DD {dd_no}" if dd_no else "UI Body (Submission)"
                    refs[ref_id] = {
                        "id": sub_row["id"],
                        "label": label,
                        "photo_path": photo_path,
                        "attributes": display_attrs,
                        "result_type": "submission",
                    }

    matches = []
    rank = 0
    for ref_id, score, best_payload, _supporting in aggregated[:20]:
        if ref_id not in refs:
            # Skip orphan vectors whose submission / reference row was deleted.
            continue
        rank += 1
        match_id = str(uuid.uuid4())
        ref_info = refs[ref_id]
        with get_db() as conn:
            conn.execute(
                "INSERT INTO matches (id, submission_id, reference_person_id, overall_score, face_score, rank, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (match_id, submission_id, ref_id, score, score, rank, "pending_review"),
            )
            audit_log_insert(conn, "match.run", "match", match_id, user_id=audit_user_id)
        conf_level = "low"
        if score >= FACE_MATCH_THRESHOLD_STRONG:
            conf_level = "high"
        elif score >= FACE_MATCH_THRESHOLD_MEDIUM:
            conf_level = "medium"
        matches.append(
            {
                "match_id": match_id,
                "rank": rank,
                "reference_person_id": ref_id,
                "label": ref_info["label"],
                "photo_path": ref_info["photo_path"],
                "scores": {"overall": score, "face": score},
                "quality_score": best_payload.get("quality_score"),
                "attributes": ref_info["attributes"],
                "confidence_level": conf_level,
                "result_type": ref_info.get("result_type") or "reference",
            }
        )
    return {"submission_id": submission_id, "matches": matches}


@router.post("/submissions/{submission_id}/match")
def run_match(
    submission_id: str,
    current_user: Annotated[dict | None, Depends(get_current_user_optional)],
):
    """Public: no login required; audit user recorded when Bearer token present."""
    uid = current_user["id"] if current_user else None
    return _run_match_impl(submission_id, audit_user_id=uid)


async def _upload_and_match_impl(
    files: list[UploadFile],
    image_types_list: list[str],
    search_target: str,
    audit_user_id: str | None,
):
    if not files:
        raise HTTPException(400, "At least one image required")
    submission_id = str(uuid.uuid4())
    file_contents = [await f.read() for f in files]
    images = []
    all_points = []
    for i, (content, img_type) in enumerate(zip(file_contents, image_types_list[: len(files)], strict=False)):
        ext = (files[i].filename or "jpg").split(".")[-1].lower() or "jpg"
        rel_path = save_upload(content, submission_id, img_type, ext)
        image_id = str(uuid.uuid4())
        embeddings = extract_embeddings_from_bytes(content, img_type, enforce_detection=False)
        point_ids = []
        for emb_data in embeddings:
            emb = emb_data["embedding"]
            conf = emb_data["confidence"]
            qual = emb_data["quality"]
            point_id = str(uuid.uuid4())
            point_ids.append(point_id)
            all_points.append(
                {
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
                }
            )
        qdrant_point_id = point_ids[0] if point_ids else None
        images.append(
            {
                "id": image_id,
                "submission_id": submission_id,
                "image_type": img_type,
                "path": rel_path,
                "embedding_confidence": embeddings[0]["confidence"] if embeddings else None,
                "quality_score": embeddings[0]["quality"] if embeddings else None,
                "qdrant_point_id": qdrant_point_id,
            }
        )
    if all_points:
        qdrant_client.upsert_points(all_points)
    probe_attrs = json.dumps({SEARCH_PROBE_MARKER: True})
    with get_db() as conn:
        conn.execute(
            "INSERT INTO submissions (id, attributes_ai, attributes_manual, face_condition) VALUES (?, ?, ?, ?)",
            (submission_id, "{}", probe_attrs, "normal"),
        )
        for im in images:
            conn.execute(
                "INSERT INTO images (id, submission_id, image_type, path, embedding_confidence, quality_score, qdrant_point_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    im["id"],
                    im["submission_id"],
                    im["image_type"],
                    im["path"],
                    im.get("embedding_confidence"),
                    im.get("quality_score"),
                    im.get("qdrant_point_id"),
                ),
            )
        audit_log_insert(conn, "submission.create", "submission", submission_id, user_id=audit_user_id)
    return _run_match_impl(submission_id, audit_user_id=audit_user_id, search_target=search_target)


@router.post("/upload-and-match")
async def upload_and_match(
    current_user: Annotated[dict | None, Depends(get_current_user_optional)],
    files: list[UploadFile] = File(...),
    image_types: str = Form(default='["face_frontal"]'),
    search_target: str = Form(default="all"),
):
    """Public: no login required; audit user recorded when Bearer token present."""
    try:
        image_types_list = json.loads(image_types) if image_types else []
    except json.JSONDecodeError:
        image_types_list = ["face_frontal"] * len(files)
    if len(image_types_list) < len(files):
        image_types_list.extend(["face_frontal"] * (len(files) - len(image_types_list)))
    uid = current_user["id"] if current_user else None
    return await _upload_and_match_impl(files, image_types_list, search_target, uid)
