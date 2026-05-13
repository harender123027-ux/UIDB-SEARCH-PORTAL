"""Unit tests for reference aggregation (UI body multi-view fusion)."""
from app.services.match_logic import aggregate_ref_hits


def test_aggregate_picks_best_payload_for_quality():
    hits = [
        ("a", 0.5, {"quality_score": 1.0}),
        ("a", 0.6, {"quality_score": 99.0}),
        ("a", 0.55, {"quality_score": 2.0}),
    ]
    out = aggregate_ref_hits(hits, medium_threshold=0.35, multiview_boost=0.07)
    assert len(out) == 1
    ref_id, fused, best_payload, supporting = out[0]
    assert ref_id == "a"
    assert best_payload["quality_score"] == 99.0
    assert supporting == 3
    assert fused >= 0.6
    assert fused <= 1.0


def test_multiview_boost_increases_score():
    single = aggregate_ref_hits([("x", 0.5, {"quality_score": 1})], medium_threshold=0.35, multiview_boost=0.1)
    multi = aggregate_ref_hits(
        [("x", 0.5, {"quality_score": 1}), ("x", 0.51, {"quality_score": 1})],
        medium_threshold=0.35,
        multiview_boost=0.1,
    )
    assert multi[0][1] > single[0][1]


def test_below_medium_filtered():
    out = aggregate_ref_hits([("z", 0.1, {})], medium_threshold=0.35, multiview_boost=0.07)
    assert out == []
