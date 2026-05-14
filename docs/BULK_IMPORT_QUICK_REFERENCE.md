# Bulk Import Quick Reference Card

**For printing and desk reference during data entry**

> **For detailed explanations and troubleshooting**, see [`BULK_IMPORT_GUIDE.md`](BULK_IMPORT_GUIDE.md).
> **For 10 000+ records, batching, and overnight runs**, see [`BULK_IMPORT_AT_SCALE.md`](BULK_IMPORT_AT_SCALE.md).

---

## Data-Entry Team Workflow (1 page)

### Before You Start
- [ ] Get `ui_body_template.xlsx` from IT
- [ ] Get master list of districts & police stations from IT
- [ ] Gather scanned/digital photos of old cases

### Per Batch (e.g., 50–100 cases)

**1. Organize Photos**
```
import-batch-001/
├── ui_body_template.csv
└── images/
    ├── DDR-101-2025/
    │   ├── face.jpg, face_left.jpg, full_body.jpg
    ├── DDR-102-2025/
    │   ├── face.jpg, full_body.jpg
```

**2. Fill CSV (one row per case)**
| Required | Optional |
|----------|----------|
| dd_no | height_cm |
| found_date (YYYY-MM-DD) | build |
| found_district | skin_tone |
| ps_name | hair_color |
| gender | beard |
| image_face_frontal_path | visible_marks |
| found_loc | clothing_description |

**3. Validate Before Sending**
- [ ] `found_date` is `YYYY-MM-DD` format
- [ ] Every image path exists in `images/` folder
- [ ] No duplicate `dd_no` values
- [ ] Dropdown fields (gender, build) have correct values
- [ ] Spot-check: 5 random photos are clear & well-lit

**4. Send to IT**
- Zip: `import-batch-001.zip`
- Via encrypted channel (not email)

**5. Spot-Check After Import**
- Open UBIS → Search for 3 imported DD numbers
- Verify photos & attributes visible

---

## IT Person Workflow (1 page)

### Receive Batch

```bash
# Extract
mkdir -p ./data/uploads/import-batch-001
unzip ~/batch.zip -d ./data/uploads/import-batch-001/

# If .xlsx, convert:
python3 -c "import pandas as pd; df = pd.read_excel('./data/uploads/import-batch-001/ui_body_template.xlsx'); df.to_csv('./data/uploads/import-batch-001/ui_body_template.csv', index=False)"
```

### Run Import

**Docker:**
```bash
docker compose -f docker-compose.onprem.yml exec -T backend \
    python -m scripts.bulk_import_ui_bodies \
    /app/uploads/import-batch-001/ui_body_template.csv \
    /app/uploads/import-batch-001
```

**Podman:**
```bash
podman compose -f docker-compose.onprem.yml --profile lite exec -T backend \
    python -m scripts.bulk_import_ui_bodies \
    /app/uploads/import-batch-001/ui_body_template.csv \
    /app/uploads/import-batch-001
```

### Expected Output
```
Imported record 1: DDR-101-2025 (ID: uuid-here)
...
Bulk import complete. Total records imported: 50
```

### Verify Success
```bash
# Check DB
sqlite3 ./data/ubis.db "SELECT COUNT(*) FROM submissions;"

# Web check: log in to UBIS, find 3 imported cases, verify photos
```

### If Errors
- Copy error output to `errors.txt`
- Send back to data-entry team
- They fix CSV, re-submit
- You re-run script

---

## Dropdown Values (Copy-Paste Sheet)

**Gender:** Male, Female, Unknown

**Build:** Slim, Medium, Heavy, Unknown

**Skin Tone:** Fair, Medium, Dark, Unknown

**Hair Color:** Black, Brown, Grey, White, Unknown

**Beard:** Yes, No, N/A

---

## Photo Quality Checklist

| Photo Type | Min Resolution | Lighting | Focus | Format | Size |
|------------|----------------|----------|-------|--------|------|
| **Face** (frontal/profile) | 600×600 px | Bright, no deep shadows | Sharp, eyes clear | .jpg/.png | <10 MB |
| **Full Body** | 400×600 px | Well-lit | Sharp | .jpg/.png | <10 MB |
| **Marks/Tattoos** | Close-up | Good contrast | Sharp, shows texture | .jpg/.png | <10 MB |

**Avoid:** Blurry, backlit, too zoomed, filters, beauty apps, screenshots of prints.

---

## CSV Column Map (Quick)

| Column | Example | Required | Notes |
|--------|---------|----------|-------|
| dd_no | DDR-101-2025 | ✓ | Case ID |
| found_date | 2025-03-12 | ✓ | ISO format |
| found_district | Gurugram | ✓ | Use dropdown |
| ps_name | Sohna | ✓ | Cascading dropdown |
| found_loc | Behind bus stand | ✓ | Free text |
| gender | Male | ✓ | Dropdown |
| age_min | 25 | ✓ | Integer |
| age_max | 35 | ✓ | Integer ≥ age_min |
| height_cm | 170 | | Integer, cm |
| build | Medium | | Dropdown |
| skin_tone | Fair | | Dropdown |
| hair_color | Black | | Dropdown |
| beard | Yes | | Dropdown |
| visible_marks | Tattoo on arm | | Text |
| clothing_description | Blue shirt, pants | | Text |
| notes | Context | | Text |
| additional_details | Family notes | | Text |
| image_face_frontal_path | images/DDR-101-2025/face.jpg | ✓ | Relative path |
| image_face_left_path | images/DDR-101-2025/face_left.jpg | | Relative path |
| image_face_right_path | | | Relative path |
| image_full_body_path | images/DDR-101-2025/full_body.jpg | | Relative path |
| image_tattoo_1_path | images/DDR-101-2025/tattoo_1.jpg | | Relative path; primary tattoo/mark |
| image_tattoo_2_path | images/DDR-101-2025/tattoo_2.jpg | | Relative path; additional mark |
| image_tattoo_3_path through image_tattoo_10_path | images/DDR-101-2025/tattoo_3.jpg, etc. | | Relative paths; up to 10 tattoo/mark items total |
| image_clothing_path | | | Relative path |
| image_belonging_path | | | Relative path |

---

## Common Errors & Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| "CSV file not found" | Wrong path or not extracted | Verify file exists: `ls ./data/uploads/.../ui_body_template.csv` |
| "Warning: Image not found" | Path mismatch (DDR_101 vs DDR-101) | Check folder names match CSV exactly |
| "invalid literal for int()" | Non-numeric in age_min / height | Change `3.5` → `3` or `4` (integer only) |
| "no attribute 'found_date'" | CSV headers missing or corrupt | Regenerate from template |
| 0 records imported | CSV header read as data row | Ensure headers in row 1; no blank rows |
| Script takes 30+ minutes | Normal for 100 rows with AI | Expected; GPU speeds it up; can run overnight |

---

## File Structure (Strict)

```
import-batch-001/
├── ui_body_template.csv          ← Exact name / csv or xlsx
└── images/                        ← MANDATORY exact name
    ├── DDR-101-2025/             ← matches dd_no
    │   ├── face.jpg
    │   └── full_body.jpg
    ├── DDR-102-2025/
    │   ├── face.jpg
```

**Rules:**
- Folder named `images` (lowercase, exact spelling)
- Each case gets subfolder named after `dd_no`
- CSV at batch root
- **Nothing else** at root

---

## Command Cheat Sheet

**Data-Entry (Excel/Sheets):**
```
Format → Cells → Text (before entering dates to prevent auto-convert)
File → Save As → CSV UTF-8 (when exporting from Excel)
```

**IT (Server):**
```bash
# Extract ZIP
unzip batch.zip -d ./data/uploads/import-batch-001/

# Convert .xlsx to .csv (if needed)
python3 -c "import pandas as pd; df = pd.read_excel('./data/uploads/import-batch-001/ui_body_template.xlsx'); df.to_csv('./data/uploads/import-batch-001/ui_body_template.csv', index=False)"

# Run import
docker compose -f docker-compose.onprem.yml exec -T backend python -m scripts.bulk_import_ui_bodies /app/uploads/import-batch-001/ui_body_template.csv /app/uploads/import-batch-001

# Verify
sqlite3 ./data/ubis.db "SELECT COUNT(*) FROM submissions;"
```

---

## Success Looks Like

- ✅ Data-entry team: Batch validated, no obvious errors, folders organized
- ✅ IT: Script runs 5–10 minutes, outputs "Imported record X: DDR-YYY" for each row
- ✅ Investigators: Log in to UBIS, search for imported DD number, case opens with photos
- ✅ Spot-check: 3 random imported cases have correct attributes & visible photos

---

## When to Call IT

- No `ui_body_template.xlsx` received
- Master list of districts/stations not provided
- File transfer channel down
- Import script crashes (not CSV errors — server-side issue)
- Photos visible in storage but not in UBIS
- Need to re-run on corrected batch

---

## Housekeeping (IT)

```bash
# List ephemeral search-probe submissions (created by face-search uploads).
podman exec ubis-backend python -m scripts.cleanup_search_probe_submissions --dry-run

# Delete them and their files + Qdrant vectors.
podman exec ubis-backend python -m scripts.cleanup_search_probe_submissions

# One-time legacy sweep after upgrading to the marker-aware build.
podman exec ubis-backend python -m scripts.cleanup_search_probe_submissions --include-legacy
```

---

## Scale at a glance

| Volume | Approach |
|--------|----------|
| ≤ 1 000 | Single batch, ~15–25 min on a 4 vCPU host |
| 1 000 – 5 000 | Single batch in a quiet window, ~30 min – 2 h |
| 5 000 – 50 000 | 10–20 batches of 2 500–5 000, one per night |
| > 50 000 | Switch to `--profile full` + dedicated Qdrant container, then raise backend workers |

Reserve ~600 GB of disk for a full 50 000-case run with ~3 photos / case at ~3 MB each.

---

**Full guide:** `docs/BULK_IMPORT_GUIDE.md`
**At-scale guide:** `docs/BULK_IMPORT_AT_SCALE.md`

**Last updated:** 2026-05-14
