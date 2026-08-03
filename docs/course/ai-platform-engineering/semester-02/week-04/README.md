# Semester 02 · Week 4 — Harden, test, performance, ship

**Milestone tag (end of week):** `sem02-w4-gateway-ship`  
**Final ship tag:** `sem02-v1.0.0`  
**Depends on:** Week 3 `sem02-w3-async-edge`  
**Spine:** THTWAAT core API as the OpenAI-compatible gateway (no separate repo this week)

| Day | Topic | Status |
|-----|--------|--------|
| 1 | Architecture + durable webhook outbox contract | Done |
| 2 | Worker claim / ACK / redrive from outbox | Done |
| 3 | Concurrency smoke + gateway k6 scripts | Done |
| 4 | Debugging: Redis fail modes + partner SSE notes | Done |
| 5 | Threat model + interview drill | Done |
| 6 | Milestone harden (checklist + gate tests) | Done |
| 7 | Review + tags `sem02-w4-gateway-ship` / `sem02-v1.0.0` | Done |

## Week goals

1. Close W3 durability gap: Postgres `webhook_deliveries` outbox + Redis fan-out.
2. Prove concurrency / load readiness for `/v1` completions (JSON + SSE).
3. Publish Sem02 gateway threat model + production ship checklist.
4. Tag a shippable OpenAI-compatible gateway surface in core API.

## Non-goals this week

- Split into a separate `thtwaat-gateway` microservice repo
- Kafka / NATS (Sem 04)
- mTLS for webhook targets (document only unless trivial)
- Wildcard DNS-01 SSL automation
