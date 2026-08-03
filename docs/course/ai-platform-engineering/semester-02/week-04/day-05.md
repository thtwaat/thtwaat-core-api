# Semester 02 · Week 4 · Day 5 — Threat model + interview drill

**Status:** Implemented (gateway threat model + webhook SSRF guard)  
**Depends on:** Days 1–4  
**Out of scope today:** mTLS, fail-closed rate limits, Day 6 ship checklist

---

## Artifacts

| File | Purpose |
|------|---------|
| [THREAT_MODEL.md](./THREAT_MODEL.md) | Sem02 `/v1` STRIDE + trust boundaries |
| `app/webhooks/url_safety.py` | Block localhost / private / link-local / metadata |
| Wired in | `WebhookService.create_webhook`, `deliver_webhook` |

### Settings

```text
WEBHOOK_URL_SSRF_GUARD_ENABLED=true
WEBHOOK_ALLOW_HTTP_URLS=false
WEBHOOK_URL_RESOLVE_DNS=true
```

---

## Interview drill (answer out loud)

1. **Where does tenancy authority come from on `/v1`?**  
   → API key → `company_id` in auth dependency. Never trust body/`X-Tenant-Id`.

2. **Redis is down — do you fail closed on rate limits?**  
   → Today **fail-open** (availability). Documented trade-off; abuse window until Redis returns. Billing still Postgres.

3. **Why is webhook delivery at-least-once acceptable?**  
   → Usage meters once on the request path; receivers dedupe on `delivery_id`.

4. **How do you stop a tenant from pointing webhooks at `169.254.169.254`?**  
   → SSRF guard on create + deliver (scheme, host denylist, private IP ranges, optional DNS resolve).

5. **SSE client hangs up at 50% — is that free?**  
   → No. Materialize-before-stream: usage/webhooks already committed. See partner SSE note.

6. **Idempotency-Key vs webhook `delivery_id`?**  
   → Different layers: client→gateway dedupe vs gateway→customer delivery dedupe.

---

## Lab checklist (Day 5)

- [x] THREAT_MODEL.md  
- [x] `assert_safe_webhook_url` + create/deliver wiring  
- [x] Unit tests for SSRF cases  
- [ ] Manual: try create webhook to `https://127.0.0.1/` → 400  

---

## Tomorrow (Day 6)

Milestone harden — Sem02 ship checklist + week-4 gate tests.

**Stop here — await approval before Day 6.**
