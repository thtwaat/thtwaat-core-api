# Semester 03 · Week 1 — Ollama → OpenAI adapter

**Milestone tag (end of week):** `sem03-w1-ollama-openai`  
**Depends on:** Sem02 `sem02-v1.0.0`  
**Spine:** existing `/v1` + `AIGatewayService` + `OllamaProvider` — **no new repo**

| Day | Topic | Status |
|-----|--------|--------|
| 1 | Architecture + Ollama↔OpenAI adapter contract | Done |
| 2 | Provider registry & default routing | Done |
| 3 | Production-grade InferenceRouter | Done |
| 4 | Debugging: timeouts, missing models, 502 mapping | Done |
| 5 | Security + interview (prompt injection / model exfil) | Done |
| 6 | Milestone build | Done |
| 7 | Review + tag `sem03-w1-ollama-openai` | Locked |

## Week goals

1. One pure adapter module: Ollama `/api/chat` JSON ↔ OpenAI completion shape.
2. Soft live probe for Ollama on `/health` (never blocks `/ready`).
3. Clear ADR: Sem02 control plane stays; Sem03 owns the inference adapter.

## Non-goals this week

- True token-stream from Ollama (Week 2)
- vLLM HTTP backend (Week 4)
- Changing Sem02 webhook/outbox behavior
