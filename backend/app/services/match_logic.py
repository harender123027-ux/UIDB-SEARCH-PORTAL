"""
Pure matching aggregation logic (UI body + missing-person gallery).
Used by match router and tests; keeps scoring rules testable without HTTP.
"""
from __future__ import annotations

from collections import defaultdict

from app.config import FACE_MATCH_THRESHOLD_MEDIUM, FACE_MULTIVIEW_SCORE_BOOST


def aggregate_ref_hits(
    hits: list[tuple[str, float, dict]],
    *,
    medium_threshold: float = FACE_MATCH_THRESHOLD_MEDIUM,
    multiview_boost: float = FACE_MULTIVIEW_SCORE_BOOST,
) -> list[tuple[str, float, dict, int]]:
    """
    Collapse Qdrant hits to one row per reference / submission gallery id.

    Each input row is (ref_id, cosine_score, payload_of_that_hit).
    - Chooses the hit with max score for ranking.
    - Applies a small boost when multiple hits support the same id (multi-angle UI body uploads).
    Returns sorted list of (ref_id, fused_score, best_payload, supporting_hit_count).
    """
    by_ref: dict[str, list[tuple[float, dict]]] = defaultdict(list)
    for ref_id, score, payload in hits:
        if not ref_id or score < medium_threshold:
            continue
        by_ref[ref_id].append((float(score), payload or {}))

    out: list[tuple[str, float, dict, int]] = []
    for ref_id, pairs in by_ref.items():
        best_score, best_payload = max(pairs, key=lambda x: x[0])
        supporting = sum(1 for s, _ in pairs if s >= medium_threshold)
        fused = min(1.0, best_score * (1.0 + multiview_boost * max(0, supporting - 1)))
        out.append((ref_id, fused, best_payload, supporting))

    out.sort(key=lambda x: -x[1])
    return out
