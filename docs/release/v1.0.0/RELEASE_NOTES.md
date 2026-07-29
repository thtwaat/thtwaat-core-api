# THTWAAT AI Platform v1.0.0 — Release Notes

**Release date:** 2026-07-30  
**API version:** `1.0.0` (`main.py`)  
**Migration head:** `a7b8c9d0e1f2`  
**Git commit baseline:** `638b7d7` (enterprise + onboarding + monitoring + copilot)

## Highlights

THTWAAT v1.0.0 is the first production-tagged release of the multi-tenant AI platform: auth, agents, knowledge, marketplace, product generation, publish, domains/SSL, branding, billing hooks, enterprise governance, onboarding, ops monitoring, and AI Copilot orchestration.

## What is in scope

| Area | Status |
|------|--------|
| Core API (FastAPI) | Included |
| PostgreSQL + Alembic | Included |
| Redis (rate limit, jobs, limiter) | Required |
| Worker + scheduler | Included |
| Nginx + SSL manager | Included |
| Prometheus `/metrics` | Included |
| Developer portal / SDKs / mobile starters | Included as companion apps |

## Upgrade / install

```bash
git checkout v1.0.0   # or main at release tag
cp .env.example .env  # if present; otherwise copy from ops secrets store
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
# API container runs: alembic upgrade head && uvicorn ...
```

Manual migration:

```bash
alembic upgrade head
```

## Breaking / ops notes

1. Set `APP_ENV=production` — disables `/docs`, `/redoc`, `/openapi.json`.
2. Set explicit `CORS_ORIGINS` — do **not** ship with `*`.
3. Configure `JWT_SECRET_KEY` and `JWT_REFRESH_SECRET_KEY` as long random secrets.
4. Wire Stripe/Razorpay keys before enabling paid checkout.
5. Replace notification stubs before relying on email/push alerts.
6. Restrict `/metrics` to private networks / Prometheus scrape ACL.

## Companion docs

See `docs/release/v1.0.0/`:

- Deployment Guide
- Operations Guide
- Administrator Guide
- Developer Guide
- API Guide
- E2E Checklist
- Security Review
- Go/No-Go Checklist
- Risk Register
- Known Issues
