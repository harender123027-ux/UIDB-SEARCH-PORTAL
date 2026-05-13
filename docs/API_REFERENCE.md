# UBIS API Reference

Complete API documentation for the Unidentified Body Identification System.

**Primary Functions:**
- Unidentified Body Identification
- Face Recognition for Proclaimed Offenders

**Base URL:** `https://haryana-facial-recog.azurewebsites.net`

**Authentication:** Most endpoints require a JWT bearer token in the Authorization header:
```
Authorization: Bearer <token>
```

---

## Table of Contents

1. [Authentication](#authentication)
2. [Submissions](#submissions)
3. [Search](#search)
4. [Matching](#matching)
5. [Proclaimed Offenders](#proclaimed-offenders)
6. [Dashboard](#dashboard)
7. [User Management (Admin)](#user-management-admin)
8. [Geographic Data](#geographic-data)
9. [Audit Log](#audit-log)
10. [Health Check](#health-check)

---

## Authentication

### POST /api/auth/login

Authenticate a user and receive a JWT access token.

**Request Body:**
```json
{
  "username": "string",
  "password": "string"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "username": "admin",
    "name": "Administrator",
    "role": "admin",
    "district": "Gurugram",
    "station": "DLF Phase 1"
  }
}
```

**Response (401 Unauthorized):**
```json
{
  "detail": "Invalid credentials"
}
```

**Example:**
```bash
curl -X POST https://haryana-facial-recog.azurewebsites.net/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "changeme"}'
```

---

## Submissions

### POST /api/submissions

Create a new case submission with images and attributes.

**Authentication:** Required

**Content-Type:** `multipart/form-data`

**Form Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `files` | File[] | Yes | Image files (JPEG, PNG) |
| `image_types` | string | Yes | JSON array: `["face_frontal", "face_left", ...]` |
| `attributes_ai` | string | No | JSON object for structured case attributes (demographics, clothing text, marks—typically from the form or bulk import; not auto-inferred by vision on upload) |
| `attributes_manual` | string | No | JSON object with manually entered attributes |
| `face_condition` | string | No | One of: `normal`, `partial`, `bloated`, `damaged` |

**Valid image_types:**
- `face_frontal` (recommended for face matching quality)
- `face_left`
- `face_right`
- `full_body`
- `tattoo_1` through `tattoo_10` (supports up to 10 tattoo/mark/person items; legacy `tattoo` is mapped to `tattoo_1`)
- `clothing` (relaxed face detection for embeddings)
- `belonging` (bags, wallets, documents—relaxed face detection)
- `other`

**Response (200 OK):**
```json
{
  "submission_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "captured",
  "images": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "image_type": "face_frontal",
      "path": "uploads/550e8400.../face_frontal.jpg",
      "embedding_confidence": 0.95,
      "qdrant_point_id": "770e8400-e29b-41d4-a716-446655440002",
      "is_primary": false
    }
  ]
}
```

**Example:**
```bash
curl -X POST https://haryana-facial-recog.azurewebsites.net/api/submissions \
  -H "Authorization: Bearer <token>" \
  -F "files=@face_photo.jpg" \
  -F 'image_types=["face_frontal"]' \
  -F 'attributes_manual={"gender": "male", "age_min": 25, "age_max": 35}' \
  -F "face_condition=normal"
```

---

### GET /api/submissions

List all submissions.

**Authentication:** Required

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 50 | Maximum results |
| `offset` | int | 0 | Pagination offset |
| `status` | string | - | Filter by status |

**Response (200 OK):**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "created_at": "2026-03-23T10:30:00",
    "status": "captured",
    "attributes_manual": {
      "gender": "male",
      "found_district": "Gurugram"
    },
    "face_condition": "normal",
    "image_count": 2,
    "match_count": 3
  }
]
```

---

### GET /api/submissions/{id}

Get detailed information about a specific submission.

**Authentication:** Required

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | UUID | Submission ID |

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2026-03-23T10:30:00",
  "status": "matched",
  "attributes_ai": {
    "gender": "male",
    "age_min": 25,
    "age_max": 30
  },
  "attributes_manual": {
    "found_district": "Gurugram",
    "found_date": "2026-03-22",
    "notes": "Found near railway station"
  },
  "face_condition": "normal",
  "images": [
    {
      "id": "image-uuid",
      "image_type": "face_frontal",
      "path": "uploads/550e8400.../face_frontal.jpg",
      "embedding_confidence": 0.95,
      "is_primary": false
    }
  ],
  "matches": [
    {
      "id": "match-uuid",
      "reference_person_id": "ref-uuid",
      "overall_score": 0.89,
      "rank": 1,
      "status": "pending_review"
    }
  ]
}
```

---

## Search

### POST /api/search/combined

Perform multi-modal search using face photo, text description, and/or voice note.

**Authentication:** Required (recommended)

**Content-Type:** `multipart/form-data`

**Form Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `files` | File | No | Face image for visual search |
| `query` | string | No | Text description |
| `audio` | File | No | Voice note (will be transcribed) |

*At least one field must be provided.*

**Response (200 OK):**
```json
{
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "label": "Rajesh Kumar",
      "photo_path": "reference_photos/rajesh.jpg",
      "score": 0.92,
      "overlap": 2,
      "sources": ["face", "text"],
      "match_count": 3,
      "matched_by": [
        {
          "submission_id": "sub-uuid",
          "score": 0.89
        }
      ]
    }
  ],
  "transcript": "male about 30 years old tattoo on left arm"
}
```

**Example - Search by photo:**
```bash
curl -X POST https://haryana-facial-recog.azurewebsites.net/api/search/combined \
  -H "Authorization: Bearer <token>" \
  -F "files=@search_photo.jpg"
```

**Example - Search by text:**
```bash
curl -X POST https://haryana-facial-recog.azurewebsites.net/api/search/combined \
  -H "Authorization: Bearer <token>" \
  -F "query=male, 25-30, scar on forehead"
```

**Example - Combined search:**
```bash
curl -X POST https://haryana-facial-recog.azurewebsites.net/api/search/combined \
  -H "Authorization: Bearer <token>" \
  -F "files=@search_photo.jpg" \
  -F "query=male, tattoo on neck"
```

---

## Matching

### POST /api/match/{submission_id}

Trigger matching for a specific submission against the reference database.

**Authentication:** Required

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `submission_id` | UUID | Submission to match |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `top_k` | int | 10 | Number of top matches to return |

**Response (200 OK):**
```json
{
  "submission_id": "550e8400-e29b-41d4-a716-446655440000",
  "matches": [
    {
      "id": "match-uuid",
      "reference_person_id": "ref-uuid",
      "reference_label": "Missing Person Name",
      "overall_score": 0.89,
      "face_score": 0.92,
      "rank": 1,
      "status": "pending_review"
    }
  ],
  "match_count": 5
}
```

---

## Proclaimed Offenders

Manage the database of proclaimed offenders and wanted criminals for face recognition matching.

### POST /api/criminals

Upload a new proclaimed offender record with mugshots/photos.

**Authentication:** Required

**Content-Type:** `multipart/form-data`

**Form Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Offender's name |
| `fir` | string | No | FIR/Case number |
| `district` | string | No | District name |
| `station` | string | No | Police station |
| `arrest_date` | string | No | Warrant/Proclamation date (YYYY-MM-DD) |
| `notes` | string | No | Offense details and additional notes |
| `photos` | File[] | No | Mugshots, surveillance images |

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "John Doe",
  "fir": "FIR/2026/001",
  "district": "Gurugram",
  "station": "DLF Phase 1",
  "arrest_date": "2026-03-22",
  "notes": "Proclaimed offender - Armed robbery",
  "photos": ["criminals/550e8400.../photo1.jpg"],
  "created_at": "2026-03-23T10:30:00"
}
```

**Example:**
```bash
curl -X POST https://haryana-facial-recog.azurewebsites.net/api/criminals \
  -H "Authorization: Bearer <token>" \
  -F "name=John Doe" \
  -F "fir=FIR/2026/001" \
  -F "district=Gurugram" \
  -F "station=DLF Phase 1" \
  -F "arrest_date=2026-03-22" \
  -F "notes=Proclaimed offender - Armed robbery" \
  -F "photos=@mugshot1.jpg" \
  -F "photos=@mugshot2.jpg"
```

---

### GET /api/criminals

List all proclaimed offender records.

**Authentication:** Required

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 50 | Maximum results |
| `offset` | int | 0 | Pagination offset |

**Response (200 OK):**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "John Doe",
    "fir": "FIR/2026/001",
    "district": "Gurugram",
    "station": "DLF Phase 1",
    "arrest_date": "2026-03-22",
    "notes": "Proclaimed offender - Armed robbery",
    "photos": ["criminals/550e8400.../photo1.jpg"],
    "created_at": "2026-03-23T10:30:00"
  }
]
```

---

### GET /api/criminals/photo/{filename}

Retrieve a proclaimed offender's photo.

**Authentication:** Required

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `filename` | string | Photo filename |

**Response:** Image file (JPEG/PNG)

---

## Dashboard

### GET /api/dashboard

Get dashboard statistics and recent activity.

**Authentication:** Required

**Response (200 OK):**
```json
{
  "total_submissions": 42,
  "matched": 15,
  "pending_review": 8,
  "reference_persons": 150,
  "recent": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "matched",
      "created_at": "2026-03-23T10:30:00",
      "match_count": 3
    }
  ]
}
```

---

## User Management (Admin)

*All endpoints require admin role.*

### GET /api/admin/users

List all users.

**Response (200 OK):**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "username": "officer1",
    "name": "Officer One",
    "role": "field_officer",
    "district": "Gurugram",
    "station": "DLF Phase 1",
    "is_active": true,
    "created_at": "2026-03-01T10:00:00"
  }
]
```

---

### POST /api/admin/users

Create a new user.

**Request Body:**
```json
{
  "username": "newuser",
  "password": "securepassword",
  "name": "New User",
  "role": "investigator",
  "district_id": "district-uuid",
  "station_id": "station-uuid"
}
```

**Valid roles:** `investigator`, `admin`

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "newuser",
  "name": "New User",
  "role": "investigator",
  "is_active": true
}
```

---

### PATCH /api/admin/users/{id}

Update a user.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | UUID | User ID |

**Request Body:**
```json
{
  "name": "Updated Name",
  "role": "investigator",
  "is_active": true,
  "password": "newpassword",
  "district_id": "district-uuid",
  "station_id": "station-uuid"
}
```

*All fields are optional.*

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "user1",
  "name": "Updated Name",
  "role": "investigator",
  "is_active": true
}
```

---

### GET /api/admin/districts

List all districts.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `is_active` | int | - | Filter by active status (0 or 1) |

**Response (200 OK):**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Gurugram",
    "is_active": true
  }
]
```

---

### POST /api/admin/districts

Create a new district.

**Request Body:**
```json
{
  "name": "New District"
}
```

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "New District",
  "is_active": true
}
```

---

### GET /api/admin/districts/{id}/stations

List police stations in a district.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `is_active` | int | - | Filter by active status |

**Response (200 OK):**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "DLF Phase 1",
    "is_active": true
  }
]
```

---

### POST /api/admin/districts/{id}/stations

Create a police station in a district.

**Request Body:**
```json
{
  "name": "New Police Station"
}
```

---

### PATCH /api/admin/stations/{id}

Update a police station.

**Request Body:**
```json
{
  "is_active": false
}
```

---

## Geographic Data

### GET /api/geo/districts

List active districts for form dropdowns.

**Response (200 OK):**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Gurugram"
  },
  {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "name": "Faridabad"
  }
]
```

---

### GET /api/geo/districts/{id}/stations

List active police stations in a district.

**Response (200 OK):**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "DLF Phase 1"
  },
  {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "name": "Cyber City"
  }
]
```

---

## Audit Log

### GET /api/audit

Get audit log entries.

**Authentication:** Required

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 100 | Maximum results |
| `offset` | int | 0 | Pagination offset |
| `action` | string | - | Filter by action type |

**Response (200 OK):**
```json
[
  {
    "id": 1,
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "action": "submission.create",
    "resource_type": "submission",
    "resource_id": "660e8400-e29b-41d4-a716-446655440001",
    "ip_address": "192.168.1.100",
    "created_at": "2026-03-23T10:30:00"
  }
]
```

**Common action types:**
- `user.login`
- `user.logout`
- `submission.create`
- `submission.view`
- `match.review`
- `feedback.submit`
- `criminal.create`
- `admin.user.create`
- `admin.user.update`

---

## Health Check

### GET /api/health

Check if the API is running.

**Authentication:** Not required

**Response (200 OK):**
```json
{
  "status": "ok"
}
```

---

## Error Responses

All endpoints may return the following error responses:

### 400 Bad Request
```json
{
  "detail": "Invalid input: field 'name' is required"
}
```

### 401 Unauthorized
```json
{
  "detail": "Not authenticated"
}
```

### 403 Forbidden
```json
{
  "detail": "Insufficient permissions"
}
```

### 404 Not Found
```json
{
  "detail": "Resource not found"
}
```

### 422 Unprocessable Entity
```json
{
  "detail": [
    {
      "loc": ["body", "username"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 500 Internal Server Error
```json
{
  "detail": "Internal server error"
}
```

---

## Rate Limiting

Currently no rate limiting is enforced. For production deployments, consider implementing rate limiting at the reverse proxy level (e.g., nginx, Cloudflare).

---

## Versioning

The API is currently at version `0.1.0`. Breaking changes will be communicated in release notes.

---

*Last updated: March 2026*
