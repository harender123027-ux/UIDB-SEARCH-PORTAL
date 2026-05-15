# Sample bulk-import bundle

A small, ready-to-run example so a new contributor can see UBIS ingest
unidentified-body (UI body) records end-to-end without preparing any data
of their own.

## What's here

```
sample_import_images/
├── demo.csv                # 2 demo rows that reference the images below
└── images/
    ├── case1/
    │   └── face.png        # one frontal face photo (640×640 JPEG, .png extension)
    └── case2/
        ├── face_front.png  # frontal face
        ├── face_left.png   # left-profile face
        ├── face_right.png  # right-profile face
        └── tattoo.png      # tattoo close-up
```

The files in `images/case1/` and `images/case2/` are royalty-free portraits
used purely to exercise the AI pipeline. They are **not** real case data.

For the full CSV column reference and a richer 5-row sample with realistic
Haryana districts and DD numbers, see [`/ui_body_template.csv`](../ui_body_template.csv)
and [`/ui_body_template.xlsx`](../ui_body_template.xlsx) at the repo root.

## Run the demo import (local dev)

From the repo root, after `pip install -r backend/requirements.txt` and a
running backend (or just using the bulk-import script directly):

```bash
cd backend
python -m scripts.bulk_import_ui_bodies \
    ../sample_import_images/demo.csv \
    ../sample_import_images
```

The two arguments are:

1. **CSV file** — `demo.csv` here.
2. **Images base directory** — the path that the `image_*_path` columns in
   the CSV are relative to. In the demo CSV those columns are
   `images/case1/face.png` etc., so the base dir is `sample_import_images/`.

Expected output:

```
Imported 2 submissions.
```

## Run the demo import against the on-prem stack

If you have the stack running via `docker-compose.onprem.yml` (see
[`docs/HANDOVER_GURUGRAM/README.md`](../docs/HANDOVER_GURUGRAM/README.md)):

> **Lite-profile gotcha.** In the default `lite` profile, Qdrant runs
> *embedded* inside the backend process and holds an **exclusive file
> lock** on `/app/qdrant_data`. If you `docker exec` the bulk-import
> script while the backend is up, the script silently fails to write
> face embeddings to Qdrant — rows land in SQLite, text search works,
> but **face-photo search will not find the imported rows**.
>
> Use one of the two patterns below.

### A. Stop backend → import → start backend (recommended, lite profile)

```bash
# 1. Stop the backend so the importer can take the Qdrant lock
docker compose -f docker-compose.onprem.yml --profile lite stop backend

# 2. Run the importer in a one-off container that mounts the same
#    data volumes the backend uses.
docker run --rm \
    -v "$PWD/data/db:/app/data" \
    -v "$PWD/data/uploads:/app/uploads" \
    -v "$PWD/data/qdrant:/app/qdrant_data" \
    -v "$PWD/data/models:/app/models" \
    -v "$PWD/sample_import_images:/tmp/sample_import_images:ro" \
    -e SQLITE_PATH=/app/data/ubis.db \
    -e SUBMISSIONS_STORAGE_PATH=/app/uploads \
    -e QDRANT_URL=/app/qdrant_data \
    -e QDRANT_COLLECTION=face_embeddings \
    ubis/backend:onprem \
    python -m scripts.bulk_import_ui_bodies \
        /tmp/sample_import_images/demo.csv \
        /tmp/sample_import_images

# 3. Bring the backend (and Qdrant lock) back up
docker compose -f docker-compose.onprem.yml --profile lite start backend
```

Replace `docker` with `podman` (or `sudo docker`) to match your host.

### B. Full profile (Qdrant runs as a separate container/service)

When `QDRANT_URL` is an HTTP/gRPC endpoint instead of a local path, the
importer and the backend can both talk to Qdrant concurrently. With the
backend running, `docker exec` is safe:

```bash
docker cp sample_import_images ubis-backend:/tmp/
docker exec -it ubis-backend \
    python -m scripts.bulk_import_ui_bodies \
        /tmp/sample_import_images/demo.csv \
        /tmp/sample_import_images
```

### How to tell the import was complete (face embeddings really in Qdrant)

```bash
docker exec ubis-backend python -c "
import sqlite3
from app.services import qdrant_client
q = qdrant_client.get_client()
c = sqlite3.connect('/app/data/ubis.db')
qids = [r[0] for r in c.execute(\"SELECT i.qdrant_point_id FROM images i JOIN submissions s ON i.submission_id=s.id WHERE s.attributes_manual LIKE '%DDR-DEMO-%' AND i.qdrant_point_id IS NOT NULL\")]
pts = q.retrieve(collection_name='face_embeddings', ids=qids, with_vectors=False)
print(f'demo qdrant_point_ids in SQLite: {len(qids)}  /  present in Qdrant: {len(pts)}')
"
# Expected: '5 / 5' after a clean import of the 2 demo rows.
```

## Verify

After the import succeeds:

1. Open the UBIS web UI (default `http://<host>:8080`).
2. Log in as `admin` (password is in `.env`).
3. Click **Search**, type `DDR-DEMO` (or `male`) in the description
   box, click **Search**. Both demo cases should appear in the
   shortlist with their photos.
4. **Face search:** click **Search**, upload
   `sample_import_images/images/case2/face_front.png`, click **Search**.
   `DDR-DEMO-002-2026` should come back at rank 1 with a `high`
   confidence score around `1.000` (the probe and the indexed image
   are the same file). This step is the real proof that the face
   embeddings made it into Qdrant.

## Cleaning up

The two demo rows can be deleted from the UI via **UI Body Records →
delete**, or from the database directly:

```bash
docker exec -it ubis-backend python -c "
import sqlite3
c = sqlite3.connect('/app/data/ubis.db')
c.execute(\"DELETE FROM submissions WHERE attributes_manual LIKE '%DDR-DEMO-%'\")
c.commit()
print('demo rows removed')
"
```

## Where to go next

- [`docs/BULK_IMPORT_QUICK_REFERENCE.md`](../docs/BULK_IMPORT_QUICK_REFERENCE.md) — one-page summary for data-entry teams.
- [`docs/BULK_IMPORT_GUIDE.md`](../docs/BULK_IMPORT_GUIDE.md) — full guide with troubleshooting.
- [`docs/BULK_IMPORT_AT_SCALE.md`](../docs/BULK_IMPORT_AT_SCALE.md) — batching strategy for 10 000+ records and overnight runs.
