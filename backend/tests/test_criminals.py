"""Tests for criminal records upload, listing, and photo retrieval."""
import io
import uuid

from app.auth import hash_password
from app.database import get_db, init_db

from tests.conftest import JPEG_BYTES


def _seed_test_user():
    """Seed a test admin user for criminal records tests."""
    init_db()
    user_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute("DELETE FROM users WHERE username = 'criminal_test_admin'")
        conn.execute(
            "INSERT INTO users (id, username, password_hash, name, role, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            (user_id, "criminal_test_admin", hash_password("testpass"), "Criminal Test Admin", "admin"),
        )
    return user_id


def _login(client, username: str, password: str) -> str:
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_upload_criminal_requires_auth(client):
    """Test that uploading a criminal record requires authentication."""
    _seed_test_user()
    data = {"name": "Test Criminal"}
    r = client.post("/api/criminals", data=data)
    assert r.status_code == 401


def test_upload_and_list_criminal(client):
    """Test uploading a criminal record with photo, listing, and retrieving photo."""
    _seed_test_user()
    token = _login(client, "criminal_test_admin", "testpass")
    headers = {"Authorization": f"Bearer {token}"}

    # Upload a criminal record with a photo
    files = {"photos": ("test.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")}
    data = {
        "name": "Test Criminal",
        "fir": "FIR123",
        "district": "Gurugram",
        "station": "DLF Phase 1",
        "arrest_date": "2026-03-22",
        "notes": "Test notes for criminal record"
    }
    resp = client.post("/api/criminals", data=data, files=files, headers=headers)
    assert resp.status_code == 200
    record_id = resp.json()["id"]
    assert record_id

    # List criminals and verify the new record is present
    resp = client.get("/api/criminals", headers=headers)
    assert resp.status_code == 200
    criminals = resp.json()
    found = [c for c in criminals if c["id"] == record_id]
    assert len(found) == 1
    rec = found[0]
    assert rec["name"] == "Test Criminal"
    assert rec["fir"] == "FIR123"
    assert rec["district"] == "Gurugram"
    assert rec["station"] == "DLF Phase 1"
    assert rec["arrest_date"] == "2026-03-22"
    assert rec["notes"] == "Test notes for criminal record"
    assert rec["photos"]

    # Retrieve the photo
    photo_name = rec["photos"][0]
    resp = client.get(f"/api/criminals/photo/{photo_name}", headers=headers)
    assert resp.status_code == 200
    assert resp.content == JPEG_BYTES


def test_upload_criminal_without_photo(client):
    """Test uploading a criminal record without a photo."""
    _seed_test_user()
    token = _login(client, "criminal_test_admin", "testpass")
    headers = {"Authorization": f"Bearer {token}"}

    data = {
        "name": "Criminal Without Photo",
        "fir": "FIR456",
        "district": "Faridabad",
        "station": "Ballabhgarh",
        "arrest_date": "2026-01-15",
        "notes": ""
    }
    resp = client.post("/api/criminals", data=data, headers=headers)
    assert resp.status_code == 200
    record_id = resp.json()["id"]

    # Verify record is listed
    resp = client.get("/api/criminals", headers=headers)
    assert resp.status_code == 200
    found = [c for c in resp.json() if c["id"] == record_id]
    assert len(found) == 1
    assert found[0]["photos"] == []


def test_upload_criminal_multiple_photos(client):
    """Test uploading a criminal record with multiple photos."""
    _seed_test_user()
    token = _login(client, "criminal_test_admin", "testpass")
    headers = {"Authorization": f"Bearer {token}"}

    # Upload with multiple photos
    files = [
        ("photos", ("photo1.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")),
        ("photos", ("photo2.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")),
        ("photos", ("photo3.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")),
    ]
    data = {
        "name": "Criminal With Multiple Photos",
        "fir": "FIR789",
        "district": "Rohtak",
        "station": "Rohtak City",
        "arrest_date": "2026-02-10",
        "notes": "Multiple mugshots"
    }
    resp = client.post("/api/criminals", data=data, files=files, headers=headers)
    assert resp.status_code == 200
    record_id = resp.json()["id"]

    # Verify all photos are stored
    resp = client.get("/api/criminals", headers=headers)
    assert resp.status_code == 200
    found = [c for c in resp.json() if c["id"] == record_id]
    assert len(found) == 1
    assert len(found[0]["photos"]) == 3


def test_get_criminal_photo_not_found(client):
    """Test that requesting a non-existent photo returns 404."""
    _seed_test_user()
    token = _login(client, "criminal_test_admin", "testpass")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/criminals/photo/nonexistent.jpg", headers=headers)
    assert resp.status_code == 404


def test_list_criminals_requires_auth(client):
    """Test that listing criminals requires authentication."""
    resp = client.get("/api/criminals")
    assert resp.status_code == 401
