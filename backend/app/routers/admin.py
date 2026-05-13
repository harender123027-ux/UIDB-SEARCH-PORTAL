import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator

from app.auth import hash_password, require_admin
from app.database import audit_log_insert, get_db
from app.services import qdrant_client
from app.storage import delete_file, get_url_path

router = APIRouter()


def _user_row_to_dict(row) -> dict:
    row = dict(row)
    return {
        "id": row["id"],
        "username": row["username"],
        "name": row["name"],
        "role": row["role"],
        "district": row["district"],
        "station": row["station"],
        "district_id": row.get("district_id"),
        "station_id": row.get("station_id"),
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
    }


class CreateUserBody(BaseModel):
    username: str
    password: str
    name: str
    role: str = "investigator"
    district_id: str | None = None
    station_id: str | None = None


class UpdateUserBody(BaseModel):
    name: str | None = None
    role: str | None = None
    district_id: str | None = None
    station_id: str | None = None
    is_active: bool | None = None
    password: str | None = None


VALID_ROLES = {"investigator", "admin"}


class CreateDistrictBody(BaseModel):
    name: str


class UpdateDistrictBody(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class CreateStationBody(BaseModel):
    name: str


class UpdateStationBody(BaseModel):
    name: str | None = None
    district_id: str | None = None
    is_active: bool | None = None


def _district_row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
    }


def _station_row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "district_id": row["district_id"],
        "name": row["name"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
    }


def _resolve_district_station(
    conn,
    district_id: str | None,
    station_id: str | None,
) -> tuple[str | None, str | None]:
    """
    Validate and resolve district/station IDs to display names.
    Rules:
    - station_id requires district_id
    - station_id must belong to district_id
    Returns (district_name, station_name) (either can be None).
    """
    if station_id and not district_id:
        raise HTTPException(status_code=400, detail="station_id requires district_id")

    district_name = None
    station_name = None

    if district_id:
        d = conn.execute("SELECT id, name FROM districts WHERE id = ?", (district_id,)).fetchone()
        if not d:
            raise HTTPException(status_code=400, detail="Invalid district_id")
        district_name = d["name"]

    if station_id:
        s = conn.execute(
            "SELECT id, district_id, name FROM police_stations WHERE id = ?",
            (station_id,),
        ).fetchone()
        if not s:
            raise HTTPException(status_code=400, detail="Invalid station_id")
        if s["district_id"] != district_id:
            raise HTTPException(status_code=400, detail="station_id does not belong to district_id")
        station_name = s["name"]

    return district_name, station_name


@router.get("/admin/users")
def list_users(
    current_user: Annotated[dict, Depends(require_admin)],
    role: str | None = Query(default=None),
    is_active: int | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
):
    with get_db() as conn:
        query = """
            SELECT
              u.id,
              u.username,
              u.name,
              u.role,
              u.district_id,
              u.station_id,
              COALESCE(d.name, u.district) AS district,
              COALESCE(s.name, u.station) AS station,
              u.is_active,
              u.created_at
            FROM users u
            LEFT JOIN districts d ON d.id = u.district_id
            LEFT JOIN police_stations s ON s.id = u.station_id
            WHERE 1=1
        """.strip()
        params = []
        if role is not None:
            query += " AND role = ?"
            params.append(role)
        if is_active is not None:
            query += " AND is_active = ?"
            params.append(bool(is_active))
        query += " ORDER BY u.created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(query, params).fetchall()
    return [_user_row_to_dict(r) for r in rows]


@router.post("/admin/users")
def create_user(
    body: CreateUserBody,
    current_user: Annotated[dict, Depends(require_admin)],
):
    username = (body.username or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {sorted(VALID_ROLES)}")
    if not (body.password or "").strip():
        raise HTTPException(status_code=400, detail="Password is required")
    user_id = str(uuid.uuid4())
    password_hash = hash_password(body.password)
    with get_db() as conn:
        district_name, station_name = _resolve_district_station(conn, body.district_id, body.station_id)
        existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Username already exists")
        conn.execute(
            """INSERT INTO users (id, username, password_hash, name, role, district, station, district_id, station_id, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, TRUE)""",
            (
                user_id,
                username,
                password_hash,
                body.name.strip(),
                body.role,
                district_name,
                station_name,
                body.district_id,
                body.station_id,
            ),
        )
        audit_log_insert(conn, "user.create", "user", user_id, user_id=current_user["id"])
        row = conn.execute(
            """
            SELECT
              u.id,
              u.username,
              u.name,
              u.role,
              u.district_id,
              u.station_id,
              COALESCE(d.name, u.district) AS district,
              COALESCE(s.name, u.station) AS station,
              u.is_active,
              u.created_at
            FROM users u
            LEFT JOIN districts d ON d.id = u.district_id
            LEFT JOIN police_stations s ON s.id = u.station_id
            WHERE u.id = ?
            """,
            (user_id,),
        ).fetchone()
    return _user_row_to_dict(dict(row))


@router.patch("/admin/users/{user_id}")
def update_user(
    user_id: str,
    body: UpdateUserBody,
    current_user: Annotated[dict, Depends(require_admin)],
):
    updates = []
    params = []
    # Resolve desired district/station if any change requested.
    wants_location_update = body.district_id is not None or body.station_id is not None
    if body.name is not None:
        updates.append("name = ?")
        params.append(body.name.strip())
    if body.role is not None:
        if body.role not in VALID_ROLES:
            raise HTTPException(status_code=400, detail=f"role must be one of {sorted(VALID_ROLES)}")
        updates.append("role = ?")
        params.append(body.role)
    if wants_location_update:
        with get_db() as conn:
            existing = conn.execute(
                "SELECT district_id, station_id FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="User not found")
        next_district_id = body.district_id if body.district_id is not None else existing["district_id"]
        next_station_id = body.station_id if body.station_id is not None else existing["station_id"]
        with get_db() as conn:
            district_name, station_name = _resolve_district_station(conn, next_district_id, next_station_id)
        updates.append("district_id = ?")
        params.append(next_district_id)
        updates.append("station_id = ?")
        params.append(next_station_id)
        updates.append("district = ?")
        params.append(district_name)
        updates.append("station = ?")
        params.append(station_name)
    if body.is_active is not None:
        updates.append("is_active = ?")
        params.append(bool(body.is_active))
    if body.password is not None and body.password.strip():
        updates.append("password_hash = ?")
        params.append(hash_password(body.password))
    if not updates:
        with get_db() as conn:
            row = conn.execute(
                """
                SELECT
                  u.id,
                  u.username,
                  u.name,
                  u.role,
                  u.district_id,
                  u.station_id,
                  COALESCE(d.name, u.district) AS district,
                  COALESCE(s.name, u.station) AS station,
                  u.is_active,
                  u.created_at
                FROM users u
                LEFT JOIN districts d ON d.id = u.district_id
                LEFT JOIN police_stations s ON s.id = u.station_id
                WHERE u.id = ?
                """,
                (user_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        return _user_row_to_dict(dict(row))
    params.append(user_id)
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        conn.execute(
            "UPDATE users SET " + ", ".join(updates) + " WHERE id = ?",
            params,
        )
        audit_log_insert(conn, "user.update", "user", user_id, user_id=current_user["id"])
        row = conn.execute(
            """
            SELECT
              u.id,
              u.username,
              u.name,
              u.role,
              u.district_id,
              u.station_id,
              COALESCE(d.name, u.district) AS district,
              COALESCE(s.name, u.station) AS station,
              u.is_active,
              u.created_at
            FROM users u
            LEFT JOIN districts d ON d.id = u.district_id
            LEFT JOIN police_stations s ON s.id = u.station_id
            WHERE u.id = ?
            """,
            (user_id,),
        ).fetchone()
    return _user_row_to_dict(dict(row))


@router.get("/admin/districts")
def list_districts(
    current_user: Annotated[dict, Depends(require_admin)],
    is_active: int | None = Query(default=None),
):
    with get_db() as conn:
        q = "SELECT id, name, is_active, created_at FROM districts WHERE 1=1"
        params: list = []
        if is_active is not None:
            q += " AND is_active = ?"
            params.append(bool(is_active))
        q += " ORDER BY name ASC"
        rows = conn.execute(q, params).fetchall()
    return [_district_row_to_dict(r) for r in rows]


@router.post("/admin/districts", status_code=status.HTTP_201_CREATED)
def create_district(
    body: CreateDistrictBody,
    current_user: Annotated[dict, Depends(require_admin)],
):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="District name is required")
    district_id = str(uuid.uuid4())
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM districts WHERE name = ?", (name,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="District already exists")
        conn.execute("INSERT INTO districts (id, name, is_active) VALUES (?, ?, TRUE)", (district_id, name))
        audit_log_insert(conn, "district.create", "district", district_id, user_id=current_user["id"])
        row = conn.execute("SELECT id, name, is_active, created_at FROM districts WHERE id = ?", (district_id,)).fetchone()
    return _district_row_to_dict(dict(row))


@router.patch("/admin/districts/{district_id}")
def update_district(
    district_id: str,
    body: UpdateDistrictBody,
    current_user: Annotated[dict, Depends(require_admin)],
):
    updates = []
    params: list = []
    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="District name cannot be empty")
        updates.append("name = ?")
        params.append(name)
    if body.is_active is not None:
        updates.append("is_active = ?")
        params.append(bool(body.is_active))
    if not updates:
        with get_db() as conn:
            row = conn.execute("SELECT id, name, is_active, created_at FROM districts WHERE id = ?", (district_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="District not found")
        return _district_row_to_dict(dict(row))

    params.append(district_id)
    with get_db() as conn:
        row = conn.execute("SELECT id FROM districts WHERE id = ?", (district_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="District not found")
        if body.name is not None:
            existing = conn.execute("SELECT id FROM districts WHERE name = ? AND id != ?", (body.name.strip(), district_id)).fetchone()
            if existing:
                raise HTTPException(status_code=400, detail="District name already exists")
        conn.execute("UPDATE districts SET " + ", ".join(updates) + " WHERE id = ?", params)
        audit_log_insert(conn, "district.update", "district", district_id, user_id=current_user["id"])
        row = conn.execute("SELECT id, name, is_active, created_at FROM districts WHERE id = ?", (district_id,)).fetchone()
    return _district_row_to_dict(dict(row))


@router.get("/admin/districts/{district_id}/stations")
def list_stations_for_district(
    district_id: str,
    current_user: Annotated[dict, Depends(require_admin)],
    is_active: int | None = Query(default=None),
):
    with get_db() as conn:
        q = "SELECT id, district_id, name, is_active, created_at FROM police_stations WHERE district_id = ?"
        params: list = [district_id]
        if is_active is not None:
            q += " AND is_active = ?"
            params.append(bool(is_active))
        q += " ORDER BY name ASC"
        rows = conn.execute(q, params).fetchall()
    return [_station_row_to_dict(r) for r in rows]


@router.post("/admin/districts/{district_id}/stations", status_code=status.HTTP_201_CREATED)
def create_station(
    district_id: str,
    body: CreateStationBody,
    current_user: Annotated[dict, Depends(require_admin)],
):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Station name is required")
    station_id = str(uuid.uuid4())
    with get_db() as conn:
        district = conn.execute("SELECT id FROM districts WHERE id = ?", (district_id,)).fetchone()
        if not district:
            raise HTTPException(status_code=404, detail="District not found")
        existing = conn.execute(
            "SELECT id FROM police_stations WHERE district_id = ? AND name = ?",
            (district_id, name),
        ).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Police station already exists in this district")
        conn.execute(
            "INSERT INTO police_stations (id, district_id, name, is_active) VALUES (?, ?, ?, TRUE)",
            (station_id, district_id, name),
        )
        audit_log_insert(conn, "station.create", "police_station", station_id, user_id=current_user["id"])
        row = conn.execute(
            "SELECT id, district_id, name, is_active, created_at FROM police_stations WHERE id = ?",
            (station_id,),
        ).fetchone()
    return _station_row_to_dict(dict(row))


@router.patch("/admin/stations/{station_id}")
def update_station(
    station_id: str,
    body: UpdateStationBody,
    current_user: Annotated[dict, Depends(require_admin)],
):
    updates = []
    params: list = []
    new_district_id = None
    if body.district_id is not None:
        new_district_id = body.district_id.strip()
        if not new_district_id:
            raise HTTPException(status_code=400, detail="district_id cannot be empty")
        updates.append("district_id = ?")
        params.append(new_district_id)
    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Station name cannot be empty")
        updates.append("name = ?")
        params.append(name)
    if body.is_active is not None:
        updates.append("is_active = ?")
        params.append(bool(body.is_active))
    if not updates:
        with get_db() as conn:
            row = conn.execute(
                "SELECT id, district_id, name, is_active, created_at FROM police_stations WHERE id = ?",
                (station_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Police station not found")
        return _station_row_to_dict(dict(row))

    with get_db() as conn:
        existing_station = conn.execute(
            "SELECT id, district_id, name FROM police_stations WHERE id = ?",
            (station_id,),
        ).fetchone()
        if not existing_station:
            raise HTTPException(status_code=404, detail="Police station not found")

        target_district_id = new_district_id or existing_station["district_id"]
        if new_district_id:
            district = conn.execute("SELECT id FROM districts WHERE id = ?", (new_district_id,)).fetchone()
            if not district:
                raise HTTPException(status_code=404, detail="District not found")

        target_name = (body.name.strip() if body.name is not None else existing_station["name"])
        dup = conn.execute(
            "SELECT id FROM police_stations WHERE district_id = ? AND name = ? AND id != ?",
            (target_district_id, target_name, station_id),
        ).fetchone()
        if dup:
            raise HTTPException(status_code=400, detail="Police station already exists in this district")

        params.append(station_id)
        conn.execute("UPDATE police_stations SET " + ", ".join(updates) + " WHERE id = ?", params)
        audit_log_insert(conn, "station.update", "police_station", station_id, user_id=current_user["id"])
        row = conn.execute(
            "SELECT id, district_id, name, is_active, created_at FROM police_stations WHERE id = ?",
            (station_id,),
        ).fetchone()
    return _station_row_to_dict(dict(row))


# ─── UI BODY (SUBMISSIONS) — admin only ──────────────────────────────────────

FACE_CONDITIONS = frozenset({"normal", "partial", "bloated", "damaged"})
SUBMISSION_STATUSES = frozenset({"captured", "pending_review", "under_review", "confirmed", "closed", "archived"})


class AdminSubmissionUpdateBody(BaseModel):
    attributes_manual: dict | None = None
    attributes_ai: dict | None = None
    face_condition: str | None = None
    status: str | None = None

    @field_validator("face_condition")
    @classmethod
    def valid_face_condition(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in FACE_CONDITIONS:
            raise ValueError(f"face_condition must be one of {sorted(FACE_CONDITIONS)}")
        return v

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in SUBMISSION_STATUSES:
            raise ValueError(f"status must be one of {sorted(SUBMISSION_STATUSES)}")
        return v


def _delete_submission_related(conn, submission_id: str) -> list[str]:
    """Remove matches/feedback and return image relative paths for storage cleanup."""
    match_rows = conn.execute("SELECT id FROM matches WHERE submission_id = ?", (submission_id,)).fetchall()
    for r in match_rows:
        conn.execute("DELETE FROM feedback WHERE match_id = ?", (r["id"],))
    conn.execute("DELETE FROM matches WHERE submission_id = ?", (submission_id,))

    ref_match_rows = conn.execute(
        "SELECT id FROM matches WHERE reference_person_id = ?", (submission_id,)
    ).fetchall()
    for r in ref_match_rows:
        conn.execute("DELETE FROM feedback WHERE match_id = ?", (r["id"],))
    conn.execute("DELETE FROM matches WHERE reference_person_id = ?", (submission_id,))

    img_rows = conn.execute("SELECT path FROM images WHERE submission_id = ?", (submission_id,)).fetchall()
    paths = [row["path"] for row in img_rows]
    conn.execute("DELETE FROM images WHERE submission_id = ?", (submission_id,))
    conn.execute("DELETE FROM submissions WHERE id = ?", (submission_id,))
    return paths


@router.get("/admin/submissions")
def admin_list_submissions(
    current_user: Annotated[dict, Depends(require_admin)],
    q: str | None = Query(default=None, description="Search id or attributes text"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    search = (q or "").strip()
    where_sql = " WHERE 1=1 "
    params: list = []
    if search:
        term = f"%{search}%"
        where_sql += " AND (s.id LIKE ? OR COALESCE(s.attributes_manual,'') LIKE ? OR COALESCE(s.attributes_ai,'') LIKE ?) "
        params.extend([term, term, term])

    count_sql = f"SELECT COUNT(*) AS c FROM submissions s {where_sql}"
    list_sql = f"""
        SELECT s.id, s.created_at, s.status, s.face_condition,
               (SELECT COUNT(*) FROM images i WHERE i.submission_id = s.id) AS image_count
        FROM submissions s
        {where_sql}
        ORDER BY s.created_at DESC
        LIMIT ? OFFSET ?
    """.strip()
    params_list = list(params) + [limit, offset]

    with get_db() as conn:
        total = conn.execute(count_sql, params).fetchone()["c"]
        rows = conn.execute(list_sql, params_list).fetchall()

    items = [
        {
            "id": r["id"],
            "created_at": r["created_at"],
            "status": r["status"],
            "face_condition": r["face_condition"],
            "image_count": r["image_count"],
        }
        for r in rows
    ]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/admin/submissions/{submission_id}")
def admin_get_submission(
    submission_id: str,
    current_user: Annotated[dict, Depends(require_admin)],
):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Submission not found")
        images = conn.execute(
            "SELECT id, image_type, path, embedding_confidence, quality_score FROM images WHERE submission_id = ? ORDER BY created_at ASC",
            (submission_id,),
        ).fetchall()
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "attributes_ai": json.loads(row["attributes_ai"] or "{}"),
        "attributes_manual": json.loads(row["attributes_manual"] or "{}"),
        "face_condition": row["face_condition"],
        "status": row["status"],
        "images": [
            {
                "id": r["id"],
                "image_type": r["image_type"],
                "path": get_url_path(r["path"], is_reference=False),
                "embedding_confidence": r["embedding_confidence"],
                "quality_score": dict(r).get("quality_score"),
            }
            for r in images
        ],
    }


@router.patch("/admin/submissions/{submission_id}")
def admin_update_submission(
    submission_id: str,
    body: AdminSubmissionUpdateBody,
    current_user: Annotated[dict, Depends(require_admin)],
):
    updates: list[str] = []
    vals: list = []
    if body.attributes_manual is not None:
        updates.append("attributes_manual = ?")
        vals.append(json.dumps(body.attributes_manual))
    if body.attributes_ai is not None:
        updates.append("attributes_ai = ?")
        vals.append(json.dumps(body.attributes_ai))
    if body.face_condition is not None:
        updates.append("face_condition = ?")
        vals.append(body.face_condition)
    if body.status is not None:
        updates.append("status = ?")
        vals.append(body.status)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    vals.append(submission_id)
    with get_db() as conn:
        row = conn.execute("SELECT id FROM submissions WHERE id = ?", (submission_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Submission not found")
        conn.execute(
            f"UPDATE submissions SET {', '.join(updates)} WHERE id = ?",
            vals,
        )
        audit_log_insert(conn, "submission.admin_update", "submission", submission_id, user_id=current_user["id"])

    with get_db() as conn:
        row = conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()
        images = conn.execute(
            "SELECT id, image_type, path, embedding_confidence, quality_score FROM images WHERE submission_id = ? ORDER BY created_at ASC",
            (submission_id,),
        ).fetchall()
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "attributes_ai": json.loads(row["attributes_ai"] or "{}"),
        "attributes_manual": json.loads(row["attributes_manual"] or "{}"),
        "face_condition": row["face_condition"],
        "status": row["status"],
        "images": [
            {
                "id": r["id"],
                "image_type": r["image_type"],
                "path": get_url_path(r["path"], is_reference=False),
                "embedding_confidence": r["embedding_confidence"],
                "quality_score": dict(r).get("quality_score"),
            }
            for r in images
        ],
    }


@router.delete("/admin/submissions/{submission_id}")
def admin_delete_submission(
    submission_id: str,
    current_user: Annotated[dict, Depends(require_admin)],
):
    path_list: list[str] = []
    with get_db() as conn:
        row = conn.execute("SELECT id FROM submissions WHERE id = ?", (submission_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Submission not found")
        path_list = _delete_submission_related(conn, submission_id)
        audit_log_insert(conn, "submission.admin_delete", "submission", submission_id, user_id=current_user["id"])

    qdrant_client.delete_by_submission(submission_id)
    for path in path_list:
        delete_file(path, is_reference=False)

    return {"deleted": True, "id": submission_id}
