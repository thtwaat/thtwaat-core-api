#!/usr/bin/env bash
# Shared helpers for THTWAAT VPS deploy scripts.
# shellcheck disable=SC2034

set -euo pipefail

DEPLOY_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${DEPLOY_LIB_DIR}/.." && pwd)"
ROOT_DIR="$(cd "${DEPLOY_DIR}/.." && pwd)"

# Capistrano-style VPS layout (/opt/thtwaat)
if [[ -n "${THTWAAT_ROOT:-}" ]]; then
  :
elif [[ -d /opt/thtwaat/current ]] && [[ -f /opt/thtwaat/shared/.env.prod || -f /opt/thtwaat/shared/.env.prod.example ]]; then
  THTWAAT_ROOT=/opt/thtwaat
fi
if [[ -n "${THTWAAT_ROOT:-}" ]] && [[ -d "${THTWAAT_ROOT}/current" ]]; then
  ROOT_DIR="${THTWAAT_ROOT}/current"
fi

ENV_FILE="${ENV_FILE:-}"
if [[ -z "${ENV_FILE}" ]]; then
  if [[ -n "${THTWAAT_ROOT:-}" ]] && [[ -f "${THTWAAT_ROOT}/shared/.env.prod" ]]; then
    ENV_FILE="${THTWAAT_ROOT}/shared/.env.prod"
  else
    ENV_FILE="${ROOT_DIR}/.env.prod"
  fi
fi
COMPOSE_FILE="${COMPOSE_FILE:-${ROOT_DIR}/docker-compose.prod.yml}"
MONITORING_COMPOSE="${MONITORING_COMPOSE:-${ROOT_DIR}/docker-compose.monitoring.yml}"
if [[ -n "${THTWAAT_ROOT:-}" ]]; then
  STATE_DIR="${STATE_DIR:-${THTWAAT_ROOT}/shared/deploy-state}"
  BACKUP_DIR="${BACKUP_DIR:-${THTWAAT_ROOT}/backups}"
  LOG_DIR="${LOG_DIR:-${THTWAAT_ROOT}/logs/deploy}"
else
  STATE_DIR="${STATE_DIR:-${ROOT_DIR}/data/deploy-state}"
  BACKUP_DIR="${BACKUP_DIR:-${ROOT_DIR}/data/backups}"
  LOG_DIR="${LOG_DIR:-${ROOT_DIR}/data/deploy-logs}"
fi

mkdir -p "${STATE_DIR}" "${BACKUP_DIR}" "${LOG_DIR}" \
  "${ROOT_DIR}/data/uploads" "${ROOT_DIR}/data/knowledge" \
  "${ROOT_DIR}/nginx/ssl/domains" "${ROOT_DIR}/nginx/conf.d/domains" \
  "${ROOT_DIR}/nginx/acme-webroot/.well-known/acme-challenge"
touch "${ROOT_DIR}/nginx/conf.d/domains/.keep"

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

log()  { echo "[$(ts)] $*"; }
ok()   { echo "[$(ts)] OK  $*"; }
warn() { echo "[$(ts)] WARN $*" >&2; }
die()  { echo "[$(ts)] ERR $*" >&2; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

compose() {
  docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" "$@"
}

load_env() {
  [[ -f "${ENV_FILE}" ]] || die "Env file not found: ${ENV_FILE} (copy .env.prod.example)"
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
  # docker-compose.prod.yml services pin env_file: .env — keep in sync
  if [[ "$(cd "$(dirname "${ENV_FILE}")" && pwd)/$(basename "${ENV_FILE}")" != "${ROOT_DIR}/.env" ]]; then
    cp -f "${ENV_FILE}" "${ROOT_DIR}/.env"
  fi
}

env_get() {
  local key="$1"
  local default="${2:-}"
  if [[ -f "${ENV_FILE}" ]]; then
    local val
    val="$(grep -E "^${key}=" "${ENV_FILE}" | tail -n1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")" || true
    if [[ -n "${val}" ]]; then
      echo "${val}"
      return
    fi
  fi
  echo "${default}"
}

is_placeholder() {
  local v="$1"
  [[ -z "$v" ]] && return 0
  echo "$v" | grep -Eqi '^(change-me|replace_|your_|xxx|todo|placeholder)' && return 0
  return 1
}

wait_http() {
  local url="$1"
  local attempts="${2:-60}"
  local sleep_s="${3:-2}"
  local i
  for i in $(seq 1 "${attempts}"); do
    if curl -fsS --max-time 5 "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep "${sleep_s}"
  done
  return 1
}

save_rollback_point() {
  local tag
  tag="$(ts | tr -d ':-')"
  local file="${STATE_DIR}/rollback-${tag}.env"
  {
    echo "CREATED_AT=$(ts)"
    echo "GIT_SHA=$(git -C "${ROOT_DIR}" rev-parse HEAD 2>/dev/null || echo unknown)"
    echo "API_IMAGE=$(compose images -q api 2>/dev/null | head -n1 || true)"
    echo "WORKER_IMAGE=$(compose images -q worker 2>/dev/null | head -n1 || true)"
    echo "NGINX_IMAGE=$(compose images -q nginx 2>/dev/null | head -n1 || true)"
    echo "COMPOSE_FILE=${COMPOSE_FILE}"
    echo "ENV_FILE=${ENV_FILE}"
  } > "${file}"
  ln -sfn "${file}" "${STATE_DIR}/rollback-latest.env"
  echo "${file}"
}
