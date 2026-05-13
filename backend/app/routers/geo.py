from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth import require_police_portal_user
from app.database import get_db

router = APIRouter()


def _district_row_to_dict(row) -> dict:
    return {"id": row["id"], "name": row["name"]}


def _station_row_to_dict(row) -> dict:
    return {"id": row["id"], "district_id": row["district_id"], "name": row["name"]}


@router.get("/geo/districts")
def list_active_districts(
    _: Annotated[dict, Depends(require_police_portal_user)],
):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, name FROM districts WHERE is_active = TRUE ORDER BY name ASC"
        ).fetchall()
    return [_district_row_to_dict(r) for r in rows]


@router.get("/geo/districts/{district_id}/stations")
def list_active_stations(
    district_id: str,
    _: Annotated[dict, Depends(require_police_portal_user)],
):
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, district_id, name
            FROM police_stations
            WHERE district_id = ? AND is_active = TRUE
            ORDER BY name ASC
            """,
            (district_id,),
        ).fetchall()
    return [_station_row_to_dict(r) for r in rows]
