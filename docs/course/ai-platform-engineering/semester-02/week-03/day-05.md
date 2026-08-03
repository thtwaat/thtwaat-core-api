# Semester 02 · Week 3 · Day 5 — Webhook HMAC security + interview drill

**Status:** Implemented (`sign_v1` / `verify_webhook_signature` + `delivery_id`)  
**Depends on:** Days 1–2 delivery path  
**Out of scope today:** mTLS, IP allowlists, full webhook_deliveries outbox table

---

## Threat model (outbound webhooks)

| Threat | Mitigation |
|--------|------------|
| Forged events | HMAC-SHA256 over `{t}.{body}` with per-hook `whsec_` |
| Replay of captured POST | `X-THTWAAT-Timestamp` + tolerance window (default **300s**) |
| Double-processing on our retries | Stable `delivery_id` (`whdel_…`) across attempts |
| Timing attacks on compare | `hmac.compare_digest` |
| Secret leak in logs | Never log raw secrets; only delivery_id / event |

### Headers (Day 5)

```http
Content-Type: application/json
X-THTWAAT-Timestamp: 1700000111
X-THTWAAT-Signature: v1=<hex>
User-Agent: THTWAAT-Webhook/1.0
```

Receiver (Python sketch):

```python
from app.webhooks.delivery import verify_webhook_signature

verify_webhook_signature(
    raw_body,
    whsec,
    signature_header=request.headers["X-THTWAAT-Signature"],
    timestamp_header=request.headers["X-THTWAAT-Timestamp"],
)
# then dedupe on payload["delivery_id"]
```

Legacy `sha256=<hex>` (body-only) still verifies for old docs, but **new deliveries use v1**.

### Settings

```text
WEBHOOK_SIGNATURE_TOLERANCE_SECONDS=300
```

---

## Interview drill (answer out loud)

1. **Why sign `t.body` instead of body alone?**  
   → Binds the signature to a freshness claim so a captured POST cannot be replayed forever.

2. **At-least-once delivery vs exactly-once billing — how do you not double-charge?**  
   → Meter on the request path once; webhooks are notifications. Customer dedupes on `delivery_id` / `completion_id`.

3. **What if the customer endpoint is slow (30s)?**  
   → Short timeout (5s), retry with backoff, dead-letter; do not block the API worker pool on the request thread (we already enqueue).

4. **Should Idempotency-Key apply to webhook HTTP?**  
   → Different layer: our Redis job retries reuse the same `delivery_id`; customer treats that id as idempotent.

5. **Fail-open enqueue vs fail-closed?**  
   → Completions stay available if Redis is down (soft-fail notify). Trade-off: possible missed webhooks — monitor queue depth / dead letter.

---

## Lab checklist (Day 5)

- [x] `sign_v1` + timestamp headers on deliver
- [x] `verify_webhook_signature` with tolerance / tamper / legacy
- [x] Stable `delivery_id` on enqueue
- [x] Unit tests
- [ ] Manual: receive with a requestbin and verify signature offline

---

## Tomorrow (Day 6)

Milestone polish — usage flush + fan-out hardening, smoke script.

**Stop here — await approval before Day 6.**
