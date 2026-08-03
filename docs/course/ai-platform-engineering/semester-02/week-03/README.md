# Semester 02 · Week 3 — Async edge (jobs, webhooks, usage)

**Milestone tag (end of week):** `sem02-w3-async-edge`  
**Depends on:** Week 2 `sem02-w2-completions`  
**Spine:** existing Redis worker (`scripts/worker.py` → `thtwaat:jobs`) — **no Celery**

| Day | Topic | Status |
|-----|--------|--------|
| 1 | Architecture + `webhook.dispatch` job contract | Done |
| 2 | Worker delivery + retries / dead-letter | Done |
| 3 | SSE streaming (`stream=true`) | Done |
| 4 | Streaming × idempotency / debugging | Done |
| 5 | Security (HMAC, replay) + interview drill | Done |
| 6 | Milestone build (usage flush + fan-out polish) | Locked |
| 7 | Review + tag `sem02-w3-async-edge` | Locked |

## Week goals

1. Fan-out `completion.succeeded` / `completion.failed` via Redis jobs (not sync `requests.post` on the request path).
2. Reuse `Webhook` subscriptions + HMAC `X-THTWAAT-Signature`.
3. Add SSE streaming for `/v1/chat/completions` without breaking Week 2 controls.
4. Keep usage metering sync on the request path; webhooks are **at-least-once** and must not double-bill.

## Non-goals this week

- Separate gateway microservice repo
- Kafka / transactional outbox table (decide Day 5 whether W4 needs it)
- Wildcard DNS-01 SSL automation
