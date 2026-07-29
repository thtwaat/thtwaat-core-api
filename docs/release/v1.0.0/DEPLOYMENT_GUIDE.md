# Deployment Guide — v1.0.0

## Architecture (prod compose)

Services in `docker-compose.prod.yml`:

| Service | Role |
|---------|------|
| `nginx` | TLS termination, ACME webroot, domain vhosts |
| `api` | FastAPI + `alembic upgrade head` on start |
| `db` | PostgreSQL |
| `redis` | Rate limit, job queue, worker heartbeat |
| `worker` | Consumes `thtwaat:jobs` |
| `scheduler` | SSL renewals, backups, enterprise retention |
| `backup` | Scheduled/on-demand backup helper |

Optional: `docker-compose.monitoring.yml` (Prometheus, Grafana, cAdvisor, node-exporter).

## Prerequisites

- Docker Engine + Compose v2
- DNS control for custom domains
- Secrets: JWT keys, DB password, Stripe/Razorpay (if billing), AI provider keys
- Disk for `data/uploads`, `data/knowledge`, `data/backups`, `nginx/ssl`

## Environment variables (minimum)

| Variable | Notes |
|----------|-------|
| `APP_ENV` | Must be `production` |
| `JWT_SECRET_KEY` | Access token signing |
| `JWT_REFRESH_SECRET_KEY` | Refresh token signing |
| `DB_HOST` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` | Or `DATABASE_URL` |
| `REDIS_HOST` / `REDIS_PORT` | Required |
| `CORS_ORIGINS` | Explicit list — never `*` in prod |
| `PUBLIC_API_BASE_URL` | Embed/widget base URL |
| `SSL_MODE` | `certbot` for real certs; avoid leaving `simulate` in live prod |
| `PROMETHEUS_URL` / `GRAFANA_URL` | Ops UI links |
| `STRIPE_*` / `RAZORPAY_*` | Billing |
| Provider AI keys | As needed |

## Deploy steps

```bash
# 1. Secrets
cp .env .env.prod   # or pull from vault
# edit .env.prod — set APP_ENV=production, CORS, JWT, DB

# 2. Build & start
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build

# 3. Verify health
curl -f https://<host>/live
curl -f https://<host>/ready
curl -f https://<host>/health

# 4. Confirm migration head
docker compose -f docker-compose.prod.yml exec api alembic current
# expect: a7b8c9d0e1f2
```

## Rolling deployment

1. `docker compose -f docker-compose.prod.yml build api`
2. `docker compose -f docker-compose.prod.yml up -d --no-deps api`
3. Health gate on `/live` then `/ready`
4. Restart `worker` / `scheduler` if code changes affect jobs
5. Reload nginx if vhost templates changed: ops API or `nginx -s reload`

## Publish pipeline (product)

Not a separate CI artifact — agent/product publish is API-driven:

- `PublishService.publish` / Product Generator `publish_product`
- Domain bind + SSL via Domains + SSL Manager
- Copilot / Onboarding can orchestrate the same services

## Rollback

1. **Image rollback:** redeploy previous image tag / commit SHA.
2. **DB rollback:** only with tested `alembic downgrade` for the specific revision; prefer restore from `data/backups/db_*.sql.gz`.
3. **Config rollback:** restore previous `.env.prod` and recreate containers.

## Post-deploy smoke

- Login + refresh token
- Create company/user (or onboarding start)
- Create agent → publish
- `/metrics` reachable from Prometheus network only
- Worker heartbeat present (`thtwaat:worker:heartbeat`)
