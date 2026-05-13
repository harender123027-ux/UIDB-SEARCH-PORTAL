#!/usr/bin/env bash
# One-shot health snapshot for UBIS on-prem.
# Prints colour-free, copy-pasteable output suitable for support tickets.

set -uo pipefail

COMPOSE_FILE="docker-compose.onprem.yml"
HTTP_PORT="${UBIS_HTTP_PORT:-8080}"
PROFILE="${UBIS_PROFILE:-lite}"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    COMPOSE=(docker compose)
elif command -v podman >/dev/null 2>&1 && podman compose version >/dev/null 2>&1; then
    COMPOSE=(podman compose)
elif command -v podman-compose >/dev/null 2>&1; then
    COMPOSE=(podman-compose)
else
    COMPOSE=(docker-compose)
fi

echo "================ UBIS status — $(date -u +'%Y-%m-%dT%H:%M:%SZ') ================"
echo
echo "[1] Containers"
"${COMPOSE[@]}" -f "$COMPOSE_FILE" --profile "$PROFILE" ps 2>&1 || true
echo

echo "[2] Backend health"
if curl -fsS -m 5 "http://localhost:${HTTP_PORT}/api/health"; then
    echo
else
    echo "  -> /api/health did NOT respond on port ${HTTP_PORT}."
fi
echo

echo "[3] Disk usage of /data"
du -sh ./data/* 2>/dev/null || echo "  ./data is empty (install not yet run?)"
echo

echo "[4] Last 20 audit-log entries"
"${COMPOSE[@]}" -f "$COMPOSE_FILE" --profile "$PROFILE" exec -T backend python - <<'PY' 2>&1 || true
from app.database import get_db
with get_db() as conn:
    rows = conn.execute(
        "SELECT created_at, user_id, action, resource_type, resource_id "
        "FROM audit_log ORDER BY created_at DESC LIMIT 20"
    ).fetchall()
    if not rows:
        print("  (audit log is empty)")
    for r in rows:
        print(f"  {r['created_at']}  {r['action']:<24}  {r['resource_type']}  {r['resource_id']}")
PY
echo

echo "[5] Container resource use"
if command -v docker >/dev/null 2>&1; then
    docker stats --no-stream ubis-backend ubis-frontend 2>/dev/null || true
elif command -v podman >/dev/null 2>&1; then
    podman stats --no-stream ubis-backend ubis-frontend 2>/dev/null || true
fi
echo "================ end of status ================"
