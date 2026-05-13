import json
import uuid

from app.database import get_db, init_db
from app.search_synonyms import text_attribute_match_score


def test_synonym_wallet_butwa(client):
    init_db()
    sid = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            "INSERT INTO submissions (id, attributes_manual, attributes_ai, face_condition, status) VALUES (?, ?, ?, ?, ?)",
            (sid, json.dumps({"clothing": "brown leather batwa with chain"}), "{}", "normal", "captured"),
        )
    r = client.post("/api/search", json={"query": "wallet", "search_target": "ui_body"})
    assert r.status_code == 200
    sl = r.json().get("shortlist") or []
    assert any(x["id"] == sid for x in sl)


def test_synonym_ornament_notes_query_english_record_hindi_colloquial(client):
    init_db()
    sid = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            "INSERT INTO submissions (id, attributes_manual, attributes_ai, face_condition, status) VALUES (?, ?, ?, ?, ?)",
            (
                sid,
                json.dumps({"ornament_notes": [{"slot": "belonging_1", "note": "chabi aur brown batwa"}]}),
                "{}",
                "normal",
                "captured",
            ),
        )
    r = client.post("/api/search", json={"query": "wallet keys", "search_target": "ui_body"})
    assert r.status_code == 200
    sl = r.json().get("shortlist") or []
    assert any(x["id"] == sid for x in sl)


def test_text_attribute_match_score_unit():
    assert text_attribute_match_score("wallet", {"clothing": "butwa in pocket"}) >= 0.35
    assert text_attribute_match_score("necklace", {"clothing": "gold haar"}) >= 0.35


def test_concept_overlap_not_inflated_by_synonym_group_size():
    """One wallet↔butwa match should score lower than wallet+keys matching batwa+chabi."""
    one_concept = text_attribute_match_score("wallet", {"clothing": "brown batwa"})
    two_concepts = text_attribute_match_score("wallet keys", {"clothing": "brown batwa chabi"})
    assert two_concepts > one_concept
    # Single shared group → not saturated to 1.0
    assert one_concept < 0.99
