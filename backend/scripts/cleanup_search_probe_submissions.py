"""
Remove ephemeral face-search rows (_search_probe in attributes_manual).

These are created by /api/upload-and-match and /api/search/combined image flow.
They must not accumulate as real cases: deletes SQLite/Postgres rows, local upload
files (when not using Azure Blob), Qdrant vectors, dependent matches/feedback.

Usage:
  python -m scripts.cleanup_search_probe_submissions
  python -m scripts.cleanup_search_probe_submissions --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import SUBMISSIONS_STORAGE_PATH, USE_AZURE_BLOB
from app.database import get_db, init_db
from app.services import qdrant_client


def _is_probe_row(attributes_manual: str | None) -> bool:
    if not attributes_manual or not str(attributes_manual).strip():
        return False
    try:
        data = json.loads(attributes_manual) if isinstance(attributes_manual, str) else attributes_manual
    except json.JSONDecodeError:
        return False
    return isinstance(data, dict) and bool(data.get("_search_probe"))


def _is_legacy_empty_row(att_manual: str | None, att_ai: str | None) -> bool:
    """
    Pre-marker upload-and-match probes left both attribute blobs empty / {} —
    a real bulk-import or form submission always populates attributes_manual.
    """
    def _blank(x: str | None) -> bool:
        if x is None:
            return True
        s = str(x).strip()
        return s in ("", "{}")

    return _blank(att_manual) and _blank(att_ai)


def _collect_probe_ids(include_legacy: bool) -> list[str]:
    init_db()
    out: list[str] = []
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, attributes_manual, attributes_ai FROM submissions"
        ).fetchall()
        for r in rows:
            am = r["attributes_manual"]
            ai = r["attributes_ai"] if "attributes_ai" in r.keys() else None
            if _is_probe_row(am):
                out.append(r["id"])
                continue
            if include_legacy and _is_legacy_empty_row(am, ai):
                out.append(r["id"])
    return out


def _delete_local_files_for_submissions(conn, submission_ids: list[str]) -> int:
    if USE_AZURE_BLOB or not submission_ids:
        return 0
    ph = ",".join("?" * len(submission_ids))
    rows = conn.execute(
        f"SELECT path FROM images WHERE submission_id IN ({ph})",
        submission_ids,
    ).fetchall()
    removed = 0
    for r in rows:
        rel = r["path"]
        if not rel:
            continue
        p = SUBMISSIONS_STORAGE_PATH / rel
        try:
            if p.is_file():
                p.unlink()
                removed += 1
        except OSError as e:
            print(f"Warning: could not delete file {p}: {e}")
    return removed


def run(*, dry_run: bool, include_legacy: bool) -> int:
    probe_ids = _collect_probe_ids(include_legacy=include_legacy)
    if not probe_ids:
        print("No search-probe submissions found (_search_probe). Nothing to do.")
        return 0

    print(f"Found {len(probe_ids)} search-probe submission(s).")
    if dry_run:
        for pid in probe_ids[:50]:
            print(f"  [dry-run] would delete: {pid}")
        if len(probe_ids) > 50:
            print(f"  ... and {len(probe_ids) - 50} more")
        return 0

    qdrant_client.ensure_collection()
    ph = ",".join("?" * len(probe_ids))

    with get_db() as conn:
        # SQLite ignores ON DELETE CASCADE unless foreign keys are enabled per connection.
        try:
            conn.execute("PRAGMA foreign_keys = ON")
        except Exception:
            pass
        # Matches where the search run was stored as submission_id, or a bad hit used probe as ref.
        conn.execute(
            f"DELETE FROM feedback WHERE match_id IN ("
            f"SELECT id FROM matches WHERE submission_id IN ({ph}) OR reference_person_id IN ({ph})"
            f")",
            probe_ids + probe_ids,
        )

        conn.execute(
            f"DELETE FROM matches WHERE submission_id IN ({ph}) OR reference_person_id IN ({ph})",
            probe_ids + probe_ids,
        )

        n_files = _delete_local_files_for_submissions(conn, probe_ids)

        for sid in probe_ids:
            qdrant_client.delete_by_submission(sid)

        conn.execute(
            f"DELETE FROM audit_log WHERE resource_type = 'submission' AND resource_id IN ({ph})",
            probe_ids,
        )

        conn.execute(
            f"DELETE FROM images WHERE submission_id IN ({ph})",
            probe_ids,
        )

        conn.execute(f"DELETE FROM submissions WHERE id IN ({ph})", probe_ids)

        # Belt-and-braces: drop any image rows whose submission is gone (legacy / cascade misses).
        conn.execute("DELETE FROM images WHERE submission_id NOT IN (SELECT id FROM submissions)")

    print(f"Deleted {len(probe_ids)} probe submission(s).")
    print(f"Removed approximately {n_files} local upload file(s) (skipped when USE_AZURE_BLOB=1).")
    return len(probe_ids)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Delete face-search probe submissions and related data.")
    ap.add_argument("--dry-run", action="store_true", help="List probe IDs only; do not delete.")
    ap.add_argument(
        "--include-legacy",
        action="store_true",
        help="Also delete submissions with empty attributes (pre-_search_probe marker). Use once after upgrade.",
    )
    args = ap.parse_args()
    n = run(dry_run=args.dry_run, include_legacy=args.include_legacy)
    sys.exit(0 if n >= 0 else 1)
