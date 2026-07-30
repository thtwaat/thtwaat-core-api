#!/usr/bin/env bash
# E2E suite — against a deployed API (E2E_BASE_URL).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f .env.test ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env.test
  set +a
fi

export E2E_BASE_URL="${E2E_BASE_URL:-http://localhost:8000}"
export JWT_SECRET_KEY="${JWT_SECRET_KEY:-unit-test-jwt-secret-key-32chars!!}"
export JWT_REFRESH_SECRET_KEY="${JWT_REFRESH_SECRET_KEY:-unit-test-refresh-secret-key-32!}"

if [[ "${START_E2E_STACK:-0}" == "1" ]]; then
  echo "==> Starting compose profile e2e..."
  docker compose -f docker-compose.test.yml --profile e2e up -d --build
  echo "==> Waiting for API..."
  python - <<'PY'
import sys, time, urllib.request
url = __import__("os").environ.get("E2E_BASE_URL", "http://localhost:8000") + "/liveness"
deadline = time.time() + 120
while time.time() < deadline:
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            if r.status == 200:
                print("api ready"); sys.exit(0)
    except Exception:
        time.sleep(2)
print("API not ready", file=sys.stderr); sys.exit(1)
PY
fi

mkdir -p reports

python -m pytest \
  -m e2e \
  --junitxml=reports/junit-e2e.xml \
  --html=reports/report-e2e.html \
  --self-contained-html \
  --timeout=60 \
  "$@"
