# THTWAAT AI Platform v1.0.0 — Release Notes

**Release date:** 2026-08-05 (Launch Freeze)  
**Tag:** `v1.0.0`  
**Commit message:** `chore(release): launch freeze v1`  
**API version:** `1.0.0`

## Highlights

THTWAAT v1.0.0 is the production launch freeze of the multi-tenant AI platform: auth, agents, knowledge, publish/widget, marketplace + publisher store, region billing (INR/Razorpay · USD/Stripe), usage quotas, enterprise Super Admin analytics, and launch-readiness E2E packs.

## Launch freeze changes (this cut)

### Reliability & security
- Billing webhooks (Stripe/Razorpay): processing failures stay **unprocessed** and return **HTTP 500** so providers retry (no silent poison of paid events).
- Agent creation: quota metering errors **fail closed** (503) instead of bypassing plan limits.
- CORS: wildcard origins no longer enable `allow_credentials=True`.
- Security headers verified (API middleware + SaaS Next headers).
- AI gateway: Redis RPM limiter + improved cost heuristics.
- Scheduler now runs monitoring `evaluate_and_raise` on a cadence.

### Cleanup & performance
- Mounted previously orphaned `/v2/agents/{id}/analytics` with single-scan SQL aggregates.
- Deprecated legacy `/api/v1/ai-platform/*` in OpenAPI (use `/v2/agents` + `/api/v1/ai/*`).
- SaaS: tab-gated marketplace queries; dynamic import of Super Admin charts; `optimizePackageImports` for lucide/recharts.

### Launch readiness
- Playwright E2E pack for 20 public-launch workflows + report generators.
- Final checklist: `docs/launch/FINAL_LAUNCH_CHECKLIST.md`.

## What is in scope

| Area | Status |
|------|--------|
| Core API (FastAPI) | Included |
| PostgreSQL + Alembic | Included |
| Redis (rate limit, jobs, limiter) | Required |
| Worker + scheduler | Included |
| Nginx + SSL manager | Included |
| Prometheus `/metrics` | Included (ACL / token required in hardened env) |
| SaaS app + widget SDK | Included |
| Developer portal / SDKs | Companion apps |

## Upgrade / install

```bash
git checkout v1.0.0
cp .env.prod.example .env.prod   # fill secrets
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
# API container runs: alembic upgrade head && uvicorn ...
```

## Breaking / ops notes

1. Set `APP_ENV=production` — disables `/docs`, `/redoc`, `/openapi.json`.
2. Set explicit `CORS_ORIGINS` — do **not** ship with `*`.
3. Distinct `JWT_SECRET_KEY` and `JWT_REFRESH_SECRET_KEY`.
4. Wire Stripe/Razorpay keys before paid checkout.
5. Replace notification stubs before public signup OTP/email.
6. Restrict `/metrics` (private network or `METRICS_TOKEN`).
7. Prefer `SSL_MODE=certbot` (or edge TLS); avoid `simulate` on public hosts.
8. New clients must use `/v2/agents` — `/ai-platform` is deprecated.

## Companion docs

- [Final Launch Checklist](../../launch/FINAL_LAUNCH_CHECKLIST.md)
- [Production Launch Readiness](../../launch/PRODUCTION_LAUNCH_READINESS.md)
- [Launch Reports](../../launch/reports/)
- Deployment / Operations / Security / Go-No-Go under this folder
