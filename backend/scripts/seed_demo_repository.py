"""
Seed the demo repository: load reference images from REFERENCE_PHOTOS_PATH,
run face embedding, insert into reference_persons and Qdrant (is_missing_person=true).
Usage: python -m scripts.seed_demo_repository
"""
import json
import sys
import uuid
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import REFERENCE_PHOTOS_PATH
from app.database import get_db, init_db
from app.services import qdrant_client
from app.services.face_embedding import extract_face_embeddings

# Default attributes per reference (customize per image if you have a manifest)
DEFAULT_ATTRIBUTES = {"gender": "male", "visible_marks": "tattoo", "age_range": "25-35"}


def seed_one_reference_image(img_path: Path, label: str = None, attributes: dict = None) -> dict | None:
    """
    Run face embedding for one image, insert into reference_persons, return point dict for Qdrant.
    Caller should call qdrant_client.upsert_points([...]) with returned points.
    Returns None if no face/embedding; otherwise returns dict with id, vector, payload.
    """
    ref_id = str(uuid.uuid4())
    att = (attributes or {}).copy()
    att["source_file"] = img_path.name
    embeddings = extract_face_embeddings(img_path, "face_frontal")
    if not embeddings:
        return None
    emb, conf = embeddings[0]
    point_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO reference_persons (id, label, photo_path, attributes) VALUES (?, ?, ?, ?)",
            (ref_id, label or f"Reference {img_path.stem}", img_path.name, json.dumps(att)),
        )
    return {
        "id": point_id,
        "vector": emb,
        "payload": {
            "reference_person_id": ref_id,
            "image_type": "face_frontal",
            "is_missing_person": True,
            "embedding_confidence": conf,
        },
    }


def main():
    init_db()
    qdrant_client.ensure_collection()
    ref_path = Path(REFERENCE_PHOTOS_PATH)
    if not ref_path.exists():
        ref_path.mkdir(parents=True, exist_ok=True)
        print(f"Created {ref_path}. Add some reference images (e.g. ref1.jpg, ref2.jpg) and run again.")
        return
    images = list(ref_path.glob("*.jpg")) + list(ref_path.glob("*.jpeg")) + list(ref_path.glob("*.png"))
    if not images:
        print(f"No jpg/png in {ref_path}. Add reference images and run again.")
        return
    points = []
    for img_path in images:
        att = DEFAULT_ATTRIBUTES.copy()
        point = seed_one_reference_image(img_path, label=f"Reference {img_path.stem}", attributes=att)
        if point:
            points.append(point)
            print(f"Added reference_person from {img_path.name}")
        else:
            print(f"No face in {img_path.name}, skipping.")
    if points:
        qdrant_client.upsert_points(points)
        print(f"Upserted {len(points)} face embeddings to Qdrant.")
    print("Done.")


if __name__ == "__main__":
    main()
