#!/usr/bin/env bash
# Verify Prometheus / Grafana when monitoring compose is running.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

PROM_URL="${PROMETHEUS_URL:-http://127.0.0.1:9090}"
GRAFANA_URL="${GRAFANA_URL:-http://127.0.0.1:3000}"

if [[ "${REQUIRE_MONITORING:-0}" != "1" ]]; then
  if ! curl -fsS --max-time 3 "${PROM_URL}/-/healthy" >/dev/null 2>&1; then
    warn "Prometheus not reachable at ${PROM_URL} (start with: docker compose -f docker-compose.monitoring.yml up -d)"
    exit 0
  fi
fi

log "Checking Prometheus ${PROM_URL}/-/healthy"
curl -fsS --max-time 5 "${PROM_URL}/-/healthy" >/dev/null || die "Prometheus unhealthy"
ok "Prometheus"

log "Checking Grafana ${GRAFANA_URL}/api/health"
curl -fsS --max-time 5 "${GRAFANA_URL}/api/health" >/dev/null || die "Grafana unhealthy"
ok "Grafana"

# Targets (best-effort)
if curl -fsS --max-time 5 "${PROM_URL}/api/v1/targets" 2>/dev/null | grep -q '"health":"up"'; then
  ok "At least one Prometheus target is up"
else
  warn "No Prometheus targets reported up yet"
fi

ok "Monitoring verification passed"
