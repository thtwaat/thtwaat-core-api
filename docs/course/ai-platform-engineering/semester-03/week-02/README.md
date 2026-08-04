# Semester 03 · Week 2 — Catalog sync + true local streaming

**Milestone tag (end of week):** `sem03-w2-local-stream`  
**Depends on:** Week 1 `sem03-w1-ollama-openai`

| Day | Topic | Status |
|-----|--------|--------|
| 1 | Production streaming engine (OpenAI-compatible SSE) | Done |
| 2 | Production streaming reliability (routing, fallback, timeouts) | Done |
| 3 | Health-aware provider fallback & intelligent routing | Done |
| 4 | Locked | Locked |
| 5 | Locked | Locked |
| 6 | Locked | Locked |
| 7 | Review + tag `sem03-w2-local-stream` | Locked |

## Week goals

1. True token SSE from local/cloud providers behind `/v1`.
2. Model catalog sync from Ollama tags (later days).
3. Keep Sem02 metering / idempotency contracts intact where possible.

## Non-goals this week

- Voice / image modalities  
- Parallel fan-out streaming  
- Full circuit-breaker product (Day 3 uses health-cache TTL cooldown only)
