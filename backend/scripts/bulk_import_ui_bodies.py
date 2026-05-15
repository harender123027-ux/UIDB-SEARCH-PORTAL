import csv
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

# Add root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import audit_log_insert, get_db, init_db
from app.services import qdrant_client
from app.services.face_embedding import extract_embeddings_from_bytes
from app.storage import save_upload

# Keep in sync with app.routers.submissions._RELAXED_FACE_DETECTION_TYPES
_RELAXED_FACE_DETECTION_TYPES = frozenset({"belonging", "clothing", "tattoo", "other"})


def import_bulk_csv(csv_path: str, images_dir: str):
    """
    Import UI Body records from a CSV file.
    csv_path: Path to the CSV template.
    images_dir: Base directory where local images are stored.
    """
    csv_path = Path(csv_path)
    images_dir = Path(images_dir)

    if not csv_path.exists():
        print(f"Error: CSV file not found at {csv_path}")
        return

    # Initialize DB and Qdrant
    init_db()
    if not qdrant_client.ensure_collection():
        print(
            "ERROR: Could not connect to Qdrant. In the on-prem 'lite' profile "
            "the embedded Qdrant store holds an exclusive file lock while the "
            "backend container is running, which prevents this importer from "
            "writing face embeddings. Stop the backend container first, run "
            "the importer in a one-off container that mounts the same data "
            "volumes, then start the backend back up. See "
            "sample_import_images/README.md for the exact commands.",
            file=sys.stderr,
        )
        sys.exit(2)

    with open(csv_path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            try:
                submission_id = str(uuid.uuid4())

                # Prepare attributes (Exactly matching ubis-pwa.jsx)
                att_ai = {
                    "gender": row.get("gender"),
                    "age_min": row.get("age_min"),
                    "age_max": row.get("age_max"),
                    "build": row.get("build"),
                    "skin": row.get("skin_tone"),
                    "hair_color": row.get("hair_color"),
                    "marks": row.get("visible_marks"),
                    "clothing": row.get("clothing_description"),
                }

                att_manual = {
                    "dd_no": row.get("dd_no"),
                    "found_district": row.get("found_district"),
                    "ps_name": row.get("ps_name"),
                    "found_date": row.get("found_date"),
                    "found_loc": row.get("found_loc"),
                    "notes": row.get("notes"),
                    "manual_notes": row.get("additional_details"),
                    "beard": row.get("beard"),
                    "height": row.get("height_cm"),
                }

                # Process Images (Exactly matching ubis-pwa.jsx slots)
                image_slots = {
                    "face_frontal": row.get("image_face_frontal_path"),
                    "face_left": row.get("image_face_left_path"),
                    "face_right": row.get("image_face_right_path"),
                    "full_body": row.get("image_full_body_path"),
                    "clothing": row.get("image_clothing_path"),
                    "belonging": row.get("image_belonging_path"),
                }
                
                # Support legacy single tattoo and new multiple tattoo columns (tattoo_1 through tattoo_10)
                legacy_tattoo = row.get("image_tattoo_path")
                if legacy_tattoo:
                    image_slots["tattoo_1"] = legacy_tattoo
                
                for i in range(1, 11):
                    tattoo_col = f"image_tattoo_{i}_path"
                    if row.get(tattoo_col):
                        image_slots[f"tattoo_{i}"] = row.get(tattoo_col)

                images_to_insert = []
                qdrant_points = []

                for img_type, rel_path in image_slots.items():
                    if not rel_path:
                        continue

                    full_img_path = images_dir / rel_path
                    if not full_img_path.exists():
                        print(f"Warning: Image {full_img_path} not found. Skipping {img_type}.")
                        continue

                    with open(full_img_path, "rb") as img_f:
                        content = img_f.read()

                    ext = full_img_path.suffix.lstrip('.').lower() or "jpg"
                    # Save to storage (Azure or Local)
                    saved_rel_path = save_upload(content, submission_id, img_type, ext)

                    image_id = str(uuid.uuid4())

                    # AI embeddings for every slot (same rules as live POST /submissions)
                    emb_confidence = None
                    quality_score = None
                    qdrant_point_id = None

                    enforce_face = img_type not in _RELAXED_FACE_DETECTION_TYPES
                    embeddings = extract_embeddings_from_bytes(
                        content, img_type, enforce_detection=enforce_face
                    )
                    if embeddings:
                        emb_data = embeddings[0]
                        emb = emb_data["embedding"]
                        emb_confidence = emb_data["confidence"]
                        quality_score = emb_data["quality"]
                        qdrant_point_id = str(uuid.uuid4())

                        qdrant_points.append({
                            "id": qdrant_point_id,
                            "vector": emb.tolist() if hasattr(emb, "tolist") else emb,
                            "payload": {
                                "submission_id": submission_id,
                                "image_id": image_id,
                                "image_type": img_type,
                                "is_missing_person": False,
                                "embedding_confidence": emb_confidence,
                                "quality_score": quality_score,
                            }
                        })

                    images_to_insert.append({
                        "id": image_id,
                        "submission_id": submission_id,
                        "image_type": img_type,
                        "path": saved_rel_path,
                        "embedding_confidence": emb_confidence,
                        "quality_score": quality_score,
                        "qdrant_point_id": qdrant_point_id
                    })

                # Database Insertion
                with get_db() as conn:
                    conn.execute(
                        "INSERT INTO submissions (id, attributes_ai, attributes_manual, face_condition, created_at) VALUES (?, ?, ?, ?, ?)",
                        (
                            submission_id,
                            json.dumps(att_ai),
                            json.dumps(att_manual),
                            "normal",
                            row.get("found_date") + " 00:00:00" if row.get("found_date") else datetime.now().isoformat()
                        ),
                    )
                    for im in images_to_insert:
                        conn.execute(
                            "INSERT INTO images (id, submission_id, image_type, path, embedding_confidence, quality_score, qdrant_point_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (im["id"], im["submission_id"], im["image_type"], im["path"], im["embedding_confidence"], im["quality_score"], im["qdrant_point_id"]),
                        )
                    audit_log_insert(conn, "bulk.import", "submission", submission_id, user_id="system")

                # Qdrant Insertion
                if qdrant_points:
                    qdrant_client.upsert_points(qdrant_points)

                count += 1
                print(f"Imported record {count}: {row.get('dd_no')} (ID: {submission_id})")

            except Exception as e:
                print(f"Error importing row {row.get('dd_no')}: {e}")
                import traceback
                traceback.print_exc()

    print(f"\nBulk import complete. Total records imported: {count}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m scripts.bulk_import_ui_bodies <csv_path> <images_base_dir>")
        sys.exit(1)

    import_bulk_csv(sys.argv[1], sys.argv[2])
