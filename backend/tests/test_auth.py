"""Tests for auth (login) and admin (user management) endpoints."""
import uuid

from app.auth import hash_password
from app.database import get_db, init_db


def _seed_test_users():
    init_db()
    admin_id = str(uuid.uuid4())
    investigator_id = str(uuid.uuid4())
    investigator2_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute("DELETE FROM users WHERE username IN ('admin_test', 'officer_test', 'investigator_test')")
        conn.execute(
            "INSERT INTO users (id, username, password_hash, name, role, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            (admin_id, "admin_test", hash_password("adminpass"), "Admin User", "admin"),
        )
        conn.execute(
            "INSERT INTO users (id, username, password_hash, name, role, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            (investigator_id, "officer_test", hash_password("officerpass"), "Officer User", "investigator"),
        )
        conn.execute(
            "INSERT INTO users (id, username, password_hash, name, role, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            (investigator2_id, "investigator_test", hash_password("investigatorpass"), "Investigator User", "investigator"),
        )
    return admin_id, investigator_id, investigator2_id


def test_login_success(client):
    _seed_test_users()
    r = client.post("/api/auth/login", json={"username": "admin_test", "password": "adminpass"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "admin_test"
    assert data["user"]["role"] == "admin"


def test_login_invalid_credentials(client):
    _seed_test_users()
    r = client.post("/api/auth/login", json={"username": "admin_test", "password": "wrong"})
    assert r.status_code == 401
    r = client.post("/api/auth/login", json={"username": "nobody", "password": "any"})
    assert r.status_code == 401


def test_admin_users_requires_auth(client):
    _seed_test_users()
    r = client.get("/api/admin/users")
    assert r.status_code == 401  # no Bearer -> 401 Unauthorized


def test_admin_users_requires_admin_role(client):
    _seed_test_users()
    login_r = client.post("/api/auth/login", json={"username": "officer_test", "password": "officerpass"})
    assert login_r.status_code == 200
    token = login_r.json()["access_token"]
    r = client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_admin_users_success(client):
    _seed_test_users()
    login_r = client.post("/api/auth/login", json={"username": "admin_test", "password": "adminpass"})
    assert login_r.status_code == 200
    token = login_r.json()["access_token"]
    r = client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    users = r.json()
    assert isinstance(users, list)
    usernames = [u["username"] for u in users]
    assert "admin_test" in usernames
    assert "officer_test" in usernames


def _login(client, username: str, password: str) -> str:
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_create_submission_requires_auth(client, sample_jpeg):
    _seed_test_users()
    r = client.post(
        "/api/submissions",
        data={"image_types": '["face_frontal"]'},
        files=[("files", ("face.jpg", sample_jpeg, "image/jpeg"))],
    )
    assert r.status_code == 401


def test_create_submission_requires_investigator_or_admin(client, sample_jpeg):
    _seed_test_users()

    # Both investigator and admin can create submissions
    investigator_token = _login(client, "officer_test", "officerpass")
    r = client.post(
        "/api/submissions",
        headers={"Authorization": f"Bearer {investigator_token}"},
        data={"image_types": '["face_frontal"]'},
        files=[("files", ("face.jpg", sample_jpeg, "image/jpeg"))],
    )
    assert r.status_code == 200

    investigator_token2 = _login(client, "investigator_test", "investigatorpass")
    r = client.post(
        "/api/submissions",
        headers={"Authorization": f"Bearer {investigator_token2}"},
        data={"image_types": '["face_frontal"]'},
        files=[("files", ("face.jpg", sample_jpeg, "image/jpeg"))],
    )
    assert r.status_code == 200

    admin_token = _login(client, "admin_test", "adminpass")
    r = client.post(
        "/api/submissions",
        headers={"Authorization": f"Bearer {admin_token}"},
        data={"image_types": '["face_frontal"]'},
        files=[("files", ("face.jpg", sample_jpeg, "image/jpeg"))],
    )
    assert r.status_code == 200
