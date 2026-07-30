#!/usr/bin/env bash
# Integration suite — requires docker-compose.test.yml (Postgres + Redis).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f .env.test ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env.test
  set +a
elif [[ -f .env.test.example ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env.test.example
  set +a
fi

export DATABASE_URL="${DATABASE_URL:-postgresql://thtwaat:thtwaat@localhost:5433/thtwaat_test}"
export REDIS_HOST="${REDIS_HOST:-localhost}"
export REDIS_PORT="${REDIS_PORT:-6380}"
export JWT_SECRET_KEY="${JWT_SECRET_KEY:-unit-test-jwt-secret-key-32chars!!}"
export JWT_REFRESH_SECRET_KEY="${JWT_REFRESH_SECRET_KEY:-unit-test-refresh-secret-key-32!}"
export APP_ENV="${APP_ENV:-test}"

echo "==> Ensuring test stack (db + redis) is up..."
docker compose -f docker-compose.test.yml up -d db redis

echo "==> Waiting for Postgres/Redis..."
python - <<'PY'
import sys, time
from tests.support import wait_for_tcp, parse_host_port_from_database_url, postgres_dsn_from_env, redis_host_port
dsn = postgres_dsn_from_env()
host, port = parse_host_port_from_database_url(dsn)
rh, rp = redis_host_port()
if not wait_for_tcp(host, port, timeout=90):
    print(f"Postgres not ready at {host}:{port}", file=sys.stderr); sys.exit(1)
if not wait_for_tcp(rh, rp, timeout=90):
    print(f"Redis not ready at {rh}:{rp}", file=sys.stderr); sys.exit(1)
print("stack ready")
PY

echo "==> Alembic upgrade..."
alembic upgrade head

mkdir -p reports

python -m pytest \
  -m "integration and not e2e" \
  --cov=app \
  --cov-report=term-missing \
  --cov-report=xml:reports/coverage-integration.xml \
  --cov-report=html:reports/htmlcov-integration \
  --junitxml=reports/junit-integration.xml \
  --html=reports/report-integration.html \
  --self-contained-html \
  --timeout=120 \
  "$@"
