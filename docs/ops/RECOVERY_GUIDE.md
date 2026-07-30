# Recovery Guide

## Principles

1. Prefer **rollback** (previous known-good git SHA / images) before risky DB surgery.  
2. Never restore production DB without `CONFIRM_RESTORE=YES`.  
3. Take a fresh backup **before** destructive recovery when the stack still runs.

## A. Application rollback (preferred)

```bash
cd /opt/thtwaat
./deploy/rollback.sh
./deploy/verify-health.sh
```

If health still fails, proceed to B/C.

## B. Restore PostgreSQL

```bash
./deploy/backup.sh --list 2>/dev/null || ./deploy/restore.sh --list
# Pick latest good db_*.sql.gz
CONFIRM_RESTORE=YES ./deploy/restore.sh --db data/backups/db_YYYYMMDDTHHMMSSZ.sql.gz
./deploy/verify-health.sh
```

Notes:

- API/worker/scheduler are stopped during DB restore.  
- Alembic history must match the restored schema; if you restored an older dump onto newer code, check `alembic current` vs code head — may need a matching git checkout.

## C. Restore uploads / knowledge

```bash
CONFIRM_RESTORE=YES ./deploy/restore.sh \
  --uploads data/backups/uploads_YYYYMMDDTHHMMSSZ.tar.gz \
  --knowledge data/backups/knowledge_YYYYMMDDTHHMMSSZ.tar.gz
```

## D. Redis / queue

Redis AOF is persisted in the `redisdata` volume. If the queue is corrupt:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod restart redis
# Last resort (loses queue state):
docker compose -f docker-compose.prod.yml --env-file .env.prod stop redis
docker volume rm <project>_redisdata   # destructive
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d redis
```

## E. Disk full

```bash
df -h
du -sh data/* nginx/ssl/*
# Prune old backups immediately
BACKUP_RETENTION_DAYS=3 ./deploy/backup.sh   # prune uses env retention on next run
find data/backups -type f -mtime +3 -delete
docker system prune -f
```

## F. TLS / nginx broken

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec nginx nginx -t
docker compose -f docker-compose.prod.yml --env-file .env.prod restart nginx
# Temporary HTTP health via API port:
curl -fsS http://127.0.0.1:8000/live
```

## G. Complete rebuild

```bash
./deploy/backup.sh
docker compose -f docker-compose.prod.yml --env-file .env.prod down
# volumes retained unless -v
./deploy.sh
```

## H. Post-recovery checklist

- [ ] `/live` and `/ready` return 200  
- [ ] Login / create company smoke test  
- [ ] Worker heartbeat present in Redis  
- [ ] Latest backup exists and timer active (`systemctl list-timers | grep thtwaat`)  
- [ ] Prometheus/Grafana up if used  
- [ ] Incident notes filed  

## Contacts / escalation

Document on-call rotation outside this repo. Attach `data/deploy-logs/deploy-*.log` and `docker compose ps` output when escalating.
