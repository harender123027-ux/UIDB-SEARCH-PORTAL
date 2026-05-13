# Training, troubleshooting & support

---

## Chapter 13 — 13 — Half-day training plan

A 4-hour training session that brings every UBIS user role to operational competence in one sitting. Designed for a mixed audience of one admin and four investigators. Adjust class size as needed.

---

## Logistics

| Item | Detail |
|---|---|
| Duration | 4 hours (with two 10-minute breaks) |
| Audience | 10–15 mixed-role officers |
| Trainers | One UBIS-knowledgeable IT person + one project nodal officer (or vendor SME for the first run) |
| Venue | A room with projector + Wi-Fi access to the UBIS server, 1 laptop per 2 trainees |
| Pre-requisites | Trainees have user accounts already created and tested by IT (`09` Section "How to create a new user") |
| Materials | Printed copies of the relevant per-role user guide for each trainee (`09–12`); a few sample face photos for the hands-on; the bulk-import sample data |

---

## Agenda (timings are indicative)

| Time | Block | What happens |
|---|---|---|
| 0:00 – 0:15 | **Welcome and context** | Why UBIS exists, expected outcomes for the Gurugram pilot, who else is using similar systems. Cover the disclaimer: investigative leads, not legal proof. |
| 0:15 – 0:45 | **System tour (everyone together)** | Trainer projects the UBIS UI: login, dashboard, case detail, search, admin panel. Trainees follow along on their laptops. |
| 0:45 – 1:00 | **Photo quality clinic** | A 15-minute demo on what makes a good face photo (frontal, well-lit, eyes open, ≥600 px). Show "good" vs. "bad" examples. Reference: `12_USER_GUIDE_FIELD_OFFICER.md` Section "How to take a good face photo". |
| 1:00 – 1:10 | **Break** | |
| 1:10 – 2:00 | **Hands-on by role (parallel breakout)** | Trainees split by role and work through the role-specific exercises (next section). Trainers circulate. |
| 2:00 – 2:30 | **Match review session** | Reconvene as a single group. Walk through 3 real (anonymised) cases with their match shortlists. For each: how would you read it? What would you record as feedback? |
| 2:30 – 2:40 | **Break** | |
| 2:40 – 3:10 | **Bulk import demo** | IT shows the data-entry team workflow end-to-end on a 3-row sample. Reference: `08_BULK_IMPORT_SOP_FOR_DATA_ENTRY.md`. |
| 3:10 – 3:30 | **Operations and security overview** | IT walks through `04_OPERATIONS_RUNBOOK.md` and `06_SECURITY_HARDENING.md` for the IT trainee(s); other trainees see the password-rotation expectations. |
| 3:30 – 3:50 | **Q&A and troubleshooting** | Open floor; surface every concern. Trainers note unanswered questions for follow-up. |
| 3:50 – 4:00 | **Sign-off and feedback** | Each trainee signs the training register; fills a 5-question feedback form (cover sheet on the next page). |

---

## Hands-on exercises by role

### Admin track (1 trainee, ~50 minutes)

1. Log in. Change your default password.
2. Create a test user `inspector.test` with role `investigator`, station "Sohna". Set a temporary password.
3. Open the audit log; find the entries from steps 1 and 2.
4. Reset `inspector.test`'s password.
5. Disable `inspector.test`. Re-enable. Confirm both actions in the audit log.
6. Open Reports → Cases → Last 30 days → Download CSV. Confirm the file opens in Excel.

### Investigator track (4 trainees, ~50 minutes)

1. Log in. Open **My cases**. If empty, create one for practice (use a sample face image the trainer provides).
2. Run a face match on the practice case. Wait for the shortlist.
3. For each candidate in the top 3, open their profile and compare. Record "Useful" / "Not useful" / "Wrong person" with a 1-line note.
4. Add a case note: "Practice exercise — confirmed UBIS workflow with [trainer name] on [date]."
5. Use **Search → Text** to find a case by description ("male, 25–35, found near Sohna"). Open it.
6. Use **Search → Voice** in Hindi: speak the description; confirm the same result.
7. Close the practice case with reason "Closed unidentified — training case".

---

## Instructor cheat sheet

> Print this page and keep it on the lectern.

- **Admin password.** The installer wrote a random one to `.env` (`grep INITIAL_ADMIN_PASSWORD .env`). Change it from the UI before any trainee sees the system. Trainees should each have their own non-admin account.
- **Wi-Fi must reach the UBIS server.** Test before trainees arrive — open `http://<server>:8080` from a laptop in the room.
- **Backup the system before training.** Trainees create test cases; you may want to delete them after.
- **Keep the projection on the trainer's screen, not a trainee's** — trainee screens may show real cases.
- **If a trainee can't log in:** check `04_OPERATIONS_RUNBOOK.md` Section "Reset another user's password".
- **If the system goes down mid-training:** continue with photo-quality and policy discussion; have IT call the support number.
- **Common questions and 1-line answers:**
  - "Will this replace officers?" — No. It speeds up the search across the gallery; an officer always confirms.
  - "Is my face data being uploaded to a cloud?" — No. Everything stays on the police server.
  - "What if the system says wrong person?" — Record "Wrong person" feedback; the model improves.
  - "Why didn't this match?" — Either the candidate isn't in the gallery yet, or photo quality was poor.
  - "Can I share a match by WhatsApp?" — No. Department channels only.

---

## Post-training

| Action | Owner | Done? |
|---|---|---|
| Collect signed training-register sheets, file in IT vault | Nodal officer | |
| Clean test data from the system (delete training cases / users) | Admin | |
| Schedule a 30-minute follow-up clinic 7 days later | Nodal officer | |
| Record outstanding issues from Q&A in the project log | IT | |
| Share the per-role guides (PDF / printed) with trainees who need them | Nodal officer | |

---

## 5-question feedback form (give to each trainee)

1. On a scale of 1 (poor) to 5 (excellent), how clear was the training?
2. On a scale of 1 to 5, how confident are you in using UBIS for your role?
3. What is the one thing that was missing from this session?
4. What is the one thing you found most useful?
5. Any other comments / requests?

---

## Chapter 14 — 14 — Troubleshooting and FAQ

Top issues you will hit, with one-line answers and the deeper-dive doc to read for context.

> **Docker vs Podman.** All command examples below use `docker compose`. If your server runs Podman, replace it with `podman compose` and add `--profile lite` (or `--profile full`) to **every** `compose exec` / `compose ps` / `compose logs` line. The installer auto-detects which engine is present; the troubleshooting commands do not.

---

## Install problems

### Service won't start (`docker compose ... up -d` returns but containers are not listed)

```bash
docker compose -f docker-compose.onprem.yml ps
docker compose -f docker-compose.onprem.yml logs --tail=200 backend
```

Common causes:

- **`JWT_SECRET` empty** — re-check `.env`. Re-run `bash scripts/onprem/install.sh` to regenerate.
- **Port 8080 already used** — `sudo ss -ltnp | grep :8080`. Change `UBIS_HTTP_PORT` in `.env`, restart.
- **No disk space** — `df -h`. Free space under `/var/lib/docker` and `./data/`.
- **OOM killed during build** — server has < 4 GB RAM. Add swap or upgrade RAM (see `01_HARDWARE_SOFTWARE_PREREQS.md`).

### Backend keeps restarting

```bash
docker compose -f docker-compose.onprem.yml logs --tail=200 backend
```

Look for the last Python traceback. Common offenders:

- `ModuleNotFoundError` — image was built incompletely. Re-run `bash scripts/onprem/install.sh`.
- `sqlalchemy.exc.OperationalError: unable to open database file` — `./data/db` permissions. Run `sudo chown -R 1000:1000 ./data`.
- `RuntimeError: insightface model file not found` — see "Offline / air-gapped install" below.

### Build fails with `g++ failed: No such file or directory`

You are using an older version of `Dockerfile.onprem`. Pull the latest from the handover archive — the multi-stage Dockerfile installs `build-essential` in the builder stage.

### Build downloads CUDA / NVIDIA wheels (multi-GB)

You are using an older version of `Dockerfile.onprem`. The current one installs CPU-only torch from `https://download.pytorch.org/whl/cpu` first.

---

## Login problems

### "Where is the initial admin password?"

`install.sh` writes a 20-character random password to `.env`:

```bash
grep INITIAL_ADMIN_PASSWORD .env
```

Use it once to log in, then change it from the UI (User menu → Change password). The value in `.env` is only consulted the **very first time** the database is seeded; rotating from the UI is the only way to change it after that.

### Forgot admin password / lost all admins

Use the same compose command as everywhere else in this guide; on Podman, add `--profile lite`:

```bash
# Replace TempReset!2026 with something only you know — and change it from the UI immediately after logging in.
docker compose -f docker-compose.onprem.yml exec -T backend python - <<'PY'
from app.database import get_db
from app.auth import hash_password
new_password = "TempReset!2026"
with get_db() as conn:
    conn.execute(
        "UPDATE users SET password_hash=? WHERE username='admin'",
        (hash_password(new_password),),
    )
print(f"Admin password reset to: {new_password}  -- log in and change immediately.")
PY
```

After login, use the UI (User menu → Change password) to set the real password. See `09_USER_GUIDE_ADMIN.md` for managing other users.

### A specific user can't log in

- Check they are typing the username **exactly** (lower-case).
- Admin → Users → confirm the user is **Active**.
- If still failing, reset the user's password (`09_USER_GUIDE_ADMIN.md` Section "How to reset another user's password").
- If `auth.login` shows `401 invalid_credentials` repeatedly, lock the account and rotate the password.

---

## Match / search problems

### "No faces detected" on a clear photo

- The face is too small in the frame. Re-take with the face filling 60–80 % of the photo.
- The image was rotated by EXIF; the model sees it sideways. Re-save the file in correct orientation, retry.
- Confirm the file is < 10 MB and a `.jpg` / `.jpeg` / `.png`.

### Match scores are all very low (< 0.3)

- The reference gallery may not yet have the person. Continue loading historical missing-person records (`08_BULK_IMPORT_SOP_FOR_DATA_ENTRY.md`).
- The query photo quality is poor. Retake.

### Same person matched against many UI bodies

- The person's reference photo may be very common-looking, or the photo quality is poor on the reference side.
- Have an investigator record "Wrong person" against incorrect matches; this trains the system.

### Search is very slow (> 30 seconds)

```bash
bash scripts/onprem/ubis-status.sh
docker stats --no-stream ubis-backend
```

- If CPU pegged at 100 % and RAM full → upgrade RAM, move to Tier B (`docs/UAT_AND_POLICE_SIGNOFF.md` Section 11).
- If `data/qdrant/` is approaching 50 GB → contact vendor; you have likely exceeded Tier A volume.

---

## Bulk import problems

### Script reports "image not found" for half the rows

The path in the spreadsheet is relative to where the spreadsheet sits. Confirm the `images/` directory is at the same level as the spreadsheet inside the import folder.

### Script reports "police station not in master"

The station name in the spreadsheet doesn't match the master. Either:

- Fix the spelling in the spreadsheet (preferred).
- Add the station via Admin → Districts → Add station, then re-run.

### Script reports "duplicate dd_no"

That `dd_no` already exists in the database. Either skip it (it's already imported) or delete the existing case from the UI and re-run.

---

## Backup and restore problems

### Restore script complains "tarball not found"

Check the path you passed; the file must exist and be readable. Use an absolute path if in doubt.

### After restore, no cases visible

- Did the restore actually run? Check the script's exit code.
- Did `./data` get repopulated? `ls -la ./data/db ./data/uploads`.
- Are the containers up? `bash scripts/onprem/ubis-status.sh`.
- If using `--profile full`, did the Postgres dump import run? Look for "Import postgres" in the script output.

### Backup tarball is suspiciously small

Less than ~200 KB suggests the script ran but `./data` was empty at that moment (containers not yet started, or a fresh install). Take a fresh backup after at least one case has been registered.

---

## Network problems

### Officers report "page can't be reached"

- From the server itself: `curl -fsS http://localhost:8080/api/health` — should return `{"status":"ok"}`.
- From a workstation: `ping <server-hostname>`. If unreachable, the firewall is blocking. See `06_SECURITY_HARDENING.md` Section 4.
- HTTPS configured? See `06_SECURITY_HARDENING.md` Section 3 for the host-nginx setup.

### Browser shows TLS warning

Either you are using a self-signed certificate (acceptable for early pilot only — see `06_SECURITY_HARDENING.md` Section 3, Option B), or the certificate has expired. Renew via your CA / department PKI.

---

## Offline / air-gapped install

If the server has no internet access:

1. On a connected machine, run `bash scripts/onprem/install.sh` once to build the images.
2. Save the images:

```bash
docker save -o ubis-images.tar ubis/backend:onprem ubis/frontend:onprem
```

3. Also download the InsightFace model files (`buffalo_l.zip`, ~280 MB) and the AdaFace checkpoint to a USB drive.
4. On the air-gapped server: copy the package + `ubis-images.tar` + the model files. Place models under `data/models/` before first start.
5. `docker load -i ubis-images.tar`.
6. Edit `install.sh` to skip the build step (or simply run `docker compose -f docker-compose.onprem.yml --profile lite up -d` directly).

Contact the vendor for a pre-built `ubis-images.tar` if you cannot do step 1.

---

## When you have to escalate

If your symptom is not in this page, follow `15_SUPPORT_AND_ESCALATION.md`. Always include:

- Output of `bash scripts/onprem/ubis-status.sh > status.txt`.
- Last 200 lines of backend logs.
- The exact action you were doing when it broke (URL, button, time).
- Browser console screenshot if it's a UI issue.

---

## Chapter 15 — 15 — Support and escalation

This page is the **single phone number / email** for help. Print it. Pin it next to the server. Share it with your end users.

---

## Quick reference

| Severity | Who to call | Response SLA (target) | Resolution SLA (target) |
|---|---|---|---|
| **P1 — System down for all users** | _IT helpline + vendor on-call number_ | 30 minutes | 4 hours |
| **P2 — Degraded (slow / partial outage)** | IT helpline | 1 business hour | 1 business day |
| **P3 — Single user / cosmetic / how-to** | IT helpline | 1 business day | 3 business days |
| **P4 — Enhancement request / question** | Project nodal officer email | 3 business days | Tracked in product backlog |

> Adjust the SLA columns to your actual department contract. The structure stays the same.

---

## Contacts (fill these in before handover)

| Role | Name | Phone | Email | Hours |
|---|---|---|---|---|
| IT — primary admin | | | | 09:00–21:00 IST |
| IT — backup admin | | | | 09:00–21:00 IST |
| Cyber cell escalation | | | | 24×7 |
| Project nodal officer | | | | Office hours |
| Vendor — primary | | | | Per contract |
| Vendor — on-call (P1 only) | | | | 24×7 (P1 only) |

---

## How to file a ticket

Always include:

1. **Severity** (P1 / P2 / P3 / P4) — be honest; misclassifying P1 burns trust.
2. **Who is affected** — one user, one station, all users.
3. **What action triggers the issue** — URL, button, exact step from the user guide.
4. **What you expected** vs. **what you saw**.
5. **When it started** — UTC and IST.
6. **Status snapshot** — paste the output of `bash scripts/onprem/ubis-status.sh`.
7. **Screenshots** if it is a UI problem.

A complete ticket is closed at least 50 % faster than a 1-line "it's broken".

---

## Severity definitions and examples

### P1 — System down

- The login page does not load for **any** user.
- The backend container is in a crash loop and won't start.
- Data appears corrupt (audit log empty, cases missing).
- Search returns 5xx errors for every query.

Action: call the IT helpline AND the vendor on-call simultaneously. Take a backup if possible (`05_BACKUP_AND_RESTORE.md`). Do not "try things" — the vendor needs the system in its current state to diagnose.

### P2 — Degraded

- Search latency > 30 seconds (was < 10 seconds last week).
- Some users can log in, others cannot.
- One feature broken (e.g. bulk import fails) but the rest of the system works.

Action: file ticket with status snapshot. Continue using working features.

### P3 — Single user / how-to

- One user can't log in (probably needs password reset).
- Match scores look wrong on one specific case.
- "How do I download a CSV report?"

Action: refer to the user guide for the role first (`09–12`), then file a ticket.

### P4 — Enhancement / question

- "Can we add a new field to the case form?"
- "Can the dashboard show last week's trend?"
- "When will federation with CCTNS be available?"

Action: email the project nodal officer. Request goes to the product backlog.

---

## Vendor SLA template (to be filled in the contract)

| Item | Value |
|---|---|
| Coverage hours | |
| Channel for P1 | |
| Channel for P2–P3 | |
| Channel for P4 | |
| Response time, P1 | |
| Resolution time, P1 | |
| Response time, P2 | |
| Resolution time, P2 | |
| Maintenance windows (notice) | |
| Updates / patches cadence | |
| Service credits (if breach) | |
| Exclusions (force majeure, network outside police LAN, …) | |

This is not legal text — it is the operational expectation. Keep the legal SLA in your contract document and copy the numbers here for day-to-day reference.

---

## What the IT team should do before calling the vendor

1. Re-create the issue (so you can describe it precisely).
2. `bash scripts/onprem/ubis-status.sh > /tmp/status.txt`.
3. `docker compose -f docker-compose.onprem.yml logs --since 1h backend > /tmp/backend.log`.
4. Take a backup if the system is up enough to allow it.
5. Search `14_TROUBLESHOOTING_AND_FAQ.md` for the symptom — if there's a fix, try it (you'll save hours).
6. If still stuck, file the ticket with status, logs, and screenshots attached.

---

## Out-of-hours

Outside the IT helpline window, only **P1** issues should be escalated to the vendor on-call line. Everything else waits until the next business morning.
