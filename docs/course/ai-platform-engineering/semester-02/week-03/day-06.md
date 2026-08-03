# Semester 02 · Week 3 · Day 6 — Milestone polish

**Status:** Implemented (cost on webhook payload + W3 smoke + gate tests)  
**Depends on:** Days 1–5  
**Out of scope today:** Tag / REVIEW (Day 7)

---

## Polish shipped

| Item | Change |
|------|--------|
| Usage → webhook | `estimated_cost` included on `completion.succeeded` event data |
| Fan-out | Still Redis `webhook.dispatch` + v1 HMAC + stable `delivery_id` |
| Smoke | `scripts/smoke_w3_openai_compat.sh` — JSON idempotency, SSE, SSE replay, usage |
| Gate tests | `tests/unit/openai_compat/test_week3_gate.py` |

### Usage vs webhook (do not confuse)

```text
Request path:  record_completion_usage()  →  meters / spend  (once)
Async path:    enqueue completion.*       →  notify customer (at-least-once)
Idempotent replay: NO second meter, NO second enqueue
```

### Smoke

```bash
export API_BASE=http://127.0.0.1:8000
export API_KEY=tht_live_...
bash scripts/smoke_w3_openai_compat.sh
```

Checks: live, JSON+idempotency header, SSE chunks + `[DONE]`, SSE replay `Idempotent-Replayed: true`, `/v1/usage`.

---

## Lab checklist (Day 6)

- [x] Cost on completion webhook payload
- [x] W3 smoke script
- [x] Week 3 gate unit tests
- [ ] Run smoke against local/staging stack
- [ ] Confirm worker consumes `webhook.dispatch` (optional with a test URL)

---

## Tomorrow (Day 7)

REVIEW.md + RETRO.md + annotated tag `sem02-w3-async-edge`.

**Stop here — await approval before Day 7.**
