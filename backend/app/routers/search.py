import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth import get_current_user_optional, require_police_portal_user
from app.config import (
    FACE_MATCH_THRESHOLD_MEDIUM,
    FACE_MATCH_THRESHOLD_STRONG,
    FACE_QUERY_MIN_EMBEDDING_CONFIDENCE,
)
from app.database import get_db
from app.search_synonyms import merge_submission_attributes, text_attribute_match_score
from app.storage import get_url_path

logger = logging.getLogger(__name__)

router = APIRouter()


def parse_query_to_filters(query: str) -> dict:
    """Simple local keyword extraction: male/female, tattoo on X, age, etc."""
    q = (query or "").lower().strip()
    filters = {}
    if "male" in q or "man" in q:
        filters["gender"] = "male"
    if "female" in q or "woman" in q:
        filters["gender"] = "female"
    if "tattoo" in q:
        filters["has_tattoo"] = True
        for part in ["neck", "arm", "right arm", "left arm", "chest", "back", "hand", "face"]:
            if part in q:
                filters["tattoo_location"] = part.replace(" ", "_")
                break
    if "mark" in q or "scar" in q:
        filters["has_marks"] = True
    return filters


def _execute_text_search(body: dict) -> dict:
    """Attribute/text shortlist (no HTTP auth — callers must gate access)."""
    query = body.get("query") or body.get("q") or ""
    search_target = body.get("search_target") or "all"
    filters = parse_query_to_filters(query)
    rows = []
    with get_db() as conn:
        if search_target in ("all", "criminal"):
            refs = conn.execute(
                "SELECT id, label, photo_path, attributes FROM reference_persons ORDER BY created_at DESC"
            ).fetchall()
            for r in refs:
                rows.append({
                    "id": r["id"],
                    "label": r["label"],
                    "photo_path": get_url_path(r["photo_path"], is_reference=True),
                    "attributes": r["attributes"],
                    "result_type": "reference",
                })
        if search_target in ("all", "ui_body"):
            subs = conn.execute(
                "SELECT id, attributes_manual, attributes_ai FROM submissions ORDER BY created_at DESC"
            ).fetchall()
            for s in subs:
                att_manual_raw = s["attributes_manual"]
                att_manual = (
                    json.loads(att_manual_raw or "{}")
                    if isinstance(att_manual_raw, str)
                    else (att_manual_raw or {})
                )
                if isinstance(att_manual, str):
                    att_manual = json.loads(att_manual) if att_manual else {}
                if att_manual.get("_search_probe"):
                    continue
                img_row = conn.execute(
                    """SELECT path FROM images WHERE submission_id = ? ORDER BY CASE image_type
                    WHEN 'face_frontal' THEN 0 WHEN 'face_left' THEN 1 WHEN 'face_right' THEN 2
                    WHEN 'full_body' THEN 3 WHEN 'tattoo' THEN 4 WHEN 'clothing' THEN 5
                    WHEN 'belonging' THEN 6 ELSE 7 END, created_at ASC LIMIT 1""",
                    (s["id"],),
                ).fetchone()
                photo_path = get_url_path(img_row["path"], is_reference=False) if img_row else None
                dd_no = att_manual.get("dd_no")
                label = f"UI Body — DD {dd_no}" if dd_no else "UI Body (Submission)"
                rows.append({
                    "id": s["id"],
                    "label": label,
                    "photo_path": photo_path,
                    "attributes_manual": s["attributes_manual"],
                    "attributes_ai": s["attributes_ai"],
                    "result_type": "submission",
                })
    results = []
    qstrip = (query or "").strip()
    for r in rows:
        if r.get("result_type") == "submission":
            att = merge_submission_attributes(r.get("attributes_manual"), r.get("attributes_ai"))
        else:
            att = json.loads(r["attributes"] or "{}") if isinstance(r["attributes"], str) else (r["attributes"] or {})
            if isinstance(att, str):
                att = json.loads(att) if att else {}
        text_score = text_attribute_match_score(query, att) if qstrip else 0.0
        filter_score = 0.0
        if filters:
            if filters.get("gender") and str(att.get("gender", "")).lower() == str(filters["gender"]).lower():
                filter_score += 0.4
            if filters.get("has_tattoo") and (
                "tattoo" in str(att.get("visible_marks", "")).lower() or "tattoo" in str(att).lower()
            ):
                filter_score += 0.3
            if filters.get("tattoo_location") and filters["tattoo_location"].replace("_", " ") in str(att).lower():
                filter_score += 0.2
            if filters.get("has_marks") and ("mark" in str(att).lower() or "scar" in str(att).lower()):
                filter_score += 0.2

        if qstrip:
            if filters:
                match_score = max(filter_score, text_score)
                if filter_score > 0 and text_score > 0:
                    match_score = min(1.0, filter_score + text_score * 0.25)
            else:
                match_score = text_score
        else:
            match_score = filter_score if filters else 0.5

        if match_score <= 0 and (qstrip or filters):
            continue
        results.append({
            "id": r["id"],
            "label": r["label"],
            "photo_path": r["photo_path"],
            "attributes": att,
            "match_score": max(match_score, 0.05),
            "result_type": r.get("result_type", "reference"),
        })
    results.sort(key=lambda x: -x["match_score"])
    return {"query": query, "filters": filters, "shortlist": results[:30]}


def _execute_details_search(filters: dict, search_target: str) -> dict:
    rows = []
    with get_db() as conn:
        if search_target in ("all", "criminal"):
            refs = conn.execute(
                "SELECT id, label, photo_path, attributes FROM reference_persons ORDER BY created_at DESC"
            ).fetchall()
            for r in refs:
                rows.append({
                    "id": r["id"],
                    "label": r["label"],
                    "photo_path": get_url_path(r["photo_path"], is_reference=True),
                    "attributes": r["attributes"],
                    "result_type": "reference",
                })
        if search_target in ("all", "ui_body"):
            subs = conn.execute(
                "SELECT id, attributes_manual, attributes_ai FROM submissions ORDER BY created_at DESC"
            ).fetchall()
            for s in subs:
                att_manual_raw = s["attributes_manual"]
                att_manual = (
                    json.loads(att_manual_raw or "{}")
                    if isinstance(att_manual_raw, str)
                    else (att_manual_raw or {})
                )
                if isinstance(att_manual, str):
                    att_manual = json.loads(att_manual) if att_manual else {}
                if att_manual.get("_search_probe"):
                    continue
                img_row = conn.execute(
                    """SELECT path FROM images WHERE submission_id = ? ORDER BY CASE image_type
                    WHEN 'face_frontal' THEN 0 WHEN 'face_left' THEN 1 WHEN 'face_right' THEN 2
                    WHEN 'full_body' THEN 3 WHEN 'tattoo' THEN 4 WHEN 'clothing' THEN 5
                    WHEN 'belonging' THEN 6 ELSE 7 END, created_at ASC LIMIT 1""",
                    (s["id"],),
                ).fetchone()
                photo_path = get_url_path(img_row["path"], is_reference=False) if img_row else None
                dd_no = att_manual.get("dd_no")
                label = f"UI Body — DD {dd_no}" if dd_no else "UI Body (Submission)"
                rows.append({
                    "id": s["id"],
                    "label": label,
                    "photo_path": photo_path,
                    "attributes_manual": s["attributes_manual"],
                    "attributes_ai": s["attributes_ai"],
                    "result_type": "submission",
                })
    results = []
    for r in rows:
        if r.get("result_type") == "submission":
            att = merge_submission_attributes(r.get("attributes_manual"), r.get("attributes_ai"))
        else:
            att = json.loads(r["attributes"] or "{}") if isinstance(r["attributes"], str) else (r["attributes"] or {})
            if isinstance(att, str):
                att = json.loads(att) if att else {}
        
        score = 0.0
        total_filters = len([v for v in filters.values() if v.strip()])
        if not total_filters:
            continue
            
        att_str = json.dumps(att).lower()
        
        if filters.get("age"):
            search_age = filters["age"].lower()
            if search_age in str(att.get("age_min", "")) or search_age in str(att.get("age_max", "")) or search_age in str(att.get("age_group", "")):
                score += 1.0
            elif search_age in att_str:
                score += 0.5
                
        if filters.get("height"):
            if filters["height"] in str(att.get("height", "")) or filters["height"] in str(att.get("height_cm", "")):
                score += 1.0
            elif filters["height"] in att_str:
                score += 0.5
                
        if filters.get("marks"):
            m = filters["marks"].lower()
            if m in str(att.get("marks", "")).lower() or m in str(att.get("visible_marks", "")).lower():
                score += 1.0
            elif m in att_str:
                score += 0.8
                
        if filters.get("police_station"):
            ps = filters["police_station"].lower()
            if ps in str(att.get("ps", "")).lower() or ps in str(att.get("ps_name", "")).lower():
                score += 1.0
            elif ps in att_str:
                score += 0.5
                
        if filters.get("found_loc"):
            loc = filters["found_loc"].lower()
            if loc in str(att.get("found_loc", "")).lower() or loc in str(att.get("found_district", "")).lower():
                score += 1.0
            elif loc in att_str:
                score += 0.5
                
        if filters.get("found_date"):
            if filters["found_date"] in str(att.get("found_date", "")):
                score += 1.0
            elif filters["found_date"] in att_str:
                score += 0.5
                
        if score > 0:
            final_score = min(1.0, score / max(1, total_filters))
            results.append({
                "id": r["id"],
                "label": r["label"],
                "photo_path": r["photo_path"],
                "attributes": att,
                "match_score": final_score,
                "result_type": r.get("result_type", "reference"),
            })
            
    results.sort(key=lambda x: -x["match_score"])
    return {"shortlist": results[:50]}


@router.post("/search")
def search_by_query(body: dict):
    """Public: no login required (text/attribute shortlist)."""
    return _execute_text_search(body)


@router.post("/search/voice")
async def search_by_voice(audio: UploadFile = File(...)):
    """Public: no login required."""
    """STT (local Whisper) then same attribute search."""
    content = await audio.read()
    if not content:
        raise HTTPException(400, "No audio data")
    transcript = ""
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(content, language="en")
        transcript = " ".join(s.text for s in segments).strip()
    except Exception as e:
        transcript = f"[STT unavailable: {e}]"
    if not transcript:
        return {"transcript": "", "shortlist": [], "query": "", "filters": {}}
    out = _execute_text_search({"query": transcript})
    out["transcript"] = transcript
    return out


def _refs_from_image_matches(matches: list) -> dict:
    """Return dict ref_id -> { label, photo_path, score, result_type, attributes }."""
    out = {}
    for m in matches:
        ref_id = m.get("reference_person_id")
        if not ref_id:
            continue
        score = (m.get("scores") or {}).get("overall") or (m.get("scores") or {}).get("face") or 0
        quality = m.get("quality_score") or (m.get("scores") or {}).get("quality") or 0
        out[ref_id] = {
            "label": m.get("label"),
            "photo_path": m.get("photo_path"),
            "score": score,
            "quality": quality,
            "result_type": m.get("result_type") or "reference",
            "attributes": m.get("attributes") or {},
        }
    return out


def _refs_from_shortlist(shortlist: list) -> dict:
    """Return dict ref_id -> { label, photo_path, score }."""
    return {
        r["id"]: {
            "label": r.get("label"),
            "photo_path": r.get("photo_path"),
            "score": r.get("match_score", 0),
            "result_type": r.get("result_type", "reference"),
            "attributes": r.get("attributes") or {}
        } for r in shortlist
    }


@router.post("/search/combined")
async def search_combined(
    current_user: Annotated[dict | None, Depends(get_current_user_optional)],
    submission_id: str = Form(default=""),
    query: str = Form(default=""),
    audio: UploadFile | None = File(default=None),
    files: list[UploadFile] | None = File(default=None),
    search_target: str = Form(default="all"),  # 'all', 'criminal', 'ui_body'
    search_type: str = Form(default=""),
    age: str = Form(default=""),
    height: str = Form(default=""),
    marks: str = Form(default=""),
    police_station: str = Form(default=""),
    found_loc: str = Form(default=""),
    found_date: str = Form(default=""),
):
    """
    Run image (submission or upload), text, and/or voice search together.
    Merge results: sort by overlap (how many modalities returned this person) then by confidence score.
    """
    from app.routers.match import _run_match_impl, _upload_and_match_impl

    files = files or []
    image_refs = {}
    text_refs = {}
    voice_refs = {}
    details_refs = {}
    transcript = ""

    if age or height or marks or police_station or found_loc or found_date:
        filters = {
            "age": age, "height": height, "marks": marks, 
            "police_station": police_station, "found_loc": found_loc, "found_date": found_date
        }
        out_details = _execute_details_search(filters, search_target)
        details_refs = _refs_from_shortlist(out_details.get("shortlist") or [])

    audit_uid = current_user["id"] if current_user else None
    if submission_id and submission_id.strip():
        try:
            res = _run_match_impl(
                submission_id.strip(),
                audit_user_id=audit_uid,
                search_target=search_target,
            )
            image_refs = _refs_from_image_matches(res.get("matches") or [])
        except Exception as e:
            logger.warning("search_combined submission match failed: %s", e)

    if not image_refs and files:
        try:
            image_types_str = '["face_frontal"]'
            try:
                it = json.loads(image_types_str) if image_types_str else []
            except json.JSONDecodeError:
                it = ["face_frontal"] * len(files)
            if len(it) < len(files):
                it.extend(["face_frontal"] * (len(files) - len(it)))
            res = await _upload_and_match_impl(files, it, search_target, audit_uid)
            image_refs = _refs_from_image_matches(res.get("matches") or [])
        except Exception as e:
            logger.warning("search_combined upload match failed: %s", e)

    if query and query.strip():
        out = _execute_text_search({"query": query.strip(), "search_target": search_target})
        text_refs = _refs_from_shortlist(out.get("shortlist") or [])

    if audio and audio.filename:
        content = await audio.read()
        if content:
            try:
                from faster_whisper import WhisperModel
                model = WhisperModel("base", device="cpu", compute_type="int8")
                segments, _ = model.transcribe(content, language="en")
                transcript = " ".join(s.text for s in segments).strip()
            except Exception:
                transcript = ""
            if transcript:
                out = _execute_text_search({"query": transcript, "search_target": search_target})
                voice_refs = _refs_from_shortlist(out.get("shortlist") or [])

    all_ids = set(image_refs) | set(text_refs) | set(voice_refs) | set(details_refs)
    merged = []
    for ref_id in all_ids:
        info = image_refs.get(ref_id) or text_refs.get(ref_id) or voice_refs.get(ref_id) or details_refs.get(ref_id)
        label = (info or {}).get("label") or ref_id
        photo_path = (info or {}).get("photo_path")
        si_raw = (image_refs.get(ref_id) or {}).get("score") or 0
        qi = (image_refs.get(ref_id) or {}).get("quality") or 0
        st = (text_refs.get(ref_id) or {}).get("score") or 0
        sv = (voice_refs.get(ref_id) or {}).get("score") or 0
        sd = (details_refs.get(ref_id) or {}).get("score") or 0
        # Keep a strong signal for "image modality agreed" without hiding borderline face-only hits.
        si_for_overlap = si_raw if si_raw >= FACE_MATCH_THRESHOLD_MEDIUM else 0
        combined_score = max(si_raw, st, sv, sd) if (si_raw or st or sv or sd) else 0
        if combined_score == 0:
            continue

        sources = []
        if si_for_overlap > 0:
            sources.append("image")
        if st > 0:
            sources.append("text")
        if sv > 0:
            sources.append("voice")
        if sd > 0:
            sources.append("details")

        overlap = len(sources)

        conf_level = "low"
        if combined_score >= FACE_MATCH_THRESHOLD_STRONG:
            conf_level = "high"
        elif combined_score >= FACE_MATCH_THRESHOLD_MEDIUM:
            conf_level = "medium"

        merged.append({
            "id": ref_id,
            "label": label,
            "photo_path": photo_path,
            "overlap": overlap,
            "sources": sources,
            "score": combined_score,
            "score_image": si_raw,
            "score_text": st,
            "score_voice": sv,
            "quality": qi,
            "confidence_level": conf_level,
            "result_type": (info or {}).get("result_type", "reference"),
            "attributes": (info or {}).get("attributes") or {}
        })

    merged.sort(key=lambda x: (-x["overlap"], -x["score"]))
    return {"results": merged[:50], "transcript": transcript}


@router.get("/reference_persons/{person_id}")
def get_reference_person(person_id: str):
    """Public: no login required (read UI body / missing-person detail for search results)."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, label, photo_path, attributes, created_at FROM reference_persons WHERE id = ?",
            (person_id,),
        ).fetchone()
        if row:
            return {
                "id": row["id"],
                "label": row["label"],
                "photo_path": get_url_path(row["photo_path"], is_reference=True),
                "attributes": json.loads(row["attributes"] or "{}") if isinstance(row["attributes"], str) else (row["attributes"] or {}),
                "created_at": row["created_at"],
            }
        # Fallback to UI Body submissions
        sub_row = conn.execute(
            "SELECT id, attributes_manual, attributes_ai, face_condition, status, created_at FROM submissions WHERE id = ?",
            (person_id,)
        ).fetchone()
        if sub_row:
            images_rows = conn.execute(
                """SELECT id, image_type, path, embedding_confidence, quality_score FROM images WHERE submission_id = ?
                ORDER BY CASE image_type
                WHEN 'face_frontal' THEN 0 WHEN 'face_left' THEN 1 WHEN 'face_right' THEN 2
                WHEN 'full_body' THEN 3 WHEN 'tattoo' THEN 4 WHEN 'clothing' THEN 5
                WHEN 'belonging' THEN 6 ELSE 7 END, created_at ASC""",
                (person_id,),
            ).fetchall()
            img_row = images_rows[0] if images_rows else None
            photo_path = img_row["path"] if img_row else None
            created_at = sub_row["created_at"] or (dict(img_row).get("created_at") or "")

            # Merge attributes
            att_man = json.loads(sub_row["attributes_manual"] or "{}") if isinstance(sub_row["attributes_manual"], str) else (sub_row["attributes_manual"] or {})
            att_ai = json.loads(sub_row["attributes_ai"] or "{}") if isinstance(sub_row["attributes_ai"], str) else (sub_row["attributes_ai"] or {})
            display_man = {k: v for k, v in att_man.items() if not str(k).startswith("_")}
            dd_no = display_man.get("dd_no")
            label = f"UI Body — DD {dd_no}" if dd_no else "UI Body (Submission)"

            return {
                "id": sub_row["id"],
                "label": label,
                "photo_path": get_url_path(photo_path, is_reference=False) if photo_path else None,
                "attributes": {**att_ai, **display_man},
                "attributes_manual": att_man,
                "attributes_ai": att_ai,
                "created_at": created_at,
                "status": dict(sub_row).get("status") or "captured",
                "face_condition": dict(sub_row).get("face_condition"),
                "images": [
                    {
                        "id": r["id"],
                        "image_type": r["image_type"],
                        "path": get_url_path(r["path"], is_reference=False),
                        "embedding_confidence": r["embedding_confidence"],
                        "quality_score": r["quality_score"],
                    }
                    for r in images_rows
                ],
            }
        raise HTTPException(404, "Reference person or UI Body not found")


@router.post("/search/all")
def search_all(_: Annotated[dict, Depends(require_police_portal_user)]):
    """
    Search through all submissions and the repository: match every submission's
    face embeddings against reference persons, then return relevant matches
    (reference persons that matched any submission), sorted by best score then
    by how many submissions matched.
    """
    from collections import defaultdict

    from app.services import qdrant_client

    with get_db() as conn:
        submission_rows = conn.execute("SELECT id FROM submissions ORDER BY created_at DESC").fetchall()
    submission_ids = [r["id"] for r in submission_rows]

    by_ref = defaultdict(list)
    for submission_id in submission_ids:
        points = qdrant_client.get_vectors_by_submission(submission_id)
        if not points:
            continue
        for p in points:
            qpayload = p.get("payload") or {}
            qconf = qpayload.get("embedding_confidence")
            if (
                FACE_QUERY_MIN_EMBEDDING_CONFIDENCE > 0
                and qconf is not None
                and float(qconf) < FACE_QUERY_MIN_EMBEDDING_CONFIDENCE
            ):
                continue
            vector = p.get("vector")
            if vector is None:
                continue
            if isinstance(vector, list):
                import numpy as np
                vector = np.array(vector, dtype=np.float32)
            results = qdrant_client.search_reference_only(vector, limit=15)
            for r in results:
                ref_id = (r.get("payload") or {}).get("reference_person_id")
                if ref_id and r.get("score") is not None:
                    score = float(r["score"])
                    if score >= FACE_MATCH_THRESHOLD_MEDIUM:
                        by_ref[ref_id].append({"submission_id": submission_id, "score": score})

    ref_ids = list(by_ref.keys())
    if not ref_ids:
        return {"results": [], "message": "No submissions with face embeddings, or no reference persons in repository."}

    with get_db() as conn:
        refs = {}
        for ref_id in ref_ids:
            row = conn.execute(
                "SELECT id, label, photo_path FROM reference_persons WHERE id = ?", (ref_id,)
            ).fetchone()
            if row:
                refs[ref_id] = {"label": row["label"], "photo_path": row["photo_path"]}

    merged = []
    for ref_id, hits in by_ref.items():
        best = max(h["score"] for h in hits)
        match_count = len(set(h["submission_id"] for h in hits))
        info = refs.get(ref_id) or {}
        conf_level = "low"
        if best >= FACE_MATCH_THRESHOLD_STRONG:
            conf_level = "high"
        elif best >= FACE_MATCH_THRESHOLD_MEDIUM:
            conf_level = "medium"

        merged.append({
            "id": ref_id,
            "label": info.get("label") or ref_id,
            "photo_path": get_url_path(info.get("photo_path"), is_reference=True) if info.get("photo_path") else None,
            "score": best,
            "match_count": match_count,
            "matched_by": [{"submission_id": h["submission_id"], "score": h["score"]} for h in hits[:10]],
            "confidence_level": conf_level,
        })

    merged.sort(key=lambda x: (-x["score"], -x["match_count"]))
    return {"results": merged[:50]}
