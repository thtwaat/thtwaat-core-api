#!/usr/bin/env bash
# Create Capistrano-style directory layout under /opt/thtwaat.
set -euo pipefail
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "${DEPLOY_DIR}/lib/common.sh"

ROOT="${THTWAAT_ROOT:-/opt/thtwaat}"
USER_NAME="${THTWAAT_APP_USER:-thtwaat}"

mkdir -p \
  "${ROOT}" \
  "${ROOT}/releases" \
  "${ROOT}/shared" \
  "${ROOT}/shared/data/uploads" \
  "${ROOT}/shared/data/knowledge" \
  "${ROOT}/shared/data/backups" \
  "${ROOT}/shared/data/static-sites" \
  "${ROOT}/shared/nginx/ssl/domains" \
  "${ROOT}/shared/nginx/conf.d/domains" \
  "${ROOT}/shared/nginx/acme-webroot/.well-known/acme-challenge" \
  "${ROOT}/shared/monitoring" \
  "${ROOT}/backups" \
  "${ROOT}/backups/postgres" \
  "${ROOT}/backups/storage" \
  "${ROOT}/logs" \
  "${ROOT}/logs/deploy" \
  "${ROOT}/logs/health"

touch "${ROOT}/shared/nginx/conf.d/domains/.keep"

# Prefer shared env path for deploys
if [[ -f "${DEPLOY_DIR}/../.env.prod.example" ]]; then
  install -m 0640 "${DEPLOY_DIR}/../.env.prod.example" "${ROOT}/shared/.env.prod.example"
fi

# Ownership once user exists (03 may create user first — re-run chown in 03)
if id "${USER_NAME}" >/dev/null 2>&1; then
  chown -R "${USER_NAME}:${USER_NAME}" "${ROOT}"
fi

ok "Directories ready under ${ROOT}"
ls -la "${ROOT}"
