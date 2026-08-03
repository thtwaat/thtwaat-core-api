# Semester 03 · Week 1 · Day 3 — Production-grade InferenceRouter

**Status:** Implemented  
**Depends on:** Day 2 provider registry  
**Out of scope today:** Streaming, retries, circuit breaker, load balancing, parallel inference

---

## What shipped

| Piece | Path |
|-------|------|
| Router | `app/openai_compat/providers/inference_router.py` — `InferenceRouter` |
| Service | `app/openai_compat/inference_routing_service.py` |
| Repository | `app/openai_compat/inference_routing_repository.py` — priority / cost / latency / quality / capabilities |
| Health cache | `app/openai_compat/providers/health_cache.py` (TTL) |
| Metrics | `app/openai_compat/providers/metrics.py` |
| Capabilities | `app/openai_compat/providers/capabilities.py` |
| Completions | gateway mode → `InferenceRoutingService.chat()` |

### Routing policies (`INFERENCE_ROUTING_POLICY`)

| Policy | Behavior |
|--------|----------|
| `default` | Prefer `INFERENCE_DEFAULT_PROVIDER`, then provider priority |
| `preferred_provider` | Same preference axis (default / explicit preferred) |
| `cheapest` | Lowest profile `cost` among healthy capable owners |
| `fastest` | Lowest profile `latency_ms` |
| `highest_quality` | Highest profile `quality` |

Health-aware: unhealthy providers are **skipped** at selection time (not retried after failure). If none remain → **503** `no_healthy_provider`. Optional `INFERENCE_FALLBACK_PROVIDER` is added to the candidate pool when it owns the model.

### Capabilities

`chat` · `embeddings` · `image_generation` · `speech_to_text` · `text_to_speech`

### Env

```text
INFERENCE_ROUTING_POLICY=default
INFERENCE_DEFAULT_PROVIDER=ollama
INFERENCE_FALLBACK_PROVIDER=openai
INFERENCE_HEALTH_CACHE_TTL_SECONDS=30
INFERENCE_PROVIDER_PRIORITY=   # optional: ollama,vllm,openai,gemini,anthropic
```

### Metrics (in-process; also under `/health` → `inference_providers.routing_metrics`)

- `provider_selected`
- `provider_latency_ms`
- `provider_errors`
- `routing_time_ms`

Architecture stays **repository + service** — no policy logic in FastAPI routers.

---

## Lab checklist (Day 3)

- [x] InferenceRouter + five policies  
- [x] Health-aware skip + TTL cache  
- [x] Capability detection  
- [x] Fallback provider config  
- [x] Provider priority  
- [x] Metrics  
- [x] Unit tests  
- [ ] Manual: set `INFERENCE_ROUTING_POLICY=cheapest` and confirm ollama wins for a multi-owner model

---

## Tomorrow (Day 4)

Lab / debugging path (timeouts, missing models, 502 mapping) — locked until approved.

**Stop here — await approval before Day 4.**
