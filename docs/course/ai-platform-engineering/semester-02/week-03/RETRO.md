# Week 3 Retrospective — Async edge

## 1. What shipped

- Completion webhooks via Redis `webhook.dispatch` (not sync HTTP on the request path)
- Delayed retries + dead-letter on the existing worker spine
- SSE `stream=true` with persist/usage/notify before frames
- Stream × Idempotency-Key: store full JSON, replay as SSE chunks
- Timestamped HMAC `v1` + stable `delivery_id`
- Milestone polish: `estimated_cost` on payloads, W3 smoke + gate tests

## 2. What slipped / deferred

- Transactional outbox / `webhook_deliveries` table
- Dedicated gateway microservice split
- mTLS / IP allowlists for webhook receivers
- Automated e2e against a real customer webhook URL in CI

## 3. Top risks entering Week 4

1. Redis-only job durability — process crash between dequeue and ACK can lose or duplicate deliveries without an outbox
2. At-least-once webhooks vs customer-side idempotency (they must key on `delivery_id`)
3. SSE clients that disconnect mid-stream still billed/notified (by design) — document for partners

## 4. Teaching note

Keep **usage metering sync** and **fan-out async**. Streaming does not change that boundary: materialize the completion first, then speak SSE. Idempotency for streams means “replay the finished artifact,” not “resume a half-sent socket.”

## 5. Milestone

Tag: `sem02-w3-async-edge`
