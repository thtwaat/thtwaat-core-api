# Week 1 Retrospective — Ollama → OpenAI inference spine

## 1. What shipped

- Pure Ollama ↔ OpenAI adapter + soft `/health` probe
- Dynamic provider registry with env enable flags and default routing
- Health-aware InferenceRouter (policies, capabilities, TTL cache, metrics)
- OpenAI-shaped failure taxonomy (404 / 400 / 503 / 502 / 504)
- Prompt injection / model-exfil edge guard + inference threat notes
- Ship checklist, W1 gate tests, smoke script

## 2. What slipped / deferred

- True local token streaming from Ollama
- Live model catalog sync from daemon tags
- Full live cloud provider HTTP (routing proven with synthetics)
- Retry / circuit breaker / parallel inference

## 3. Top risks entering Week 2

1. Streaming must preserve Sem02 metering, idempotency, and webhook semantics  
2. Catalog sync can thrash `/v1/models` cache if TTL/invalidation is wrong  
3. Prompt-guard heuristics will have false positives — need `log` mode soak before hard prod enforcement on all tenants  

## 4. Teaching note

**Control plane vs inference plane:** Sem02 ownership of keys/usage/webhooks stayed intact; Sem03 added an inference adapter and router behind the same `/v1`.  
**Fail soft:** Ollama down must not fail `/ready`; timeouts and unhealthy providers map to clear client errors.  
**Security at the edge:** same pattern as Sem02 SSRF — assert-safe before expensive side effects.

## 5. Milestone

Tag: `sem03-w1-ollama-openai`
