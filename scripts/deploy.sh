#!/usr/bin/env bash
# One-click production deployment for THTWAAT AI Platform
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${ENV_FILE:-.env}"
COMPOSE="docker compose -f docker-compose.prod.yml --env-file ${ENV_FILE}"

mkdir -p data/uploads data/knowledge data/backups nginx/ssl/domains nginx/conf.d/domains nginx/acme-webroot/.well-known/acme-challenge
touch nginx/conf.d/domains/.keep

echo "==> Building & starting production stack"
$COMPOSE up -d --build

echo "==> Waiting for API health"
for i in $(seq 1 60); do
  if curl -fsS http://localhost:8000/live >/dev/null 2>&1; then
    echo "API is live"
    break
  fi
  sleep 2
done

echo "==> Alembic (also runs in api startup)"
$COMPOSE exec -T api alembic upgrade head || true

echo "==> Status"
$COMPOSE ps

echo ""
echo "Deploy complete."
echo "  Health:  http://localhost/health  (via nginx) or http://localhost:8000/health"
echo "  Ready:   http://localhost:8000/ready"
echo "  Live:    http://localhost:8000/live"
echo "  Dashboard: GET /api/v1/deploy/dashboard (auth required)"
