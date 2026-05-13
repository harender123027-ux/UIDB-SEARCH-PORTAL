import uuid

from app.database import get_db, init_db
from app.services import qdrant_client


def test_matching_thresholds(client, auth_headers):
    """
    Matches are filtered by FACE_MATCH_THRESHOLD_MEDIUM and assigned confidence_level.
    """
    init_db()
    qdrant_client.ensure_collection()

    submission_id = str(uuid.uuid4())
    ref_high = str(uuid.uuid4())
    ref_med = str(uuid.uuid4())
    ref_low = str(uuid.uuid4())

    import app.routers.match as match_router

    original_search = match_router.qdrant_client.search_all
    original_get = match_router.qdrant_client.get_vectors_by_submission

    try:
        match_router.qdrant_client.get_vectors_by_submission = lambda _id: [
            {
                "vector": [0] * 512,
                "id": "p1",
                "payload": {"embedding_confidence": 0.99},
            }
        ]
        match_router.qdrant_client.search_all = lambda v, limit: [
            {"id": "r1", "score": 0.9, "payload": {"reference_person_id": ref_high, "quality_score": 12.0}},
            {"id": "r2", "score": 0.4, "payload": {"reference_person_id": ref_med, "quality_score": 8.0}},
            {"id": "r3", "score": 0.2, "payload": {"reference_person_id": ref_low}},
        ]

        with get_db() as conn:
            conn.execute("INSERT INTO submissions (id) VALUES (?)", (submission_id,))
            conn.execute("INSERT INTO reference_persons (id, label) VALUES (?, ?)", (ref_high, "High"))
            conn.execute("INSERT INTO reference_persons (id, label) VALUES (?, ?)", (ref_med, "Medium"))
            conn.execute("INSERT INTO reference_persons (id, label) VALUES (?, ?)", (ref_low, "Low"))

        r = client.post(f"/api/submissions/{submission_id}/match", headers=auth_headers)
        assert r.status_code == 200
        matches = r.json()["matches"]

        assert len(matches) == 2

        assert matches[0]["reference_person_id"] == ref_high
        assert matches[0]["confidence_level"] == "high"
        assert matches[0]["quality_score"] == 12.0

        assert matches[1]["reference_person_id"] == ref_med
        assert matches[1]["confidence_level"] == "medium"
        assert matches[1]["quality_score"] == 8.0

    finally:
        match_router.qdrant_client.search_all = original_search
        match_router.qdrant_client.get_vectors_by_submission = original_get
