# Operations Runbook

## Service map

| Service | Role | Health |
|---------|------|--------|
| `nginx` | TLS + reverse proxy | `nginx -t`, `/live` via :443 |
| `api` | FastAPI | `/live`, `/ready`, `/health` |
| `worker` | Redis job consumer | Redis `thtwaat:worker:heartbeat` |
| `scheduler` | SSL renew / backup enqueue | process up |
| `db` | PostgreSQL + pgvector | `pg_isready` |
| `redis` | Cache / queue / rate limit | `PING` |

## Daily checks

```bash
cd /opt/thtwaat
docker compose -f docker-compose.prod.yml --env-file .env.prod ps
./deploy/verify-health.sh
./deploy/verify-monitoring.sh   # if monitoring stack is up
df -h /opt/thtwaat/data
ls -lt data/backups | head
```

## Deploy

```bash
./deploy.sh
```

On failure the deploy trap calls `deploy/rollback.sh` automatically.

## Manual rollback

```bash
./deploy/rollback.sh
# or point at a specific snapshot:
ROLLBACK_POINT=data/deploy-state/rollback-....env ./deploy/rollback.sh
```

## Certificates

- Compose nginx serves `nginx/ssl/server.crt` by default.
- For public TLS set `SSL_MODE=certbot` and configure ACME email; domain vhosts land in `nginx/conf.d/domains/`.
- Host certbot is installed by bootstrap for optional edge mode (`FORCE_HOST_NGINX=1`).

## Firewall / intrusion

```bash
sudo ufw status verbose
sudo fail2ban-client status
sudo fail2ban-client status sshd
```

## Logs

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f api --tail=200
ls data/deploy-logs/
journalctl -u thtwaat-backup.service -n 100
```

## Scaling notes

- Vertical: increase VPS CPU/RAM; tune uvicorn workers only via deliberate compose command change.
- Horizontal: put multiple API replicas behind an external LB — out of scope for single-VPS compose.

## Incident severity

| Sev | Example | Action |
|-----|---------|--------|
| SEV1 | `/live` down | rollback; check `docker ps`, disk, OOM |
| SEV2 | `/ready` failing | DB/Redis connectivity; migrate status |
| SEV3 | Worker backlog | inspect `thtwaat:jobs` / dead letter |
| SEV4 | Backup missed | run `./deploy/backup.sh`; check timer |
