#!/usr/bin/env bash
# Fast unit suite — no Docker / Postgres / Redis required.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export JWT_SECRET_KEY="${JWT_SECRET_KEY:-unit-test-jwt-secret-key-32chars!!}"
export JWT_REFRESH_SECRET_KEY="${JWT_REFRESH_SECRET_KEY:-unit-test-refresh-secret-key-32!}"
export APP_ENV="${APP_ENV:-test}"

mkdir -p reports

python -m pytest \
  -m unit \
  --cov=app \
  --cov-report=term-missing \
  --cov-report=xml:reports/coverage-unit.xml \
  --cov-report=html:reports/htmlcov-unit \
  --junitxml=reports/junit-unit.xml \
  --html=reports/report-unit.html \
  --self-contained-html \
  "$@"
