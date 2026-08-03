# Semester 03 — Inference Engineering

**Duration:** 4 weeks (compressed, production-intensity)  
**Prerequisite:** Semester 02 (`sem02-v1.0.0` — OpenAI-compatible gateway in core)  
**Instructor mode:** **One day at a time** — do not skip ahead  
**Final project:** Local inference gateway — **Ollama → OpenAI schema** (vLLM-ready seam by Week 4)

---

## Learning outcomes

By the end of Semester 03 you can:

1. Map native Ollama (and later vLLM) chat APIs onto OpenAI `chat.completion` / SSE shapes.
2. Run and diagnose a local inference daemon beside THTWAAT `/v1`.
3. Sync model catalogs from the inference backend into `GET /v1/models`.
4. Stream tokens from local inference without breaking Sem02 metering / idempotency rules.
5. Apply backpressure and failure taxonomy (502 vs 429) for scarce GPU/CPU capacity.
6. Ship a pluggable inference backend (`ollama` | `vllm` stub) behind the existing gateway.

---

## Four-week map

| Week | Theme | Git milestone | Weekly ship |
|------|-------|---------------|-------------|
| **1** | Ollama → OpenAI adapter + local run path | `sem03-w1-ollama-openai` | Adapter contract + DX for `provider=ollama` |
| **2** | Catalog sync + true local streaming | `sem03-w2-local-stream` | Models from Ollama tags; SSE from daemon stream |
| **3** | Concurrency, batching, backpressure | `sem03-w3-inference-edge` | Limits + failure taxonomy |
| **4** | vLLM-ready seam + harden/ship | `sem03-w4-infer-ship` | Pluggable backend + tag `sem03-v1.0.0` |

Daily cadence (same as Sem 02): Mon architecture → … → Sun review/tag.

---

## Non-goals (this semester)

- Separate inference microservice repo (stay in `thtwaat-core-api`)
- Multi-node GPU cluster / K8s (Sem 05)
- Fine-tuning pipelines
- Replacing Sem02 Redis/webhook controls

---

## Week index

- [Week 1](./week-01/README.md) — **you are here** → start [Day 1](./week-01/day-01.md)
- Week 2–4 — locked until prior week review passes
