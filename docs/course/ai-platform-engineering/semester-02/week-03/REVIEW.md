# Week 3 Review — `sem02-w3-async-edge`

**Date:** 2026-08-03  
**Scope:** completion webhooks via Redis worker, delayed retries / DLQ, SSE streaming, stream×idempotency, HMAC v1  
**Blockers:** none

---

## A. Async fan-out (Days 1–2)

| Item | Status | Evidence |
|------|--------|----------|
| `completion.succeeded` / `.failed` after persist | Pass | `service.py` → `_notify_completion` |
| Job type `webhook.dispatch` on `thtwaat:jobs` | Pass | `notify.py` + `scripts/worker.py` |
| Fail-open if Redis down | Pass | notify soft-fail |
| No sync `requests.post` on request path | Pass | enqueue only |
| Retries → delayed ZSET → dead-letter | Pass | `queue.enqueue_delayed` / `dead_letter` |
| `WEBHOOK_MAX_ATTEMPTS` + backoff settings | Pass | `settings.py` + `delivery.py` |
| Cache HIT / idempotent replay: no second enqueue | Pass | service paths (Day 1/4 design) |

## B. SSE streaming (Days 3–4)

| Item | Status | Evidence |
|------|--------|----------|
| `stream=true` → `text/event-stream` | Pass | `router.py` + `streaming.py` |
| Persist + usage + webhook **before** SSE frames | Pass | `build_stream_material` |
| Stub / gateway piece-stream | Pass | `streaming.py` |
| Idempotency-Key + stream store full JSON then re-chunk | Pass | Day 4 `material_from_stored_response` |
| Replay header `Idempotent-Replayed` | Pass | router + smoke |
| Replay skips rate-limit consume | Pass | Day 4 tests |
| Hash includes `stream` flag | Pass | idempotency |

## C. Security (Day 5)

| Item | Status | Evidence |
|------|--------|----------|
| Sign `v1={hmac}` over `{t}.{body}` | Pass | `delivery.sign_v1` |
| Headers `X-THTWAAT-Timestamp` + `X-THTWAAT-Signature` | Pass | `deliver_webhook` |
| Timestamp tolerance (300s default) | Pass | `verify_webhook_signature` |
| Stable `delivery_id` (`whdel_…`) at enqueue | Pass | `notify` + `new_delivery_id` |
| Legacy `sha256=` still verifiable | Pass | verify path |

## D. Milestone polish (Day 6)

| Item | Status | Evidence |
|------|--------|----------|
| `estimated_cost` on succeeded event data | Pass | `events.py` + service |
| Usage sync vs webhook async (no double-bill) | Pass | day-06 matrix |
| Smoke script | Pass | `scripts/smoke_w3_openai_compat.sh` |
| Gate unit tests | Pass | `test_week3_gate.py` |

## E. Engineering hygiene

| Item | Status | Evidence |
|------|--------|----------|
| Unit tests Days 1–6 (notify, stream, signature, gate) | Pass | `tests/unit/openai_compat/` |
| Course docs Days 1–7 | Pass | `docs/course/.../week-03/` |
| Spine remains Redis worker — **no Celery** | Pass | `scripts/worker.py` |
| Secrets not in git | Pass | Review status |

---

## Known debt (≤5, non-blocking)

1. No durable `webhook_deliveries` outbox table (Redis-only; W4 candidate)  
2. Customer endpoint e2e smoke against live webhook URL optional / not CI-gated  
3. Separate `thtwaat-gateway` repo still curriculum-only  
4. mTLS / IP allowlists for webhook targets deferred  
5. Load-test / k6 for SSE + worker depth not attached to this tag  

**Verdict:** Ready to tag `sem02-w3-async-edge`.
