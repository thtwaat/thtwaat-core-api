# Week 1 Review — `sem03-w1-ollama-openai`

**Date:** 2026-08-03  
**Scope:** Ollama↔OpenAI adapter, provider registry, InferenceRouter, error taxonomy, prompt guard, ship gate  
**Blockers:** none  
**Prerequisite:** Sem02 `sem02-v1.0.0`

---

## A. Adapter + health (Day 1)

| Item | Status | Evidence |
|------|--------|----------|
| Pure `inference_adapter` map | Pass | `app/openai_compat/inference_adapter.py` |
| Soft `ollama_live` on `/health` | Pass | `app/deploy/health.py` |
| `/ready` not gated on Ollama | Pass | ADR in `day-01.md` |

## B. Registry (Day 2)

| Item | Status | Evidence |
|------|--------|----------|
| Dynamic registry (ollama/openai/gemini/anthropic/vllm) | Pass | `providers/` + tests |
| Default provider + model→provider | Pass | `routing.py` |
| Disabled providers hidden from `/v1/models` | Pass | `catalog.py` + tests |
| Aggregate inference health fail-soft | Pass | `registry.aggregate_health` |

## C. InferenceRouter (Day 3)

| Item | Status | Evidence |
|------|--------|----------|
| Five routing policies | Pass | `inference_router.py` |
| Health cache TTL + skip unhealthy | Pass | `health_cache.py` |
| Capabilities + priority profiles | Pass | `inference_routing_repository.py` |
| Repo + service architecture | Pass | `InferenceRoutingService` |
| Metrics snapshot | Pass | `providers/metrics.py` |

## D. Debugging / taxonomy (Day 4)

| Item | Status | Evidence |
|------|--------|----------|
| Shared OpenAI-shaped mapper | Pass | `errors.py` |
| Timeout → 504 `upstream_timeout` | Pass | `test_inference_errors.py` |
| Missing model stays 404 | Pass | same |
| Configurable Ollama timeout | Pass | `INFERENCE_OLLAMA_TIMEOUT_SECONDS` |

## E. Security (Day 5)

| Item | Status | Evidence |
|------|--------|----------|
| Prompt injection / exfil edge guard | Pass | `prompt_guard.py` |
| Inference threat notes | Pass | `INFERENCE_THREAT_MODEL.md` |
| Interview drill | Pass | `day-05.md` |

## F. Ship harden (Day 6)

| Item | Status | Evidence |
|------|--------|----------|
| SHIP_CHECKLIST | Pass | `SHIP_CHECKLIST.md` |
| Sem03 W1 gate tests | Pass | `test_sem03_w1_gate.py` |
| Smoke script | Pass | `scripts/smoke_sem03_w1_inference.sh` |

## G. Engineering hygiene

| Item | Status | Evidence |
|------|--------|----------|
| Course docs Days 1–7 | Pass | `semester-03/week-01/` |
| Inference stays in core API (no new repo) | Pass | Sem03 decision |
| Sem02 webhook/outbox untouched | Pass | no W1 changes to outbox |
| Secrets not in git | Pass | review status |

---

## Known debt (≤5, non-blocking)

1. True Ollama token SSE (Week 2)  
2. Catalog sync from Ollama `/api/tags` (Week 2)  
3. Live remote HTTP for openai/gemini/anthropic (still synthetic chat in places)  
4. Retries / circuit breaker / load balancing (explicitly deferred)  
5. Semantic injection classifiers beyond heuristics  

**Verdict:** Ready to tag `sem03-w1-ollama-openai`.
