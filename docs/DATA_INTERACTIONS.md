# Data Flow & Storage Architecture

**Purpose:** Details how data flows through the UBIS system and how different storage layers interact.  
**Audience:** Architects, Developers, DevOps staff  
**Last Updated:** May 2026

---

## Quick Overview

This document explains the data journey from submission → storage → embedding → search. See `SYSTEM_DESIGN.md` for high-level architecture overview.

## 1. Data Models (Database Schema)

The PostgreSQL/SQLite database stores metadata, users, and mapping data.

### Districts (`districts`)
| Column | Type | Description |
|---|---|---|
| `id` | UUID | Primary Key |
| `name` | String | Unique District Name |
| `code` | String | Official District Code (from Master Excel) |
| `is_active` | Boolean | Soft-delete flag |
| `created_at` | DateTime | Auto-timestamp |

### Police Stations (`police_stations`)
| Column | Type | Description |
|---|---|---|
| `id` | UUID | Primary Key |
| `district_id` | UUID | Foreign Key -> `districts.id` |
| `name` | String | Station Name (Unique within district) |
| `code` | String | Official Station Code (from Master Excel) |
| `is_active` | Boolean | Soft-delete flag |
| `created_at` | DateTime | Auto-timestamp |

### Other Core Tables
- **`submissions`**: `id`, `created_at`, `attributes_ai`, `attributes_manual`, `face_condition`, `status`
- **`images`**: `id`, `submission_id`, `image_type`, `path`, `face_condition`, `embedding_confidence`, `quality_score`, `qdrant_point_id`, `created_at`
- **`reference_persons`**: `id`, `label`, `photo_path`, `attributes`, `created_at` — *retained but unused in Phase 1 (criminal/missing-person matching out of scope).*
- **`criminals`**: `id`, `name`, `fir`, `district`, `station`, `arrest_date`, `notes`, `photo_paths`, `created_by`, `created_at` — *retained but unused in Phase 1.*
- **`audit_log`**: `id`, `user_id`, `action`, `resource_type`, `resource_id`, `ip_address`, `created_at`

## 2. File Storage

- **Development**: Local filesystem (`backend/uploads/` and `backend/reference_photos/`).
- **Production**: Azure Blob Storage containers (`uploads` and `references`).
- **Abstraction**: `app/storage.py` provides a unified interface for both environments.

## 3. Vector Interactions (Qdrant)

Face embeddings are stored in Qdrant for fast similarity search.

- **Point Structure**:
    - **ID**: `qdrant_point_id` matching the `images` table's ID.
    - **Vector**: 512-dimensional embedding from InsightFace.
    - **Payload**: Metadata like `submission_id`, `image_type`, and `label`.
- **Search Logic**: Uses cosine similarity to find the closes matches in high-dimensional space.

## Data Migration

The system includes a robust migration tool for populating the District/PS master data:
- **Location**: `backend/scripts/migrate_districts_stations.py`
- **Source**: `District PS master.xlsx` (Root directory)
- **Operation**: Upserts data based on names and ensures `code` columns are populated correctly.
- **Production**: Run against the Azure PostgreSQL instance using the `DATABASE_URL` environment variable.

## 4. Submission Data Flow

1.  **Client POST**: The frontend sends a multipart/form-data request with images and attributes.
2.  **API Handler**: `app/routers/submissions.py` receives the request.
3.  **Storage**: Images are saved to the persistent storage layer.
4.  **Embedding**: `services/face_embedding.py` processes each image to extract its feature vector.
5.  **Vector DB**: The embedding is UPSERTED into Qdrant.
6.  **Relational DB**: Metadata is INSERTED into `submissions` and `images` tables.
7.  **Audit**: A record is added to the `audit_log`.
8.  **Completion**: The submission ID is returned to the client.

## 5. Criminal Record Matching — Out of scope for Phase 1

Criminal-records / proclaimed-offender matching (e.g. for CCTV / surveillance
use cases) and missing-person matching are **out of scope** for the Phase 1
Gurugram pilot. The supporting tables (`criminals`, `reference_persons`) and
the Qdrant `reference_*` payload flag remain in the codebase, but no UI is
exposed and the search endpoints are restricted to the UI-body repository.

To reintroduce the feature in a later phase, re-enable the "Search In"
selector in `ubis-pwa.jsx` and re-mount the `CriminalRecords` admin tab.
