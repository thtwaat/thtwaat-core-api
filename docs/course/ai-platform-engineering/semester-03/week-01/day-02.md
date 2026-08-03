# Semester 03 · Week 1 · Day 2 — Provider registry & default routing

**Status:** Implemented  
**Depends on:** Day 1 adapter  
**Out of scope today:** Streaming, routing policies, retries, fallback (later days)

---

## What shipped

| Piece | Path |
|-------|------|
| Interface | `app/openai_compat/providers/base.py` — `chat` / `embeddings` / `health` / `models` |
| Registry | `app/openai_compat/providers/registry.py` |
| Routing | `app/openai_compat/providers/routing.py` |
| Providers | `ollama`, `openai`, `gemini`, `anthropic`, `vllm` (stub) |
| Catalog | `catalog.py` lists **enabled** providers only |
| Completions | gateway mode → `resolve_provider_for_request` → `provider.chat()` |
| Health | `/health` → `inference_providers` aggregate (API stays up if one is down) |

### Default routing

1. Unknown model (not in any **enabled** catalog) → **404** `model_not_found`  
2. Explicit unknown/disabled provider → **400** `unknown_provider`  
3. Provider omitted → **model → provider** map (prefers `INFERENCE_DEFAULT_PROVIDER=ollama` when tied)  
4. `resolve_provider_name(None)` → `ollama`

### Env flags

```text
INFERENCE_DEFAULT_PROVIDER=ollama
INFERENCE_ENABLE_OLLAMA=true
INFERENCE_ENABLE_OPENAI=true
INFERENCE_ENABLE_GEMINI=true
INFERENCE_ENABLE_ANTHROPIC=true
INFERENCE_ENABLE_VLLM=false
VLLM_BASE_URL=   # optional, stub only
```

Disabled providers do **not** appear in `GET /v1/models`.

---

## Lab checklist (Day 2)

- [x] Dynamic registry registration  
- [x] Default provider ollama + model→provider resolution  
- [x] Unknown model 404 / unknown provider 400  
- [x] Disabled provider excluded from catalog  
- [x] Aggregate health fail-soft  
- [x] Unit tests  
- [ ] Manual: set `INFERENCE_ENABLE_OPENAI=false` and confirm `gpt-4o` gone from `/v1/models`

---

## Tomorrow (Day 3)

Production-grade InferenceRouter (policies, health-aware routing) — see [day-03.md](./day-03.md).

**Day 2 complete.**
