"""
Seed reference_persons and Qdrant from a DigiFace1M-style directory layout.

DigiFace1M (https://github.com/microsoft/DigiFace1M) uses one folder per identity:
  subj_00001/0.png, 1.png, ...
  subj_00002/0.png, 1.png, ...

This script copies the first image of each identity into REFERENCE_PHOTOS_PATH,
then runs face embedding and inserts into reference_persons + Qdrant.

Usage:
  python -m scripts.seed_from_digiface1m /path/to/digiface_part

Example: after downloading one part of DigiFace1M, run:
  python -m scripts.seed_from_digiface1m /path/to/DigiFace1M_part1
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import REFERENCE_PHOTOS_PATH
from app.database import init_db
from app.services import qdrant_client

from scripts.seed_demo_repository import seed_one_reference_image

DEFAULT_ATTRIBUTES = {"source": "digiface1m"}


def _first_image_in_dir(dir_path: Path) -> Path | None:
    """Return path to first image (0.png, 1.png, or first jpg/png by name) in dir_path."""
    for name in ["0.png", "0.jpg", "1.png", "1.jpg"]:
        p = dir_path / name
        if p.is_file():
            return p
    for ext in ["*.png", "*.jpg", "*.jpeg"]:
        images = sorted(dir_path.glob(ext))
        if images:
            return images[0]
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.seed_from_digiface1m /path/to/digiface_root")
        sys.exit(1)
    root = Path(sys.argv[1])
    if not root.is_dir():
        print(f"Not a directory: {root}")
        sys.exit(1)

    ref_path = Path(REFERENCE_PHOTOS_PATH)
    ref_path.mkdir(parents=True, exist_ok=True)

    # Find identity subdirs (subj_* or any non-hidden directory)
    subdirs = sorted([d for d in root.iterdir() if d.is_dir() and not d.name.startswith(".")])
    # Prefer subj_* naming
    if not subdirs:
        subdirs = sorted([d for d in root.iterdir() if d.is_dir() and d.name.startswith("subj_")])
    if not subdirs:
        print(f"No subdirectories found under {root}. Expected layout: subj_00001/0.png, ...")
        sys.exit(1)

    copied = []
    for subdir in subdirs:
        first_img = _first_image_in_dir(subdir)
        if not first_img:
            print(f"No image in {subdir.name}, skipping.")
            continue
        dest_name = f"digiface_{subdir.name}_{first_img.name}"
        dest_path = ref_path / dest_name
        shutil.copy2(first_img, dest_path)
        copied.append((dest_path, f"DigiFace {subdir.name}"))

    if not copied:
        print("No images copied.")
        sys.exit(1)

    print(f"Copied {len(copied)} images to {ref_path}. Seeding repository...")
    init_db()
    qdrant_client.ensure_collection()

    points = []
    for img_path, label in copied:
        point = seed_one_reference_image(img_path, label=label, attributes=DEFAULT_ATTRIBUTES.copy())
        if point:
            points.append(point)
            print(f"Added {label} from {img_path.name}")
        else:
            print(f"No face in {img_path.name}, skipping.")

    if points:
        qdrant_client.upsert_points(points)
        print(f"Upserted {len(points)} face embeddings to Qdrant.")
    print("Done.")


if __name__ == "__main__":
    main()
