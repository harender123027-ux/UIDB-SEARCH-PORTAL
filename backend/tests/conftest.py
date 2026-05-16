"""Pytest fixtures. Use temp DB and storage so tests don't touch real data."""
import os
import tempfile
from pathlib import Path

# Set env before any app import so config uses test paths
_TEST_DIR = tempfile.mkdtemp(prefix="ubis_test_")
os.environ["SQLITE_PATH"] = str(Path(_TEST_DIR) / "test.db")
os.environ["SUBMISSIONS_STORAGE_PATH"] = str(Path(_TEST_DIR) / "uploads")
os.environ["REFERENCE_PHOTOS_PATH"] = str(Path(_TEST_DIR) / "reference_photos")
os.environ["QDRANT_URL"] = ":memory:"  # in-memory Qdrant for tests (no server needed)
os.environ["FACE_QUERY_MIN_EMBEDDING_CONFIDENCE"] = "0"  # allow low-det test fixtures
Path(os.environ["SUBMISSIONS_STORAGE_PATH"]).mkdir(parents=True, exist_ok=True)
Path(os.environ["REFERENCE_PHOTOS_PATH"]).mkdir(parents=True, exist_ok=True)

import pytest  # noqa: E402  (must be after env-var setup above)
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(autouse=True)
def reset_qdrant():
    """Reset Qdrant client so each test gets a fresh in-memory store."""
    import app.services.qdrant_client as _qdrant
    _qdrant._client = None
    yield


@pytest.fixture(autouse=True)
def reset_feedback_rate_limit():
    from app.feedback_rate_limit import clear_state

    clear_state()
    yield


@pytest.fixture(autouse=True)
def stub_face_embedding(monkeypatch):
    """Replace the face-embedding extractor with a deterministic 512-d unit
    vector by default, so unit tests that POST blank/fixture JPEGs to
    /api/submissions can exercise routing/persistence without needing real
    face images. Tests that want to assert the no-face rejection path can
    override this with their own ``monkeypatch.setattr(...)`` to return [].
    The real AI pipeline is exercised separately in test_matching_e2e.py.
    """
    import numpy as np

    import app.routers.submissions as _submissions

    vec = np.zeros(512, dtype=np.float32)
    vec[0] = 1.0
    stub_result = [{"embedding": vec, "confidence": 0.9, "quality": 1.0}]
    monkeypatch.setattr(
        _submissions, "extract_embeddings_from_bytes",
        lambda *a, **kw: list(stub_result),
    )
    yield


@pytest.fixture
def client():
    from app.database import init_db
    from app.main import app
    init_db()
    return TestClient(app)


# Minimal valid JPEG (1x1 pixel)
JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' \",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07\"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17\x18\x19\x1a%&\'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xda\x00\x08\x01\x01\x00\x00\x00?\x00\xfc\xbe\xa2\x8a\xff\xd9"
)


@pytest.fixture
def auth_headers(client):
    from tests.test_auth import _login, _seed_test_users

    _seed_test_users()
    token = _login(client, "investigator_test", "investigatorpass")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def public_headers(client):
    """JWT for role public_user (family / loved-one search only)."""
    import uuid

    from app.auth import hash_password
    from app.database import get_db, init_db

    from tests.test_auth import _login

    init_db()
    user_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute("DELETE FROM users WHERE username = ?", ("public_journey_test",))
        conn.execute(
            "INSERT INTO users (id, username, password_hash, name, role, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            (user_id, "public_journey_test", hash_password("publicpass"), "Public Test", "public_user"),
        )
    token = _login(client, "public_journey_test", "publicpass")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_jpeg():
    return JPEG_BYTES
