# User guides & bulk import SOP

---

## Chapter 09 — 09 — User guide for the Admin

For **department-level UBIS administrators** — typically one or two officers and the project nodal officer.

> Open UBIS in your browser at the URL the IT team gave you (for example `https://ubis.ggn.haryanapolice.gov.in`). Log in with the admin account.

---

## What you can do

As an admin you can:

- Create, edit, disable any user (any role).
- Reset another user's password.
- See **every** case across all districts and police stations (other roles see only their jurisdiction).
- View the dashboard with case counts, match counts, recent activity.
- Read the full audit log.
- Manage the district / police-station master (when the IT team has loaded the master file).
- Manage the criminals / proclaimed-offenders list.

---

## Daily routine (10 minutes)

| # | Action | Where |
|---|--------|-------|
| 1 | Skim the dashboard for the day's case-creation and search counts. | Dashboard tab |
| 2 | Open the audit log; look for any unfamiliar admin actions overnight. | Admin → Audit |
| 3 | Check the IT team's daily backup confirmation (separate channel). | (out of UBIS) |
| 4 | Resolve any "Pending feedback" badge on cases — either you or the assigned investigator. | Cases → Filter: "Pending feedback" |

---

## How to create a new user

1. Admin menu → **Users** → **Create user**.
2. Fill in:
   - Username (lower-case, no spaces — e.g. `inspector.singh`).
   - Display name.
   - Role (see below).
   - District and police station the user belongs to (binds their visibility).
   - Temporary password (you set this; the user changes it on first login).
3. Save.
4. Send the temporary password through your secure channel (in person, signed handover, or a department-approved password tool). **Never** by SMS or WhatsApp.

### Roles cheat sheet

| Role | Sees | Can change |
|---|---|---|
| `admin` | Everything | Anything |
| `investigator` | Cases assigned to them or their station | Match feedback, case notes, close case |

---

## How to reset another user's password

1. Admin → **Users** → click the user.
2. Click **Reset password**.
3. UBIS generates a temporary password — share it through your secure channel.
4. The user must change it at their next login.
5. The action is recorded in the audit log under `admin.user.password_reset`.

If you have lost **all** admin accounts, see `14_TROUBLESHOOTING_AND_FAQ.md` "Forgot admin password".

---

## How to read the audit log

Admin → **Audit log**. Every row records: time, user, action, and what was acted upon. Useful filters:

- `action = auth.login` — who logged in when.
- `action = submission.create` or `submission.update` — case-creation activity per user.
- `action = match.run` — search activity.
- `action = admin.user.*` — administrative changes (create / disable / password reset).

If you spot something suspicious, export the day's log (Download CSV) and forward to your cyber cell with the full row contents.

---

## How to manage the district / police-station master

This is usually a one-off setup task done by the IT team. As an admin you can:

- See the current master under **Admin → Districts**.
- Add a new police station (e.g. when a new station is notified) — Admin → Districts → pick district → Add station.
- Rename a station — Admin → Districts → pick station → Edit. **Renaming changes how cases are reported in dashboards but does NOT move existing cases**; coordinate with the IT team if you reorganise.

---

## How to manage criminals / proclaimed-offenders

Admin → **Criminals** → **Add criminal**. Upload a clear face photo, name, FIR reference, charges. The system creates a vector embedding so any future UI-body match against this person is flagged.

---

## When in doubt

- For **case-handling questions**: refer to `11_USER_GUIDE_INVESTIGATOR.md`.
- For **system errors** (page won't load, save button greys out): note the time and what you were doing, then call IT (`15_SUPPORT_AND_ESCALATION.md`).
- For **a wrong match**: encourage the investigator to record their feedback (Useful / Not useful / Wrong person). The system learns from this over time.

---

## Reading a match shortlist

When an investigator runs a face match on an unidentified body, the case detail page shows up to 10 ranked candidates from the missing-person reference gallery and the criminals master. For each candidate you see:

| Column | What it means |
|---|---|
| Photo | A reference photo of the candidate. |
| Name + ID | The candidate's record. Click to open. |
| Score | Cosine similarity 0.00–1.00. The system colour-codes:<br>**Green ≥ 0.45** = strong; **Amber 0.35–0.45** = medium; **Grey < 0.35** = weak. |
| Sources | How many separate photos of the candidate matched (more = more reliable). |
| Investigator action | Useful / Not useful / Wrong person — your team's feedback. |

**Always treat matches as leads, not as proof.** Confirm via dental records, kin identification, fingerprints, or DNA per investigative protocol.

---

## Reports

Reports → **Cases** or **Matches** → choose date range and (optionally) station → Download CSV.

Useful for:

- Monthly review with the SP.
- District-level statistics for senior staff.
- Audit / compliance review.

---

## When something looks wrong

- **A match score of 0.95 against a recent UI body and a missing-person record**: very strong lead. Tell the investigator to bring in family for in-person ID immediately. Capture in the case notes.
- **No matches at all on a clear face photo**: the gallery may be sparse. Encourage the data-entry team to keep loading historical missing-person records (`08_BULK_IMPORT_SOP_FOR_DATA_ENTRY.md`).
- **The same UI body appears matched to many candidates with similar scores**: the photo quality is probably poor. Ask the field officer to retake (`12_USER_GUIDE_FIELD_OFFICER.md`).

---

## Escalation

Use the **Escalate** button on a case to notify the admin / district nodal officer when:

- You need a sensitive case re-classified.
- You need a case visibility extended beyond your jurisdiction (e.g. interstate).
- You suspect data quality issues.

Escalations are tracked in the audit log and visible to the admin.

---

## Chapter 11 — 11 — User guide for the Investigator

For **investigating officers** — your job is to work assigned UI-body cases and act on the match shortlists UBIS produces.

---

## What you see

When you log in:

- **My cases**: cases assigned to you or your police station.
- **Search**: face / text / voice search across the entire UBIS gallery.
- **New case**: register a UI body (often a field officer does this; you can too).

You **cannot**:

- Create or disable users.
- See cases outside your station / jurisdiction (your supervisor / admin can).

---

## A typical case workflow

### Step 1 — Open a case

1. **My cases** → click an open case.
2. The case detail page shows: photos, attributes (date, location, gender, height), match shortlist, notes.

### Step 2 — Run / refresh the match

1. Click **Run match** if the shortlist is empty or stale.
2. Wait ~30 seconds. The shortlist appears with up to 10 candidates ranked by similarity.

### Step 3 — Review each candidate

For each candidate row:

1. Click the candidate's name to open their reference profile in a side panel.
2. Compare faces side-by-side. Look for:
   - Eye spacing and shape.
   - Nose bridge and tip.
   - Mouth shape, lip thickness.
   - Distinctive marks (moles, scars, tattoos).
3. Compare attributes (estimated age range, height, build).
4. Record your judgement using the action buttons:

| Button | When to use |
|---|---|
| **Useful** | Candidate looks like a plausible match — proceed with verification. |
| **Confirmed (with proof)** | Independent proof obtained (kin ID, dental, fingerprint). |
| **Not useful** | Visibly different person. |
| **Wrong person** (special) | Candidate confirmed to be alive elsewhere — critical to flag. |

Your feedback improves the system over time.

### Step 4 — Add case notes

The **Notes** tab lets you record:

- Family/kin contacted on (date).
- Verification method used.
- Status of the body (post-mortem, released to family, unclaimed).

### Step 5 — Close the case

When the case is identified or formally closed unidentified:

1. Click **Close case**.
2. Pick the reason: Identified by UBIS lead / Identified by other means / Closed unidentified.
3. Save. The case stays in history; nothing is deleted.

---

## How to do a free-text or voice search

Use this when a citizen comes to the station with limited information ("woman in her 30s, found near Sohna last month").

1. **Search** tab.
2. Type the description, OR click the microphone icon and speak in Hindi/English.
3. The system searches across attributes (gender, age range, district, date, build, clothing, marks) and returns matching cases.
4. Click any result to open the case.

For face-photo search (you have a photo of a missing person and want to see if any UI body matches), use **Search → Face**.

---

## Quality tips

- **The system is only as good as the photos it sees.** If your match shortlist is consistently weak on a case, ask the field officer to retake the frontal face photo (good lighting, eyes open, no shadows).
- **Always confirm matches via independent means**: kin identification, fingerprints, dental, DNA. UBIS is an investigative lead, never the final answer.
- **Record your feedback every time.** "Useful" / "Not useful" both train the model.

---

## When something looks wrong

- **No matches even on a clear photo**: the missing-person gallery may not yet have a record for this person. Encourage the data-entry team to keep loading.
- **Same person showing up against many UI bodies**: feedback "Wrong person" — this teaches the system.
- **A case won't save**: the file might be too large (> 10 MB). Resize the photo and retry.
- **System is slow**: tell IT — they will check `bash scripts/onprem/ubis-status.sh`.

---

## Escalation to your supervisor

Use the **Escalate** button on a case to bring it to your supervisor's attention when:

- Possible interstate ID lead (suspect from outside Haryana).
- Sensitive case (VIP / political / media-attention).
- You suspect a data quality issue you cannot fix.

---

## Chapter 12 — 12 — User guide for the Field Officer

For **constables and ASIs registering UI bodies at the scene** — your job is to capture good photos and a few essential attributes. The system does the rest.

---

## Six steps to register a UI body

> Time: 5–8 minutes per case once you know the form.

1. **Log in** — open UBIS in your phone or laptop browser, enter your username and password.
2. **Tap "New case"** (top right).
3. **Take photos** in this order, using the camera button on each tile:
   - **Frontal face** — required.
   - **Left profile** — recommended.
   - **Right profile** — recommended.
   - **Full body** — recommended.
   - **Marks / tattoos / scars** (one or more) — if any.
   - **Clothing** — if intact.
   - **Belongings** — if any.
4. **Fill the basics:**
   - Found date.
   - Found location (text).
   - District = Gurugram (or your district).
   - Police station = pick your station from the dropdown.
   - Gender = Male / Female / Unknown.
   - Estimated age range (min and max).
5. **Add anything else you observed** — height, build, skin tone, hair colour, beard, distinctive marks, clothing description.
6. **Save** — the system gives you a case ID. Hand the case ID to the duty officer.

The system automatically runs a match in the background. Your investigator sees the shortlist within a minute.

---

## How to take a good face photo

This is the single most important thing you do. The system's accuracy depends on it.

| Do | Don't |
|---|---|
| Use natural light or a strong torch from the front | Photograph in deep shadow or with strong backlight |
| Hold the phone steady, eye-level with the face | Shoot from above or below |
| Get close: **face fills 60–80 % of the frame** | Stand 10 feet away and zoom in |
| Eyes open if possible; clean blood / mud gently first | Use heavy filters, beautify modes, flash that washes out features |
| Take 2–3 shots from slightly different angles | Use one blurry shot |
| Profile shots (left and right) help a lot | Skip profiles even when easy to take |

Aim for **at least 600 × 600 pixels** at the face. Most modern phones produce this easily.

---

## Phone camera tips

- Tap-to-focus on the face before pressing the shutter.
- Switch off the **beauty filter** in your camera settings — it removes the very features the system uses (skin texture, exact nose shape).
- Use the **rear camera**, not the selfie camera.
- If the body is in a vehicle / mortuary trolley, ask for a moment to take it out — better surface = better photo.

---

## What if there is no face?

If the face is destroyed / not visible:

- Take photos of any **distinctive marks**: tattoos, scars, jewellery, deformities, dental work.
- Take a **full-body** photo (helps with stature / clothing).
- Photograph **belongings** clearly (Aadhaar / driving licence if found, mobile phones, jewellery).
- Fill in the **clothing description** thoroughly.

The system can still help — investigators can do text / attribute search on cases without a face match.

---

## Privacy and dignity

- Cover the body appropriately; only the photographed parts (face / marks / belongings) need to be visible.
- Photograph in a private setting where possible. Avoid spectators.
- Never share UBIS photos via WhatsApp, social media, or personal devices outside the police network.

---

## Common mistakes to avoid

- Saving without the **frontal face** photo (you cannot match on the face later if it isn't uploaded).
- Picking the wrong **police station** (the case gets routed to a wrong investigator).
- Leaving **gender** as Unknown when it is clearly known (reduces filter accuracy).
- Uploading screenshots of phone galleries instead of original photos (screenshots throw away EXIF and quality).

---

## When in doubt

Ask your duty officer or call the IT helpdesk number from `15_SUPPORT_AND_ESCALATION.md`. Better to take 5 minutes to get help than to register a case with poor photos that the system cannot match.

---

## Chapter 08 — 08 — Bulk import SOP (for the data-entry team)

This SOP is for the **data-entry team at District HQ** that prepares historical UI-body records for upload.

> **📖 See [`BULK_IMPORT_GUIDE.md`](../../BULK_IMPORT_GUIDE.md) in the root `docs/` folder for the complete, detailed guide.** This chapter provides a quick overview; refer to the full guide for step-by-step instructions, troubleshooting, and worked examples.

The IT team (one person) does the actual import on the server. The data-entry team prepares the materials.

---

## Quick Overview: What You'll Deliver to IT

A single ZIP file per district / police station containing:

1. `ui_body_template.xlsx` filled in (one row per case).
2. An `images/` folder, with one sub-folder per case, containing the photos referenced from the spreadsheet.

**For complete instructions on preparing this ZIP, see [`BULK_IMPORT_GUIDE.md`](../../BULK_IMPORT_GUIDE.md) Sections 2–4.**

---

## Quick File Structure Reminder

Example layout inside the ZIP:

```
GGN_PS-Sohna_2025-Q1.zip
├── ui_body_template.xlsx
└── images/
    ├── DDR-101-2025/
    │   ├── face.jpg
    │   ├── face_left.jpg
    │   ├── full_body.jpg
    │   └── tattoo_left_arm.jpg
    ├── DDR-102-2025/
    │   ├── face.jpg
    │   └── full_body.jpg
    └── ...
```

---

## 2. Step-by-step preparation

**👉 See [`BULK_IMPORT_GUIDE.md`](../../BULK_IMPORT_GUIDE.md) for complete, detailed step-by-step instructions.** The guide includes:
- Getting & filling the template
- Photo quality requirements (600×600px minimum)
- Validation checklist
- Worked examples with 3 sample cases
- Troubleshooting common errors

---

## 3. IT Execution

### Step 2 — Fill one row per case

| Column | What to enter | Example |
|---|---|---|
| `dd_no` | Daily Diary / case number from your station register | `DDR-101-2025` |
| `found_date` | Date the body was found, `YYYY-MM-DD` | `2025-03-12` |
| `found_district` | Pick from dropdown (Gurugram for this pilot) | `Gurugram` |
| `ps_name` | Police station name (must match master) | `Sohna` |
| `found_loc` | Free-text location | `Behind Sohna bus stand` |
| `gender` | Dropdown: Male / Female / Unknown | `Male` |
| `age_min`, `age_max` | Estimated age range | `25` and `35` |
| `height_cm` | Estimated height in cm | `170` |
| `build` | Dropdown | `Medium` |
| `skin_tone` | Dropdown | `Medium` |
| `hair_color` | Dropdown | `Black` |
| `beard` | Yes / No / N/A | `Yes` |
| `visible_marks` | Tattoos, scars | `Tattoo of "Maa" on left forearm` |
| `clothing_description` | What they were wearing | `Blue jeans, white t-shirt with red logo` |
| `notes` | Any case context | `Found near railway track; PCR call PCR-555-2025` |
| `additional_details` | Family / officer remarks | `Family of Ramesh Kumar reported similar missing` |
| `image_face_frontal_path` | Path **relative to the spreadsheet** | `images/DDR-101-2025/face.jpg` |
| `image_face_left_path` | Optional | `images/DDR-101-2025/face_left.jpg` |
| `image_face_right_path` | Optional | |
| `image_full_body_path` | Recommended | `images/DDR-101-2025/full_body.jpg` |
| `image_tattoo_path` | If marks present | `images/DDR-101-2025/tattoo_left_arm.jpg` |
| `image_clothing_path` | Optional | |
| `image_belonging_path` | Optional | |

**Required minimum:** `dd_no`, `found_date`, `found_district`, `ps_name`, `gender`, `image_face_frontal_path`.

### Step 3 — Photo quality

- **Frontal face**: clear, well-lit, eyes visible, no heavy shadows, **at least 600 × 600 pixels** at the face.
- **Profiles** (left / right): only if available; not mandatory.
- **Full body**: from a few feet away, full clothing visible.
- **Marks / tattoos**: close-up, in focus.
- **No selfies, no group shots, no print-then-rephotograph** (digital original wherever possible).
- Acceptable formats: `.jpg`, `.jpeg`, `.png`. Keep file size under ~10 MB each.

### Step 4 — Sanity-check before zipping

Before sending the ZIP to IT, check:

| Check | How |
|---|---|
| Every `image_*_path` cell has the correct path | Open random rows and click the cell to see the path; verify the file exists in `images/`. |
| District / police station names match the system master | Use the dropdown — if the cell turns yellow / errors, the value is wrong. |
| No row has `dd_no` blank | Sort by `dd_no`; gaps mean missing data. |
| File names contain no spaces or special characters | Spaces work but are fragile across systems. |

### Step 5 — Hand off

Zip the entire folder (spreadsheet + `images/`). Use the **encrypted upload channel** the IT team gives you (typically a department secure file transfer). **Never** email police case images to anyone.

---

## 3. Worked example (3 rows)

| dd_no | found_date | found_district | ps_name | gender | image_face_frontal_path |
|---|---|---|---|---|---|
| DDR-101-2025 | 2025-03-12 | Gurugram | Sohna | Male | images/DDR-101-2025/face.jpg |
| DDR-102-2025 | 2025-03-13 | Gurugram | Cyber City | Female | images/DDR-102-2025/face.jpg |
| DDR-103-2025 | 2025-03-15 | Gurugram | Manesar | Unknown | images/DDR-103-2025/face.jpg |

A complete worked example with sample images is included as `sample_import_images/` in the handover package — IT can use it for an end-to-end test before your real batch.

---

## 4. What IT does next (informational)

The IT operator unzips your batch under `data/uploads/import-batch-001/` on the server and runs:

```bash
# Docker:
docker compose -f docker-compose.onprem.yml exec -T backend \
    python -m scripts.bulk_import_ui_bodies \
    /app/uploads/import-batch-001/ui_body_template.csv \
    /app/uploads/import-batch-001

# Podman (note the --profile flag):
podman compose -f docker-compose.onprem.yml --profile lite exec -T backend \
    python -m scripts.bulk_import_ui_bodies \
    /app/uploads/import-batch-001/ui_body_template.csv \
    /app/uploads/import-batch-001
```

The script takes **two** positional arguments:
1. the path to the filled-in CSV inside the container (`/app/uploads/...` — the `./data/uploads` directory on the host is mounted at `/app/uploads`).
2. the base directory containing the `images/` folder.

If your team prefers the `.xlsx` template, IT first exports it to CSV (File → Save As → CSV UTF-8) before running the script. The columns must be unchanged.

The script:

- Validates each row (you will get a row-by-row error list).
- For every filled `image_*_path`, runs face embedding and stores it in Qdrant.
- Inserts the case into the database.
- Writes an audit-log entry per row.

If a row fails (bad image, missing file), IT shares the error log with you. You fix only those rows and resend.

---

## 5. Checklist for the data-entry team lead

- [ ] All officers preparing data have read [`BULK_IMPORT_GUIDE.md`](../../BULK_IMPORT_GUIDE.md)
- [ ] Master districts/stations list shared with data-entry team
- [ ] Encrypted file-transfer channel agreed with IT
- [ ] First batch is small (~25 rows) to validate workflow
- [ ] After import: spot-check 3 random cases in the system (photos visible, attributes correct)
- [ ] Sign-off recorded in `UAT_AND_POLICE_SIGNOFF.md` Section 9
