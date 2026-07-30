#!/usr/bin/env bash
# Verify API / nginx health endpoints after deploy.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

require_cmd curl
load_env

API_URL="${HEALTH_BASE_URL:-http://127.0.0.1:8000}"
NGINX_URL="${NGINX_HEALTH_URL:-http://127.0.0.1}"

log "Waiting for API liveness at ${API_URL}/live ..."
wait_http "${API_URL}/live" 60 2 || die "API /live failed"
ok "/live"

log "Checking readiness ${API_URL}/ready ..."
wait_http "${API_URL}/ready" 30 2 || die "API /ready failed"
ok "/ready"

log "Checking health ${API_URL}/health ..."
wait_http "${API_URL}/health" 15 2 || die "API /health failed"
ok "/health"

# Nginx edge (may redirect HTTP→HTTPS; accept 200/301/302 on /live via -k for TLS)
if curl -fsS --max-time 5 "${NGINX_URL}/live" >/dev/null 2>&1 \
  || curl -kfsS --max-time 5 "https://127.0.0.1/live" >/dev/null 2>&1; then
  ok "nginx edge /live"
else
  warn "nginx edge /live not reachable yet (API itself is healthy)"
fi

# Compose health status
unhealthy="$(compose ps --format json 2>/dev/null | grep -c '"unhealthy"' || true)"
if [[ "${unhealthy}" != "0" && -n "${unhealthy}" ]]; then
  compose ps
  die "One or more compose services report unhealthy"
fi

ok "Health verification passed"
