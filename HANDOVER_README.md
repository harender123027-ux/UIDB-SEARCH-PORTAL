# UBIS Gurugram - Handover Package

**Date:** May 2026  
**Version:** 1.0 - Production Ready

---

## 📦 What's Included

This handover package contains the complete UBIS (Unidentified Bodies Information System) deployment for Gurugram Police.

### Folder Structure

```
UBIS_Gurugram_Handover/
├── README.md                              ← Start here
├── INSTALL.txt                            ← Quick installation steps
├── backend/                               ← FastAPI backend + models
│   ├── app/                               ← Application code
│   ├── models/                            ← AI models (InsightFace, AdaFace)
│   ├── scripts/                           ← Utilities (bulk import, seeding)
│   ├── tests/                             ← Unit tests
│   ├── requirements.txt                   ← Python dependencies
│   ├── Dockerfile.onprem                  ← On-premises deployment
│   └── seed_admin.py                      ← Initialize admin user
├── docs/                                  ← Complete documentation
│   ├── API_REFERENCE.md                   ← REST API endpoints
│   ├── SYSTEM_DESIGN.md                   ← Architecture overview
│   ├── BULK_IMPORT_GUIDE.md               ← Import older records (→ START HERE)
│   ├── BULK_IMPORT_QUICK_REFERENCE.md     ← Quick reference card
│   ├── DATA_INTERACTIONS.md               ← Data flow & storage
│   ├── TESTING_GUIDE.md                   ← QA procedures
│   ├── UAT_AND_POLICE_SIGNOFF.md          ← Sign-off process
│   └── HANDOVER_GURUGRAM/                 ← Full deployment guide
│       ├── 01_INSTALL.md                  ← Prerequisites & installation
│       ├── 02_OPERATIONS.md               ← Day-to-day operations
│       ├── 03_USER_GUIDES.md              ← Officer workflows
│       ├── 04_TRAINING_AND_SUPPORT.md     ← Training & FAQ
│       └── 05_ACCEPTANCE.md               ← Acceptance testing
├── ui_body_template.xlsx                  ← Excel template for bulk import
├── sample_import_images/                  ← Example images for testing
├── tests/                                 ← Frontend tests
├── explainer/                             ← System overview HTML
└── ubis-pwa.jsx                           ← System documentation (schema, etc.)
```

---

## 🚀 Quick Start

### For IT Installation
1. Read: **`docs/HANDOVER_GURUGRAM/01_INSTALL.md`** (5 minutes)
2. Follow the installation steps for your environment (on-prem or cloud)
3. Run `seed_admin.py` to create initial admin user
4. Verify: **`docs/HANDOVER_GURUGRAM/01_INSTALL.md` Section 3 (First Boot Checklist)**

### For Data Import
1. Read: **`docs/BULK_IMPORT_GUIDE.md`** (10 minutes)
2. Data entry team prepares Excel + images using template
3. IT runs bulk import script (one command)
4. System automatically processes all 1000+ cases in ~2-5 minutes

### For Operations
1. Read: **`docs/HANDOVER_GURUGRAM/02_OPERATIONS.md`** (day-to-day tasks)
2. Read: **`docs/HANDOVER_GURUGRAM/03_USER_GUIDES.md`** (officer workflows)

---

## 📋 Key Features

✅ **Face Recognition** — InsightFace (buffalo_l) + AdaFace embeddings  
✅ **Vector Search** — Qdrant for fast similarity matching  
✅ **Bulk Import** — Import 1000s of old cases in minutes  
✅ **Multi-Angle Support** — Up to 10 tattoo/mark images per case  
✅ **Audit Trail** — Complete action logging for compliance  
✅ **Role-Based Access** — Admin & Investigator roles  
✅ **On-Premises** — Runs on local Docker/Podman (no cloud required)  

---

## 🔧 System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 4 cores | 8+ cores |
| RAM | 8 GB | 16+ GB |
| Storage | 50 GB | 100+ GB |
| Disk I/O | SATA SSD | NVMe SSD |
| Network | 10 Mbps | 100 Mbps |

---

## 📚 Documentation Map

| Audience | Start Here | Then Read |
|----------|-----------|-----------|
| **IT/DevOps** | `01_INSTALL.md` | `02_OPERATIONS.md`, `14_TROUBLESHOOTING.md` |
| **Police Officers** | `03_USER_GUIDES.md` | `04_TRAINING_AND_SUPPORT.md` |
| **Data Entry** | `BULK_IMPORT_GUIDE.md` | `BULK_IMPORT_QUICK_REFERENCE.md` |
| **Developers** | `SYSTEM_DESIGN.md` | `API_REFERENCE.md`, `DATA_INTERACTIONS.md` |
| **Testers** | `TESTING_GUIDE.md` | `UAT_AND_POLICE_SIGNOFF.md` |

---

## 🔑 Important Files

- **`.env.example`** — Copy to `.env` and fill in your secrets (database URL, JWT key, etc.)
- **`backend/models/`** — AI weights (~600 MB). Auto-downloaded on first run if missing.
- **`ui_body_template.xlsx`** — Data entry template. Use for bulk import.
- **`docker-compose.onprem.yml`** — Complete deployment stack definition

---

## ⚠️ Before Deployment

1. **Read the security section** in `02_OPERATIONS.md`
2. **Change default passwords** (`INITIAL_ADMIN_PASSWORD` in `.env`)
3. **Verify TLS certificates** are installed (HTTPS only in production)
4. **Test backup/restore** procedure before going live
5. **Run UAT** per `UAT_AND_POLICE_SIGNOFF.md` before sign-off

---

## 📞 Support

For issues:
1. Check **`04_TRAINING_AND_SUPPORT.md` — FAQ section**
2. Check logs: `docker compose logs backend | tail -100`
3. Review **`docs/SYSTEM_DESIGN.md`** for architecture context

---

## ✅ Verification Checklist

Before considering deployment complete:

- [ ] Installation completed per `01_INSTALL.md`
- [ ] Admin user created and password changed
- [ ] Bulk import tested with sample data (25 rows)
- [ ] All 3 random imported cases visible in system
- [ ] Match functionality works (try face search)
- [ ] Backup tested and working
- [ ] Users trained per `04_TRAINING_AND_SUPPORT.md`
- [ ] Sign-off documented in `05_ACCEPTANCE.md`

---

## 📦 Package Contents Summary

- **Code:** 440 KB (frontend + backend)
- **Models:** 600 MB (InsightFace + AdaFace)
- **Documentation:** 1.5 MB (comprehensive guides)
- **Sample Data:** 400 KB (test images)
- **Total:** ~603 MB

**Note:** Python dependencies (`.venv`) and Node packages (`node_modules`) are NOT included — they'll be installed fresh on first deployment (adds ~300 MB during setup).

---

## 🎯 Next Steps

1. **Extract this zip** to your deployment directory
2. **Read `docs/HANDOVER_GURUGRAM/01_INSTALL.md`**
3. **Follow the installation steps**
4. **Run the first-boot checklist**
5. **Begin data import** using `BULK_IMPORT_GUIDE.md`

Good luck! 🚀
