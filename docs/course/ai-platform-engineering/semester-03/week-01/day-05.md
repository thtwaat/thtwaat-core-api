# Semester 03 · Week 1 · Day 5 — Security + interview (prompt injection / model exfil)

**Status:** Implemented  
**Depends on:** Days 1–4 (adapter, registry, router, error taxonomy)  
**Out of scope today:** Full LLM firewall, output redaction, Day 6 milestone build

---

## What shipped

| Piece | Path |
|-------|------|
| Edge guard | `app/openai_compat/prompt_guard.py` |
| Wired in | `CompletionsService.create_completion` + `build_stream_material` |
| Threat notes | [INFERENCE_THREAT_MODEL.md](./INFERENCE_THREAT_MODEL.md) |
| Tests | `tests/unit/openai_compat/test_prompt_guard.py` |

### Codes

| Code | HTTP | Meaning |
|------|------|---------|
| `prompt_injection_blocked` | 400 | Instruction-override / jailbreak heuristic |
| `model_exfil_blocked` | 400 | System-prompt / secret / weights exfil heuristic |

### Env

```text
INFERENCE_PROMPT_GUARD_ENABLED=true
INFERENCE_PROMPT_GUARD_MODE=block   # or log
```

**Honesty:** heuristics are **defense-in-depth**, not complete prevention. Pair with tenancy, secret hygiene, and (later) output filters.

---

## Interview drill (answer out loud)

1. **What is prompt injection vs jailbreak?**  
   → Injection: untrusted input tries to override instructions (often via retrieved docs or user text). Jailbreak: persuade the model to drop safety policies. Gateways can reject obvious patterns; models still need alignment.

2. **How would an attacker exfiltrate a system prompt through `/v1`?**  
   → Ask the model to “reveal/print/repeat system prompt”, or smuggle via “repeat text above”. Day 5 blocks common phrasings at the edge.

3. **Why not only rely on the model saying “I can’t share that”?**  
   → Models are inconsistent under adversarial framing; edge rejection + logging reduces blast radius and gives ops signal.

4. **Where should secrets live relative to prompts?**  
   → Never in system prompts sent to tenants. Use env/secret store; providers get keys server-side only.

5. **`block` vs `log` mode — when use each?**  
   → `block` for prod default. `log` for measuring false positives before enforcing.

6. **How does this relate to Sem02 SSRF webhook guard?**  
   → Same pattern: untrusted client input → assert-safe helper → OpenAI/HTTP shaped 400 — defense before expensive side effects.

---

## Lab checklist (Day 5)

- [x] Prompt injection patterns → 400  
- [x] Model/secret exfil patterns → 400  
- [x] Enable/disable + log mode  
- [x] Service short-circuits before inference  
- [x] Unit tests + threat notes  
- [ ] Manual: curl injection phrase → 400 `prompt_injection_blocked`  

---

## Tomorrow (Day 6)

Milestone build (ship checklist + gate + smoke) — see [day-06.md](./day-06.md).

**Day 5 complete.**
