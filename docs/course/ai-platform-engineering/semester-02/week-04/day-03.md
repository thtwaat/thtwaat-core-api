# Semester 02 · Week 4 · Day 3 — Concurrency smoke + gateway k6

**Status:** Implemented  
**Depends on:** Days 1–2 (outbox + worker ACK)  
**Out of scope today:** Redis fail-mode matrix / SSE partner notes (Day 4)

---

## Why today

Ship gate needs evidence that `/v1` holds under concurrent callers and that
idempotency races do not double-execute.

Also: worker ORM bootstrap hardened (`app/database/orm_bootstrap.py`) so outbox
redrive no longer dies on unfinished SQLAlchemy relationship graphs.

---

## Concurrency smoke (pytest)

| Test | Asserts |
|------|---------|
| `test_concurrent_stub_completions_unique_ids` | 8 parallel stub completions → 8 unique ids |
| `test_concurrent_idempotency_only_one_proceeds` | 12 threads, one key → exactly one `proceed`, rest `idempotency_in_progress` |
| `test_orm_bootstrap_idempotent` | `register_orm_models()` safe to call twice |

```bash
python -m pytest tests/unit/openai_compat/test_concurrency_smoke.py -q
```

---

## k6 gateway script

File: `performance/k6/openai_compat.js`

Per VU iteration: JSON completion + SSE stream + `GET /v1/models`.

```bash
export BASE_URL=http://127.0.0.1:8000   # or https://api.yourdomain
export API_KEY=tht_live_...
k6 run performance/k6/openai_compat.js
# heavier:
k6 run -e VUS=20 -e DURATION=30s performance/k6/openai_compat.js
```

Thresholds (defaults): p95 &lt; 2s, failure rate &lt; 5%.

---

## Lab checklist (Day 3)

- [x] Concurrency unit smoke
- [x] k6 `openai_compat.js`
- [x] Worker ORM bootstrap fix (Company → User → …)
- [ ] Run k6 against local or VPS (ops)
- [ ] Confirm worker logs clean (no mapper errors)

---

## Tomorrow (Day 4)

Debugging: Redis fail-open/closed matrix + partner note for SSE disconnect billing.

**Stop here — await approval before Day 4.**
