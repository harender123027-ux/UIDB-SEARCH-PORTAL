from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth import require_police_portal_user
from app.database import get_db

router = APIRouter()


@router.get("/dashboard")
def get_dashboard(_: Annotated[dict, Depends(require_police_portal_user)]):
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) as c FROM submissions").fetchone()["c"]
        pending = conn.execute("SELECT COUNT(*) as c FROM matches WHERE status = 'pending_review'").fetchone()["c"]
        matched = conn.execute("SELECT COUNT(*) as c FROM matches WHERE status = 'confirmed'").fetchone()["c"]
        rows = conn.execute(
            """SELECT s.id, s.created_at, s.status, s.face_condition,
               (SELECT COUNT(*) FROM matches m WHERE m.submission_id = s.id) as match_count
               FROM submissions s ORDER BY s.created_at DESC LIMIT 50"""
        ).fetchall()
    return {
        "total_submissions": total,
        "pending_review": pending,
        "matched": matched,
        "recent": [dict(r) for r in rows],
    }
