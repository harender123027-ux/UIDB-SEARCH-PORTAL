import uuid

from app.auth import hash_password
from app.database import get_db, init_db


def _seed_admin_and_login(client) -> str:
    init_db()
    admin_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute("DELETE FROM users WHERE username = ?", ("admin_geo_test",))
        conn.execute(
            "INSERT INTO users (id, username, password_hash, name, role, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            (admin_id, "admin_geo_test", hash_password("adminpass"), "Admin", "admin"),
        )
    r = client.post("/api/auth/login", json={"username": "admin_geo_test", "password": "adminpass"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _seed_investigator_and_login(client) -> str:
    init_db()
    user_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute("DELETE FROM users WHERE username = ?", ("officer_geo_test",))
        conn.execute(
            "INSERT INTO users (id, username, password_hash, name, role, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            (user_id, "officer_geo_test", hash_password("officerpass"), "Officer", "investigator"),
        )
    r = client.post("/api/auth/login", json={"username": "officer_geo_test", "password": "officerpass"})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_admin_mapping_requires_admin(client):
    token = _seed_investigator_and_login(client)
    r = client.get("/api/admin/districts", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_admin_can_create_district_and_station_and_lookups_work(client):
    admin_token = _seed_admin_and_login(client)

    # Create district
    r = client.post(
        "/api/admin/districts",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "TestDistrict"},
    )
    assert r.status_code == 201
    district = r.json()
    assert district["name"] == "TestDistrict"
    district_id = district["id"]

    # Create station
    r = client.post(
        f"/api/admin/districts/{district_id}/stations",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "TestPS"},
    )
    assert r.status_code == 201
    station = r.json()
    assert station["name"] == "TestPS"
    assert station["district_id"] == district_id

    # Non-admin can access lookups when authenticated
    investigator_token = _seed_investigator_and_login(client)
    r = client.get("/api/geo/districts", headers={"Authorization": f"Bearer {investigator_token}"})
    assert r.status_code == 200
    assert any(d["id"] == district_id for d in r.json())

    r = client.get(f"/api/geo/districts/{district_id}/stations", headers={"Authorization": f"Bearer {investigator_token}"})
    assert r.status_code == 200
    assert any(s["name"] == "TestPS" for s in r.json())


def test_user_district_station_validation(client):
    admin_token = _seed_admin_and_login(client)

    d1 = client.post("/api/admin/districts", headers={"Authorization": f"Bearer {admin_token}"}, json={"name": "D1"}).json()
    d2 = client.post("/api/admin/districts", headers={"Authorization": f"Bearer {admin_token}"}, json={"name": "D2"}).json()
    s1 = client.post(f"/api/admin/districts/{d1['id']}/stations", headers={"Authorization": f"Bearer {admin_token}"}, json={"name": "S1"}).json()

    # station_id without district_id should fail
    r = client.post(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"username": "u1", "password": "pass", "name": "U1", "role": "investigator", "station_id": s1["id"]},
    )
    assert r.status_code == 400

    # mismatch district/station should fail
    r = client.post(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"username": "u2", "password": "pass", "name": "U2", "role": "investigator", "district_id": d2["id"], "station_id": s1["id"]},
    )
    assert r.status_code == 400

