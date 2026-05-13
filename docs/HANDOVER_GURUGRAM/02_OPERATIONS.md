# Operations, backup & security

---

## Chapter 04 — 04 — Operations runbook

Day-to-day commands for the IT team running UBIS. Keep this page open in a tab. Every command assumes you are inside the unzipped package directory (e.g. `/opt/ubis/UBIS_Gurugram_Handover`).

---

## 1. Start, stop, restart

| Action | Command |
|---|---|
| Start everything | `docker compose -f docker-compose.onprem.yml --profile lite up -d` |
| Stop everything (keep data) | `docker compose -f docker-compose.onprem.yml down` |
| Restart just the backend | `docker compose -f docker-compose.onprem.yml restart backend` |
| Restart just the frontend | `docker compose -f docker-compose.onprem.yml restart frontend` |
| Status snapshot for a ticket | `bash scripts/onprem/ubis-status.sh > /tmp/ubis-status-$(date +%F).txt` |

If you are using Podman: replace `docker compose` with `podman compose` (or `podman-compose`). The installer detects whichever is present.

---

## 2. Logs

| Need | Command |
|---|---|
| Tail backend logs | `docker compose -f docker-compose.onprem.yml logs -f --tail=200 backend` |
| Tail nginx / frontend logs | `docker compose -f docker-compose.onprem.yml logs -f --tail=200 frontend` |
| Save the last hour of backend logs to a file | `docker compose -f docker-compose.onprem.yml logs --since 1h backend > /tmp/backend.log` |
| Last 20 audit-log entries (DB) | `bash scripts/onprem/ubis-status.sh` |

Look for these patterns:

| Pattern | Meaning |
|---|---|
| `--- STARTING UBIS BACKEND ---` | Backend booted. |
| `Database initialization successful.` | DB is ready. |
| `Using SQLite database` (or `Using PostgreSQL database`) | Storage profile in use. |
| `INFO ... 200 OK` | Normal request. |
| `ERROR` or Python traceback | Investigate; capture the trace into your ticket. |

---

## 3. Add or remove a user

There is no command-line user management — use the admin UI:

1. Log in as the admin.
2. Open **Admin → Users**.
3. Click **Create user**, set username, role (`admin`, `investigator`), and a temporary password.
4. Send the temporary password to the new user via your secure channel; ask them to change it on first login.
5. To disable a user, toggle them inactive (audit log records the change).

If you ever lose all admin accounts, see `14_TROUBLESHOOTING_AND_FAQ.md` "Forgot admin password / lost all admins".

---

## 4. Reset another user's password

Admin UI → **Users → (pick user) → Reset password**. You set a temporary password; the user is forced to change it next login. The action is recorded in the audit log under `admin.user.password_reset`.

---

## 5. Daily / weekly / monthly checklist

### Daily (5 minutes)

- [ ] `bash scripts/onprem/ubis-status.sh` — both containers healthy.
- [ ] `df -h` — root and `data/` partitions have ≥ 20 % free.
- [ ] Confirm last night's `ubis-backup.sh` tarball exists in `./backups/`.

### Weekly (15 minutes)

- [ ] Skim `data/logs/backup.log` and the last 200 lines of backend logs for repeated `ERROR` entries.
- [ ] Copy the latest backup off the server to your secondary storage.
- [ ] Review the audit log for any suspicious admin actions.

### Monthly (45 minutes)

- [ ] Apply OS security updates: `sudo apt-get update && sudo apt-get upgrade -y && sudo reboot` (after stopping containers).
- [ ] Pull the latest container images if the vendor has shipped an update: `docker compose -f docker-compose.onprem.yml --profile lite build --pull && docker compose ... up -d`.
- [ ] Run a backup-restore drill on a test VM (`05_BACKUP_AND_RESTORE.md` Section 4).
- [ ] Rotate the admin password and any service passwords created in `06_SECURITY_HARDENING.md`.

### Quarterly

- [ ] Rotate `JWT_SECRET` (forces all users to log in again).
- [ ] Update TLS certificate if it is within 30 days of expiry.
- [ ] Review user list; disable accounts of officers transferred out of Gurugram unit.

---

## 6. Apply a vendor update

When the vendor sends a new `UBIS_Gurugram_Handover.zip`:

```bash
cd /opt/ubis
# 1. Take a backup first.
( cd UBIS_Gurugram_Handover && bash scripts/onprem/ubis-backup.sh )

# 2. Rename the current copy as a rollback safety net.
mv UBIS_Gurugram_Handover UBIS_Gurugram_Handover.previous

# 3. Unpack the new archive.
unzip /tmp/UBIS_Gurugram_Handover.zip
cd UBIS_Gurugram_Handover

# 4. Re-use your existing .env and data directory.
cp ../UBIS_Gurugram_Handover.previous/.env .
ln -s ../UBIS_Gurugram_Handover.previous/data ./data

# 5. Run installer (idempotent — rebuilds images, restarts containers).
bash scripts/onprem/install.sh

# 6. Verify with the first-boot checklist (03_FIRST_BOOT_CHECKLIST.md A and C only).
bash scripts/onprem/ubis-status.sh
```

If anything goes wrong:

```bash
cd /opt/ubis
docker compose -f UBIS_Gurugram_Handover/docker-compose.onprem.yml down
mv UBIS_Gurugram_Handover UBIS_Gurugram_Handover.failed
mv UBIS_Gurugram_Handover.previous UBIS_Gurugram_Handover
( cd UBIS_Gurugram_Handover && docker compose -f docker-compose.onprem.yml --profile lite up -d )
```

---

## 7. Disk space pressure

When `data/` exceeds 70 % of the partition:

1. Check the largest sub-directory: `du -sh data/*`.
2. `data/uploads/` is usually the largest (case images). Do **not** delete files manually; archive old cases via the admin UI when that feature is enabled. As a temporary measure, ensure backups are succeeding so you can move older case images to cold storage with vendor guidance.
3. `data/qdrant/` grows linearly with embeddings. If this exceeds the planning estimate, contact the vendor — you may have moved beyond Tier A and need Tier B sizing (`docs/UAT_AND_POLICE_SIGNOFF.md` Section 11).
4. `data/logs/` can be safely truncated: `truncate -s 0 data/logs/*.log`.

---

## 8. Bringing UBIS up after a server reboot

Containers come up automatically because compose uses `restart: unless-stopped`. After a reboot, wait 2 minutes and check:

```bash
bash scripts/onprem/ubis-status.sh
```

If the containers are not running:

```bash
cd /opt/ubis/UBIS_Gurugram_Handover
docker compose -f docker-compose.onprem.yml --profile lite up -d
```

---

## Chapter 05 — 05 — Backup and restore

UBIS does not back itself up. Run `ubis-backup.sh` nightly via cron and copy the tarball off the server.

---

## 1. What gets backed up

`scripts/onprem/ubis-backup.sh` produces **one tarball** under `./backups/` containing:

| Inside the tarball | Source | Why |
|---|---|---|
| `ubis.db` | `./data/db/ubis.db` (lite profile) | Users, cases, audit log, criminals. |
| `postgres.sql` | `pg_dump` of the `postgres` container (full profile) | Same as above for Postgres deployments. |
| `data/uploads/` | `./data/uploads/` | Case photos. |
| `data/reference_photos/` | `./data/reference_photos/` | Missing-person reference gallery. |
| `data/qdrant/` | `./data/qdrant/` | Vector index — without this, search has to be re-built. |
| `data/models/` | `./data/models/` | InsightFace + AdaFace weights (large but downloadable). |
| `dot.env` | `./.env` | So a restore on a new server keeps the same `JWT_SECRET`. |
| `MANIFEST.txt` | generated | Inventory of the backup. |

---

## 2. Run a backup manually

```bash
cd /opt/ubis/UBIS_Gurugram_Handover
bash scripts/onprem/ubis-backup.sh
ls -lh backups/
```

Optional encryption (recommended for off-site storage):

```bash
gpg --import /etc/ubis/department-public-key.asc
UBIS_BACKUP_GPG_RECIPIENT=backup@ubis.haryanapolice.gov.in bash scripts/onprem/ubis-backup.sh
ls -lh backups/  # produces *.tar.gz.gpg
```

---

## 3. Schedule a nightly backup

```bash
# Backup nightly at 02:00 IST and prune backups older than 30 days at 02:30.
( crontab -l 2>/dev/null;
  echo "0 2 * * * cd /opt/ubis/UBIS_Gurugram_Handover && bash scripts/onprem/ubis-backup.sh >> data/logs/backup.log 2>&1";
  echo "30 2 * * * find /opt/ubis/UBIS_Gurugram_Handover/backups -type f -mtime +30 -delete"
) | crontab -
crontab -l
```

Copy the tarball off the server (the backup is useless if the server is lost). Examples:

```bash
# rsync to a department NAS
rsync -av /opt/ubis/UBIS_Gurugram_Handover/backups/ backup-user@nas.haryanapolice.local:/srv/ubis-backups/

# or scp to a secondary server
scp /opt/ubis/UBIS_Gurugram_Handover/backups/ubis-backup-*.tar.gz \
    backup-user@secondary.haryanapolice.local:/srv/ubis-backups/
```

Schedule the off-site copy in cron immediately after the backup job.

---

## 4. Restore drill (mandatory before sign-off, then quarterly)

**Never** drill restore on the production server. Use a separate VM that meets the same hardware spec.

On the drill VM:

```bash
# 1. Install prerequisites and unpack the package (same as a fresh install).
unzip UBIS_Gurugram_Handover.zip && cd UBIS_Gurugram_Handover

# 2. Copy the backup tarball over.
scp backup-user@nas.haryanapolice.local:/srv/ubis-backups/ubis-backup-LATEST.tar.gz ./backups/

# 3. Restore.
bash scripts/onprem/ubis-restore.sh ./backups/ubis-backup-LATEST.tar.gz
# Type RESTORE when prompted.

# 4. Verify.
bash scripts/onprem/ubis-status.sh
# Open http://<drill-vm>:8080 — the cases you saw in production should be present.
```

Record the drill date and result in your operations log. If any step fails, raise a ticket with the vendor before relying on the backup chain.

---

## 5. Restore on production (disaster recovery)

Only do this when production is genuinely lost or corrupted.

```bash
cd /opt/ubis/UBIS_Gurugram_Handover
bash scripts/onprem/ubis-restore.sh ./backups/ubis-backup-<latest>.tar.gz
# Type RESTORE when prompted.
bash scripts/onprem/ubis-status.sh
```

The script:

1. Stops the containers.
2. Renames the existing `./data` directory to `./data.before-restore-<timestamp>` (so nothing is destroyed silently).
3. Extracts the tarball into `./data/`.
4. If `dot.env` was in the tarball **and there is no current `.env`**, restores it; otherwise keeps your current `.env` (so you don't accidentally overwrite a rotated secret).
5. Brings the stack back up.
6. If a Postgres dump is in the tarball and the `full` profile is active, imports it after Postgres is healthy.

After a successful production restore, log in and run the `03_FIRST_BOOT_CHECKLIST.md` Section C end-to-end check to confirm the AI pipeline still works.

---

## 6. Backup retention policy (recommendation)

| Retention | Where |
|---|---|
| Last 7 daily backups | On the server (`./backups/`). Cron job above prunes after 30 days. |
| Last 4 weekly backups | NAS / secondary server. |
| Last 12 monthly backups | Off-site / cold storage (encrypted). |
| Annual snapshot | Long-term legal retention per department policy. |

Adjust to your department's data retention rules.

---

## Chapter 06 — 06 — Security hardening

UBIS as installed by `install.sh` is suitable for an isolated test on a closed police LAN. It is **not** suitable for production use until you complete every item below.

---

## 1. Mandatory before any officer logs in

| # | Action | Owner | Done? |
|---|--------|-------|-------|
| S1 | Change the installer-generated admin password (read with `grep INITIAL_ADMIN_PASSWORD .env`, then change from the UI on first login) | IT admin | |
| S2 | Restrict port 8080 to the police LAN subnet only (UFW / firewalld) | IT admin / network | |
| S3 | Put TLS in front of UBIS (Section 3 below) | IT admin | |
| S4 | Confirm `JWT_SECRET` in `.env` is the random value the installer generated, not the placeholder | IT admin | |
| S5 | Move `.env` to mode `600` and ensure ownership is the install user | IT admin | |
| S6 | Disable any test users created during the first-boot checklist | IT admin | |
| S7 | Confirm `ubis-backup.sh` cron job is scheduled (`05_BACKUP_AND_RESTORE.md`) | IT admin | |
| S8 | Confirm time-zone is `Asia/Kolkata` and NTP is in sync (`timedatectl`) | IT admin | |

---

## 2. Strong passwords

- **Admin user**: at least 14 characters, mix of upper/lower/digit/symbol, not based on dictionary words.
- **All other users**: enforce the same standard via your password manager.
- **`JWT_SECRET`**: 64 hex characters from `openssl rand -hex 32` — already the installer's default.
- **`POSTGRES_PASSWORD`** (if using `--profile full`): 32+ random characters.

Generate a fresh batch any time with:

```bash
bash scripts/onprem/generate_secrets.sh
```

The script prints to stdout only; it does not write anywhere. Save the values in your password vault, then `clear` your terminal.

---

## 3. TLS / HTTPS

UBIS itself listens on plain HTTP (port 80 inside the container, mapped to `UBIS_HTTP_PORT=8080` on the host). For HTTPS, place a TLS-terminating reverse proxy in front of it.

### Option A — Use the host's nginx with a department certificate (recommended)

```bash
# Install the host nginx (separate from the container)
sudo apt-get install -y nginx

# Place the cert and key (from your CA / department PKI)
sudo install -d /etc/ssl/ubis
sudo cp ubis.crt /etc/ssl/ubis/server.crt
sudo cp ubis.key /etc/ssl/ubis/server.key
sudo chmod 640 /etc/ssl/ubis/server.key

# Drop the site config
sudo tee /etc/nginx/sites-available/ubis <<'EOF'
server {
    listen 443 ssl http2;
    server_name ubis.ggn.haryanapolice.gov.in;

    ssl_certificate     /etc/ssl/ubis/server.crt;
    ssl_certificate_key /etc/ssl/ubis/server.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;

    add_header Strict-Transport-Security "max-age=31536000" always;
    client_max_body_size 100m;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
server {
    listen 80;
    server_name ubis.ggn.haryanapolice.gov.in;
    return 301 https://$host$request_uri;
}
EOF
sudo ln -s /etc/nginx/sites-available/ubis /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### Option B — Self-signed (only for very early pilot use)

```bash
sudo install -d /etc/ssl/ubis
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -subj "/CN=ubis.ggn.haryanapolice.gov.in" \
    -keyout /etc/ssl/ubis/server.key \
    -out    /etc/ssl/ubis/server.crt
# then use the same nginx site as Option A
```

Officers will see a browser warning; this is acceptable only for a closed pilot.

### Option C — Department-internal CA via NIC

Submit a CSR generated from the server with the hostname your users will type. Install the issued cert under `/etc/ssl/ubis/` and proceed as Option A.

---

## 4. Firewall

The only port your officers need to reach is 443 (TLS via the host nginx). The 8080 you exposed in `docker-compose.onprem.yml` should be closed at the host firewall once nginx is in front.

```bash
# Example UFW rules — adjust the LAN subnet to your reality
sudo ufw allow OpenSSH
sudo ufw allow from 10.0.0.0/8 to any port 443 proto tcp comment 'UBIS HTTPS'
sudo ufw deny 8080
sudo ufw enable
sudo ufw status verbose
```

For RHEL / firewalld:

```bash
sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="10.0.0.0/8" port port="443" protocol="tcp" accept'
sudo firewall-cmd --permanent --remove-port=8080/tcp
sudo firewall-cmd --reload
```

---

## 5. SSH hardening (server itself)

This is general server hygiene; not specific to UBIS but expected by any cyber cell audit.

- Disable password SSH: `PasswordAuthentication no` in `/etc/ssh/sshd_config`.
- Use key-based authentication only for the admin user.
- Disable root SSH: `PermitRootLogin no`.
- Restart SSH: `sudo systemctl restart ssh`.
- Limit SSH to the IT admin VLAN at the firewall.

---

## 6. Audit and log retention

UBIS writes an internal `audit_log` table for every authenticated action (login, case create, match run, admin actions). Backup automatically captures it. Retain backups per department policy (default suggestion in `05_BACKUP_AND_RESTORE.md` Section 6).

For OS-level logs (auth, sudo, container start/stop), configure your existing centralised logging or `rsyslog` per cyber cell standard.

---

## 7. Rotation schedule

| Secret / credential | Rotate every | How |
|---|---|---|
| Admin password | 90 days | UI → Admin → Users → Reset password |
| All user passwords | 180 days | Same; users self-rotate |
| `JWT_SECRET` | 180 days | Generate new value, edit `.env`, `docker compose ... restart backend`. **All sessions are invalidated**, users log in again. |
| `POSTGRES_PASSWORD` (if used) | 180 days | Update `.env`, `ALTER USER` in Postgres, restart backend. |
| TLS certificate | At least 30 days before expiry | Re-issue CSR; install; reload nginx |

Schedule rotation reminders in your team's calendar.

---

## 8. Public-facing search (DO NOT enable without approval)

UBIS supports a public search mode (text / voice / photo by missing-person family). It is **off** in this on-prem package by default because exposing the system to the public internet has legal and operational implications. Before enabling:

1. Get written approval from your authorising officer.
2. Place the system behind a public-facing reverse proxy with WAF (Web Application Firewall) protection.
3. Read the data-and-legal section of `docs/UAT_AND_POLICE_SIGNOFF.md` Section 9 row 5.

Until then, keep UBIS strictly on the police intranet.
