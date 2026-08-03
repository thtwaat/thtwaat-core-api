# Sem02 Gateway Ship Checklist — `sem02-w4-gateway-ship` / `sem02-v1.0.0`

**Date:** 2026-08-03  
**Surface:** THTWAAT core API OpenAI-compatible `/v1`  
**Prerequisite tags:** `sem02-w1-api-core`, `sem02-w2-completions`, `sem02-w3-async-edge`

Use this before Day 7 tag ceremony. Ops items marked **ops** are env/network, not code blockers.

---

## A. API surface

| Check | Status |
|-------|--------|
| `GET /v1/models` (+ pagination) | Code ✓ |
| `GET /v1/models/{id}` | Code ✓ |
| `POST /v1/chat/completions` JSON | Code ✓ |
| `POST /v1/chat/completions` SSE `stream=true` | Code ✓ |
| `GET /v1/usage` | Code ✓ |
| Auth 401 without Bearer `tht_*` | Code ✓ / gate test |
| `X-Request-ID` middleware | Code ✓ |

## B. Redis controls

| Check | Status |
|-------|--------|
| Cache HIT/MISS | Code ✓ |
| Idempotency-Key JSON + SSE | Code ✓ |
| Rate limits + `Retry-After` | Code ✓ |
| Redis down → fail-open (documented) | Code ✓ / Day 4 tests |

## C. Async edge

| Check | Status |
|-------|--------|
| `webhook.dispatch` via Redis worker | Code ✓ |
| Delayed retry + dead-letter | Code ✓ |
| HMAC v1 + `delivery_id` | Code ✓ |
| `webhook_deliveries` outbox dual-write | Code ✓ |
| Worker ACK + redrive + ORM bootstrap | Code ✓ |
| SSRF guard on webhook URL | Code ✓ / Day 5 tests |

## D. Evidence

| Check | Command / path |
|-------|----------------|
| Unit gate W4 | `pytest tests/unit/openai_compat/test_week4_gate.py -q` |
| Broader openai_compat | `pytest tests/unit/openai_compat/ -q` |
| Smoke W3/W4 | `bash scripts/smoke_w4_openai_compat.sh` |
| k6 (optional) | `k6 run performance/k6/openai_compat.js` |
| Threat model | `docs/.../week-04/THREAT_MODEL.md` |
| Partner SSE | `docs/partners/openai-compat-sse.md` |

## E. Production (ops)

| Check | Owner |
|-------|--------|
| `alembic current` includes `g1a2b3c4d5e6` | ops |
| CORS not `*` with credentials | ops (SECURITY_REVIEW S1) |
| `/metrics` network-restricted | ops (S3) |
| Live SSL mode if public domains | ops (S4) |
| Worker logs clean (no mapper errors) | ops |

## F. Explicit non-goals (accepted debt)

- Separate `thtwaat-gateway` microservice repo  
- Kafka / transactional outbox beyond Postgres table  
- mTLS to customer webhooks  
- Fail-closed rate limits when Redis is down  

---

**Day 6 DoD:** sections A–D code evidence green → unlock Day 7 REVIEW + tags.
