import uuid

from app.auth import hash_password
from app.database import get_db, init_db


def _seed_investigator(client) -> str:
    init_db()
    user_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute("DELETE FROM users WHERE username = ?", ("investigator_test",))
        conn.execute(
            "INSERT INTO users (id, username, password_hash, name, role, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            (user_id, "investigator_test", hash_password("investigatorpass"), "Investigator User", "investigator"),
        )
    r = client.post("/api/auth/login", json={"username": "investigator_test", "password": "investigatorpass"})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_create_submission(client, sample_jpeg):
    token = _seed_investigator(client)
    files = [("files", ("face.jpg", sample_jpeg, "image/jpeg"))]
    data = {
        "image_types": '["face_frontal"]',
        "attributes_ai": "{}",
        "attributes_manual": "{}",
        "face_condition": "normal",
    }
    r = client.post("/api/submissions", files=files, data=data, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "submission_id" in body
    assert "images" in body
    assert len(body["images"]) >= 1


def test_list_submissions(client, sample_jpeg, auth_headers):
    r = client.get("/api/submissions", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_submission(client, sample_jpeg):
    token = _seed_investigator(client)
    files = [("files", ("face.jpg", sample_jpeg, "image/jpeg"))]
    data = {"image_types": '["face_frontal"]', "attributes_ai": "{}", "attributes_manual": "{}"}
    create = client.post("/api/submissions", files=files, data=data, headers={"Authorization": f"Bearer {token}"})
    sid = create.json()["submission_id"]
    r = client.get(f"/api/submissions/{sid}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["id"] == sid
    assert "images" in r.json()


def test_get_submission_404(client, auth_headers):
    r = client.get("/api/submissions/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert r.status_code == 404


def test_face_frontal_without_face_is_rejected(client, sample_jpeg, monkeypatch):
    """A face-slot upload that produces no face embedding must be rejected
    with 422 when face_condition is 'normal' — the system must not silently
    accept blank/faceless photos as valid registrations."""
    import app.routers.submissions as submissions_module

    monkeypatch.setattr(submissions_module, "extract_embeddings_from_bytes", lambda *a, **kw: [])

    token = _seed_investigator(client)
    files = [("files", ("blank.jpg", sample_jpeg, "image/jpeg"))]
    data = {
        "image_types": '["face_frontal"]',
        "attributes_ai": "{}",
        "attributes_manual": "{}",
        "face_condition": "normal",
    }
    r = client.post(
        "/api/submissions", files=files, data=data,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422, r.text
    detail = (r.json().get("detail") or "").lower()
    assert "no face" in detail
    assert "face frontal" in detail


def test_face_frontal_without_face_allowed_when_damaged(client, sample_jpeg, monkeypatch):
    """When face_condition is set to 'damaged' (or any non-normal value),
    a face-slot upload with no detectable face must still be accepted, so
    operators are not blocked from registering decomposed/burnt cases."""
    import app.routers.submissions as submissions_module

    monkeypatch.setattr(submissions_module, "extract_embeddings_from_bytes", lambda *a, **kw: [])

    token = _seed_investigator(client)
    files = [("files", ("damaged.jpg", sample_jpeg, "image/jpeg"))]
    data = {
        "image_types": '["face_frontal"]',
        "attributes_ai": "{}",
        "attributes_manual": "{}",
        "face_condition": "damaged",
    }
    r = client.post(
        "/api/submissions", files=files, data=data,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "submission_id" in body
