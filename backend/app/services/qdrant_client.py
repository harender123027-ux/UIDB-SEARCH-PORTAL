"""
Qdrant client for face embeddings.

Supports:
- Local persistent storage (development): QDRANT_URL = "./qdrant_data"
- In-memory (testing): QDRANT_URL = ":memory:"
- Local Docker: QDRANT_URL = "http://localhost:6333"
- Qdrant Cloud (production): QDRANT_URL = "https://your-cluster.qdrant.io" + QDRANT_API_KEY
"""
import logging
from typing import Any

import numpy as np

from app.config import (
    EMBEDDING_DIM,
    IS_PRODUCTION,
    QDRANT_API_KEY,
    QDRANT_COLLECTION,
    QDRANT_URL,
)

logger = logging.getLogger(__name__)

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance,
        FieldCondition,
        Filter,
        MatchValue,
        PointStruct,
        VectorParams,
    )
    QDRANT_AVAILABLE = True
except ImportError:
    QdrantClient = None
    PointStruct = None
    Filter = None
    FieldCondition = None
    MatchValue = None
    Distance = None
    VectorParams = None
    QDRANT_AVAILABLE = False
    logger.warning("qdrant-client not installed. Vector search will be disabled.")

_client: Any | None = None


def get_client() -> Any | None:
    """
    Get or create Qdrant client.

    Connection modes:
    - ":memory:" - In-memory storage for testing
    - Local path (no "://") - Persistent local storage
    - URL with API key - Qdrant Cloud
    - URL without API key - Local Docker
    """
    global _client
    if _client is None and QDRANT_AVAILABLE:
        try:
            if QDRANT_URL == ":memory:":
                # In-memory for testing
                _client = QdrantClient(":memory:")
                logger.info("Qdrant client initialized (in-memory)")

            elif "://" not in QDRANT_URL:
                # Local path (persistent storage) - development
                _client = QdrantClient(path=QDRANT_URL)
                logger.info(f"Qdrant client initialized (local path: {QDRANT_URL})")

            elif QDRANT_API_KEY:
                # Qdrant Cloud with API key - production
                _client = QdrantClient(
                    url=QDRANT_URL,
                    api_key=QDRANT_API_KEY,
                    timeout=30,  # Increased timeout for cloud
                    prefer_grpc=False,  # Use HTTP for better compatibility
                )
                logger.info(f"Qdrant client initialized (cloud: {QDRANT_URL[:30]}...)")

            else:
                # Local Docker/self-hosted without auth
                _client = QdrantClient(url=QDRANT_URL)
                logger.info(f"Qdrant client initialized (self-hosted: {QDRANT_URL})")

        except Exception as e:
            logger.error(f"Failed to initialize Qdrant client: {e}")
            _client = None

    return _client


def ensure_collection() -> bool:
    """
    Create collection if not exists.

    Returns:
        True if collection exists or was created, False otherwise
    """
    client = get_client()
    if client is None:
        return False

    try:
        collections = client.get_collections()
        collection_names = [c.name for c in collections.collections]

        if QDRANT_COLLECTION not in collection_names:
            client.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=VectorParams(
                    size=EMBEDDING_DIM,
                    distance=Distance.COSINE
                ),
                # Optimizations for large collections
                on_disk_payload=IS_PRODUCTION,  # Store payload on disk in production
            )
            logger.info(f"Created Qdrant collection: {QDRANT_COLLECTION}")
        return True

    except Exception as e:
        logger.error(f"Failed to ensure collection exists: {e}")
        return False


def get_collection_info() -> dict | None:
    """Get information about the current collection."""
    client = get_client()
    if client is None:
        return None

    try:
        ensure_collection()
        info = client.get_collection(QDRANT_COLLECTION)
        return {
            "name": QDRANT_COLLECTION,
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
            "status": info.status.name if info.status else "unknown",
            "indexed_vectors_count": getattr(info, 'indexed_vectors_count', 0),
        }
    except Exception as e:
        logger.error(f"Failed to get collection info: {e}")
        return None


def upsert_points(points: list[dict[str, Any]]) -> bool:
    """
    Upsert embedding points.

    Args:
        points: List of dicts with keys: id, vector, payload
                payload should contain: submission_id, image_id, image_type, is_missing_person, etc.

    Returns:
        True if successful, False otherwise
    """
    client = get_client()
    if client is None or not points:
        return False

    if not ensure_collection():
        return False

    try:
        structs = [
            PointStruct(
                id=p["id"],
                vector=p["vector"].tolist() if hasattr(p["vector"], "tolist") else p["vector"],
                payload=p["payload"],
            )
            for p in points
        ]

        # Batch upsert for better performance with large datasets
        batch_size = 100
        for i in range(0, len(structs), batch_size):
            batch = structs[i:i + batch_size]
            client.upsert(collection_name=QDRANT_COLLECTION, points=batch)

        logger.debug(f"Upserted {len(points)} points to Qdrant")
        return True

    except Exception as e:
        logger.error(f"Failed to upsert points: {e}")
        return False


def search_reference_only(vector: np.ndarray, limit: int = 20) -> list[dict]:
    """
    Search only reference persons (is_missing_person=true).

    Args:
        vector: Query embedding vector
        limit: Maximum number of results

    Returns:
        List of {id, score, payload} dicts sorted by score descending
    """
    client = get_client()
    if client is None:
        return []

    if not ensure_collection():
        return []

    try:
        vec = vector.tolist() if hasattr(vector, "tolist") else vector
        result = client.query_points(
            collection_name=QDRANT_COLLECTION,
            query=vec,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="is_missing_person",
                        match=MatchValue(value=True)
                    )
                ]
            ),
            limit=limit,
            with_payload=True,
        )
        points = result.points if hasattr(result, "points") else []
        return [
            {"id": r.id, "score": r.score, "payload": r.payload or {}}
            for r in points
        ]

    except Exception as e:
        logger.error(f"Search reference failed: {e}")
        return []


def search_criminals(vector: np.ndarray, limit: int = 20) -> list[dict]:
    """
    Search criminal records (is_criminal=true).

    Args:
        vector: Query embedding vector
        limit: Maximum number of results

    Returns:
        List of {id, score, payload} dicts sorted by score descending
    """
    client = get_client()
    if client is None:
        return []

    if not ensure_collection():
        return []

    try:
        vec = vector.tolist() if hasattr(vector, "tolist") else vector
        result = client.query_points(
            collection_name=QDRANT_COLLECTION,
            query=vec,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="is_criminal",
                        match=MatchValue(value=True)
                    )
                ]
            ),
            limit=limit,
            with_payload=True,
        )
        points = result.points if hasattr(result, "points") else []
        return [
            {"id": r.id, "score": r.score, "payload": r.payload or {}}
            for r in points
        ]

    except Exception as e:
        logger.error(f"Search criminals failed: {e}")
        return []


def search_all(vector: np.ndarray, limit: int = 20) -> list[dict]:
    """
    Search without filter (all vectors).

    Args:
        vector: Query embedding vector
        limit: Maximum number of results

    Returns:
        List of {id, score, payload} dicts sorted by score descending
    """
    client = get_client()
    if client is None:
        return []

    if not ensure_collection():
        return []

    try:
        vec = vector.tolist() if hasattr(vector, "tolist") else vector
        result = client.query_points(
            collection_name=QDRANT_COLLECTION,
            query=vec,
            limit=limit,
            with_payload=True,
        )
        points = result.points if hasattr(result, "points") else []
        return [
            {"id": r.id, "score": r.score, "payload": r.payload or {}}
            for r in points
        ]

    except Exception as e:
        logger.error(f"Search all failed: {e}")
        return []


def get_vectors_by_submission(submission_id: str) -> list[dict]:
    """
    Get all vectors for a submission (for multi-angle match aggregation).

    Args:
        submission_id: The submission ID to filter by

    Returns:
        List of {id, vector, payload} dicts
    """
    client = get_client()
    if client is None:
        return []

    if not ensure_collection():
        return []

    try:
        points, _ = client.scroll(
            collection_name=QDRANT_COLLECTION,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="submission_id",
                        match=MatchValue(value=submission_id)
                    ),
                    FieldCondition(
                        key="is_missing_person",
                        match=MatchValue(value=False)
                    ),
                ]
            ),
            with_payload=True,
            with_vectors=True,
            limit=50,
        )
        return [
            {"id": p.id, "vector": p.vector, "payload": p.payload or {}}
            for p in points
        ]

    except Exception as e:
        logger.error(f"Get vectors by submission failed: {e}")
        return []


def delete_by_submission(submission_id: str) -> bool:
    """
    Delete all vectors for a submission.

    Args:
        submission_id: The submission ID to delete

    Returns:
        True if successful, False otherwise
    """
    client = get_client()
    if client is None:
        return False

    try:
        client.delete(
            collection_name=QDRANT_COLLECTION,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="submission_id",
                        match=MatchValue(value=submission_id)
                    )
                ]
            ),
        )
        logger.debug(f"Deleted vectors for submission: {submission_id}")
        return True

    except Exception as e:
        logger.error(f"Delete by submission failed: {e}")
        return False


def delete_by_ids(point_ids: list[str]) -> bool:
    """
    Delete vectors by their IDs.

    Args:
        point_ids: List of point IDs to delete

    Returns:
        True if successful, False otherwise
    """
    client = get_client()
    if client is None or not point_ids:
        return False

    try:
        client.delete(
            collection_name=QDRANT_COLLECTION,
            points_selector=point_ids,
        )
        logger.debug(f"Deleted {len(point_ids)} points from Qdrant")
        return True

    except Exception as e:
        logger.error(f"Delete by IDs failed: {e}")
        return False


def health_check() -> dict:
    """
    Check Qdrant health and connectivity.

    Returns:
        Dict with health status information
    """
    result = {
        "available": QDRANT_AVAILABLE,
        "connected": False,
        "url": QDRANT_URL[:50] + "..." if len(QDRANT_URL) > 50 else QDRANT_URL,
        "has_api_key": bool(QDRANT_API_KEY),
        "collection": None,
        "error": None,
    }

    if not QDRANT_AVAILABLE:
        result["error"] = "qdrant-client package not installed"
        return result

    client = get_client()
    if client is None:
        result["error"] = "Failed to initialize client"
        return result

    try:
        client.get_collections()
        result["connected"] = True

        # Get collection info if it exists
        collection_info = get_collection_info()
        if collection_info:
            result["collection"] = collection_info

    except Exception as e:
        result["error"] = str(e)

    return result
