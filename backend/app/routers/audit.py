from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.auth import require_police_portal_user
from app.database import get_db

router = APIRouter()


@router.get("/audit")
def list_audit(
    _: Annotated[dict, Depends(require_police_portal_user)],
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, user_id, action, resource_type, resource_id, ip_address, created_at FROM audit_log ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [dict(r) for r in rows]
