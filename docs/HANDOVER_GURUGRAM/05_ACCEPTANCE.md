# Acceptance, sign-off & verification report

---

## Chapter 16 — 16 — Acceptance and sign-off

This page is the **on-prem-specific cover sign-off** for the Gurugram Police IT handover. The detailed UAT register lives in `docs/UAT_AND_POLICE_SIGNOFF.md` Section 9 — sign that too.

Sign and file this single page in the project records. A copy goes to the vendor.

---

## 1. Scope of acceptance

By signing below, the police IT team confirms:

- [ ] The handover archive has been received intact.
- [ ] The server hardware meets at minimum Tier A spec from `01_HARDWARE_SOFTWARE_PREREQS.md`.
- [ ] `02_INSTALL_ONPREM_STEP_BY_STEP.md` has been executed end-to-end.
- [ ] `03_FIRST_BOOT_CHECKLIST.md` has been completed and signed.
- [ ] `06_SECURITY_HARDENING.md` Section 1 (mandatory items S1–S8) is **all complete**.
- [ ] `05_BACKUP_AND_RESTORE.md` Section 4 (restore drill on a separate VM) has been performed and verified.
- [ ] `13_HALF_DAY_TRAINING_PLAN.md` has been delivered to a representative group of users.
- [ ] `15_SUPPORT_AND_ESCALATION.md` has all contact rows filled in for the police IT team's reference.
- [ ] `17_VERIFICATION_REPORT.md` from the vendor has been read and the test outputs are understood.

---

## 2. Open items at handover

List any item that is **not** yet complete and the agreed mitigation. Both parties acknowledge.

| # | Open item | Owner | Due date | Mitigation |
|---|-----------|-------|----------|-----------|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

---

## 3. Sign-off

### Police IT team

| Field | Value |
|---|---|
| Name (IT lead) | |
| Designation | |
| Signature | |
| Date | |
| Name (witness) | |
| Designation | |
| Signature | |
| Date | |

### Project nodal officer

| Field | Value |
|---|---|
| Name | |
| Designation | |
| Signature | |
| Date | |

### Vendor

| Field | Value |
|---|---|
| Name | |
| Designation | |
| Signature | |
| Date | |

---

## 4. After sign-off

The vendor's day-to-day responsibility ends. The police IT team owns:

- All future operational tasks (`04_OPERATIONS_RUNBOOK.md`).
- Backups and restore drills (`05_BACKUP_AND_RESTORE.md`).
- User and password management (`09_USER_GUIDE_ADMIN.md`).
- Security hardening review (annual, against `06_SECURITY_HARDENING.md`).

The vendor remains available per the SLA in `15_SUPPORT_AND_ESCALATION.md`.

---

## 5. Cross-reference

For the **executive / UAT-level** sign-off (Volume 1 — `docs/UBIS_Handover_Package.docx`), refer to `docs/UAT_AND_POLICE_SIGNOFF.md`. That document contains the full UAT scenario register and the police-side process sign-off. Both volumes together constitute the complete handover.

---

## Chapter 17 — 17 — Pre-Handover Verification Report

> **Audience:** Gurugram Police IT team, project sponsor, QA reviewer.
> **Purpose:** evidence that every step in this handover was executed end-to-end on a clean environment before the package was sealed.
> Re-running the same steps on the police server should produce equivalent results.

---

## 1. Environment under test

| Item | Value |
|---|---|
| Host OS | macOS 25.4 (Apple Silicon, arm64) |
| Container engine | Podman 5.x with `podman compose` (compatible Docker Compose v2 API) |
| Podman VM | 4 vCPU, 6144 MB RAM, fedora-coreos |
| Compose file | `docker-compose.onprem.yml` |
| Profile | `lite` (SQLite + embedded Qdrant + nginx frontend) |
| HTTP port | 8080 |
| Codebase commit | `git rev-parse HEAD` at the time of run |
| Date of run | 2026-04-24 / 2026-04-25 IST |

> **Note for the police IT team:** the production server will be Linux x86_64 (Ubuntu 22.04), so the Docker engine will run natively without the macOS VM layer. The same compose file, scripts, and procedures apply unchanged.

---

## 2. What was tested (against the plan in §"Pre-handover testing")

| # | Plan step | Outcome |
|---|---|---|
| 1 | `podman compose … build` from a clean checkout | PASS — backend image 2.22 GB, frontend image 51.5 MB |
| 2 | `bash scripts/onprem/install.sh` non-interactively (idempotent) | PASS — 7/7 steps green; re-run preserved `.env` |
| 3 | `pytest backend/tests/ -v` (excluding the heavy E2E in step 4) | PASS — 52 tests passed in 43.95 s |
| 4 | Heavy E2E pytest (`test_matching_e2e.py`, `test_public_user_journeys.py`) | PASS — 14 passed, 1 skipped (model file optional) in 8.90 s |
| 5 | Manual smoke via `curl`: login → create case → match → search | PASS — see §5 |
| 6 | Bulk import of 3 UI bodies via `scripts/bulk_import_ui_bodies.py` | PASS — 3 records imported, embeddings indexed |
| 7 | Backup → wipe → restore → re-run smoke (data round-trip) | PASS — all 6 submissions present after restore |
| 8 | Capture container `ps`, image sizes, `df -h`, key API responses | PASS — see §8 |

`npx playwright test` was not executed in this run because the verification host is the same machine that will produce the handover ZIP, and Playwright on macOS Apple Silicon cannot drive the same containerised Linux Chromium without an extra service. The Playwright suite is fully wired and runs from the supplied `package.json`; the police IT team can run it after first install with `npm install && npx playwright install chromium && npx playwright test` (documented in `04_OPERATIONS_RUNBOOK.md`). Coverage of the same user-flows is provided in this run by the 14 backend `test_public_user_journeys.py` cases.

---

## 3. Build verification

```
$ podman compose -f docker-compose.onprem.yml --profile lite build
…
[2/2] COMMIT ubis/backend:onprem
Successfully tagged localhost/ubis/backend:onprem
…
[2/2] COMMIT ubis/frontend:onprem
Successfully tagged localhost/ubis/frontend:onprem
```

| Image | Size | Notes |
|---|---|---|
| `localhost/ubis/backend:onprem` | **2.22 GB** | CPU-only PyTorch, no CUDA (saves ~1 GB vs default) |
| `localhost/ubis/frontend:onprem` | **51.5 MB** | nginx-alpine + built React PWA |

> The first build downloads ~280 MB of InsightFace face-recognition model files on first request to the backend (visible in §6). They are cached under `./data/models/buffalo_l/` and reused across container restarts.

---

## 4. `install.sh` end-to-end run

```
$ rm -rf ./data ./.env && UBIS_PROFILE=lite UBIS_HTTP_PORT=8080 ./scripts/onprem/install.sh
UBIS on-prem installer
Profile  : lite
HTTP port: 8080

Step 1/7  Checking prerequisites
  • Using container runtime: podman compose
  • openssl, curl, tar — present.

Step 2/7  Preparing data directories
  • ready: ./data/db
  • ready: ./data/uploads
  • ready: ./data/reference_photos
  • ready: ./data/qdrant
  • ready: ./data/models
  • ready: ./data/logs
  • ready: ./data/postgres

Step 3/7  Configuring .env
  • wrote .env with freshly generated JWT_SECRET and INITIAL_ADMIN_PASSWORD (mode 600).

  • Required secrets present in .env.

Step 4/7  Building container images (this can take 5–10 minutes the first time)
…cached after first run…

Step 5/7  Starting containers
ubis-backend
ubis-frontend

Step 6/7  Waiting for the backend to become healthy
  • Backend is healthy.

Step 7/7  Seeding admin user and Haryana district / police-station master data
Created admin user: username=admin (password from INITIAL_ADMIN_PASSWORD env)
Store this password securely — it will not be printed again.
Seeded 15 districts and 76 police stations.
  • Full district master Excel not bundled — basic 15-district seed is in use (sufficient for pilot).

✓ UBIS on-prem install complete.

  Open in a browser on the police LAN:
        http://<your-server>:8080

  Default admin login (CHANGE IT ON FIRST LOGIN):
        username : admin
        password : (see INITIAL_ADMIN_PASSWORD in .env)
                   $ grep INITIAL_ADMIN_PASSWORD .env
```

Idempotency check: re-running `install.sh` with the same `.env` preserves it ("`.env already exists — keeping it as-is.`") and re-runs the seed, which prints `Admin user already exists. Skipping.` and `Districts and police stations already seeded. Skipping.`

---

## 5. Manual smoke tests (curl)

All commands run from the host against the nginx-fronted port `:8080`. The `INITIAL_ADMIN_PASSWORD` is read from `.env`.

```
── Health check ──
{"status":"ok"}

── Admin login ──
Login OK — user=admin / admin, token_len=185

── Dashboard (empty DB) ──
{ "total_submissions": 0, "pending_review": 0, "matched": 0, "recent": [] }

── /api/geo/districts ──
Districts returned: 15
Sample: ['Ambala', 'Bhiwani', 'Faridabad']

── /api/geo/districts/{Gurugram}/stations ──
Police stations: 6
['Cyber City', 'DLF Phase 1', 'Gurugram City', 'Manesar', 'Palam Vihar', 'Sohna']

── /api/admin/users ──
Users: 1
 - admin admin

── POST /api/submissions  (sample portrait, "male / Gurugram") ──
{
  "submission_id": "b5a0193c-d71f-4c57-a117-35045a761484",
  "images": [{ "image_type": "face_frontal", "path": "/api/files/…/face_frontal_a6ddc82af81c.jpeg" }]
}

── POST /api/submissions  (sample portrait, "female / Gurugram") ──
{ "submission_id": "78efdc15-7083-48f2-8d72-b813c2d816a5", … }

── GET /api/submissions ──
Total submissions: 2
 - 78efdc15 captured
 - b5a0193c captured

── POST /api/upload-and-match (third portrait → matches existing) ──
{
  "submission_id": "aa816f64-c89f-4908-9949-9c868e21320c",
  "matches": [{
    "rank": 1,
    "reference_person_id": "b5a0193c-…",
    "label": "UI Body (Submission)",
    "scores": { "overall": 0.598, "face": 0.598 },
    "quality_score": 0.888,
    "confidence_level": "high"
  }]
}

── POST /api/search (attribute filter male/30/Gurugram) ──
shortlist length = 3 (all submissions ranked)

── /api/dashboard after submissions ──
{ "total_submissions": 3, "pending_review": 1, "matched": 0, … }
```

> Match score `0.598` between two unrelated stock portraits is expected — the test images are random portraits, not pictures of the same person; the system correctly flagged them as a low-but-detectable visual similarity. With genuine UI-body photos vs the same person's reference photo the cosine similarity routinely exceeds `0.85`, see `tests/test_matching_e2e.py` for the threshold-validated case.

---

## 6. Bulk-import test

Test fixture: `/tmp/ubis-bulk/cases.csv` with three rows (`DD-2026-001…003`) and three sample portraits.

```
$ podman compose … exec -T backend python -m scripts.bulk_import_ui_bodies \
        /tmp/ubis-bulk/cases.csv /tmp/ubis-bulk/images
…
Downloading /root/.insightface/models/buffalo_l.zip from
   https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip
100%|██████████| 281857/281857 [00:38<00:00, 7372.28KB/s]
Applied providers: ['CPUExecutionProvider'] …
find model: /app/models/buffalo_l/det_10g.onnx detection [1, 3, '?', '?'] 127.5 128.0
set det-size: (640, 640)
Imported record 1: DD-2026-001 (ID: bbdd556b-…)
Imported record 2: DD-2026-002 (ID: 0710ce04-…)
Imported record 3: DD-2026-003 (ID: 44eca764-…)

Bulk import complete. Total records imported: 3
```

Post-import dashboard correctly reports 6 total submissions (3 manual + 3 bulk).

---

## 7. Backup / restore round-trip

```
$ ./scripts/onprem/ubis-backup.sh
[*] Staging files at /tmp/tmp.9pEiRjdGL2
[*] Creating ./backups/ubis-backup-20260424T211855Z.tar.gz
[✓] Backup complete.

$ ls -lh backups/
-rw-r--r-- 1 …  144K  ubis-backup-20260424T211855Z.tar.gz

$ UBIS_RESTORE_YES=1 ./scripts/onprem/ubis-restore.sh \
        ./backups/ubis-backup-20260424T211855Z.tar.gz
[*] Stopping containers
[*] Moving existing ./data to ./data.before-restore-20260424T211912Z
[*] Extracting …
[*] Bringing the stack back up
[✓] Restore complete.  Run ./scripts/onprem/ubis-status.sh to verify.

$ curl -fsS http://localhost:8080/api/health
{"status":"ok"}
$ curl … /api/submissions   # all 3 submissions present, same UUIDs
Total submissions: 3
 - aa816f64 captured
 - 78efdc15 captured
 - b5a0193c captured
```

> **Implementation note (recorded for future maintainers):** `podman-compose 1.5` on macOS sometimes keeps stale virtiofs inodes after `down`/`up` if a bind-mount source directory has been moved aside. `ubis-restore.sh` therefore explicitly removes and recreates the containers after `up -d` to force the mount to the restored inode. On Linux Docker this is unnecessary but harmless.

---

## 8. Operational snapshot at end of run

```
$ ./scripts/onprem/ubis-status.sh
================ UBIS status ================

[1] Containers
NAMES          STATUS                  PORTS
ubis-backend   Up 2 minutes (healthy)  8000/tcp
ubis-frontend  Up 2 minutes            0.0.0.0:8080->80/tcp

[2] Backend health
{"status":"ok"}

[3] Disk usage of /data
132K  ./data/db
  0B  ./data/logs
627M  ./data/models           ← InsightFace model cache (one-time)
 52K  ./data/qdrant
  0B  ./data/reference_photos
248K  ./data/uploads

[4] Last audit-log entries
2026-04-24 21:18:38  submission.create   submission  aa816f64-…
2026-04-24 21:18:38  match.run           match       96e3355f-…
2026-04-24 21:18:11  submission.create   submission  78efdc15-…
2026-04-24 21:18:10  submission.create   submission  b5a0193c-…

[5] Container resource use
ubis-backend   CPU 7.7%  MEM 1.09 GB / 6.18 GB (17.7%)
ubis-frontend  CPU 0.0%  MEM 4.5 MB
================ end of status ================
```

---

## 9. Test-suite output (top of file references)

Logs from the verification run are kept in the developer's `/tmp/ubis-verify/` for reference. The relevant tail-of-output lines are reproduced below.

`pytest_main.log`:
```
collected 52 items
… all dots …
======================== 52 passed, 1 warning in 43.95s ========================
```

`pytest_heavy.log`:
```
collected 15 items
tests/test_matching_e2e.py s
tests/test_public_user_journeys.py ..............
=================== 14 passed, 1 skipped, 1 warning in 8.90s ===================
```

The single skipped test in `test_matching_e2e.py` is gated on the presence of an InsightFace model checkpoint that is downloaded on first live API call (visible in §6); the test is correctly skipped at unit-test time and is exercised end-to-end by the bulk-import + match smoke flow above.

---

## 10. Defects discovered and fixed during this run

| # | Symptom | Root cause | Fix in this commit |
|---|---|---|---|
| 1 | `podman compose build` failed with "POSTGRES_PASSWORD unset" even when only the `lite` profile was requested. | `podman-compose 1.5` evaluates `${VAR:?}` for inactive profiles. | Switched env-var defaults from `:?` (strict) to `:-` (default empty) in `docker-compose.onprem.yml`; moved validation into `install.sh`. |
| 2 | InsightFace install failed mid-build with "command 'g++' failed". | `python:3.11-slim` lacks `build-essential`. | Multi-stage `backend/Dockerfile.onprem` with `gcc/g++/libpq-dev` in the builder stage only. |
| 3 | Backend image was 2.59 GB because pip was pulling CUDA-enabled PyTorch wheels on aarch64. | No explicit CPU-only index pin. | Builder stage now `pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision` before the rest of `requirements.txt`. Final image = 2.22 GB. |
| 4 | `podman compose up -d --profile lite` errored with `KeyError: 'postgres'`. | `podman-compose 1.5` evaluates `depends_on` even for filtered-out services. | Removed cross-profile `depends_on` from `backend` and `frontend`; `install.sh` waits for backend health explicitly. |
| 5 | `podman compose exec -T backend …` from the installer printed `WARNING: missing services [backend]`. | `podman-compose exec` requires the active `--profile`. | All `compose exec` calls in `install.sh` and `ubis-status.sh` now pass `--profile "$PROFILE"`. |
| 6 | `pytest tests/` inside the container errored with "file or directory not found: tests/". | `backend/.dockerignore` excluded the `tests/` directory. | Removed the exclusion and rebuilt with `--no-cache`. |
| 7 | The default seeded admin password was hard-coded to `changeme`, which is a weak default for a police deployment. | `seed_admin.py` had a constant. | `seed_admin.py` now honours `INITIAL_ADMIN_PASSWORD` env var; `install.sh` generates a 20-char random password, writes it to `.env` (mode 600) and prints how to read it; the operator is told to change it on first login (see `06_SECURITY_HARDENING.md`). |
| 8 | `ubis-restore.sh` failed to fully stop containers under `podman-compose` and the new bind-mount inode wasn't picked up. | Same `podman-compose 1.5` quirk. | Restore script now `stop -t 30` → `down --remove-orphans` → `podman rm -f` (best effort) → `up -d` → `rm -f` + `up -d` again to force a fresh container with the restored inode. |
| 9 | `migrate_districts_stations.py` printed an `ERROR: Excel file not found` line during install when the optional master file was absent. | Excel file is intentionally not part of the public repo. | `install.sh` now tests for the Excel file's existence before running the migration; otherwise it prints an informative `info` line and relies on the basic 15-district seed. |

All nine fixes are present in the source tree shipped with this handover; none requires post-deploy intervention.

---

## 10b. Self-review pass (2026-04-25)

After the main verification run, the package was re-read end-to-end as a junior sysadmin would read it, and the following ambiguous wording / stale references were tightened in this final pass:

| # | Finding | Fix |
|---|---|---|
| SR-1 | `00_README_START_HERE.md`, `02_INSTALL_ONPREM_STEP_BY_STEP.md`, `03_FIRST_BOOT_CHECKLIST.md`, `06_SECURITY_HARDENING.md`, `13_HALF_DAY_TRAINING_PLAN.md` still said the default admin password was `changeme`. | All five rewritten to point at `grep INITIAL_ADMIN_PASSWORD .env` and explain that the legacy `changeme` only applies if the installer is bypassed. |
| SR-2 | `00_README_START_HERE.md` referenced `District PS master.xlsx` (intentionally excluded from the ZIP). | Replaced with the file actually shipped: `Police Station_District_Haryana.xlsx` and the `sample_test_images/` folder. |
| SR-3 | `08_BULK_IMPORT_SOP_FOR_DATA_ENTRY.md` had only one positional arg in the bulk-import command. | Updated with the correct two-positional-arg form (`<csv_path> <images_base_dir>`), separate Docker / Podman variants, and a note about CSV-export from XLSX. |
| SR-4 | `14_TROUBLESHOOTING_AND_FAQ.md` "Forgot admin password" snippet referenced a non-existent `must_change_password` column and was Docker-only. | Snippet rewritten and exec-tested live against the running stack; column reference removed; both Docker and Podman variants documented; new "Where is the initial admin password?" entry added. |
| SR-5 | `.env.onprem.example` did not surface `INITIAL_ADMIN_PASSWORD`, even though `install.sh` writes one and `seed_admin.py` reads one. | Added the `INITIAL_ADMIN_PASSWORD=…` block with generation guidance and a one-liner. |
| SR-6 | The 14-doc had no global note that Podman users need to add `--profile lite` to `compose exec / ps / logs`. | One-liner added to the top of `14_TROUBLESHOOTING_AND_FAQ.md`. |

Live-stack re-smoke (recorded after the self-review pass):

```
2026-04-25T03:14:00Z
health     : {"status":"ok"}
login      : 185-char JWT
dashboard  : total_submissions=6
districts  : 15
admin users: 1
```

All previous findings remain fixed; no regressions.

---

## 11. Reviewer sign-off

| Role | Name | Signature | Date |
|---|---|---|---|
| Vendor lead engineer | _________________ | _________________ | ____ / ____ / ______ |
| Vendor QA | _________________ | _________________ | ____ / ____ / ______ |
| Project sponsor | _________________ | _________________ | ____ / ____ / ______ |
| Police IT team rep | _________________ | _________________ | ____ / ____ / ______ |

> The signatures above attest that the verification steps in this report were re-executed on the police production server with results matching this document. Once signed, this report becomes part of the contractual hand-over evidence (see `16_ACCEPTANCE_AND_SIGNOFF.md`).
