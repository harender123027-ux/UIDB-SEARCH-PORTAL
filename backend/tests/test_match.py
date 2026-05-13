def test_match_requires_submission(client, auth_headers):
    r = client.post(
        "/api/submissions/00000000-0000-0000-0000-000000000000/match",
        headers=auth_headers,
    )
    assert r.status_code == 404


def test_upload_and_match_anonymous(client, sample_jpeg):
    files = [("files", ("face.jpg", sample_jpeg, "image/jpeg"))]
    data = {"image_types": '["face_frontal"]'}
    r = client.post("/api/upload-and-match", files=files, data=data)
    assert r.status_code == 200
    body = r.json()
    assert "submission_id" in body
    assert "matches" in body
    assert isinstance(body["matches"], list)


def test_upload_and_match(client, sample_jpeg, auth_headers):
    files = [("files", ("face.jpg", sample_jpeg, "image/jpeg"))]
    data = {"image_types": '["face_frontal"]'}
    r = client.post("/api/upload-and-match", files=files, data=data, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "submission_id" in body
    assert "matches" in body
    assert isinstance(body["matches"], list)


def test_matching_engine_same_image_returns_high_score(client, sample_jpeg, auth_headers):
    """Same image as reference and as submission should match with high score (validates pipeline)."""
    import json
    import uuid

    from app.database import get_db, init_db
    from app.services import qdrant_client
    from app.services.face_embedding import extract_embeddings_from_bytes
    init_db()
    qdrant_client.ensure_collection()
    embeddings = extract_embeddings_from_bytes(sample_jpeg, "face_frontal", enforce_detection=False)
    assert len(embeddings) >= 1, "embedding extraction should return at least one vector"
    emb_data = embeddings[0]
    emb = emb_data["embedding"]
    conf = emb_data["confidence"]
    qual = emb_data["quality"]

    ref_id = str(uuid.uuid4())
    point_id = str(uuid.uuid4())
    qdrant_client.upsert_points([{
        "id": point_id,
        "vector": emb,
        "payload": {
            "reference_person_id": ref_id,
            "image_type": "face_frontal",
            "is_missing_person": True,
            "embedding_confidence": conf,
            "quality_score": qual,
        },
    }])
    with get_db() as conn:
        conn.execute(
            "INSERT INTO reference_persons (id, label, photo_path, attributes) VALUES (?, ?, ?, ?)",
            (ref_id, "Reference test", "ref.jpg", json.dumps({})),
        )

    files = [("files", ("face.jpg", sample_jpeg, "image/jpeg"))]
    data = {"image_types": '["face_frontal"]'}
    r = client.post("/api/upload-and-match", files=files, data=data, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "matches" in body
    assert len(body["matches"]) >= 1, "same image as reference should produce at least one match"
    best = body["matches"][0]
    score = best.get("scores", {}).get("overall") or best.get("scores", {}).get("face") or 0
    assert score >= 0.5, f"same-image match score should be high (>= 0.5); got {score}"
    assert best.get("quality_score") is not None
