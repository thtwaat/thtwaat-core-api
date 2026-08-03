# Week 4 Review — `sem02-w4-gateway-ship` / `sem02-v1.0.0`

**Date:** 2026-08-03  
**Scope:** durable webhook outbox, worker ACK/redrive, concurrency + k6, Redis fail modes, threat model, SSRF guard, ship checklist  
**Blockers:** none

---

## A. Durable async edge (Days 1–2)

| Item | Status | Evidence |
|------|--------|----------|
| `webhook_deliveries` table + Alembic `g1a2b3c4d5e6` | Pass | migration + VPS `\d` |
| Dual-write pending → Redis → queued | Pass | `notify.py` + `outbox.py` |
| Worker ACK delivered / failed / dead | Pass | `scripts/worker.py` |
| Stuck-row redrive (pending/queued/failed) | Pass | `redrive_stuck_deliveries` |
| ORM bootstrap for worker/scheduler | Pass | `orm_bootstrap.py` |
| Secrets not stored on outbox rows | Pass | redrive loads `webhooks.secret` |

## B. Load / concurrency (Day 3)

| Item | Status | Evidence |
|------|--------|----------|
| Concurrent stub completions unique ids | Pass | `test_concurrency_smoke.py` |
| Idempotency race → one proceed | Pass | same (needs fakeredis when available) |
| k6 `openai_compat.js` (JSON + SSE + models) | Pass | `performance/k6/openai_compat.js` |

## C. Resilience + partners (Day 4)

| Item | Status | Evidence |
|------|--------|----------|
| Cache / idempotency / rate-limit fail-open | Pass | `test_redis_fail_open.py` + day-04 matrix |
| SSE disconnect still billed (documented) | Pass | `docs/partners/openai-compat-sse.md` |

## D. Security (Day 5)

| Item | Status | Evidence |
|------|--------|----------|
| Sem02 gateway THREAT_MODEL | Pass | `week-04/THREAT_MODEL.md` |
| Webhook URL SSRF guard (create + deliver) | Pass | `url_safety.py` + tests |
| Interview drill | Pass | `day-05.md` |

## E. Ship harden (Day 6)

| Item | Status | Evidence |
|------|--------|----------|
| SHIP_CHECKLIST | Pass | `SHIP_CHECKLIST.md` |
| Week 4 gate unit tests | Pass | `test_week4_gate.py` |
| Smoke W4 wrapper | Pass | `scripts/smoke_w4_openai_compat.sh` |

## F. Engineering hygiene

| Item | Status | Evidence |
|------|--------|----------|
| Course docs Days 1–7 | Pass | `docs/course/.../week-04/` |
| Spine remains Redis worker — no Celery | Pass | worker |
| Gateway stays in core API (no repo split) | Pass | Sem02 decision |
| Secrets not in git | Pass | Review status |

---

## Known debt (≤5, non-blocking)

1. Same-TX outbox with completion log (still dual-commit after persist)  
2. Fail-closed rate limits when Redis is down (product decision)  
3. mTLS to customer webhooks  
4. Live customer webhook URL e2e in CI  
5. Separate `thtwaat-gateway` microservice repo (curriculum-only)

**Verdict:** Ready to tag `sem02-w4-gateway-ship` and Sem02 final `sem02-v1.0.0`.
