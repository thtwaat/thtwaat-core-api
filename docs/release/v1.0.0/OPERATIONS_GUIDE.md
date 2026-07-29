# Operations Guide — v1.0.0

## Daily checks

| Check | How |
|-------|-----|
| API live/ready | `GET /live`, `GET /ready` |
| Full health | `GET /health` or `GET /api/v1/monitoring/health` (platform admin) |
| Worker alive | Redis key `thtwaat:worker:heartbeat` |
| Queue depth | `GET /api/v1/operations/jobs` or Redis `LLEN thtwaat:jobs` |
| Dead letter | Redis `thtwaat:jobs:dead` |
| SSL expiry | Deploy metrics / domains dashboard |
| Disk backups | `data/backups/` or `GET /api/v1/deploy/backups` |

## Background jobs

Queue: Redis list `thtwaat:jobs`  
Worker: `scripts/worker.py`  
Job types: `ssl.renew`, `ssl.auto_renew`, `backup.full`, `nginx.reload`

Ops controls (platform admin):

- List / retry / cancel / enqueue → `/api/v1/operations/jobs*`
- Alerts evaluate → `POST /api/v1/monitoring/alerts/evaluate`

## Backups

Implemented in `app/deploy/backup.py`:

| Artifact | Pattern |
|----------|---------|
| PostgreSQL | `db_<ts>.sql.gz` via `pg_dump` |
| Uploads | `uploads_<ts>.tar.gz` |
| Knowledge | `knowledge_<ts>.tar.gz` |
| Retention | `BACKUP_RETENTION_DAYS` (default 14) |

Trigger: scheduler hour (`BACKUP_HOUR_UTC`) or `POST /api/v1/deploy/backup`.

### Restore procedure

1. **Stop writers** (api/worker) or put in maintenance.
2. **Database:**  
   `gunzip -c data/backups/db_....sql.gz | psql <DATABASE_URL>`
3. **Filesystem:** extract tar.gz into `data/uploads` / `data/knowledge` (see `restore_filesystem`).
4. **Redis:** treat as ephemeral; rebuild rate-limit state; re-queue critical jobs if needed.
5. **Start services** and run `/ready` + smoke tests.
6. Record restore in ops audit / incident ticket.

### Redis persistence

Ensure Redis `appendonly` / RDB configured in your Redis image/compose for job durability if required. Default ephemeral Redis loses queue on restart — acceptable if jobs are re-enqueued by scheduler.

## Observability

| Signal | Location |
|--------|----------|
| Prometheus scrape | `GET /metrics` (Instrumentator) |
| JSON ops snapshot | `GET /api/v1/deploy/metrics` |
| Grafana | `GRAFANA_URL` (default `:3000`) |
| Logs | Container stdout; configure log shipper externally |
| Alerts | `/api/v1/monitoring/alerts*` + NotificationEventBus |
| Tracing | **Not configured** in v1.0.0 — use Prometheus + logs |

## Incident playbooks (short)

**API 503 / degraded:** check DB + Redis `/health` checks; scale/restart api.  
**Worker down:** inspect heartbeat; restart worker; drain dead-letter.  
**SSL fail:** set `SSL_MODE=certbot`, check ACME webroot, retry `ssl.renew`.  
**Publish fail:** diagnostics via Copilot task diagnostics or PublishService errors; check quotas.
