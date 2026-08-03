# Sem03 Week 1 — Inference plane threat notes (Day 5)

Scoped STRIDE notes for local/cloud inference behind `/v1` (Ollama + routed providers). Complements Sem02 gateway [THREAT_MODEL.md](../../semester-02/week-04/THREAT_MODEL.md).

## Trust boundaries

```text
Client (API key) → /v1 CompletionsService → InferenceRouter → Provider (Ollama/cloud)
                         ↑
                   PromptGuard (Day 5)
```

| Boundary | Trust |
|----------|--------|
| API key → `company_id` | Trusted tenancy authority (Sem02) |
| Message content | **Untrusted** |
| Provider credentials / env | Server-only; never in client prompts |
| Ollama daemon | Trusted infra; still untrusted *content* flowing through it |

## STRIDE (inference-focused)

| Threat | Example | Mitigation (W1) |
|--------|---------|-----------------|
| **S**poofing | Fake tenant in body | Sem02 API key principal only |
| **T**ampering | “Ignore previous instructions…” | Prompt guard → 400 |
| **R**epudiation | Denial of abusive prompt | Completion logs + guard warnings |
| **I**nfo disclosure | “Reveal system prompt / API key” | Exfil heuristics → 400; secrets not in prompts |
| **D**oS | Hang Ollama | Day 4 timeouts → 504 |
| **E**levation | Provider pivot via SSRF-like URL tools | Not in W1 chat path; Sem02 webhook SSRF |

## Explicit non-goals (later weeks)

- Semantic injection classifiers / LLM-as-judge
- Output streaming redaction
- Tool/RAG document isolation policies
- Circuit breaker / retry abuse controls
