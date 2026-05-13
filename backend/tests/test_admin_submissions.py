"""Admin UI body (submission) management API."""
import uuid

from app.auth import hash_password
from app.database import get_db, init_db


def _admin_token(client):
    init_db()
    user_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute("DELETE FROM users WHERE username = ?", ("admin_ui_body_test",))
        conn.execute(
            "INSERT INTO users (id, username, password_hash, name, role, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            (user_id, "admin_ui_body_test", hash_password("adminpass"), "Admin", "admin"),
        )
    r = client.post("/api/auth/login", json={"username": "admin_ui_body_test", "password": "adminpass"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _inv_token(client):
    init_db()
    user_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute("DELETE FROM users WHERE username = ?", ("inv_ui_body_test",))
        conn.execute(
            "INSERT INTO users (id, username, password_hash, name, role, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            (user_id, "inv_ui_body_test", hash_password("invpass"), "Inv", "investigator"),
        )
    r = client.post("/api/auth/login", json={"username": "inv_ui_body_test", "password": "invpass"})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_admin_submissions_list_requires_admin(client):
    inv = _inv_token(client)
    r = client.get("/api/admin/submissions", headers={"Authorization": f"Bearer {inv}"})
    assert r.status_code == 403


def test_admin_submissions_crud(client):
    token = _admin_token(client)
    h = {"Authorization": f"Bearer {token}"}
    sid = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            "INSERT INTO submissions (id, attributes_manual, attributes_ai, face_condition, status) VALUES (?, ?, ?, ?, ?)",
            (sid, "{}", '{"x":1}', "normal", "captured"),
        )
        conn.execute(
            "INSERT INTO images (id, submission_id, image_type, path) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), sid, "face_frontal", "test/path.jpg"),
        )

    r = client.get("/api/admin/submissions", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    assert any(x["id"] == sid for x in data["items"])

    r = client.get(f"/api/admin/submissions/{sid}", headers=h)
    assert r.status_code == 200
    assert r.json()["id"] == sid
    assert r.json()["attributes_ai"]["x"] == 1

    r = client.patch(
        f"/api/admin/submissions/{sid}",
        headers=h,
        json={"attributes_manual": {"note": "updated"}, "status": "under_review"},
    )
    assert r.status_code == 200
    assert r.json()["attributes_manual"]["note"] == "updated"
    assert r.json()["status"] == "under_review"

    r = client.delete(f"/api/admin/submissions/{sid}", headers=h)
    assert r.status_code == 200
    assert r.json()["deleted"] is True

    r = client.get(f"/api/admin/submissions/{sid}", headers=h)
    assert r.status_code == 404
