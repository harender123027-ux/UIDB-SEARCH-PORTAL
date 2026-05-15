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
[`docs/HANDOVER_GURUGRAM/README.md`](../docs/HANDOVER_GURUGRAM/README.md)),
copy this folder into the backend container and run the script inside it:

```bash
# Copy sample bundle into the backend container
docker cp sample_import_images ubis-backend:/tmp/

# Run the importer inside the container
docker exec -it ubis-backend \
    python -m scripts.bulk_import_ui_bodies \
        /tmp/sample_import_images/demo.csv \
        /tmp/sample_import_images
```

Replace `docker` with `podman` (or `sudo docker`) to match your host.

## Verify

After the import succeeds:

1. Open the UBIS web UI (default `http://<host>:8080`).
2. Log in as `admin` (password is in `.env`).
3. Click **Search**, type `male` in the description box, click **Search**.
4. You should see `DDR-DEMO-001-2026` and `DDR-DEMO-002-2026` in the
   shortlist with their photos.

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
