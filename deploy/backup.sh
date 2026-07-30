#!/usr/bin/env bash
# Automated PostgreSQL + storage backup with retention.
# Uses app backup helper when API container is up; falls back to docker exec pg_dump.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

load_env
require_cmd docker
mkdir -p "${BACKUP_DIR}"
RETENTION_DAYS="$(env_get BACKUP_RETENTION_DAYS 14)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

log "Backup starting → ${BACKUP_DIR} (retention=${RETENTION_DAYS}d)"

# Prefer in-app backup (handles uploads/knowledge + prune)
if compose ps --status running 2>/dev/null | grep -qE '[[:space:]]api[[:space:]]'; then
  log "Running scripts/backup.py inside api/backup service..."
  if compose --profile manual-backup run --rm backup; then
    ok "Application backup finished"
  else
    warn "backup profile failed — falling back to pg_dump + tar"
    FALLBACK=1
  fi
else
  log "API not running — using host/docker fallback backup"
  FALLBACK=1
fi

if [[ "${FALLBACK:-0}" == "1" ]]; then
  DB_OUT="${BACKUP_DIR}/db_${STAMP}.sql.gz"
  if compose ps --status running 2>/dev/null | grep -qE '[[:space:]]db[[:space:]]'; then
    compose exec -T db pg_dump -U "$(env_get DB_USER)" "$(env_get DB_NAME)" | gzip > "${DB_OUT}"
    ok "DB → ${DB_OUT}"
  else
    if [[ "${ALLOW_BACKUP_FAILURE:-0}" == "1" ]]; then
      warn "Database not running; skip DB backup"
    else
      die "Cannot backup: db service not running"
    fi
  fi

  if [[ -d "${ROOT_DIR}/data/uploads" ]]; then
    tar -czf "${BACKUP_DIR}/uploads_${STAMP}.tar.gz" -C "${ROOT_DIR}/data" uploads
    ok "uploads archive"
  fi
  if [[ -d "${ROOT_DIR}/data/knowledge" ]]; then
    tar -czf "${BACKUP_DIR}/knowledge_${STAMP}.tar.gz" -C "${ROOT_DIR}/data" knowledge
    ok "knowledge archive"
  fi
fi

# Retention prune
if [[ "${RETENTION_DAYS}" =~ ^[0-9]+$ ]]; then
  find "${BACKUP_DIR}" -type f \( -name 'db_*.sql.gz' -o -name 'uploads_*.tar.gz' -o -name 'knowledge_*.tar.gz' \) \
    -mtime "+${RETENTION_DAYS}" -print -delete || true
  ok "Retention prune (>${RETENTION_DAYS} days)"
fi

ok "Backup complete"
ls -lah "${BACKUP_DIR}" | tail -n 20 || true
