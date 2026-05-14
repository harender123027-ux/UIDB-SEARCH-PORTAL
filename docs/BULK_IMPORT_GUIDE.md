# Bulk Import Guide: CSV + Images for UBIS
**For Data Entry Officers and IT Staff**

> For volumes above ~2 500 rows per batch, also read
> **[`BULK_IMPORT_AT_SCALE.md`](BULK_IMPORT_AT_SCALE.md)** (batching strategy,
> overnight runs, storage sizing, and the path from the lite profile to a
> dedicated Qdrant server when you cross ~50 000 cases).

---

## Quick Summary

This guide explains how to bulk-import older unidentified bodies (UI bodies) into UBIS from CSV spreadsheets and photos. Instead of manually entering each case through the web form, you'll prepare a batch in a structured CSV file with organized photos, and the IT team will import them all at once using an automated script.

**What you'll achieve:**
- Many historical cases loaded into UBIS in a single operation
- All photos indexed with face embeddings (InsightFace `buffalo_l/w600k_r50.onnx`) for fast searching
- Audit trail logged for compliance (`action = bulk.import`)
- Zero manual data entry at the server side

**Time per batch:** 2–3 hours for the data-entry team; ~15–25 minutes of IT time per 1 000 rows (CPU-only on-prem host).

**Sample CSV:** the file `ui_body_template.csv` at the repository root ships
with 5 fully-populated example rows (`DDR-SAMPLE-101-2026` … `DDR-SAMPLE-105-2026`)
covering face, profile, full-body, tattoo, clothing, and belonging slots. Copy
it into your batch folder, rename to your batch's CSV, and replace the rows
with real cases.

---

## Prerequisites

### For the Data-Entry Team

- [ ] A spreadsheet program (Microsoft Excel, Google Sheets, or LibreOffice Calc)
- [ ] Access to the `ui_body_template.xlsx` file (IT provides this)
- [ ] Access to the master list of **valid district and police station names** (from IT)
- [ ] Scanned or digitized copies of old case files (including photos)
- [ ] A secure file-transfer channel to send batch ZIPs to IT (e.g., department secure server, encrypted upload, **never email**)
- [ ] Read permission on the UBIS system after import (to spot-check results)

### For the IT Person

- [ ] Shell access to the server running UBIS
- [ ] Docker or Podman installed (check: `docker --version` or `podman --version`)
- [ ] The UBIS backend codebase (with `scripts/bulk_import_ui_bodies.py`)
- [ ] Access to `docker-compose.onprem.yml` file. On the **lite** profile this
      already pins the backend to `--workers 1` because embedded Qdrant holds
      an exclusive write lock on `data/qdrant/`.
- [ ] ~0.4–0.8 s per face image on CPU (counted across detection + InsightFace
      embedding). Plan ~15–25 minutes per 1 000 rows on a 4 vCPU host.
- [ ] Error log from data-entry team (they send CSV + images; you send back any errors)

---

## Data Preparation: Step-by-Step

### Step 1: Gather and Organize Photos

Create a **folder structure** on your computer (or shared drive) like this:

```
import-batch-001/
├── images/
│   ├── DDR-101-2025/
│   │   ├── face.jpg
│   │   ├── face_left.jpg
│   │   ├── full_body.jpg
│   │   └── tattoo_left_arm.jpg
│   ├── DDR-102-2025/
│   │   ├── face.jpg
│   │   └── full_body.jpg
│   └── DDR-103-2025/
│       ├── face.jpg
│       ├── face_left.jpg
│       ├── face_right.jpg
│       ├── full_body.jpg
│       └── clothing.jpg
└── ui_body_template.csv  (or .xlsx — we'll export to CSV)
```

**Key points:**
- Folder name = case ID (e.g., `DDR-101-2025`). Use the **Daily Diary number** from your station register.
- One subfolder per case.
- Photo filenames do **not** need to match exactly (e.g., `face.jpg`, `front.jpg`, `face_frontal.jpg` all work). What matters is the CSV column that points to it.
- Keep file names **simple**: no spaces, no special characters (use hyphens instead of spaces).

**Success looks like:** You can navigate the `images/` folder and see one subfolder per case.

---

### Step 2: Get the Template

Ask the IT team for `ui_body_template.xlsx`. This is a spreadsheet with:
- Pre-built dropdown menus (gender, build, district, police station).
- All 24 column headers already set up.
- Reference data on a hidden sheet.

**Do not create your own CSV from scratch.** Use the template.

**Success looks like:** You open the file in Excel and see column headers like `dd_no`, `found_date`, `gender`, `image_face_frontal_path`, etc.

---

### Step 3: Fill in the CSV Row by Row

Open `ui_body_template.xlsx` in Excel (or Sheets, Calc, etc.) and create one **row per case**.

> **Time-saver:** If you have 100 cases, consider splitting the work among 3–4 people. Each person fills one "chunk" in parallel. Combine them before validation.

#### Example Row

```
dd_no              | DDR-101-2025
found_date         | 2025-03-12
found_district     | Gurugram
ps_name            | Sohna
found_loc          | Behind Sohna bus stand, near water tank
gender             | Male
age_min            | 25
age_max            | 35
height_cm          | 170
build              | Medium
skin_tone          | Fair
hair_color         | Black
beard              | Yes
visible_marks      | Tattoo of "Maa" on left forearm, scar on chin
clothing_description | Blue jeans, white t-shirt with red logo, no shoes
notes              | Found near railway track; PCR call PCR-555-2025; initial suspicion: 15-day-old body
additional_details | Family of Ramesh Kumar (DDR-99-2024) reported similar missing; possible relative
image_face_frontal_path | images/DDR-101-2025/face.jpg
image_face_left_path    | images/DDR-101-2025/face_left.jpg
image_face_right_path   | (blank)
image_full_body_path    | images/DDR-101-2025/full_body.jpg
image_tattoo_path       | (blank)
image_clothing_path     | (blank)
image_belonging_path    | (blank)
```

---

## CSV Column Reference

| Column | What it means | Example | Required? | Notes |
|--------|---------------|---------|-----------|-------|
| **dd_no** | Daily Diary / case registration number from your station | `DDR-101-2025` | **YES** | Must be unique; appears as Case ID in UBIS |
| **found_date** | Date body was found | `2025-03-12` | **YES** | Format: `YYYY-MM-DD` (ISO). Not the autopsy date or report date. |
| **found_district** | District where found | `Gurugram` | **YES** | Must match the master list. Use the dropdown menu. |
| **ps_name** | Police station name | `Sohna` | **YES** | Must match the district. Use the cascading dropdown (auto-filters). |
| **found_loc** | Location description (free text) | `Behind bus stand, Mile Marker 5` | **YES** | Helps investigators; no special format. |
| **gender** | Observed gender | `Male`, `Female`, or `Unknown` | **YES** | Use dropdown. Avoid typos. |
| **age_min** | Minimum estimated age (in years) | `25` | **YES** | Integer only (no `.5`). Conservative estimate. |
| **age_max** | Maximum estimated age (in years) | `35` | **YES** | Should be ≥ age_min. Typical range: 8–12 years. |
| **height_cm** | Estimated height in centimeters | `170` | No | Integer. Leave blank if uncertain. |
| **build** | Body build / frame | `Slim`, `Medium`, `Heavy`, or `Unknown` | No | Use dropdown. Important for matching. |
| **skin_tone** | Observed skin tone | `Fair`, `Medium`, `Dark`, or `Unknown` | No | Use dropdown. |
| **hair_color** | Hair color | `Black`, `Brown`, `Grey`, `White`, or `Unknown` | No | Use dropdown. |
| **beard** | Facial hair observed | `Yes`, `No`, or `N/A` | No | `N/A` if gender unknown. Use dropdown. |
| **visible_marks** | Tattoos, scars, birthmarks, moles | `Tattoo of name on left arm; scar above left eyebrow` | No | Comma-separated. Critical for matching. |
| **clothing_description** | Clothing worn (at scene) | `Blue jeans, white shirt, red scarf, one brown shoe` | No | As detailed as possible; helps context. |
| **notes** | Investigation notes / context | `PCR Call PCR-555; body collected from highway` | No | Case-handling notes; not visible to field. |
| **additional_details** | Family / manual remarks | `Sister contacted; Aadhaar DDR-556` | No | Officer observations. |
| **image_face_frontal_path** | Path to frontal face photo | `images/DDR-101-2025/face.jpg` | **YES** | Relative path from batch root. Mandatory for matching. |
| **image_face_left_path** | Path to left profile photo | `images/DDR-101-2025/face_left.jpg` | No | Improves matching. |
| **image_face_right_path** | Path to right profile photo | `images/DDR-101-2025/face_right.jpg` | No | Improves matching. |
| **image_full_body_path** | Path to full-body photo | `images/DDR-101-2025/full_body.jpg` | No | Shows clothing, stature. |
| **image_tattoo_1_path** | Path to first tattoo / mark / person item photo | `images/DDR-101-2025/tattoo_1.jpg` | No | Close-up of visible marks. Primary tattoo/item shown by default. Replaces legacy `image_tattoo_path`. |
| **image_tattoo_2_path** | Path to second tattoo / mark / person item photo | `images/DDR-101-2025/tattoo_2.jpg` | No | Additional tattoo or mark (up to 10 total). |
| **image_tattoo_3_path** through **image_tattoo_10_path** | Paths to 3rd–10th tattoo / mark / person items | `images/DDR-101-2025/tattoo_3.jpg`, etc. | No | Fill in as many as available for the case. |
| **image_clothing_path** | Path to clothing detail | `images/DDR-101-2025/clothing.jpg` | No | Detail shot if clothing distinctive. |
| **image_belonging_path** | Path to belongings | `images/DDR-101-2025/belongings.jpg` | No | Wallet, phone, jewelry, etc. |

### Column Fill Rules

1. **Age range:** Be conservative. If the body looks 35–50, enter `age_min=35` and `age_max=50`, not `30–55`. The system will match against the full range.

2. **Height:** Estimate standing height (pre-mortem). If decomposed, make your best judgment or leave blank.

3. **Dates:** Always use `YYYY-MM-DD` format. Excel might auto-convert to `MM/DD/YYYY` — **check before saving**. Better: format the column as "Text" in Excel, then type the date manually.

4. **Dropdown fields:** If you type a value not in the dropdown, the cell will show a yellow warning. This is Excel telling you the value is invalid. Use **only** the predefined values.

5. **Image paths:** **Must be relative paths** from the batch root. If your batch folder is `import-batch-001/`, and a photo is at `import-batch-001/images/DDR-101-2025/face.jpg`, the cell should say:
   ```
   images/DDR-101-2025/face.jpg
   ```
   **Not** `/import-batch-001/images/DDR-101-2025/face.jpg` or `/Users/you/Desktop/...` (absolute paths will fail).

---

## Photo Quality Requirements

The system depends on photo quality. Poor photos = weak matches.

### Face Photos (Frontal, Left, Right)

- **Resolution:** Minimum **600 × 600 pixels** at the face (face fills at least 60–80% of the frame).
- **Lighting:** Well-lit, natural or strong torch light. **Avoid shadows** on the face.
- **Focus:** Sharp. Eyes, nose, mouth features must be clear.
- **Angle:** Frontal face straight-on; profiles at ~45° left and right.
- **Background:** Neutral if possible (can be messy scene; just avoid glare on face).
- **Format:** `.jpg`, `.jpeg`, `.png`. Maximum **~10 MB** per file (most phones produce 2–5 MB).
- **No filters:** Remove beauty apps, heavy filters, blur effects. The system uses exact skin texture and feature position.
- **Eyes open:** If eyes are closed or decomposed, mark in `visible_marks` ("eyes decomposed").

✅ **Good:**
- Fresh body, good lighting, clear facial features, eyes visible, 800 × 800 pixels, natural color.

❌ **Bad:**
- Blurry; backlit (face is silhouette); too dark; too zoomed-in (only nose visible); too far away (face tiny); heavy Instagram filter; screenshot of phone gallery.

### Full-Body Photo

- **Distance:** 3–5 feet away from the body.
- **Coverage:** Entire body head-to-toe (or as much as visible).
- **Detail:** Clothing, stature, build all clear.
- **Format:** `.jpg`, `.png`. Maximum ~10 MB.

### Marks / Tattoos / Scars

- **Close-up:** Zoom in enough to see the mark clearly.
- **Focus:** Sharp. Scars should show texture / color.
- **Angle:** Photograph from directly above or at a slight angle; avoid glare.
- **No cropping needed:** Show enough context to help identify which body part.

### Belongings / Clothing Detail

- Optional, but helpful for context matching.
- Photograph clearly; avoid shadows.
- Include any text (e.g., label on clothing) that's legible.

### Digital Originals Only

- **Do NOT** photograph print-outs of old case files, then re-upload the photo. This degrades quality.
- **Use originals:** If you have digital photos from 2015, use those directly.
- **Scan old prints:** If you only have printed photos, use a scanner (not a camera) — scanners preserve more detail.

---

## File Structure Diagram

Before you zip up your batch, your folder should look **exactly like this:**

```
import-batch-001/                    (batch folder name; can be anything)
│
├── ui_body_template.csv             (exported from Excel; or keep as .xlsx)
│
└── images/                          (MANDATORY subfolder name: "images")
    │
    ├── DDR-101-2025/                (one folder per case; matches dd_no)
    │   ├── face.jpg                 (recommended)
    │   ├── face_left.jpg            (optional)
    │   ├── full_body.jpg            (recommended)
    │   └── tattoo.jpg               (optional)
    │
    ├── DDR-102-2025/
    │   ├── face.jpg
    │   ├── face_left.jpg
    │   ├── face_right.jpg
    │   ├── full_body.jpg
    │   ├── clothing.jpg
    │   └── belongings.jpg
    │
    └── DDR-103-2025/
        └── face.jpg
```

**Strict rules:**
- Folder at root level must be named **`images`** (lowercase, exact spelling).
- Every case gets its own subfolder under `images/`.
- Subfolder name = the `dd_no` value for that case.
- CSV file at the root level of the batch folder.
- **No other files** at root (no `.txt` notes, no `.docx` files, just CSV + images/ folder).

---

## Validation Checklist (Before Sending to IT)

Before you zip up and send the batch, **the data-entry team lead should verify:**

- [ ] **CSV structure**
  - [ ] Column headers are unchanged from the template (24 columns exactly).
  - [ ] No rows are completely blank.
  - [ ] No row has both `age_min` and `age_max` blank (if age is unknown, enter "Unknown" — wait, no, the template shows they are numeric. Leave blank if uncertain.).

- [ ] **Mandatory fields present** (for every row)
  - [ ] `dd_no` — not blank, unique, no duplicates.
  - [ ] `found_date` — matches `YYYY-MM-DD` format, no `03/12/2025` or `12-Mar-2025`.
  - [ ] `found_district` — exactly matches the system master (if unsure, IT provides a reference list).
  - [ ] `ps_name` — cascading dropdown filled; auto-filters based on district.
  - [ ] `gender` — one of: Male, Female, Unknown.
  - [ ] `image_face_frontal_path` — pointing to an existing file in the `images/` folder.

- [ ] **Image structure**
  - [ ] `images/` folder exists at the batch root.
  - [ ] Every subfolder name matches a `dd_no` in the CSV (e.g., if row has `DDR-101-2025`, there is a `images/DDR-101-2025/` folder).
  - [ ] Every path in the CSV (e.g., `images/DDR-101-2025/face.jpg`) points to a file that actually exists.
  - [ ] No image file names have spaces (use `face.jpg`, not `face photo.jpg`).

- [ ] **Image quality spot-check**
  - [ ] Open 5 random case folders; open 3 photos in each using image viewer.
  - [ ] Verify: face photos are clear (not blurry), lighting is okay, no heavy filters.
  - [ ] Spot-check: at least one full-body photo per case (if claimed in CSV).

- [ ] **Data quality spot-check**
  - [ ] Open 10 random rows. For each: do the attributes match the photos? (e.g., if CSV says "Male, ~40 years", does the face look male and ~40?)
  - [ ] No obviously inconsistent data (e.g., `height_cm=50` — that's too short for an adult).

- [ ] **Before zipping**
  - [ ] Batch folder contains ONLY two things: `ui_body_template.csv` (or `.xlsx`) and `images/` subfolder.
  - [ ] No readme files, no notes, no `.txt` files at the root.

---

## Example Worked Case: Start to Finish

**Scenario:** You have a case file from 2018 (old paper record). The police diary says:

> Case: DDR-42-2018, Found: 12 March 2018, Location: Sohna Bypass, District: Gurugram, Police Station: Sohna. Male body, estimated 45–55 years. Height: ~165 cm. Build: Medium. Skin: Dark. Hair: Grey. Beard: Yes. Marks: Birthmark on left shoulder, scar on right temple. Clothing: White shirt, brown pants, no shoes.

You have **four old photos** stored as image files on your computer:
- `~/Documents/case_42_face.jpg` (clear frontal face photo)
- `~/Documents/case_42_full_body.jpg` (full body standing against a wall)
- `~/Documents/case_42_birthmark.jpg` (close-up of shoulder mark)
- `~/Documents/case_42_temple_scar.jpg` (close-up of scar)

### Action Steps

1. **Create the case folder:**
   ```
   import-batch-001/images/DDR-42-2018/
   ```

2. **Copy photos into the folder:**
   ```
   import-batch-001/
   └── images/
       └── DDR-42-2018/
           ├── face.jpg                  (copied from ~/Documents/case_42_face.jpg)
           ├── full_body.jpg             (copied from ~/Documents/case_42_full_body.jpg)
           ├── birthmark.jpg             (copied from ~/Documents/case_42_birthmark.jpg)
           └── temple_scar.jpg           (copied from ~/Documents/case_42_temple_scar.jpg)
   ```

3. **Fill the CSV row:**

   | Column | Value |
   |--------|-------|
   | dd_no | DDR-42-2018 |
   | found_date | 2018-03-12 |
   | found_district | Gurugram |
   | ps_name | Sohna |
   | found_loc | Sohna Bypass |
   | gender | Male |
   | age_min | 45 |
   | age_max | 55 |
   | height_cm | 165 |
   | build | Medium |
   | skin_tone | Dark |
   | hair_color | Grey |
   | beard | Yes |
   | visible_marks | Birthmark on left shoulder, scar on right temple |
   | clothing_description | White shirt, brown pants, no shoes |
   | notes | (blank) |
   | additional_details | (blank) |
   | image_face_frontal_path | images/DDR-42-2018/face.jpg |
   | image_face_left_path | (blank) |
   | image_face_right_path | (blank) |
   | image_full_body_path | images/DDR-42-2018/full_body.jpg |
   | image_tattoo_path | (blank) |
   | image_clothing_path | (blank) |
   | image_belonging_path | (blank) |

4. **Verify:**
   - Open the `images/DDR-42-2018/` folder → see 4 files. ✓
   - Open `face.jpg` in image viewer → clear, well-lit, face visible. ✓
   - CSV row is filled with correct district / PS (both from dropdown). ✓
   - Paths in CSV match actual files. ✓

5. **Success:** This case is ready to import. When IT runs the script, it will:
   - Create a new UBIS case with ID `DDR-42-2018`.
   - Load all four photos.
   - Generate face embeddings from `face.jpg` and `full_body.jpg`.
   - Index the case so investigators can search on "Male, ~50 years, grey hair" and find it.

---

## IT Execution Guide

### What the IT Person Does

The IT operator has received a **ZIP file** from the data-entry team. Inside the ZIP:
- `ui_body_template.csv` (or `.xlsx` — convert to CSV if needed)
- `images/` folder with case subfolders

### Commands to Run

#### 1. Prepare the Server

SSH into the UBIS server and navigate to the project root:

```bash
cd /path/to/ubis/repo  # e.g., /opt/ubis or /home/ubis/app
```

#### 2. Extract the Batch

```bash
# Create a working directory
mkdir -p ./data/uploads/import-batch-001

# Extract the ZIP (adjust the path to the ZIP you received)
unzip ~/Downloads/batch_ggn_sohna_2025q1.zip -d ./data/uploads/import-batch-001/

# Verify structure
ls -la ./data/uploads/import-batch-001/
# Should see: ui_body_template.csv, images/
```

#### 3. Export CSV (if data-entry team sent `.xlsx`)

If the file is still `.xlsx`, convert it:

```bash
# Using a Python one-liner (if pandas is installed):
python3 -c "import pandas as pd; df = pd.read_excel('./data/uploads/import-batch-001/ui_body_template.xlsx'); df.to_csv('./data/uploads/import-batch-001/ui_body_template.csv', index=False)"

# Or use a spreadsheet tool on a desktop and copy the CSV back.
```

#### 4. Run the Import Script

**Option A: Using Docker**

```bash
docker compose -f docker-compose.onprem.yml exec -T backend \
    python -m scripts.bulk_import_ui_bodies \
    /app/uploads/import-batch-001/ui_body_template.csv \
    /app/uploads/import-batch-001
```

**Option B: Using Podman** (with lite profile)

```bash
podman compose -f docker-compose.onprem.yml --profile lite exec -T backend \
    python -m scripts.bulk_import_ui_bodies \
    /app/uploads/import-batch-001/ui_body_template.csv \
    /app/uploads/import-batch-001
```

### What to Expect

The script will run for several minutes (slower on first run; depends on image count and AI model speed).

**Expected output (console):**

```
Imported record 1: DDR-42-2018 (ID: a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6)
Imported record 2: DDR-43-2018 (ID: q1r2s3t4-u5v6-w7x8-y9z0-a1b2c3d4e5f6)
...
Imported record 42: DDR-83-2018 (ID: z9y8x7w6-v5u4-t3s2-r1q0-p9o8n7m6l5k4)

Bulk import complete. Total records imported: 42
```

**Meanings:**
- ✅ **"Imported record X: DDR-YYY-ZZZZ"** → row succeeded; case created.
- ⚠️ **"Warning: Image `/app/uploads/.../images/...jpg` not found"** → file missing (row still imports; that image slot is skipped).
- ❌ **"Error importing row DDR-YYY-ZZZZ: [reason]"** → row failed (bad data, invalid date format, missing required field, etc.). The script continues; other rows may still succeed.

### Handling Errors

If rows fail, the script will print a detailed error message **per row**. Example:

```
Error importing row DDR-42-2018: ... ValueError: invalid literal for int() with base 10: 'abc' ...
```

**What to do:**

1. Copy the error output to a text file: `errors.txt`.
2. Send `errors.txt` back to the data-entry team.
3. The team fixes only the bad rows in the CSV, re-creates the batch ZIP, and sends it back.
4. Re-run the script on the corrected batch.

### Verify Import Success

After the script finishes:

```bash
# Query the database (if SQLite):
sqlite3 ./data/ubis.db "SELECT COUNT(*) as total_cases FROM submissions;"

# Or in Docker:
docker compose -f docker-compose.onprem.yml exec -T backend \
    sqlite3 /app/ubis.db "SELECT COUNT(*) FROM submissions;"
```

You should see the count **increase** by the number of imported rows.

**Then:**
1. Open the UBIS web interface.
2. Log in as admin or investigator.
3. Go to **Cases** → **My cases** (or **All cases** if admin).
4. **Spot-check:** Find 3 of the imported cases (search by DD number). Verify:
   - Photos are visible.
   - Attributes (gender, age range, height) match the CSV.
   - No error badges.

---

## Troubleshooting

### Common Problems and Fixes

#### Problem: "CSV file not found at /app/uploads/import-batch-001/ui_body_template.csv"

**Cause:** File path wrong or CSV not extracted.

**Fix:**
```bash
# Check the file exists:
ls -la ./data/uploads/import-batch-001/ui_body_template.csv

# If missing, re-extract the ZIP:
unzip -l ~/Downloads/your_batch.zip  # List contents
unzip ~/Downloads/your_batch.zip -d ./data/uploads/import-batch-001/
```

#### Problem: "Warning: Image not found. Skipping face_frontal."

**Cause:** The CSV path doesn't match the actual file location.

**Example:**
- CSV says: `images/DDR-101-2025/face.jpg`
- Actual file: `images/ddr_101_2025/face.jpg` (lowercase, different naming)

**Fix:**
- Data-entry team: verify CSV paths match folder/file names exactly (case-sensitive on Linux servers).
- Rename the image folder or update the CSV path.

#### Problem: "Error importing row DDR-101-2025: ... invalid literal for int() with base 10: '3.5' ..."

**Cause:** A numeric field (like `age_min`) contains a decimal or text.

**Fix (Data-Entry Team):**
- Open the CSV in Excel.
- Find the column `age_min` in row DDR-101-2025.
- Delete the value `3.5`; enter `3` or `4` (integer only).
- Re-export to CSV.

#### Problem: "Error importing row: ... no attribute 'found_date' ..."

**Cause:** Column name misspelled or CSV header row was deleted.

**Fix:**
- Check first row of CSV has all 24 headers (use: `head -1 ui_body_template.csv`).
- If headers are missing or wrong, regenerate from the template.

#### Problem: Script runs but imports 0 records

**Cause:** CSV header row is being read as a data row (and fails validation), so no rows pass.

**Fix:**
- IT: Check if the CSV file was corrupted during transfer. Re-export from Excel.
- Data-entry team: Ensure first row is headers; no blank rows between header and data.

#### Problem: "Error: Docker container not running" or "podman: command not found"

**Cause:** Container runtime issue.

**Fix:**
```bash
# Check if Docker is running:
docker ps

# If not, start it:
sudo systemctl start docker  # Linux
# or re-start Docker Desktop on Mac/Windows

# If using Podman:
podman ps  # Check status
```

#### Problem: Long runtime — script takes 30+ minutes on 100 rows

**Cause:** Face embedding AI model is slow (normal on first run; uses CPU if GPU unavailable).

**Fix:** This is expected. The script processes images in sequence; each face embedding takes ~5–10 seconds. 100 rows = 5–10 images per row on average = 50–100 minutes. You can:
- Run on a machine with GPU (much faster).
- Import in smaller batches (25 rows per batch, parallel runs).
- Leave it running overnight.

---

## Photo Quality Checklist (Quick Reference)

Print this and post in the data-entry team's work area:

```
PHOTO QUALITY CHECK

Before zipping the batch, open 3 random photos and verify:

FACE PHOTOS (Frontal, Left, Right)
☐ Resolution: at least 600×600 pixels
☐ Lighting: bright, no deep shadows on face
☐ Focus: sharp; can see eye details clearly
☐ Angle: straight-on for frontal; ~45° for profiles
☐ Eyes: open (or if closed, marked in "visible_marks")
☐ No filters: no Instagram, Snapchat, or Beauty app effects
☐ Format: .jpg or .png
☐ File size: under 10 MB

FULL-BODY PHOTOS
☐ Distance: 3–5 feet away
☐ Coverage: head to feet visible
☐ Clothing: clear, not obscured
☐ Format: .jpg or .png
☐ File size: under 10 MB

MARKS / TATTOOS
☐ Close-up: mark fills most of frame
☐ Focus: sharp; can see texture/color
☐ Angle: directly above or slight angle
☐ Context: enough of the body visible to identify location
```

---

## Quick Reference: Column Dropdowns

When you see a yellow cell warning in Excel, it means the value is not in the dropdown list. Use **only these values:**

### Gender
- Male
- Female
- Unknown

### Build
- Slim
- Medium
- Heavy
- Unknown

### Skin Tone
- Fair
- Medium
- Dark
- Unknown

### Hair Color
- Black
- Brown
- Grey
- White
- Unknown

### Beard
- Yes
- No
- N/A

### District & Police Station
**District:** (dropdown filled from system master; ask IT if unsure)
- Gurugram (for pilot)
- Other districts (when system expands)

**Police Station:** (cascading; auto-filters based on district — type district name first)

---

## Success Criteria

You'll know the import worked when:

1. **Data-entry team:**
   - ✅ All rows in CSV match the folder structure.
   - ✅ Spot-check: open 5 random imported cases in UBIS, see photos and attributes.

2. **IT:**
   - ✅ Script runs without "Error importing" lines (warnings about missing images are OK).
   - ✅ Database count increases by expected number: `SELECT COUNT(*) FROM submissions` goes from N to N + batch_size.
   - ✅ Spot-check: log in to UBIS web interface, search for a DD number from the batch, case appears with photos.

3. **Investigators:**
   - ✅ After import, investigators can search face photos against the imported cases.
   - ✅ Match scores appear within 30 seconds.
   - ✅ Audit log shows `action = bulk.import` entries per row.

---

## When to Contact IT

Reach out to IT if:

- ❓ You don't have the `ui_body_template.xlsx` file.
- ❓ You need the list of valid district / police station names.
- ❓ The secure file-transfer channel is down.
- ❓ Import script crashes on the server side (you've checked the obvious: CSV format, file paths).
- ❓ Cases imported but photos are not visible in UBIS (database issue or storage path issue).
- ❓ You need to re-run an import on a corrected batch.

---

## Appendix: Dates and Formats

**Correct date format:** `YYYY-MM-DD`

| Use | Don't use |
|-----|-----------|
| `2025-03-12` | `12/03/2025` |
| `2025-03-12` | `12-03-2025` |
| `2025-03-12` | `Mar 12, 2025` |
| `2025-03-12` | `12/03/25` |
| `2025-03-12` | `03-12-2025` |

**Why?** The import script expects ISO format. Excel may auto-convert dates; **always double-check** by clicking a date cell and seeing the formula bar (should show `2025-03-12`, not `43789` or `12/03/2025`).

**Pro tip:** In Excel, format the entire date column as **Text** before entering dates. Then type manually: this prevents auto-conversion.

---

## Appendix: File Size and Storage

**Estimated space per batch:**
- Average photo: 2–5 MB.
- Average case: 3–4 photos = 6–20 MB.
- Batch of 100 cases: 600–2000 MB (0.6–2 GB).

**Server considerations:**
- Unzipped batch stays on disk in `./data/uploads/` for ~1 week (per your retention policy).
- AI face embeddings are stored in the Qdrant vector DB (~100–200 bytes per embedding).
- Database entries are small (<10 KB per submission).

Check available disk space before import:
```bash
df -h ./data/uploads/
```

---

## Housekeeping: removing search-probe submissions

Anonymous face-search uploads create a short-lived submission marked
`_search_probe = true`. They should never show up in the case gallery. A
helper script removes them and their related rows (matches, feedback, audit,
files, Qdrant vectors):

```bash
# Dry-run: list probe IDs only.
podman exec ubis-backend python -m scripts.cleanup_search_probe_submissions --dry-run

# Remove probes created by the current (marker-aware) build.
podman exec ubis-backend python -m scripts.cleanup_search_probe_submissions

# One-time legacy sweep: also delete submissions with empty attributes
# (created by pre-marker upload-and-match builds). Use after upgrading.
podman exec ubis-backend python -m scripts.cleanup_search_probe_submissions --include-legacy
```

Replace `podman exec` with `docker compose -f docker-compose.onprem.yml --profile lite exec -T` if you use Docker.

---

## Scaling to 10k+ records

A short version: **split into batches of 2 500–5 000 rows** and run them one
after another (overnight if needed). Full plan, including sizing, time
budgets, failure recovery, and the upgrade path to a dedicated Qdrant server,
is in **[`BULK_IMPORT_AT_SCALE.md`](BULK_IMPORT_AT_SCALE.md)**.

Quick orientation:

| Volume | Approach | Wall-clock |
|--------|----------|------------|
| ≤ 1 000 | Single batch | ~15–25 min |
| 1 000 – 5 000 | Single batch, run during a quiet window | ~30 min – 2 h |
| 5 000 – 50 000 | 10–20 batches of 2 500–5 000, one per night | 1–3 weeks of nightly runs |
| > 50 000 | Switch to `--profile full` (Postgres) and Qdrant **server** container; then raise backend workers | Hours, not days |

---

## Version History

| Date | Update |
|------|--------|
| 2025-03-10 | Initial draft; aligned with bulk_import_ui_bodies.py v1.0 |
| 2026-05-14 | Embedding switched to InsightFace `buffalo_l/w600k_r50.onnx`; `--workers 1` requirement for embedded Qdrant documented; added scaling guide link and search-probe cleanup steps. |

**Last updated:** 2026-05-14
**Next review:** 2026-08-14 (or when workflow changes)

---

**Questions?** Contact the data-entry team lead or IT support (see `15_SUPPORT_AND_ESCALATION.md`).
