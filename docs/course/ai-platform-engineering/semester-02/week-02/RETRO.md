# Week 2 Retrospective — Completions plane

## 1. What shipped

- OpenAI-compatible root `/v1` in THTWAAT core: completions, models, usage  
- Redis: cache, idempotency, tenant rate limits  
- Usage/cost flush into existing Usage Meter + billing spend hook  
- Prod recoveries: API healthcheck start_period, FTS trigger migration, external network  

## 2. What slipped / deferred

- SSE streaming  
- Completion webhooks / worker fan-out  
- Dedicated gateway microservice split  

## 3. Top risks entering Week 3

1. Streaming + idempotency interaction (partial responses)  
2. Webhook delivery at-least-once vs usage double-count  
3. Noisy-neighbor still possible if plan RPM misconfigured in prod env  

## 4. Teaching note

Ship **one day = one concern** (cache ≠ idempotency ≠ rate limit). The VPS FTS failure showed why migrations must match Postgres immutability rules — prefer trigger/helpers when GENERATED columns fight the catalog.

## 5. Milestone

Tag: `sem02-w2-completions`
