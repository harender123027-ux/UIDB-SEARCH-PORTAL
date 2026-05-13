def test_feedback_requires_valid_match(client, auth_headers):
    r = client.post(
        "/api/feedback",
        headers=auth_headers,
        json={
            "match_id": "00000000-0000-0000-0000-000000000000",
            "verdict": "incorrect_match",
            "action_taken": "none",
        },
    )
    assert r.status_code == 404


def test_feedback_anonymous_rate_limited(client, monkeypatch):
    import app.config as app_config

    monkeypatch.setattr(app_config, "FEEDBACK_ANONYMOUS_RATE_LIMIT", 3)
    monkeypatch.setattr(app_config, "FEEDBACK_ANONYMOUS_RATE_WINDOW_SEC", 60)
    import uuid

    from app.database import get_db

    mid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    ref_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute("INSERT INTO submissions (id) VALUES (?)", (sid,))
        conn.execute(
            "INSERT INTO reference_persons (id, label) VALUES (?, ?)",
            (ref_id, "Test Ref"),
        )
        conn.execute(
            "INSERT INTO matches (id, submission_id, reference_person_id, overall_score, face_score, rank) VALUES (?, ?, ?, ?, ?, ?)",
            (mid, sid, ref_id, 0.8, 0.8, 1),
        )
    payload = {
        "match_id": mid,
        "verdict": "incorrect_match",
        "action_taken": "none",
    }
    for _ in range(3):
        assert client.post("/api/feedback", json=payload).status_code == 200
    assert client.post("/api/feedback", json=payload).status_code == 429


def test_feedback_anonymous_success(client, sample_jpeg):
    """Feedback without login (reviewer_id null)."""
    import uuid

    from app.database import get_db

    mid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    ref_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute("INSERT INTO submissions (id) VALUES (?)", (sid,))
        conn.execute(
            "INSERT INTO reference_persons (id, label) VALUES (?, ?)",
            (ref_id, "Test Ref"),
        )
        conn.execute(
            "INSERT INTO matches (id, submission_id, reference_person_id, overall_score, face_score, rank) VALUES (?, ?, ?, ?, ?, ?)",
            (mid, sid, ref_id, 0.8, 0.8, 1),
        )
    r = client.post(
        "/api/feedback",
        json={
            "match_id": mid,
            "verdict": "incorrect_match",
            "face_assessment": "no_match",
            "action_taken": "none",
            "notes": "Anonymous note",
        },
    )
    assert r.status_code == 200
    assert "id" in r.json()


def test_feedback_authenticated_bypasses_anon_rate_limit(client, sample_jpeg, auth_headers, monkeypatch):
    import uuid

    import app.config as app_config
    from app.database import get_db

    monkeypatch.setattr(app_config, "FEEDBACK_ANONYMOUS_RATE_LIMIT", 2)
    mid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    ref_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute("INSERT INTO submissions (id) VALUES (?)", (sid,))
        conn.execute(
            "INSERT INTO reference_persons (id, label) VALUES (?, ?)",
            (ref_id, "Test Ref"),
        )
        conn.execute(
            "INSERT INTO matches (id, submission_id, reference_person_id, overall_score, face_score, rank) VALUES (?, ?, ?, ?, ?, ?)",
            (mid, sid, ref_id, 0.8, 0.8, 1),
        )
    payload = {
        "match_id": mid,
        "verdict": "incorrect_match",
        "action_taken": "none",
    }
    for _ in range(4):
        assert client.post("/api/feedback", headers=auth_headers, json=payload).status_code == 200


def test_feedback_success(client, sample_jpeg, auth_headers):
    import uuid

    from app.database import get_db

    mid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    ref_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute("INSERT INTO submissions (id) VALUES (?)", (sid,))
        conn.execute(
            "INSERT INTO reference_persons (id, label) VALUES (?, ?)",
            (ref_id, "Test Ref"),
        )
        conn.execute(
            "INSERT INTO matches (id, submission_id, reference_person_id, overall_score, face_score, rank) VALUES (?, ?, ?, ?, ?, ?)",
            (mid, sid, ref_id, 0.8, 0.8, 1),
        )
    r = client.post(
        "/api/feedback",
        headers=auth_headers,
        json={
            "match_id": mid,
            "verdict": "incorrect_match",
            "face_assessment": "no_match",
            "action_taken": "none",
            "notes": "Test note",
        },
    )
    assert r.status_code == 200
    assert "id" in r.json()
