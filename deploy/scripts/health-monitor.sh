#!/usr/bin/env bash
# Periodic health probe — logs + optional webhook alert.
set -euo pipefail

ROOT="${THTWAAT_ROOT:-/opt/thtwaat}"
CURRENT="${ROOT}/current"
LOG="${HEALTH_LOG:-${ROOT}/logs/health/health.log}"
API_URL="${HEALTH_BASE_URL:-http://127.0.0.1:8000}"
mkdir -p "$(dirname "${LOG}")"
ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

fail=0
for path in /live /ready /health; do
  if curl -fsS --max-time 5 "${API_URL}${path}" >/dev/null 2>&1; then
    echo "${ts} OK ${path}" >> "${LOG}"
  else
    echo "${ts} FAIL ${path}" >> "${LOG}"
    fail=1
  fi
done

# Keep log bounded (~5MB)
if [[ -f "${LOG}" ]] && [[ "$(wc -c < "${LOG}")" -gt 5000000 ]]; then
  tail -n 2000 "${LOG}" > "${LOG}.tmp" && mv "${LOG}.tmp" "${LOG}"
fi

if [[ "${fail}" -ne 0 ]]; then
  if [[ -n "${HEALTH_WEBHOOK_URL:-}" ]]; then
    curl -fsS -X POST -H 'Content-Type: application/json' \
      -d "{\"text\":\"THTWAAT health check failed at ${ts}\"}" \
      "${HEALTH_WEBHOOK_URL}" >/dev/null 2>&1 || true
  fi
  exit 1
fi
exit 0
