# Monitoring & Admin Operations

Production-ready platform ops module for THTWAAT AI Platform.

This package is an **aggregation and control facade**. It reuses existing
Prometheus/Grafana, deploy health checks, Redis job workers, notifications,
RBAC, publish, enterprise audit, billing, marketplace, and product generator
surfaces. It does **not** duplicate Prometheus scrape exposition.

## What it reuses

| Concern | Existing source |
|---------|-----------------|
| Prometheus scrape | `prometheus-fastapi-instrumentator` → `/metrics` |
| Grafana | `docker-compose.monitoring.yml` + `GRAFANA_URL` |
| Health probes | `app.deploy.health` (`/health`, `/ready`, `/live`) |
| In-process counters | `app.deploy.metrics.snapshot` |
| Job queue | Redis `thtwaat:jobs` / `thtwaat:jobs:dead` (`scripts/worker.py`) |
| Alerts delivery | `NotificationService` + `NotificationEventBus` |
| Security audit | `EnterpriseAuditLog` |
| Billing / usage | Invoices, subscriptions, usage daily aggregates |
| Publish surface | `AgentConfig` + `PublishService` (synchronous) |

## API surface

All routes require `platform:admin` (`SUPER_ADMIN`).

### `/api/v1/admin/*`

- `GET /admin/overview` — users, companies, agents, KBs, installs, generations, billing
- `GET /admin/reports/{daily|weekly|monthly}` — growth, revenue, usage trends
- `GET /admin/audit/timeline` — admin + ops + security events
- `GET /admin/audit/export?format=csv|json`

### `/api/v1/operations/*`

- `GET /operations/jobs` — active + dead-letter queue
- `POST /operations/jobs/retry` — retry dead-letter job
- `POST /operations/jobs/cancel` — remove queued job
- `POST /operations/jobs/enqueue` — enqueue `{ "type": "backup.full", "payload": {} }`
- `GET /operations/deployments` — deployment/ops history
- `GET /operations/publish-queue` — draft vs published agents

### `/api/v1/monitoring/*`

- `GET /monitoring/health` — API / DB / Redis / queue / storage / workers
- `GET /monitoring/observability` — Grafana/Prometheus links, latency, error rate, volume, queue depth, cache hit ratio
- `GET /monitoring/alerts`
- `POST /monitoring/alerts` — manual alert (+ optional push/email)
- `POST /monitoring/alerts/evaluate` — raise from health/queue rules
- `POST /monitoring/alerts/{id}/acknowledge`
- `POST /monitoring/alerts/{id}/resolve`

## Observability policy

- Time-series SLOs → Prometheus + Grafana (not this module)
- Admin UX / ops actions → these JSON APIs
- Optional env: `PROMETHEUS_URL`, `GRAFANA_URL`

## Migration

```bash
alembic upgrade head
```

Revision: `f6a7b8c9d0e1` (after onboarding `e5f6a7b8c9d0`).

Tables: `ops_alerts`, `ops_deployment_events`, `ops_admin_activities`.

## Tests

```bash
pytest tests/monitoring -q -m "not integration"
```
