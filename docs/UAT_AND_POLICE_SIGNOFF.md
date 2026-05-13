# UBIS — UAT, Testing & Police Sign-Off

**Audience:** Police IT, Cyber Cell, project nodal officers, and authorised signatories for go-live on **department-owned or department-contracted infrastructure**.

**Purpose:** This document defines how the police department validates UBIS before wider use, what evidence is expected from testing, and **who must formally sign off**. It complements the developer-focused [Testing Guide](TESTING_GUIDE.md) (automated pytest / Playwright).

**Related:** [On-prem install & secrets](HANDOVER_GURUGRAM/01_INSTALL.md), [Operations](HANDOVER_GURUGRAM/02_OPERATIONS.md), [API Reference](API_REFERENCE.md).

---

## 1. Definitions

| Term | Meaning |
|------|---------|
| **UAT** | User Acceptance Testing — police users verify workflows, data handling, and outcomes against agreed requirements. |
| **SIT** | System Integration Testing — IT verifies components (app, DB, object storage, vector DB, TLS, backups) work together on **target hosting**. |
| **Internal release** | Limited rollout (e.g. Cyber Cell + pilot districts) before public announcement. |
| **Sign-off** | Written approval by an authorised role that a checklist item or phase is accepted. |
| **Historic data pilot** | Police-prepared past UI-body / missing-person records uploaded via bulk import (or equivalent) onto UAT/staging for realistic load and match testing. |
| **Accuracy evaluation** | Police-led measurement of whether top matches are **useful leads** (and recording of misses), using agreed sample size and ground truth or blind review. |

---

## 2. UAT Objectives

1. Confirm core workflows work on **police-controlled** servers and networks.  
2. Confirm **roles and access** match operational policy (who may create cases, view all cases, administer users).  
3. Confirm **audit trail** and match **feedback** meet investigation and accountability needs.  
4. Confirm **search and matching** behaviour is understood: outputs are **investigative leads**, subject to officer verification.  
5. Confirm **data residency, retention, and backup** align with department rules.  
6. **Police upload of past (historic) records** in agreed pilot volume; verify import completeness and search/match behaviour on real department data patterns.  
7. **Police sign-off on match usefulness and accuracy** against an agreed evaluation method (Section 5.9).  
8. Capture defects and **go / no-go** for wider rollout.

---

## 3. Prerequisites Before UAT Starts

| # | Item | Owner (typical) |
|---|------|-----------------|
| 1 | UBIS deployed to **UAT/staging** environment on infrastructure approved by police IT | Police IT / vendor |
| 2 | TLS certificates, domain names, and firewall rules configured | Police IT |
| 3 | Secrets (DB URL, JWT secret, storage keys, Qdrant) stored securely per [01_INSTALL.md — secrets chapter](HANDOVER_GURUGRAM/01_INSTALL.md) — not in email or chat | Police IT |
| 4 | AI model files available on server (or mounted storage) per deployment guide | Police IT |
| 5 | Admin account created; **default passwords changed** | Police IT + admin user |
| 6 | Test / pilot users created per role (`investigator`, `admin` as needed) | Admin |
| 7 | Optional: anonymised or synthetic images for UAT (no real PII without legal clearance) | Nodal officer |
| 8 | Nodal officer and escalation matrix published | Police leadership |
| 9 | **Historic pilot dataset:** police units prepare past cases per [Police Station Bulk Data Guide](POLICE_STATION_BULK_DATA_GUIDE.md) (Excel/CSV + images); legal / sensitivity clearance as per department policy | District nodal + HQ coordination |
| 10 | **Accuracy evaluation plan agreed:** sample size, who scores matches, definition of “useful lead” / “miss”, and whether any rows have known ground truth (closed cases only, if used) | Nodal officer + investigation lead |

---

## 4. Testing Layers (What the Department Runs)

| Layer | Description | Typical owner |
|-------|-------------|----------------|
| **A. Smoke** | App loads, login, health endpoint, one case upload, one search | IT |
| **B. SIT** | API ↔ DB ↔ file storage ↔ Qdrant; backups restore drill (if applicable) | IT |
| **C. Security** | HTTPS only, session timeout, password policy, access from approved IPs/VPN, vulnerability scan per department policy | Cyber Cell / IT |
| **D. Functional UAT** | Scenarios in Section 5 executed by real users | Field / investigation staff |
| **E. Operational** | SOP fit: who captures photos, review of shortlists, logging of decisions | Supervisory officer |
| **F. Historic data & accuracy** | Police-led bulk upload of past records + structured scoring of match quality (Section 5.8–5.9) | District data entry + investigation / nodal |

Developer automated tests (`backend/tests/`, Playwright) may be run by IT or vendor as **evidence of build quality**; they **do not replace** police UAT.

---

## 5. UAT Scenario Checklist (Sign When Passed)

Use one row per scenario; record **Pass / Fail / Blocked**, tester name, and date. Attach screenshots or ticket IDs for failures.

### 5.1 Authentication & access

| ID | Scenario | Expected result |
|----|----------|-----------------|
| A1 | Valid user login | JWT issued; user lands in permitted UI |
| A2 | Invalid password | Access denied; no sensitive leak in error |
| A3 | Role: investigator cannot access admin-only screens | Denied or hidden |
| A4 | Session behaviour after idle (if configured) | Per policy |

### 5.2 Unidentified body case (submission)

| ID | Scenario | Expected result |
|----|----------|-----------------|
| C1 | Create case with frontal face + optional angles | Case saved; images stored; thumbnails/paths visible |
| C2 | Create case with clothing / belonging photos | Saved; relaxed embedding path acceptable |
| C3 | `face_condition` set (e.g. partial / damaged) | Stored and visible on detail view |
| C4 | Attributes (manual / structured) saved | Searchable in text flows |

### 5.3 Search & match

| ID | Scenario | Expected result |
|----|----------|-----------------|
| S1 | Text search returns shortlist | Relevant cases appear; scores understandable |
| S2 | Photo search / combined search | Results returned; latency acceptable on police network |
| S3 | Voice search (if enabled in UAT) | Transcript + shortlist; failure mode graceful if STT unavailable |
| S4 | Run match on a submission | Ranked list; confidence bands understandable to officers |
| S5 | Investigator records match feedback | Stored; visible in audit/history as designed |

### 5.4 Reference / missing persons & criminals (if in scope)

| ID | Scenario | Expected result |
|----|----------|-----------------|
| R1 | Admin adds reference person with photo | Embeddings stored; searchable |
| M1 | Criminal record upload and search target `criminal` | Per operational scope |

### 5.5 Admin & governance

| ID | Scenario | Expected result |
|----|----------|-----------------|
| G1 | Admin creates / disables user | Effect immediate |
| G2 | Audit log shows login, submission, match, admin actions | Timestamps and actors traceable |
| G3 | Dashboard loads with expected aggregates | No unauthorised data exposure |

### 5.6 Bulk import (smoke)

| ID | Scenario | Expected result |
|----|----------|-----------------|
| B1 | Import small pilot CSV + images per [Police Station Bulk Data Guide](POLICE_STATION_BULK_DATA_GUIDE.md) | Rows created; embeddings for filled columns |
| B2 | Invalid path / missing image | Clear error or skip per agreed rule |

### 5.7 Public search (if enabled in UAT)

| ID | Scenario | Expected result |
|----|----------|-----------------|
| P1 | Anonymous user cannot access internal case registry | Denied |
| P2 | Public search limited to published policy | Only permitted endpoints/data |

### 5.8 Historic / past data upload (police responsibility — required for full UAT)

Police departments **must** run a realistic historic upload on UAT/staging (not only vendor test data). This validates templates, image paths, district–PS fields, and system behaviour under real volumes.

| ID | Scenario | Expected result |
|----|----------|-----------------|
| H1 | Police prepares pilot batch (agreed **N** records, e.g. 50–500) from past UI-body registers | File checklist complete; sensitive images handled per policy |
| H2 | Bulk import executed by police IT / nodal team on target server | Import log reviewed; record count matches expectation |
| H3 | Spot-check **K** random imported cases in UI | Photos visible; attributes readable; match can be run |
| H4 | Optional: full district backlog import after H1–H3 pass | Agreed cut-over window; backup taken first |

### 5.9 Match accuracy & usefulness (police-measured — required sign-off)

Automated developer tests do **not** prove field accuracy. Police must record outcomes using one or both methods below (agree in advance which applies).

**Method A — Known or closed cases (strongest):**  
Subset where true identity or correct missing-person link is **already known** to police (closed / traced cases only, with legal clearance). For each query image, note whether correct person appears in **Top 1**, **Top 5**, or **Not in top 5**.

**Method B — Blind expert review (always possible):**  
Investigating officers review **Top 5** matches for each of **M** sampled cases and mark each candidate: *Useful lead* / *Not useful* / *Cannot judge*. Aggregate **useful lead rate** at rank 1 and within top 5.

| ID | Activity | Record in annex sheet |
|----|----------|------------------------|
| ACC1 | Agree sample size **M** (queries) and method A/B | M = \_\_\_\_ |
| ACC2 | Run match (or combined search) for each query; export or screenshot shortlists | Attached / ticket IDs |
| ACC3 | Score each query per Method A and/or B | Fill result columns |
| ACC4 | Note failure modes (blur, PM condition, wrong angle, duplicate gallery entries) | Free text |
| ACC5 | Workshop with nodal officers: are scores acceptable for **internal release**? | Yes / No + conditions |
| ACC6 | If No: list required fixes (thresholds, SOP, training, data cleanup) before re-test | |

**Suggested annex columns (Excel):** Query case ID | Date tested | Tester rank | Top1 ID | Top1 useful Y/N | Correct in Top1 Y/N | Correct in Top5 Y/N | Notes.

---

## 6. Non-Functional Checks (Minimum)

| # | Check | Pass criteria |
|---|--------|----------------|
| N1 | HTTPS for all user-facing URLs | No mixed-content warnings for core flows |
| N2 | Backup of DB and blob storage | Restore tested on non-production copy where possible |
| N3 | Incident contact | 24×7 or agreed hours documented |
| N4 | Log retention | Meets police / cyber policy |
| N5 | Performance | Agreed concurrent users complete key flows without unacceptable timeout |

---

## 7. Defects & Exit Criteria

| Severity | Description | UAT exit rule (recommended) |
|----------|-------------|------------------------------|
| **Critical** | Data loss, wrong user sees others’ restricted data, auth bypass | **No go** until fixed and retested |
| **Major** | Core workflow broken (cannot submit case, match always empty incorrectly) | **No go** until fixed or waived in writing by authorised officer |
| **Minor** | UI text, non-blocking errors | May go with documented workaround and fix date |

**UAT complete** when: all Critical and agreed Major items are closed **or** formally waived; **Sections 5.8–5.9 completed** (historic pilot upload + accuracy sheet); sign-off sheet (Section 9) is filled for the **internal release** phase, including rows **8** and **9** where applicable.

---

## 8. Infrastructure Handover (Police-Hosted Servers)

When the department hosts UBIS on their own cloud or data centre, IT should verify and sign the handover block below (adapt hostnames to your environment).

| # | Handover item | Verified (Y/N) | Notes |
|---|---------------|------------------|-------|
| H1 | Source / container images / build pipeline access documented | | |
| H2 | PostgreSQL (or approved DB) provisioned; `DATABASE_URL` set | | |
| H3 | Object storage for uploads + reference photos | | |
| H4 | Qdrant reachable from API; persistence volume / backup | | |
| H5 | Application settings: `ENVIRONMENT`, JWT, CORS, public URL | | |
| H6 | AI models mounted at path expected by container | | |
| H7 | Monitoring and alerting (uptime, errors, disk) | | |
| H8 | Runbook: deploy, rollback, restart, seed admin | | |
| H9 | **Capacity plan** agreed against indicative sizing (Section 11) for expected case volume | | |

---

## 9. Police Department Sign-Off Register

**Instructions:** Each signatory prints name, designation, department/unit, signature, and date. Electronic approval may be used if permitted by local rules; attach reference number.

| # | Sign-off item | What is being certified | Role / title (example) | Name | Signature | Date |
|---|---------------|-------------------------|--------------------------|------|-----------|------|
| 1 | **IT readiness** | Hosting, TLS, backups, secrets, monitoring per Section 8 | Head IT / SIO IT | | | |
| 2 | **Cyber / security** | Security checks in Section 6 acceptable; no open Critical issues | Cyber Cell nodal | | | |
| 3 | **Functional UAT** | Scenarios in Section 5 passed (or waivers attached) | Nodal IO / SP (pilot) | | | |
| 4 | **Operational SOP** | Field SOP for capture, review, and escalation agreed | ADDL SP / DIG (Ops) | | | |
| 5 | **Data & legal** | Data handling, retention, public search scope approved | Legal / prosecution advisor | | | |
| 6 | **Internal release authorisation** | Proceed with limited rollout (Cyber Cell + pilots) | Authorised superior officer | | | |
| 7 | **Wider rollout & announcement** (later) | Production scale-up and public communication approved | Commissioner / delegated authority | | | |
| 8 | **Historic data pilot** | Police-prepared past records uploaded per Section 5.8; import verified; spot-checks passed (attach count **N**, log, sample list) | HQ nodal / District coordination / IT | | | |
| 9 | **Accuracy & match quality** | Section 5.9 completed; **useful lead rate** / **Top-1 or Top-5** metrics reviewed; acceptable for internal use **with stated limits** (attach annex sheet) | Investigation lead / nodal officer / forensic advisor (as applicable) | | | |

*Roles in column 3 are examples; the department should map them to actual posts. Rows 8–9 are **mandatory** before treating UAT as complete for production-scale decisions unless the authorised officer waives in writing (e.g. time-bound pilot without historic load).*

---

## 10. Document Control

| Field | Value |
|-------|--------|
| Document | UBIS UAT & Police Sign-Off |
| Version | 1.2 |
| Maintained with | UBIS repository `docs/` |

---

## 11. Recommended cloud sizing (indicative — adjust with IT)

These are **order-of-magnitude** guidelines for a typical UBIS layout: **API container/VM** (FastAPI + PyTorch + face models), **PostgreSQL**, **object storage** (case and reference images), **Qdrant** (vector index), optional **CDN** for static frontend. Actual needs depend on image resolution, concurrent users, bulk-import peaks, and retention policy.

### 11.1 Rough planning inputs (for IT to plug into their calculator)

| Input | How to estimate |
|-------|------------------|
| **Active UI-body + reference gallery rows** | Count of cases you expect **online** at once (not every historic paper file). |
| **Images per case** | Often 3–10; bulk historic rows may average 2–6 usable photos. |
| **Object storage** | `≈ (total images stored) × (average compressed JPEG size, often 0.5–3 MB)` + **30–50%** headroom + legal retention years. |
| **Vector points (Qdrant)** | Roughly **one point per embedded image** (sometimes more if multiple faces per image); 512-dimensional floats + small JSON payload — budget **~3–8 KB per point** including overhead (IT should validate with a sample import). |
| **API CPU/RAM** | Face embedding is **CPU-heavy** on upload and match spikes; **RAM** holds models — budget **≥ 8 GB** where PyTorch + InsightFace run in one process unless models are split to a worker service. |
| **GPU** | **Not strictly required** if batch latency is acceptable; add a **small GPU worker** (or larger CPU) if you need fast **bulk backfill** of tens of thousands of faces in hours instead of days. |

### 11.2 Example tiers (cloud-agnostic “shape”)

Assume **moderate JPEG sizes**, **CPU-only** embedding on the API unless noted. Scale **up** if many concurrent uploaders or same-day bulk of **>10k** images.

| Tier | Typical scale (order of magnitude) | API / app runtime | Qdrant | PostgreSQL | Object storage (starting point) | Notes |
|------|------------------------------------|-------------------|--------|------------|-----------------------------------|--------|
| **A — UAT / pilot** | ≤ **500** live cases; **≤ ~5k** embedded images; tens of concurrent users | **2 vCPU**, **8 GB RAM** | **1–2 vCPU**, **4 GB RAM**, **50 GB** fast disk | **1–2 vCPU**, **2–4 GB RAM**, **20–50 GB** | **100 GB** | Enough for internal release + historic pilot import; may feel slow on **large** single-day bulk imports. |
| **B — District / multi-district** | **~2k–10k** cases; **~20k–80k** images in index | **4 vCPU**, **16 GB RAM** (or **2×** smaller instances behind load balancer) | **2–4 vCPU**, **8 GB RAM**, **100–200 GB** SSD | **2–4 vCPU**, **8 GB RAM**, **100 GB+** | **0.5–2 TB** | Match daily operational use + periodic bulk; add **autoscale rules** on CPU if traffic spiky. |
| **C — State-wide active index** | **~20k–100k+** cases; **~200k–1M** vectors | **8+ vCPU**, **32 GB RAM** **or** horizontal replicas + **dedicated embedding workers** | **Dedicated** Qdrant host or cluster, **8+ GB RAM**, **200 GB–1 TB+** SSD | Managed DB tier per vendor sizing (IOPS matters for audit tables) | **Multi-TB** with lifecycle to cold tier | Consider **separating** bulk-import embedding to a **queue + worker** so interactive users stay responsive. |

### 11.3 Network, region, and settings (checklist)

| Item | Recommendation |
|------|----------------|
| **Region** | Keep **database, object storage, Qdrant, and API** in the **same cloud region** as legally/operationally required (e.g. India regions if policy mandates data residency). |
| **TLS** | Terminate TLS at load balancer / ingress; **HTTPS only** for browser and API. |
| **Secrets** | No secrets in images; use vault / key vault / parameter store per [01_INSTALL.md](HANDOVER_GURUGRAM/01_INSTALL.md) / [02_OPERATIONS.md](HANDOVER_GURUGRAM/02_OPERATIONS.md). |
| **Backups** | Automated **Postgres** snapshots + **blob** versioning or periodic backup + **Qdrant** volume snapshot (verify restore in UAT). |
| **Qdrant persistence** | Use a **mounted volume** or managed vector offering; do not rely on ephemeral container disk for production. |
| **Frontend** | Static hosting (object storage + CDN or static web app); minimal compute. |

### 11.4 When to revisit sizing

- Before **large historic import** (Section 5.8).  
- When **concurrent stations** or **public search** traffic increases sharply.  
- When enabling **GPU** paths or adding **video** processing in future (would materially increase compute and storage).

*Figures are engineering estimates for procurement discussions, not a performance guarantee. Validate with a load test on representative data.*

---

*UBIS outputs are investigative leads; human verification and legal process remain mandatory.*
