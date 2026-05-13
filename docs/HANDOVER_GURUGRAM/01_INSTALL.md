# Install & first boot

---

## Chapter 01 — 01 — Hardware and software prerequisites

Confirm every item below **before** running the installer. Most install failures we have seen are caused by skipping this check.

---

## 1. Server hardware (Tier A — pilot)

This is the recommended starting tier for the Gurugram pilot (≤ 5,000 active cases). It is taken from Section 11.2 of `docs/UAT_AND_POLICE_SIGNOFF.md`.

| Resource | Minimum | Recommended | Why |
|---|---|---|---|
| CPU | 4 cores | 8 cores | Face embedding is CPU-heavy on upload and match. |
| RAM | 8 GB | 16 GB | PyTorch + InsightFace models stay in memory. |
| Disk | 100 GB SSD | 250 GB SSD | Case images plus Qdrant vector index. Plan disk against estimated case volume × 5–10 photos × ~1.5 MB. |
| Network | 1 Gbps internal LAN | 1 Gbps | Officers upload large images; latency matters for search. |
| GPU | Not required | Not required at this tier | CPU is sufficient for ≤ 5k gallery and tens of concurrent users. |

For larger deployments, see Section 11 of `docs/UAT_AND_POLICE_SIGNOFF.md` (Tiers B and C) and contact the vendor before scaling.

---

## 2. Operating system

Tested and supported:

- **Ubuntu 22.04 LTS** (preferred — what the vendor tested with).
- **RHEL 9 / Rocky Linux 9** (works; replace `apt` with `dnf` in the prerequisite commands below).

Other Linux distributions will likely work, but are not certified by the vendor.

---

## 3. Software prerequisites

Run these as `root` or with `sudo`. They install Docker (which works just as well as Podman for this package).

### 3.1 Ubuntu 22.04

```bash
sudo apt-get update
sudo apt-get install -y \
    ca-certificates curl gnupg lsb-release \
    unzip tar openssl \
    ufw chrony

# Docker engine + compose plugin (official Docker apt repository)
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
   https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
   sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo systemctl enable --now docker chrony
```

### 3.2 RHEL 9 / Rocky Linux 9

```bash
sudo dnf install -y dnf-plugins-core unzip tar openssl chrony firewalld
sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable --now docker chronyd firewalld
```

### 3.3 Podman alternative (if your security policy forbids Docker)

```bash
# Ubuntu
sudo apt-get install -y podman podman-compose

# RHEL 9 / Rocky 9
sudo dnf install -y podman podman-compose
```

The installer detects whichever of `docker compose`, `podman compose`, or `podman-compose` is available and uses it automatically.

---

## 4. Verify your prerequisites

Run this verification block. Every line should succeed:

```bash
docker --version           || podman --version
docker compose version     || podman compose version || podman-compose --version
openssl version
unzip -v   | head -1
tar --version | head -1
curl --version | head -1
free -h
nproc
df -h /
```

If any line fails, install the missing tool before continuing.

---

## 5. Network and firewall

UBIS only needs **one inbound TCP port** to be reachable from police user workstations: by default **8080** (changeable via `UBIS_HTTP_PORT` in `.env`). When you put TLS in front of it, you will instead expose 443 and proxy to 8080 — see `06_SECURITY_HARDENING.md`.

For Ubuntu UFW:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 8080/tcp comment 'UBIS web UI (LAN only — restrict to your subnet)'
sudo ufw enable
sudo ufw status verbose
```

For RHEL/Rocky firewalld:

```bash
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --reload
```

**Best practice:** restrict 8080 to the police LAN subnet, not `0.0.0.0/0`. Example UFW restriction:

```bash
sudo ufw delete allow 8080/tcp
sudo ufw allow from 10.0.0.0/8 to any port 8080 proto tcp
```

---

## 6. Time synchronisation (NTP)

JWT tokens, audit logs, and backup timestamps depend on accurate clock time.

```bash
# Ubuntu / Debian
timedatectl status                # check
sudo timedatectl set-timezone Asia/Kolkata
sudo systemctl enable --now chrony

# RHEL / Rocky
sudo systemctl enable --now chronyd
sudo timedatectl set-timezone Asia/Kolkata
```

---

## 7. TLS certificate (optional for first install, mandatory before production use)

Three acceptable options, in order of preference:

1. **Department / NIC internal CA** — request a server certificate for your hostname (e.g. `ubis.ggn.haryanapolice.gov.in`). Place the cert and key under `/etc/ssl/ubis/`.
2. **Let's Encrypt** — only if the server is reachable from the public internet on port 80 (most police networks deny this).
3. **Self-signed** — for very early pilot use only; users will see a browser warning. See `06_SECURITY_HARDENING.md` for the exact `openssl` command.

You **do not** need a certificate to complete the install in this document. You **do** need one before the system is used by real officers.

---

## 8. Pre-install checklist

Tick every box before continuing to `02_INSTALL_ONPREM_STEP_BY_STEP.md`.

- [ ] Server meets Tier A hardware spec (Section 1).
- [ ] OS is Ubuntu 22.04 LTS or RHEL/Rocky 9 (Section 2).
- [ ] Docker (or Podman) and compose are installed and verified (Section 4).
- [ ] Port 8080 is reachable from one test workstation on the police LAN (Section 5).
- [ ] Server time zone is Asia/Kolkata and `timedatectl` reports synchronised (Section 6).
- [ ] You have at least 50 GB of free disk under `/var` or wherever you will place `./data` (Section 1).
- [ ] You have a plan for TLS — even if you defer it to after first install (Section 7).

---

## Chapter 07 — 07 — Secrets generation methodology

The vendor ships **no live secrets** in this package. Every cryptographic value used by your installation is generated on your server, by you, and never leaves it.

---

## 1. Secrets used by UBIS

| Secret | Purpose | Where it lives | Rotation cadence |
|---|---|---|---|
| `JWT_SECRET` | Signs login tokens. Anyone with this value can mint a valid session. | `.env` on the server (mode 600) | 180 days |
| `POSTGRES_PASSWORD` | Database account (only used with `--profile full`) | `.env` on the server (mode 600) | 180 days |
| Admin user password | First admin login | UBIS database (bcrypt hash) | 90 days |
| Each user's password | Login | UBIS database (bcrypt hash) | 180 days |
| TLS private key | Encrypts officer ↔ server traffic | `/etc/ssl/ubis/server.key` (mode 640) | At cert renewal |
| Backup encryption key (optional) | Encrypts off-site backup tarballs | Department GPG keyring | At least annually |

---

## 2. Generate them

The installer (`install.sh`) generates `JWT_SECRET` automatically the first time. Whenever you need a fresh batch by hand:

```bash
bash scripts/onprem/generate_secrets.sh
```

Output looks like (values are illustrative, never reused):

```
# UBIS — generated secrets (2026-04-25T10:14:27Z)
# Copy the lines below into your .env file, replacing the placeholders.
# These values are NOT stored anywhere by this script.

JWT_SECRET=4f8b...redacted...c19e
POSTGRES_PASSWORD=rN9k...redacted...QmPx
INITIAL_ADMIN_PASSWORD=zC3m...redacted...
```

The script writes nothing to disk. It does not log to history (assuming you have `HISTCONTROL=ignorespace` set, you can also prefix the command with a leading space to keep it out of bash history).

---

## 3. Edit `.env` safely

```bash
cd /opt/ubis/UBIS_Gurugram_Handover
sudo cp .env .env.bak.$(date -u +%Y%m%dT%H%M%SZ)
sudo chmod 600 .env.bak.*
sudo nano .env        # paste the new values, save
sudo chmod 600 .env
docker compose -f docker-compose.onprem.yml restart backend
clear                 # so the values are not on screen
```

After rotating `JWT_SECRET`, every logged-in user is signed out. They log in again with their existing passwords; data is unaffected.

---

## 4. What to do with `.env`

- **Never** email it.
- **Never** put it in chat or a ticket.
- **Never** commit it to any source control.
- **Do** print it once, seal in an envelope, and store in the IT vault (per your department's secrets-handling policy).
- **Do** keep one off-server encrypted copy for disaster recovery, separate from the backup tarballs.

---

## 5. If you suspect a secret is compromised

1. Generate fresh values immediately (`generate_secrets.sh`).
2. Edit `.env`, restart the backend.
3. For a leaked admin password: log in as admin, reset all admin and supervisor passwords, audit the `audit_log` table for unfamiliar activity since the suspected leak time.
4. For a leaked TLS private key: revoke the certificate with your CA, issue a new one.
5. Take a backup before and after, label both.
6. Raise a security incident per your cyber cell SOP.

---

## 6. Why we ship no live secrets

If the vendor gave you a `JWT_SECRET` already filled in:

- Anyone in the vendor's team who saw the file could forge admin sessions.
- The same secret would be used by every department that received the package.
- A single leaked email would compromise every install.

By generating secrets on your server, the only people who ever know them are the IT staff that ran `install.sh`. That is the **least-privilege** position.

---

## Chapter 02 — 02 — Install UBIS on-prem, step by step

This is the only document you need open during the install. Read each step's **expected output** and **if you see X** notes carefully.

> Before you start: confirm every box in `01_HARDWARE_SOFTWARE_PREREQS.md` Section 8 is ticked.

---

## Step 1 — Copy the package to the server

From the laptop where you received the handover archive:

```bash
scp UBIS_Gurugram_Handover.zip <you>@<server>:/tmp/
```

On the server:

```bash
sudo mkdir -p /opt/ubis
sudo chown "$USER":"$USER" /opt/ubis
cd /opt/ubis
unzip /tmp/UBIS_Gurugram_Handover.zip
cd UBIS_Gurugram_Handover
ls
```

**Expected output:**

```
INSTALL.txt    backend/        docker-compose.onprem.yml   ...
docs/          frontend/       nginx/                       scripts/    ...
```

**If you see `unzip: command not found`:** install it with `sudo apt-get install -y unzip` and retry.

---

## Step 2 — Run the installer

This single command does everything: prerequisites check, secret generation, image build, container start, admin user seed, district master seed.

```bash
bash scripts/onprem/install.sh
```

**Expected output (abridged):**

```
UBIS on-prem installer
Profile  : lite
HTTP port: 8080

Step 1/7  Checking prerequisites
  • Using container runtime: docker compose
  • openssl, curl, tar — present.

Step 2/7  Preparing data directories
  • ready: ./data/db
  ...

Step 3/7  Configuring .env
  • wrote .env with freshly generated JWT_SECRET and INITIAL_ADMIN_PASSWORD (mode 600).
  • Required secrets present in .env.

Step 4/7  Building container images (this can take 5–10 minutes the first time)
[+] Building 312.1s (24/24) FINISHED
...
Step 5/7  Starting containers
[+] Running 2/2
 ✔ Container ubis-backend   Started
 ✔ Container ubis-frontend  Started

Step 6/7  Waiting for the backend to become healthy
  • Backend is healthy.

Step 7/7  Seeding admin user and Haryana district / police-station master data
Created admin user: username=admin (password from INITIAL_ADMIN_PASSWORD env)
Store this password securely — it will not be printed again.
Seeded 15 districts and 76 police stations.

✓ UBIS on-prem install complete.

  Open in a browser on the police LAN:
        http://ubis-server.gurugram.local:8080

  Default admin login (CHANGE IT ON FIRST LOGIN):
        username : admin
        password : (see INITIAL_ADMIN_PASSWORD in .env)
                   $ grep INITIAL_ADMIN_PASSWORD .env
```

**If Step 4 fails with a network error** (image pull timeout): check that the server can reach `https://registry-1.docker.io` and `https://pypi.org`. If not, your security team must whitelist them or you must follow the offline-install steps in `14_TROUBLESHOOTING_AND_FAQ.md`.

**If Step 6 says "Backend did not become healthy within 5 minutes":** the install is incomplete. Run `docker compose -f docker-compose.onprem.yml logs backend | tail -50` and look for Python tracebacks. Common cause: the InsightFace model failed to download because the server has no internet — see `14_TROUBLESHOOTING_AND_FAQ.md` Section "Offline / air-gapped install".

---

## Step 3 — Open the application

From a workstation on the police LAN:

```
http://<your-server-hostname>:8080
```

You should see the UBIS login screen.

Log in with:

| Field | Value |
|---|---|
| Username | `admin` |
| Password | The 20-character random string from `.env`. Read it with: `grep INITIAL_ADMIN_PASSWORD .env` (or `awk -F= '/INITIAL_ADMIN_PASSWORD/ {print $2}' .env`). |

Click the user icon → **Change password**. **Do this immediately.** Pick a long password and store it in your password manager. The installer-generated password in `.env` is only used the very first time the database is seeded; rotating it from the UI does not invalidate the value in `.env`, so once you have changed it, you can scrub the line from `.env` if you wish (it will not be re-read).

---

## Step 4 — First-boot smoke check

Run the health snapshot script:

```bash
bash scripts/onprem/ubis-status.sh
```

**Expected output:** `[2] Backend health` should print `{"status":"ok"}` and `[1] Containers` should show both `ubis-backend` and `ubis-frontend` as healthy.

Then complete `03_FIRST_BOOT_CHECKLIST.md` (login, create one test case, run one search) and **sign at the bottom of that page**.

---

## Step 5 — Save your `.env`

The installer wrote a `.env` file with a randomly generated `JWT_SECRET` and a randomly generated `INITIAL_ADMIN_PASSWORD`. **Print it, seal it, store it offline** — see `07_SECRETS_GENERATION_METHODOLOGY.md`. If you lose `JWT_SECRET`, every existing user will need to log in again after the secret is regenerated, but case data is not lost.

```bash
cat .env
# Take a printout / store in the department's IT vault, then `chmod 600 .env`.
```

---

## Step 6 — Schedule a backup

Add a cron job that runs the backup nightly at 02:00:

```bash
( crontab -l 2>/dev/null; echo "0 2 * * * cd /opt/ubis/UBIS_Gurugram_Handover && bash scripts/onprem/ubis-backup.sh >> data/logs/backup.log 2>&1" ) | crontab -
crontab -l
```

See `05_BACKUP_AND_RESTORE.md` for verification and off-server copy procedures.

---

## Step 7 — Plan TLS and firewall (before letting officers use the system)

You have **not** yet:

- put TLS in front of UBIS,
- restricted port 8080 to the police LAN subnet,
- changed the installer-generated admin password from the UI (do this NOW if you have not).

All three are mandatory before officer use. Follow `06_SECURITY_HARDENING.md` end-to-end.

---

## Re-running the installer

`install.sh` is idempotent. Re-running it is safe:

- Existing `.env` is preserved (your `JWT_SECRET` is not regenerated).
- Container images are rebuilt only if their inputs changed.
- Seed scripts detect existing rows and exit cleanly.

Re-run the installer after any package update the vendor sends you.

---

## Chapter 03 — 03 — First-boot checklist

Run this checklist immediately after `02_INSTALL_ONPREM_STEP_BY_STEP.md` finishes. **Sign at the bottom before letting any officer use the system.**

The whole list should take 15 minutes.

---

## A. Containers and ports

| # | Step | Command / action | Expected | Result (Pass / Fail) |
|---|------|------------------|----------|----------------------|
| A1 | Containers running | `bash scripts/onprem/ubis-status.sh` | Both `ubis-backend` and `ubis-frontend` show `Up` and `(healthy)` | |
| A2 | API health endpoint | `curl -fsS http://localhost:8080/api/health` | `{"status":"ok"}` | |
| A3 | Web UI loads | Open `http://<server>:8080` from a workstation on the police LAN | Login screen appears | |
| A4 | API reachable through nginx | `curl -fsS http://localhost:8080/api/geo/districts \| head -c 200` | JSON list with district records | |

If any A-row fails, do not proceed. See `14_TROUBLESHOOTING_AND_FAQ.md` Section "Service won't start".

---

## B. Authentication and admin access

| # | Step | Action | Expected | Result |
|---|------|--------|----------|--------|
| B1 | Admin login | Login as `admin`. Password = the value of `INITIAL_ADMIN_PASSWORD` in `.env` (read with `grep INITIAL_ADMIN_PASSWORD .env`). | Dashboard loads | |
| B2 | Change admin password | User menu → Change password → set a long password | Logout, log back in with new password | |
| B3 | Audit log records the change | Admin panel → Audit log | Latest entry shows `auth.password_change` for `admin` | |

---

## C. End-to-end case workflow (one round trip)

This proves the AI pipeline, file storage, and database are all wired correctly.

| # | Step | Action | Expected | Result |
|---|------|--------|----------|--------|
| C1 | Open New Case | Click "New Case" / "Register UI Body" | Form appears with photo capture slots | |
| C2 | Add a frontal face photo | Use any clear face image from `sample_test_images/` (or your own) | Image preview appears, no upload error | |
| C3 | Fill required attributes | Found date, gender, district = Gurugram, police station = any | Save button enabled | |
| C4 | Submit | Click Save | Success toast; you land on the case detail page; case ID is shown | |
| C5 | Run match on the case | "Find matches" / "Match" button | Match shortlist returns within ~30 seconds | |
| C6 | Audit entry exists | Admin → Audit log | Two new entries: `submission.create` and `match.run` | |

---

## D. Data and storage

| # | Step | Command | Expected | Result |
|---|------|---------|----------|--------|
| D1 | Upload landed on disk | `ls -la data/uploads` | At least one file from C2 | |
| D2 | DB row written | `bash scripts/onprem/ubis-status.sh \| sed -n '/audit-log/,$p' \| head` | Audit rows for the actions above | |
| D3 | Qdrant index has vectors | `du -sh data/qdrant` | More than `0K` after C2 | |

---

## E. Backup smoke

| # | Step | Command | Expected | Result |
|---|------|---------|----------|--------|
| E1 | Create a backup | `bash scripts/onprem/ubis-backup.sh` | New tarball under `./backups/`, last line "Backup complete" | |
| E2 | Tarball size sane | `ls -lh backups/` | At least a few hundred KB; not zero | |

(A full restore drill is in `05_BACKUP_AND_RESTORE.md`. Do not perform a restore on the production server during first-boot — do it on a test VM.)

---

## F. Sign-off

> Once every row above is "Pass", record this page on the project register and store the signed copy in the IT vault.

| Field | Value |
|---|---|
| Server hostname |  |
| UBIS package version | UBIS Gurugram Handover (Vol. 2) |
| Install date and time |  |
| Installer (name, designation) |  |
| Witness (name, designation) |  |
| All 19 checklist rows passed (Y/N) |  |
| Notes / waivers (if any) |  |
| Signature (installer) |  |
| Signature (witness) |  |
| Date |  |

After this page is signed, follow `06_SECURITY_HARDENING.md` before any officer logs in for real work.
