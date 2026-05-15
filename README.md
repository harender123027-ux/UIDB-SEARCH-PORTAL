# UBIS — Unidentified Body Identification System

Law-enforcement web application for unidentified-body (UI body) registration,
face / attribute / voice search, and case management. Built for the
Haryana Police Gurugram pilot.

> **Phase 1 scope:** UI-body registration and within-repository matching.
> Criminal-records / proclaimed-offender management and missing-person
> matching are deferred to a later phase — the underlying tables and
> `/api/criminals` endpoints stay in the codebase but are not exposed in
> the UI.

## Public demo (reference only)

- Frontend: https://agreeable-sky-09757b500.4.azurestaticapps.net/
- API: https://haryana-facial-recog.azurewebsites.net/docs

Production police deployments should use **on-prem** install below, not these URLs.

---

## On-prem (recommended for police IT)

| Resource | Link |
|----------|------|
| **On-prem guide (read this first)** | [`docs/HANDOVER_GURUGRAM/README.md`](docs/HANDOVER_GURUGRAM/README.md) |
| **One-command install** | `bash scripts/onprem/install.sh` (after [INSTALL.txt](INSTALL.txt) prerequisites) |
| **Compose file** | `docker-compose.onprem.yml` |

---

## Sample data (try the pipeline end-to-end)

| File / folder | Use for |
|---------------|---------|
| [`sample_import_images/`](sample_import_images/) | Ready-to-run bulk-import demo: `demo.csv` plus two cases of real face photos. See [`sample_import_images/README.md`](sample_import_images/README.md) for the one-command import. |
| [`ui_body_template.csv`](ui_body_template.csv) | Full bulk-import template with 5 realistic Haryana sample rows showing every column. |
| [`ui_body_template.xlsx`](ui_body_template.xlsx) | Excel version of the same template (with dropdown validation) for data-entry teams. |
| [`Police Station_District_Haryana.xlsx`](Police%20Station_District_Haryana.xlsx) | District / police-station master used by the geo-mapping seed. |
| [`sample_test_images/`](sample_test_images/) | Loose portrait photos for ad-hoc Search-tab testing. |

---

## Documentation

| Document | Description |
|----------|-------------|
| [`docs/SYSTEM_DESIGN.md`](docs/SYSTEM_DESIGN.md) | Architecture and AI pipeline |
| [`docs/DATA_INTERACTIONS.md`](docs/DATA_INTERACTIONS.md) | Data flow and storage |
| [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md) | HTTP API |
| [`docs/TESTING_GUIDE.md`](docs/TESTING_GUIDE.md) | pytest & Playwright |
| [`docs/BULK_IMPORT_GUIDE.md`](docs/BULK_IMPORT_GUIDE.md) | Bulk import (CSV + images) |
| [`docs/BULK_IMPORT_QUICK_REFERENCE.md`](docs/BULK_IMPORT_QUICK_REFERENCE.md) | Bulk import one-pager |
| [`HANDOVER_README.md`](HANDOVER_README.md) | Handover package overview |
| [`docs/UAT_AND_POLICE_SIGNOFF.md`](docs/UAT_AND_POLICE_SIGNOFF.md) | UAT & sign-off |
| [`docs/HANDOVER_GURUGRAM/`](docs/HANDOVER_GURUGRAM/) | Install, operations, training, acceptance |

---

## Local development (engineers)

**Backend**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
DATABASE_URL= POSTGRES_HOST= POSTGRES_USER= POSTGRES_PASSWORD= python -m scripts.seed_admin
uvicorn app.main:app --reload --port 8000
```

Use empty Postgres env vars if `.env` points at a cloud DB you cannot reach; otherwise SQLite is used.

**Frontend**

```bash
npm install
VITE_API_URL=http://localhost:8000 npm run dev
```

Default seed login: `admin` / `changeme` unless overridden by `INITIAL_ADMIN_PASSWORD`.

---

## Tests

```bash
cd backend && source .venv/bin/activate && pytest tests/ -v
cd .. && npx playwright test
```

---

## Stack

FastAPI · SQLite or PostgreSQL · Qdrant · InsightFace / PyTorch · React (Vite PWA)

---

**UBIS — Haryana Police** · AI outputs are investigative leads only; human verification required. · Proprietary

---

## Git and model weights

Large files under `backend/models/` are **ignored by Git** (see `.gitignore`). Official **handover ZIP** builds may still include that folder so deployments work offline. After `git clone`, copy weights from the handover package or follow `docs/HANDOVER_GURUGRAM/01_INSTALL.md`. See `backend/models/README.md`.
