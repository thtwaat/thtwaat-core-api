# Week 2 Review — `sem02-w2-completions`

**Date:** 2026-08-03  
**Scope:** `app/openai_compat/*`, related settings, Alembic `f2a3b4c5d6e7`, prod healthcheck, FTS trigger migration  
**Blockers:** none

---

## A. Product / API contract

| Item | Status | Evidence |
|------|--------|----------|
| `POST /v1/chat/completions` | Pass | `app/openai_compat/router.py` |
| `GET /v1/models` + `/{id}` | Pass | Router + `ModelsService` |
| Pagination `limit`/`offset` (1–100) | Pass | Day 6 harden |
| Auth required (401) | Pass | Unit tests + smoke |
| OpenAPI `AgentAPIKey` on `/v1/*` | Pass | `openapi_security._AGENT_API_KEY_PATHS` |
| `stream:true` rejected | Pass | Service 400 `stream_not_supported` |
| `GET /v1/usage` | Pass | Day 5 |

## B. Redis controls

| Item | Status | Evidence |
|------|--------|----------|
| Model metadata cache + TTL | Pass | `cache.py` / Day 2 |
| Response cache only `temperature==0` | Pass | Tests |
| `X-Cache` headers | Pass | Router |
| Idempotency-Key + replay / 409 | Pass | Day 3 tests |
| Tenant rate limits + `Retry-After` | Pass | Day 4 |
| Idempotent replay skips rate burn | Pass | Day 4 test |

## C. Tenancy & metering

| Item | Status | Evidence |
|------|--------|----------|
| Company derived from API key only | Pass | `dependencies.py` |
| Completion audit log | Pass | `openai_completion_logs` |
| UsageService flush + cost | Pass | `usage.py` |
| Cache HIT / idempotent replay do not double-bill | Pass | Design + service path |

## D. Reliability / prod

| Item | Status | Evidence |
|------|--------|----------|
| `/live` liveness (no DB) | Pass | `main.py` + prod healthcheck |
| API `start_period` 120s | Pass | `docker-compose.prod.yml` |
| FTS migration immutable (trigger) | Pass | `e1f2a3b4c5d6` → VPS applied |
| Shared network `external: true` | Pass | Day 6 compose fix |
| `X-Request-ID` | Pass | `RequestContextMiddleware` |

## E. Engineering hygiene

| Item | Status | Evidence |
|------|--------|----------|
| Unit tests Days 1–5 + gate | Pass | `tests/unit/openai_compat/` |
| Course docs Days 1–7 | Pass | `docs/course/.../week-02/` |
| Smoke script | Pass | `scripts/smoke_w2_openai_compat.sh` |
| Secrets not in git | Pass | Review status |

---

## Known debt (≤5, non-blocking)

1. SSE `stream:true` deferred to later week  
2. Customer webhooks on completion events → Week 3  
3. Separate `thtwaat-gateway` repo still curriculum-only; shipped in core API  
4. Models `owned=` filter not on openai_compat catalog (static + tenant DB merge)  
5. Load-test / k6 suite not yet attached to this tag  

**Verdict:** Ready to tag `sem02-w2-completions`.
