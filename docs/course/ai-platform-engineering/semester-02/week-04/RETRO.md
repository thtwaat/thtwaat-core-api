# Week 4 Retrospective — Harden, test, ship

## 1. What shipped

- Postgres `webhook_deliveries` outbox + dual-write from notify
- Worker ACK / dead-letter alignment + stuck-row redrive
- ORM bootstrap so worker queries no longer break on unfinished mappers
- Concurrency smoke + gateway-focused k6 script
- Redis fail-open matrix + partner SSE disconnect billing note
- Sem02 gateway threat model + webhook SSRF guard
- Ship checklist, W4 gate tests, smoke_w4

## 2. What slipped / deferred

- True same-transaction outbox with completion audit row
- Fail-closed rate limiting under Redis outage
- mTLS / IP allowlists for webhook targets
- Dedicated gateway microservice repository

## 3. Top risks entering Sem 03 (inference)

1. Stub vs live gateway load — k6 thresholds assume stub-speed responses  
2. DNS rebinding race on webhook SSRF (resolve-at-check vs resolve-at-connect)  
3. Outbox growth without retention/TTL policy  

## 4. Teaching note

**Availability vs abuse controls:** Redis fail-open keeps `/v1` alive; document the abuse window.  
**Security on the async edge:** sign what you send (HMAC), and refuse where you send it (SSRF).  
**Ship in-place:** Sem02 proved the OpenAI-compatible gateway can live inside the core API without a premature repo split.

## 5. Milestone

Tags: `sem02-w4-gateway-ship`, `sem02-v1.0.0`
