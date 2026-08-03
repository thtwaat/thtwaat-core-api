# Sem03 Week 1 Ship Checklist — `sem03-w1-ollama-openai`

**Date:** 2026-08-03  
**Surface:** Inference adapter + provider registry/router behind existing `/v1`  
**Prerequisite:** Sem02 `sem02-v1.0.0`

Use this before Day 7 tag ceremony. Ops items are env/network, not code blockers.

---

## A. Adapter + health (Day 1)

| Check | Status |
|-------|--------|
| `inference_adapter` Ollama ↔ OpenAI map | Code ✓ |
| Soft `ollama_live` on `/health` | Code ✓ |
| `/ready` **not** gated on Ollama | Code ✓ (ADR) |

## B. Registry + catalog (Day 2)

| Check | Status |
|-------|--------|
| Providers: ollama, openai, gemini, anthropic, vllm stub | Code ✓ |
| Default provider `ollama` when omitted | Code ✓ |
| Unknown model → 404 `model_not_found` | Code ✓ |
| Disabled provider omitted from `/v1/models` | Code ✓ |
| Aggregate `inference_providers` health (fail-soft) | Code ✓ |

## C. InferenceRouter (Day 3)

| Check | Status |
|-------|--------|
| Policies: default / cheapest / fastest / highest_quality / preferred_provider | Code ✓ |
| Health-aware skip + TTL cache | Code ✓ |
| Capabilities map | Code ✓ |
| Routing metrics snapshot | Code ✓ |
| Repository + service layer (no policy in FastAPI routers) | Code ✓ |

## D. Failure taxonomy (Day 4)

| Check | Status |
|-------|--------|
| Shared `errors.py` mapper | Code ✓ |
| Timeout → 504 `upstream_timeout` | Code ✓ |
| Upstream fail → 502 `upstream_error` | Code ✓ |
| `INFERENCE_OLLAMA_TIMEOUT_SECONDS` | Code ✓ |

## E. Security (Day 5)

| Check | Status |
|-------|--------|
| Prompt injection / model-exfil edge guard | Code ✓ |
| `INFERENCE_PROMPT_GUARD_*` env | Code ✓ |
| Inference threat notes | Code ✓ |

## F. Evidence

| Check | Command / path |
|-------|----------------|
| Unit gate W1 | `pytest tests/unit/openai_compat/test_sem03_w1_gate.py -q` |
| Broader openai_compat | `pytest tests/unit/openai_compat/ -q` |
| Smoke Sem03 W1 | `bash scripts/smoke_sem03_w1_inference.sh` |
| Days 1–6 docs | `docs/.../semester-03/week-01/day-0*.md` |
| Threat notes | `INFERENCE_THREAT_MODEL.md` |

## G. Production (ops)

| Check | Owner |
|-------|--------|
| `OPENAI_COMPAT_INFERENCE=gateway` when using live Ollama | ops |
| `OLLAMA_URL` reachable from API container | ops |
| Pull at least one chat model (`llama3.2` or lab model) | ops |
| Confirm `/ready` 200 while Ollama cold/down | ops |
| Optional: tiny timeout lab → 504 | ops |

## H. Explicit non-goals (accepted — later weeks)

- True Ollama token SSE (Week 2)  
- Catalog sync from Ollama `/api/tags` (Week 2)  
- Retries / circuit breaker / load balancing  
- Live vLLM HTTP backend (Week 4)  
- Changing Sem02 webhook/outbox behavior  

---

**Day 6 DoD:** sections A–F code evidence green → unlock Day 7 REVIEW + tag `sem03-w1-ollama-openai`.
