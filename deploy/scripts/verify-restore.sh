#!/usr/bin/env bash
# Verify a PostgreSQL backup can be loaded into a temporary database.
# Usage: ./verify-restore.sh --archive /opt/thtwaat/backups/postgres/db_....sql.gz
set -euo pipefail

ROOT="${THTWAAT_ROOT:-/opt/thtwaat}"
CURRENT="${ROOT}/current"
ENV_FILE="${ENV_FILE:-${ROOT}/shared/.env.prod}"
ARCHIVE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --archive) ARCHIVE="$2"; shift 2 ;;
    *) echo "Unknown arg $1" >&2; exit 1 ;;
  esac
done
[[ -n "${ARCHIVE}" && -f "${ARCHIVE}" ]] || { echo "Need --archive" >&2; exit 1; }

cd "${CURRENT}"
set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

TMP_DB="thtwaat_restore_verify"
COMPOSE=(docker compose -f docker-compose.prod.yml --env-file "${ENV_FILE}")

echo "Creating temp DB ${TMP_DB}..."
"${COMPOSE[@]}" exec -T db psql -U "${DB_USER}" -d postgres -c "DROP DATABASE IF EXISTS ${TMP_DB};" >/dev/null
"${COMPOSE[@]}" exec -T db psql -U "${DB_USER}" -d postgres -c "CREATE DATABASE ${TMP_DB};" >/dev/null

echo "Loading archive (this may take a while)..."
gunzip -c "${ARCHIVE}" | "${COMPOSE[@]}" exec -T db psql -U "${DB_USER}" -d "${TMP_DB}" >/dev/null

COUNT="$("${COMPOSE[@]}" exec -T db psql -U "${DB_USER}" -d "${TMP_DB}" -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';")"
echo "Restore verify OK — public tables=${COUNT}"

"${COMPOSE[@]}" exec -T db psql -U "${DB_USER}" -d postgres -c "DROP DATABASE IF EXISTS ${TMP_DB};" >/dev/null
echo "Temp DB dropped"
