import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

import app.config as app_config
from app.auth import get_current_user_optional
from app.database import audit_log_insert, get_db
from app.feedback_rate_limit import allow_anonymous_feedback

router = APIRouter()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        part = forwarded.split(",")[0].strip()
        if part:
            return part
    if request.client:
        return request.client.host
    return "unknown"


class FeedbackCreate(BaseModel):
    match_id: str
    verdict: str
    face_assessment: str | None = None
    action_taken: str
    notes: str | None = None


@router.post("/feedback")
def create_feedback(
    request: Request,
    body: FeedbackCreate,
    current_user: Annotated[dict | None, Depends(get_current_user_optional)],
):
    """Public: anonymous feedback allowed; reviewer_id set when Bearer token present."""
    feedback_id = str(uuid.uuid4())
    reviewer_id = current_user["id"] if current_user else None
    if not current_user:
        lim = app_config.FEEDBACK_ANONYMOUS_RATE_LIMIT
        win = app_config.FEEDBACK_ANONYMOUS_RATE_WINDOW_SEC
        if not allow_anonymous_feedback(_client_ip(request), lim, win):
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many feedback submissions from this address. Sign in or try again later.",
            )
    with get_db() as conn:
        row = conn.execute("SELECT id FROM matches WHERE id = ?", (body.match_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Match not found")
        conn.execute(
            "INSERT INTO feedback (id, match_id, reviewer_id, verdict, face_assessment, action_taken, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (feedback_id, body.match_id, reviewer_id, body.verdict, body.face_assessment, body.action_taken, body.notes or ""),
        )
        audit_log_insert(conn, "feedback.submit", "feedback", feedback_id, user_id=reviewer_id)
    return {"id": feedback_id, "message": "Feedback saved"}
