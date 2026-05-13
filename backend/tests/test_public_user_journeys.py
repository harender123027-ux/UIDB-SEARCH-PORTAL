"""
Journey tests: anonymous + public_user JWT can search UI bodies; police-only routes stay blocked for public_user.

Police roles keep access to submissions list, dashboard, geo, criminals, bulk search.
"""
import json
import uuid

from app.database import get_db, init_db
from app.services import qdrant_client
from app.services.face_embedding import extract_embeddings_from_bytes

from tests.test_auth import _login, _seed_test_users


def test_anonymous_upload_and_match_ui_body_target(client, sample_jpeg):
    files = [("files", ("loved_one.jpg", sample_jpeg, "image/jpeg"))]
    data = {"image_types": '["face_frontal"]', "search_target": "ui_body"}
    r = client.post("/api/upload-and-match", files=files, data=data)
    assert r.status_code == 200
    out = r.json()
    assert "submission_id" in out
    assert "matches" in out
    assert isinstance(out["matches"], list)


def test_anonymous_match_same_image_high_score(client, sample_jpeg):
    init_db()
    qdrant_client.ensure_collection()
    embeddings = extract_embeddings_from_bytes(sample_jpeg, "face_frontal", enforce_detection=False)
    assert len(embeddings) >= 1
    ref_id = str(uuid.uuid4())
    point_id = str(uuid.uuid4())
    emb_data = embeddings[0]
    qdrant_client.upsert_points([
        {
            "id": point_id,
            "vector": emb_data["embedding"],
            "payload": {
                "reference_person_id": ref_id,
                "image_type": "face_frontal",
                "is_missing_person": True,
                "embedding_confidence": emb_data["confidence"],
                "quality_score": emb_data["quality"],
            },
        }
    ])
    with get_db() as conn:
        conn.execute(
            "INSERT INTO reference_persons (id, label, photo_path, attributes) VALUES (?, ?, ?, ?)",
            (ref_id, "Missing person ref", "x.jpg", json.dumps({})),
        )
    files = [("files", ("q.jpg", sample_jpeg, "image/jpeg"))]
    r = client.post(
        "/api/upload-and-match",
        files=files,
        data={"image_types": '["face_frontal"]', "search_target": "all"},
    )
    assert r.status_code == 200
    matches = r.json().get("matches") or []
    assert len(matches) >= 1
    assert matches[0].get("scores", {}).get("overall", 0) >= 0.5


def test_anonymous_get_reference_person(client, sample_jpeg):
    init_db()
    sid = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            "INSERT INTO submissions (id, attributes_manual, face_condition, status) VALUES (?, ?, ?, ?)",
            (sid, json.dumps({"note": "test"}), "normal", "captured"),
        )
        conn.execute(
            "INSERT INTO images (id, submission_id, image_type, path) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), sid, "face_frontal", "t/p.jpg"),
        )
    r = client.get(f"/api/reference_persons/{sid}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == sid
    assert body.get("label") == "UI Body (Submission)"


def test_public_blocked_submissions_list(client, public_headers):
    assert client.get("/api/submissions", headers=public_headers).status_code == 403


def test_public_blocked_submission_detail(client, public_headers):
    sid = str(uuid.uuid4())
    assert client.get(f"/api/submissions/{sid}", headers=public_headers).status_code == 403


def test_public_blocked_dashboard(client, public_headers):
    assert client.get("/api/dashboard", headers=public_headers).status_code == 403


def test_public_blocked_audit(client, public_headers):
    assert client.get("/api/audit", headers=public_headers).status_code == 403


def test_public_blocked_geo(client, public_headers):
    assert client.get("/api/geo/districts", headers=public_headers).status_code == 403


def test_public_blocked_search_all(client, public_headers):
    assert client.post("/api/search/all", headers=public_headers).status_code == 403


def test_public_blocked_criminals_list(client, public_headers):
    assert client.get("/api/criminals", headers=public_headers).status_code == 403


def test_public_blocked_create_submission(client, public_headers, sample_jpeg):
    r = client.post(
        "/api/submissions",
        headers=public_headers,
        data={"image_types": '["face_frontal"]', "attributes_ai": "{}", "attributes_manual": "{}"},
        files=[("files", ("a.jpg", sample_jpeg, "image/jpeg"))],
    )
    assert r.status_code == 403


def test_public_blocked_admin_users(client, public_headers):
    assert client.get("/api/admin/users", headers=public_headers).status_code == 403


def test_investigator_can_list_submissions(client, sample_jpeg):
    _seed_test_users()
    token = _login(client, "officer_test", "officerpass")
    h = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/submissions", headers=h).status_code == 200


def test_investigator_journey_create_and_list(client, sample_jpeg):
    _seed_test_users()
    token = _login(client, "investigator_test", "investigatorpass")
    h = {"Authorization": f"Bearer {token}"}
    rCreate = client.post(
        "/api/submissions",
        headers=h,
        data={"image_types": '["face_frontal"]', "attributes_ai": "{}", "attributes_manual": "{}"},
        files=[("files", ("a.jpg", sample_jpeg, "image/jpeg"))],
    )
    assert rCreate.status_code == 200
    rList = client.get("/api/submissions", headers=h)
    assert rList.status_code == 200
    assert len(rList.json()) >= 1
