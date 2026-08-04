# Production Deployment (VPS)

Fully automated Ubuntu 24.04 LTS deployment for THTWAAT Core API.

## Components

| Path | Purpose |
|------|---------|
| `./deploy.sh` | One-command deploy entrypoint |
| `deploy/bootstrap-ubuntu.sh` | Install Docker, Compose, Nginx, Certbot, UFW, Fail2Ban |
| `deploy/validate-env.sh` | Fail-fast secrets / env validation |
| `deploy/deploy.sh` | Pull → build → migrate → health → rollback on failure |
| `deploy/rollback.sh` | Restore last rollback point |
| `deploy/backup.sh` / `restore.sh` | DB + storage backup/restore + retention |
| `deploy/verify-health.sh` | `/live` `/ready` `/health` |
| `deploy/verify-monitoring.sh` | Prometheus + Grafana |
| `docker-compose.prod.yml` | Production stack (**Compose v2 only**) |

## First-time VPS setup

```bash
# 1) As root on Ubuntu 24.04
sudo THTWAAT_ROOT=/opt/thtwaat ./deploy/bootstrap-ubuntu.sh

# 2) App tree
sudo mkdir -p /opt/thtwaat
sudo chown -R "$USER":docker /opt/thtwaat
git clone <repo> /opt/thtwaat
cd /opt/thtwaat

# 3) Secrets
cp .env.prod.example .env.prod
# edit: JWT_*, DB_PASSWORD, CORS_ORIGINS, PUBLIC_API_BASE_URL (https), ...
./deploy/validate-env.sh

# 4) Deploy
./deploy.sh
```

## Day-2 deploy

```bash
./deploy.sh
# or pin a release:
DEPLOY_REF=v1.0.0 ./deploy.sh
```

## Environment validation

Required (deploy fails if missing/placeholder):

- `APP_ENV=production`
- `JWT_SECRET_KEY` / `JWT_REFRESH_SECRET_KEY` (different, ≥32 chars)
- `DB_USER` / `DB_PASSWORD` / `DB_NAME`
- `CORS_ORIGINS` without `*`
- `PUBLIC_API_BASE_URL` starting with `https://`

Optional SMTP — enforce with `REQUIRE_SMTP=1 ./deploy/validate-env.sh`.

## Security baseline

- **UFW**: deny inbound except SSH/80/443
- **Fail2Ban**: sshd + nginx rate-limit filter
- **TLS**: compose nginx HSTS + security headers (see `nginx/nginx.conf`)
- **Containers**: `security_opt: no-new-privileges:true` on api/worker/scheduler/nginx
- DB/Redis **not** published to host ports in prod compose

## Backups

```bash
./deploy/backup.sh
CONFIRM_RESTORE=YES ./deploy/restore.sh --db data/backups/db_YYYYMMDDTHHMMSSZ.sql.gz
```

Systemd timer (installed by bootstrap): daily ~03:15 UTC → `deploy/backup.sh`.  
Retention: `BACKUP_RETENTION_DAYS` (default 14).

## Monitoring

```bash
docker compose -f docker-compose.monitoring.yml up -d
./deploy/verify-monitoring.sh
```

## SaaS frontend (`web_app`) vs API

`app.thtwaat.com` is served by Compose service **`web_app`** (`apps/templates/saas` → Next.js).  
`api.thtwaat.com` is **`api`**.

**Common mistake:** after pulling SaaS routes (e.g. `/app/inbox`, `/app/providers`) only rebuild API:

```bash
# WRONG for UI — leaves stale Next.js image → App Router 404
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build api
```

**Correct when frontend files change:**

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build web_app
# Prefer both when API + UI shipped together:
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build web_app api
```

Verify Inbox is inside the running image:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec web_app \
  ls /app/.next/server/app/app/inbox
```

## CI/CD

Workflow: `.github/workflows/deploy-production.yml`

1. Build & push image to GHCR  
2. SSH to VPS → `./deploy/deploy.sh`  
3. Health verification  
4. On failure → `./deploy/rollback.sh`

Required GitHub secrets: `PROD_HOST`, `PROD_USER`, `PROD_SSH_KEY`, optional `PROD_SSH_PORT`, `PROD_APP_PATH`.  
Use GitHub Environment `production` for approvals.

See also: [OPERATIONS_RUNBOOK.md](./OPERATIONS_RUNBOOK.md), [RECOVERY_GUIDE.md](./RECOVERY_GUIDE.md).
