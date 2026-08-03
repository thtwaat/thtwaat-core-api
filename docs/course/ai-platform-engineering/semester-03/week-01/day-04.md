# Semester 03 · Week 1 · Day 4 — Debugging: timeouts, missing models, 502 mapping

**Status:** Implemented  
**Depends on:** Day 3 InferenceRouter  
**Out of scope today:** Streaming, retries, circuit breaker, load balancing, 429 capacity taxonomy (Week 3)

---

## Failure taxonomy

| Condition | HTTP | `error.code` | Source |
|-----------|------|--------------|--------|
| Unknown / unlistable model | **404** | `model_not_found` | Router / Day 2 resolver |
| Unknown or disabled provider | **400** | `unknown_provider` | Router / Day 2 resolver |
| All capable owners unhealthy | **503** | `no_healthy_provider` | InferenceRouter |
| Upstream timeout | **504** | `upstream_timeout` | `map_provider_exception` |
| Upstream HTTP / transport fail | **502** | `upstream_error` | `map_provider_exception` |
| Provider misconfigured | **502** | `provider_config_error` | `ProviderConfigError` |

OpenAI-shaped body (unchanged Sem02 contract):

```json
{ "error": { "message": "...", "type": "api_error|invalid_request_error", "code": "..." } }
```

`HTTPException` from the router is **never** rewritten into `upstream_error`.

---

## What shipped

| Piece | Path |
|-------|------|
| Shared mapper | `app/openai_compat/errors.py` |
| Typed errors | `ProviderTimeoutError`, `ProviderUpstreamError` in `providers/base.py` |
| Ollama timeout | `INFERENCE_OLLAMA_TIMEOUT_SECONDS` (default `120`) |
| Completions | catch paths → `map_provider_exception` |
| Tests | `tests/unit/openai_compat/test_inference_errors.py` |

---

## Env

```text
INFERENCE_OLLAMA_TIMEOUT_SECONDS=120
```

Lab tip: set to `2` and stop Ollama to observe **504** `upstream_timeout`.

---

## Lab checklist (Day 4)

- [x] Shared OpenAI error mapper  
- [x] Timeout → 504 `upstream_timeout`  
- [x] Missing model stays 404  
- [x] Upstream fail → 502 `upstream_error`  
- [x] Router HTTPException not double-wrapped  
- [ ] Manual: wrong model id → 404; Ollama down + tiny timeout → 504  

---

## Tomorrow (Day 5)

Security + interview (prompt injection / model exfil) — locked until approved.

**Stop here — await approval before Day 5.**
