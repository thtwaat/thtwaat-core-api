#!/usr/bin/env bash
# Nightly PostgreSQL dump → /opt/thtwaat/backups/postgres + rotation + restore smoke.
set -euo pipefail

ROOT="${THTWAAT_ROOT:-/opt/thtwaat}"
CURRENT="${ROOT}/current"
ENV_FILE="${ENV_FILE:-${ROOT}/shared/.env.prod}"
OUT_DIR="${ROOT}/backups/postgres"
RETENTION_DAYS="${POSTGRES_BACKUP_RETENTION_DAYS:-14}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "${OUT_DIR}" "${ROOT}/logs"

cd "${CURRENT}"
set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

OUT="${OUT_DIR}/db_${STAMP}.sql.gz"
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Nightly PG backup → ${OUT}"

docker compose -f docker-compose.prod.yml --env-file "${ENV_FILE}" \
  exec -T db pg_dump -U "${DB_USER}" "${DB_NAME}" | gzip > "${OUT}"

# Rotation
find "${OUT_DIR}" -type f -name 'db_*.sql.gz' -mtime "+${RETENTION_DAYS}" -delete || true

# Restore verification (smoke): gunzip -t integrity check + optional logical probe
if gunzip -t "${OUT}" 2>/dev/null; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Restore verify: gzip integrity OK"
else
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Restore verify FAILED" >&2
  exit 1
fi

# Optional deep verify into throwaway DB
if [[ "${VERIFY_RESTORE_DEEP:-0}" == "1" ]]; then
  bash "${CURRENT}/deploy/scripts/verify-restore.sh" --archive "${OUT}"
fi

ls -lah "${OUT_DIR}" | tail -n 10
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Nightly backup complete"
