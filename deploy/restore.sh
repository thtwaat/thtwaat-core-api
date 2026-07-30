#!/usr/bin/env bash
# Restore PostgreSQL and/or filesystem archives from data/backups.
#
#   ./deploy/restore.sh --db data/backups/db_YYYYMMDD.sql.gz
#   ./deploy/restore.sh --uploads data/backups/uploads_YYYYMMDD.tar.gz
#   ./deploy/restore.sh --knowledge data/backups/knowledge_YYYYMMDD.tar.gz
#   ./deploy/restore.sh --list
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

load_env
require_cmd docker

DB_ARCHIVE=""
UPLOADS_ARCHIVE=""
KNOWLEDGE_ARCHIVE=""
LIST_ONLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --db) DB_ARCHIVE="$2"; shift 2 ;;
    --uploads) UPLOADS_ARCHIVE="$2"; shift 2 ;;
    --knowledge) KNOWLEDGE_ARCHIVE="$2"; shift 2 ;;
    --list) LIST_ONLY=1; shift ;;
    -h|--help)
      sed -n '1,12p' "$0"
      exit 0
      ;;
    *) die "Unknown arg: $1" ;;
  esac
done

if [[ "${LIST_ONLY}" == "1" ]]; then
  ls -lah "${BACKUP_DIR}"
  exit 0
fi

[[ -n "${DB_ARCHIVE}${UPLOADS_ARCHIVE}${KNOWLEDGE_ARCHIVE}" ]] || die "Specify --db / --uploads / --knowledge or --list"

confirm="${CONFIRM_RESTORE:-}"
if [[ "${confirm}" != "YES" ]]; then
  die "Refusing restore without CONFIRM_RESTORE=YES (destructive)"
fi

if [[ -n "${DB_ARCHIVE}" ]]; then
  [[ -f "${DB_ARCHIVE}" ]] || die "Missing ${DB_ARCHIVE}"
  log "Restoring database from ${DB_ARCHIVE}"
  warn "Stopping api/worker/scheduler to avoid writes..."
  compose stop api worker scheduler || true
  gunzip -c "${DB_ARCHIVE}" | compose exec -T db psql -U "$(env_get DB_USER)" -d "$(env_get DB_NAME)"
  ok "Database restore applied"
  compose start api worker scheduler
fi

if [[ -n "${UPLOADS_ARCHIVE}" ]]; then
  [[ -f "${UPLOADS_ARCHIVE}" ]] || die "Missing ${UPLOADS_ARCHIVE}"
  log "Restoring uploads..."
  mkdir -p "${ROOT_DIR}/data"
  tar -xzf "${UPLOADS_ARCHIVE}" -C "${ROOT_DIR}/data"
  ok "Uploads restored"
fi

if [[ -n "${KNOWLEDGE_ARCHIVE}" ]]; then
  [[ -f "${KNOWLEDGE_ARCHIVE}" ]] || die "Missing ${KNOWLEDGE_ARCHIVE}"
  log "Restoring knowledge..."
  mkdir -p "${ROOT_DIR}/data"
  tar -xzf "${KNOWLEDGE_ARCHIVE}" -C "${ROOT_DIR}/data"
  ok "Knowledge restored"
fi

bash "${SCRIPT_DIR}/verify-health.sh" || warn "Post-restore health check failed"
ok "Restore finished"
