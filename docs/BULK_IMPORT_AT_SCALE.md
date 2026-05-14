# Bulk Import at Scale (10k – 50k records)

**Audience:** Police IT operating the UBIS on-prem server when historical UI-body data must be loaded in volume.

This guide complements **[`BULK_IMPORT_GUIDE.md`](BULK_IMPORT_GUIDE.md)**. The
small-batch workflow there (≤ ~500 cases per batch) is identical; the differences
at scale are **planning, batching, runtime, and storage**.

---

## 1. What the import does, in one paragraph

`backend/scripts/bulk_import_ui_bodies.py` reads a CSV, for each row writes the
case metadata into the `submissions` table, copies the listed images into the
configured storage (local `data/uploads/<submission_id>/...` or Azure Blob),
runs face detection + embedding through **InsightFace `buffalo_l/w600k_r50.onnx`**,
and upserts one 512-d vector per detected face into the Qdrant collection
`face_embeddings`. An audit row (`action = bulk.import`) is written per
submission. The script is **resumable in batches**: each CSV is processed
top-down and a failed row prints an error and continues.

---

## 2. Time and resource budget

The dominant cost at scale is face embedding (CPU-bound on-prem, no GPU). The
following numbers are for a typical 4 vCPU / 8 GB RAM on-prem host with embedded
Qdrant (lite profile) and the **single backend worker** required by that
profile:

| Per-image cost | Value |
|----------------|-------|
| Face detection + embedding (CPU) | **~0.4 – 0.8 s** |
| Storage write + DB insert | ~5 – 15 ms |
| Qdrant upsert (embedded) | ~2 – 8 ms |

| Per-record cost (avg 1.5 face-bearing images per case) | Value |
|--------------------------------------------------------|-------|
| End-to-end | **~0.8 – 1.5 s** |
| 1 000 records | ~15 – 25 minutes |
| 10 000 records | ~3 – 4 hours |
| **50 000 records** | **~15 – 20 hours** (run overnight in batches) |

The numbers scale linearly with image count per case. Records with 6–10 tattoo
photos plus full-body / belonging shots take 4–6× longer than face-only rows.

GPU acceleration (CUDA-capable host) brings per-image cost to **~30–60 ms** and
shortens 50 k to **~1.5 – 2 hours**, but is not part of the default on-prem
package.

---

## 3. Storage planning

Rule of thumb for **50 000 cases**:

| Component | Estimate |
|-----------|----------|
| Average case (3 images, ~3 MB each) | ~9 MB |
| Image storage total (`data/uploads/`) | **~450 GB** |
| Qdrant vectors (512-d float32 + payload, ~3 KB ea) | ~750 MB for 250 k vectors |
| SQLite database | ~250–500 MB (rows + indices) |
| Logs + audit table | ~100 MB |
| **Free disk required before import** | **~600 GB** with headroom |

Before starting a large run:

```bash
df -h ./data/uploads ./data/qdrant ./data/db
```

If storage is on the network (NFS, SMB), benchmark with `dd if=/dev/zero of=./data/uploads/_t bs=1M count=1024` before relying on it for a 50 k import.

---

## 4. Batch layout strategy

Do **not** ship 50 000 rows in one CSV. Split into **10–20 batches** of
**2 500 – 5 000 rows each**:

```
import-batch-001/   (2 500 rows)
  ui_body_template.csv
  images/
import-batch-002/
  ...
import-batch-020/
```

Why batch:

- A crash, full disk, or operator stop interrupts only one batch.
- Each batch is its own zip/tar transfer (manageable size, resumable).
- You can spread imports across nights without locking the system out of
  interactive use during the day.
- The data-entry team can validate per-batch (5 000 rows is auditable in a few
  hours).

Use a stable batch numbering convention so any rerun is unambiguous, e.g.
`gurugram-2026q1-batch-007`.

---

## 5. Running a batch

Single worker is mandatory on the **lite** profile (embedded Qdrant takes an
exclusive lock on `/app/qdrant_data`). The `docker-compose.onprem.yml` shipped
in this handover already sets `--workers 1` on the backend service; do **not**
raise it unless you switch to a dedicated Qdrant server container.

```bash
# Stage the batch in a location bind-mounted by the backend container.
mkdir -p ./data/uploads/import-batch-007
unzip /media/usb/import-batch-007.zip -d ./data/uploads/import-batch-007/

# Confirm shape.
ls ./data/uploads/import-batch-007/
# Expected: ui_body_template.csv  images/

# Run the import (Podman).
podman compose -f docker-compose.onprem.yml --profile lite exec -T backend \
  python -m scripts.bulk_import_ui_bodies \
  /app/uploads/import-batch-007/ui_body_template.csv \
  /app/uploads/import-batch-007 \
  | tee ./data/logs/import-batch-007.log
```

The `tee` captures `Imported record …` and any `Error importing row …` lines
in a per-batch log under `./data/logs/`.

> If you use Docker instead of Podman, replace `podman compose` with
> `docker compose`. The rest of the command is identical.

---

## 6. Running multiple batches overnight

A safe overnight runner does one batch at a time, logs each one, and stops on
failure:

```bash
#!/usr/bin/env bash
# scripts/onprem/run_import_queue.sh — minimal example, edit batch list as needed.
set -euo pipefail
BATCHES=( import-batch-001 import-batch-002 import-batch-003 )
for B in "${BATCHES[@]}"; do
  echo "[*] $(date -Iseconds) starting $B"
  podman compose -f docker-compose.onprem.yml --profile lite exec -T backend \
    python -m scripts.bulk_import_ui_bodies \
    "/app/uploads/${B}/ui_body_template.csv" "/app/uploads/${B}" \
    2>&1 | tee -a "./data/logs/${B}.log"
  echo "[*] $(date -Iseconds) finished $B"
done
```

Do not run two batches in parallel against the same backend — the embedded
Qdrant store is single-writer.

---

## 7. Validating a batch after import

```bash
# Row count delta.
podman exec ubis-backend python -c "
import sqlite3
c = sqlite3.connect('/app/data/ubis.db')
print('submissions:', c.execute('SELECT COUNT(*) FROM submissions').fetchone()[0])
print('images:     ', c.execute('SELECT COUNT(*) FROM images').fetchone()[0])
print('audit rows :', c.execute(\"SELECT COUNT(*) FROM audit_log WHERE action='bulk.import'\").fetchone()[0])
"

# Per-batch error count from the log.
grep -c '^Error importing row' ./data/logs/import-batch-007.log
```

Then open UBIS in the browser and search 3–5 DD numbers from that batch. Every
case should open with the listed images and DD number visible.

---

## 8. Housekeeping after large runs

### 8.1 Search-probe submissions

Anonymous face-search uploads create a temporary submission row marked with
`_search_probe = true` in `attributes_manual`. They should never appear in the
case gallery. The cleanup script removes them, along with their files,
matches, audit rows, and Qdrant vectors:

```bash
podman exec ubis-backend python -m scripts.cleanup_search_probe_submissions --dry-run
podman exec ubis-backend python -m scripts.cleanup_search_probe_submissions
```

After upgrading from a build that pre-dated the `_search_probe` marker, run
once with `--include-legacy` to sweep empty-attribute rows left by the old
upload-and-match path:

```bash
podman exec ubis-backend python -m scripts.cleanup_search_probe_submissions --include-legacy
```

> Embedded Qdrant note: the cleanup script tries to delete vectors via the
> shared Qdrant store. If the backend is running, the script logs
> `Storage folder ... is already accessed by another instance ...`. The DB and
> file deletions still succeed, and the backend keeps orphan Qdrant points
> hidden because the match path filters refs that no longer exist in SQLite.
> For a hard scrub, stop the backend (`podman stop ubis-backend`) then run the
> script in a one-shot container that mounts `data/qdrant`, and finally
> `podman start ubis-backend`.

### 8.2 SQLite vacuum

After many batches, reclaim space:

```bash
podman exec ubis-backend python -c "
import sqlite3
sqlite3.connect('/app/data/ubis.db').execute('VACUUM')
"
```

### 8.3 Backup

Take a full backup after each import batch finishes:

```bash
bash scripts/onprem/ubis-backup.sh
```

The backup script archives `./data/` (DB, Qdrant, uploads, logs).

---

## 9. When the lite profile stops being enough

You will outgrow the embedded Qdrant + SQLite setup around **~50 000 cases**
or once two officers regularly search concurrently. The handover stack is
ready for this:

- Switch to **`--profile full`** which adds Postgres (`docker-compose.onprem.yml`
  defines it). Set `DATABASE_URL` in `.env`.
- Run **Qdrant as a separate container** (`qdrant/qdrant` image) instead of
  embedded mode by changing `QDRANT_URL` in `.env` to `http://qdrant:6333`.
  Once Qdrant is a server, you can raise the backend `--workers` count.
- For ongoing imports while officers use the system, move embedding into a
  background queue (e.g. RQ, Celery, Arq) and have `bulk_import_ui_bodies.py`
  enqueue jobs rather than run them inline. The script is structured so the
  embedding step is the only network-bound call to replace.

See **`docs/UAT_AND_POLICE_SIGNOFF.md` §A — Sizing** for the matching hardware
tiers.

---

## 10. Failure modes and recovery

| Symptom | Cause | Recovery |
|---------|-------|----------|
| `Error: CSV file not found` | Wrong path / not extracted | `ls` the path; re-unzip the batch |
| `Warning: Image … not found. Skipping <slot>.` | CSV path mismatch (case / slashes) | Fix path in CSV; re-run batch (idempotent only if you delete the half-imported `dd_no` rows first) |
| `Error importing row …: invalid literal for int()` | Non-integer in `age_min`, `age_max`, or `height_cm` | Fix the CSV cell; re-run that row only by creating a 1-row batch CSV |
| Script halts mid-batch | Disk full / OOM | Free space, re-run; delete already-imported rows from the CSV before re-running |
| `No face embeddings found for this submission` on search | InsightFace model failed to load | Confirm `data/models/buffalo_l/*.onnx` exists; restart backend; rerun import |
| `Storage folder ... is already accessed by another instance` | Two processes opening embedded Qdrant | Only the running backend may hold the lock; stop other tools before invoking `cleanup_search_probe_submissions` directly |

---

## 11. Worked timeline for 50 000 cases

Assuming a single 4 vCPU / 16 GB on-prem host, lite profile, average 2 photos
per case:

| Day | Activity |
|-----|----------|
| Day 0 | Data-entry team validates schema, ships first ZIP batch of 2 500 rows |
| Day 1 evening | IT imports batch 001 (~2 h) + nightly backup |
| Days 2 – 14 | One 2 500-row batch per night = 20 nights ≈ 50 000 rows total |
| Day 7 | Mid-run vacuum + backup checkpoint |
| Day 14 | Final batch + full backup + spot-check of 50 random DD numbers |
| Day 15 | Officer training session against the populated index |

Run a **dress rehearsal with 250 rows** on Day 0 before committing to the
20-night plan — it surfaces any CSV-format or photo-path issue in two hours.

---

**Last updated:** 2026-05-14
