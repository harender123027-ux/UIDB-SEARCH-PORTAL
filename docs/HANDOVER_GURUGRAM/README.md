# UBIS — install on your own server (on-prem)

**What it is:** A web app for police to register unidentified bodies, upload photos, and search by face / text / voice. Runs on **one Linux PC** in your network. **No cloud account.** Match results are **leads only** — officers must verify.

**What you run:** `Podman` or `Docker` + our script. That’s it.

---

## 1. You need

- **PC:** Linux, 4+ CPU, 8+ GB RAM, 100+ GB free disk (Ubuntu 22.04 or RHEL/Rocky 9 is fine).
- **Access:** `sudo` on that PC, and the UBIS zip (or this folder) copied onto it.
- **Network:** Port **8080** open on the police LAN (or another port you set in `.env`).
- **First install only:** internet to download system packages and container images (or an approved offline mirror).

---

## 2. Install Podman + tools (once)

**Ubuntu**

```bash
sudo apt-get update
sudo apt-get install -y podman podman-compose curl openssl tar unzip
```

**RHEL / Rocky**

```bash
sudo dnf install -y podman podman-compose curl openssl tar unzip
```

Use **Docker** instead if your policy requires it — the installer detects `docker compose` too.

---

## 3. Unzip and install UBIS

```bash
cd /opt && sudo mkdir -p ubis && sudo chown "$USER":"$USER" ubis && cd ubis
unzip /path/to/UBIS_Gurugram_Handover.zip
cd UBIS_Gurugram_Handover
bash scripts/onprem/install.sh
```

Wait until it finishes (first time **5–15 minutes** while images build). You should see **install complete** and your URL (default port **8080**).

---

## 4. Open the app and log in

In a browser on the LAN: `http://<this-server-ip-or-name>:8080`

| Field | Value |
|-------|--------|
| Username | `admin` |
| Password | Run on the server: `grep INITIAL_ADMIN_PASSWORD .env` |

Change the password in the app **immediately** after login.

---

## 5. Useful commands (run inside the UBIS folder)

| Task | Command |
|------|---------|
| Health check | `bash scripts/onprem/ubis-status.sh` |
| Stop | `podman compose -f docker-compose.onprem.yml --profile lite down` |
| Start | `podman compose -f docker-compose.onprem.yml --profile lite up -d` |

Replace `podman` with `docker` if you use Docker.

**Your data** lives in the **`data/`** folder next to `docker-compose.onprem.yml`. Back it up with `bash scripts/onprem/ubis-backup.sh` on a schedule.

---

## 6. If something fails

- Read the **last lines** printed by `install.sh`.
- Run `bash scripts/onprem/ubis-status.sh` and share the output with support.
- **Permission errors on `./data`** (often RHEL): `sudo chown -R "$USER":"$USER" ./data`
- **No disk space:** free **50+ GB** before building again.
- **Mac:** only for testing; production should be **Linux**.

---

## 7. Extra manuals (optional)

Longer versions for audits, training, and sign-off:

| File | Topic |
|------|--------|
| `01_INSTALL.md` | Full prerequisites & first-boot checklist |
| `02_OPERATIONS.md` | Backups, security, day-to-day ops |
| `03_USER_GUIDES.md` | Officer / admin how-tos |
| `04_TRAINING_AND_SUPPORT.md` | Training & FAQ |
| `05_ACCEPTANCE.md` | Sign-off |

---

*Compose file: `docker-compose.onprem.yml` · Env template: `.env.onprem.example`*
