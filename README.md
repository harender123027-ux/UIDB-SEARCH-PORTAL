# UBIS — Unidentified Body Identification System

Law-enforcement web application for unidentified-body registration, face matching, text/voice search, and proclaimed-offender workflows.

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

## Documentation (remaining)

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
