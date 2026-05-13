"""
Expand regional / Hinglish terms and English variants so text search matches
clothing & ornaments fields (e.g. "wallet" vs "butwa" / "batwa").

Scoring uses *concept* overlap (synonym equivalence classes + literal tokens),
not expanded token bags — so a single wallet↔butwa match does not inflate to
the full size of the synonym group.
"""

import json
import re
from typing import Any

# Lowercase strings; include common spellings. Groups are equivalence classes.
ATTRIBUTE_SYNONYM_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"wallet", "batwa", "batua", "butwa", "purse", "बटुआ"}),
    frozenset({"necklace", "chain", "gold", "haar", "har", "locket", "pendant", "माला"}),
    frozenset({"ring", "angoothi", "अंगूठी"}),
    frozenset({"watch", "ghadi", "wristwatch", "घड़ी"}),
    frozenset({"bracelet", "kada", "bangle", "churi", "चूड़ी", "कड़ा"}),
    frozenset({"keys", "key", "chabi", "चाबी"}),
    frozenset({"mobile", "phone", "smartphone", "मोबाइल"}),
    frozenset({"belt", "kamarband", "कमरबंद"}),
    frozenset({"cap", "topi", "hat", "टोपी"}),
    frozenset({"socks", "mojari", "juti", "shoes", "footwear", "चप्पल", "जूता"}),
    frozenset({"earring", "ear", "baliyan", "बाली"}),
)


def _tokenize(text: str) -> set[str]:
    if not text:
        return set()
    t = text.lower()
    # Latin letters, digits, underscore, Devanagari block
    return set(re.findall(r"[\w\u0900-\u097F]+", t, flags=re.UNICODE))


def _synonym_group_indexes_for_tokens(tokens: set[str]) -> set[int]:
    """Indices of synonym groups that contain at least one token from the set."""
    idxs: set[int] = set()
    for i, group in enumerate(ATTRIBUTE_SYNONYM_GROUPS):
        if tokens & group:
            idxs.add(i)
    return idxs


def _tokens_covered_by_synonym_groups(tokens: set[str]) -> set[str]:
    """Query/doc tokens that belong to at least one synonym group."""
    covered: set[str] = set()
    for group in ATTRIBUTE_SYNONYM_GROUPS:
        covered |= tokens & group
    return covered


def _literal_query_tokens(tokens: set[str]) -> set[str]:
    """Tokens that are not part of any defined synonym group (matched literally)."""
    return tokens - _tokens_covered_by_synonym_groups(tokens)


def expand_tokens(tokens: set[str]) -> set[str]:
    """Add all synonyms for any token that appears in a group (for enrichment strings only)."""
    out = set(tokens)
    for group in ATTRIBUTE_SYNONYM_GROUPS:
        if tokens & group:
            out |= group
    return out


def attribute_search_blob(attributes: dict[str, Any]) -> str:
    """Flatten structured attributes into one searchable string."""
    parts: list[str] = []

    def walk(obj: Any) -> None:
        if obj is None:
            return
        if isinstance(obj, str):
            s = obj.strip()
            if s:
                parts.append(s)
            return
        if isinstance(obj, (int, float)):
            parts.append(str(obj))
            return
        if isinstance(obj, dict):
            for v in obj.values():
                walk(v)
            return
        if isinstance(obj, (list, tuple)):
            for v in obj:
                walk(v)

    walk(attributes)
    return " ".join(parts).lower()


def text_attribute_match_score(query: str, attributes: dict[str, Any]) -> float:
    """
    Score 0..1 for free-text query vs clothing / ornaments / notes.
    Counts (1) shared synonym *groups* between query and document, plus
    (2) literal query tokens that appear in the document — not the size of
    an expanded token intersection.
    """
    q = (query or "").strip()
    if not q:
        return 0.0
    blob = attribute_search_blob(attributes)
    if not blob:
        return 0.0

    q_raw = _tokenize(q)
    d_raw = _tokenize(blob)
    if not q_raw:
        return 0.0

    q_syn = _synonym_group_indexes_for_tokens(q_raw)
    d_syn = _synonym_group_indexes_for_tokens(d_raw)
    syn_hits = len(q_syn & d_syn)

    literal_hits = 0
    for tok in _literal_query_tokens(q_raw):
        if tok in d_raw or len(tok) >= 3 and tok in blob:
            literal_hits += 1

    concept_hits = syn_hits + literal_hits
    if concept_hits:
        return min(1.0, 0.35 + 0.2 * concept_hits)

    # Fallback: phrase / token substring against blob enriched with synonym spellings
    enriched = blob
    for group in ATTRIBUTE_SYNONYM_GROUPS:
        if d_raw & group:
            enriched += " " + " ".join(group)

    q_lower = q.lower()
    if len(q_lower) >= 3 and q_lower in enriched:
        return 0.45

    q_expanded_for_sub = expand_tokens(q_raw)
    for tok in sorted(q_expanded_for_sub, key=len, reverse=True):
        if len(tok) >= 3 and tok in enriched:
            return 0.4

    return 0.0


def merge_submission_attributes(attributes_manual_raw: Any, attributes_ai_raw: Any) -> dict:
    """Parse JSON attribute columns into one dict for search."""
    def parse(raw: Any) -> dict:
        if raw is None:
            return {}
        if isinstance(raw, dict):
            return dict(raw)
        if isinstance(raw, str):
            try:
                return json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return {}
        return {}

    att_man = parse(attributes_manual_raw)
    att_ai = parse(attributes_ai_raw)
    return {**att_ai, **att_man}
