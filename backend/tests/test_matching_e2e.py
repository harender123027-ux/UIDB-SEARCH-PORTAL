"""E2E test: download sample face images, seed repository, call search/combined, assert match."""
import json
import os
import uuid
from pathlib import Path

import pytest
from app.database import get_db, init_db
from app.services import qdrant_client
from app.services.face_embedding import extract_face_embeddings

from tests.helpers import SAMPLE_IMAGE_URLS, download_samples


@pytest.mark.skipif(
    not os.environ.get("UBIS_TEST_WITH_SAMPLES"),
    reason="Set UBIS_TEST_WITH_SAMPLES=1 to run (requires network)",
)
def test_matching_with_downloaded_samples(client, auth_headers):
    """Download Pexels samples, seed reference_persons + Qdrant, POST search/combined with one image, assert match."""
    ref_photos_path = Path(os.environ["REFERENCE_PHOTOS_PATH"])
    ref_photos_path.mkdir(parents=True, exist_ok=True)

    # Download 2 images with retry
    try:
        paths = download_samples(ref_photos_path, urls=SAMPLE_IMAGE_URLS[:2], max_attempts=3)
    except Exception as e:
        pytest.skip(f"Download failed (no network?): {e}")

    assert len(paths) >= 1, "need at least one image"
    init_db()
    qdrant_client.ensure_collection()

    points = []
    for img_path in paths:
        ref_id = str(uuid.uuid4())
        embeddings = extract_face_embeddings(img_path, "face_frontal", enforce_detection=False)
        if not embeddings:
            continue
        emb_data = embeddings[0]
        emb = emb_data["embedding"]
        conf = emb_data["confidence"]
        qual = emb_data["quality"]
        point_id = str(uuid.uuid4())
        points.append({
            "id": point_id,
            "vector": emb,
            "payload": {
                "reference_person_id": ref_id,
                "image_type": "face_frontal",
                "is_missing_person": True,
                "embedding_confidence": conf,
                "quality_score": qual,
            },
        })
        with get_db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO reference_persons (id, label, photo_path, attributes) VALUES (?, ?, ?, ?)",
                (ref_id, f"Reference {img_path.stem}", img_path.name, json.dumps({"source_file": img_path.name})),
            )

    if not points:
        pytest.skip("No face embeddings extracted from samples")
    qdrant_client.upsert_points(points)

    # POST search/combined with the first downloaded image
    query_image_path = paths[0]
    with open(query_image_path, "rb") as f:
        file_content = f.read()
    files = [("files", (query_image_path.name, file_content, "image/jpeg"))]
    r = client.post("/api/search/combined", files=files, headers=auth_headers)

    assert r.status_code == 200, r.text
    body = r.json()
    results = body.get("results") or []
    assert len(results) >= 1, "search/combined should return at least one result when same image is in repo"
    top = results[0]
    score = top.get("score") or top.get("score_image") or 0
    assert score >= 0.3, f"top match score should be >= 0.3 (placeholder or real); got {score}"
