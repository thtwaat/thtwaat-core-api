# Performance Notes — v1.0.0

Static readiness notes (no load-test cluster was assumed available during packaging).

## Measure in staging before Go

| Metric | How | Target (suggested) |
|--------|-----|--------------------|
| API p95 latency | Prometheus Instrumentator histograms / Grafana | < 300ms read; < 1s write |
| Error rate | `/metrics` + deploy snapshot errors | < 1% |
| DB latency | `/health` database.latency_ms | < 50ms local net |
| Redis latency | `/health` redis.latency_ms | < 10ms |
| Queue depth | `thtwaat:jobs` / operations API | < 25 steady; alert ≥ 100 |
| Worker heartbeat | Redis key TTL 60s | Always present |
| Memory / CPU | cAdvisor + `deploy/metrics` process gauges | < 80% sustained |
| Streaming | AI/chat streaming endpoints under load | No disconnect storms |

## Known hotspots

1. **Product Generator** — multi-service orchestration; treat as async UX (progress), not sub-100ms.
2. **Knowledge upload** — background indexing; do not block HTTP on embedding completion.
3. **Rate limiter** — Redis dependency; Redis outage impacts limiter init/startup.
4. **Enterprise audit middleware** — writes on mutating requests; monitor DB write amplification.

## Redis usage

- FastAPI-Limiter
- Job queue + dead letter
- Worker heartbeat
- Optional cache hit ratio via `INFO stats` (monitoring observability)

## Background jobs

Prefer scheduler for periodic SSL/backup; avoid flooding `thtwaat:jobs`. Use operations API to inspect depth.

## Tooling already in repo

- `docker-compose.performance.yml` — use for load-oriented local runs
- `docker-compose.monitoring.yml` — Prometheus/Grafana/cAdvisor/node-exporter
