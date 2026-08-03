# Semester 03 · Week 1 · Day 7 — Code review + tag

**Depends on:** Day 6 DoD / SHIP_CHECKLIST  
**Unlocks:** Week 2 (catalog sync + local streaming) when approved

---

## Ceremony

1. Fill [REVIEW.md](./REVIEW.md) — blockers must be none  
2. File [RETRO.md](./RETRO.md)  
3. Re-run Sem03 W1 gate (+ related unit tests)  
4. Annotated tag:
   - `sem03-w1-ollama-openai`

---

## Tag commands

```bash
git status
python -m pytest tests/unit/openai_compat/test_sem03_w1_gate.py -q
git tag -a sem03-w1-ollama-openai -m "Sem03 W1: Ollama OpenAI adapter, registry, router, error taxonomy, prompt guard"
# optional push when ready:
# git push origin sem03-w1-ollama-openai
# git push origin main
```

---

## Exit ticket (Week 1 complete)

1. Tag + SHA  
2. `REVIEW.md` → blockers: none  
3. `RETRO.md` path  
4. Ready for **Week 2** when asked  

**Week 1 complete — stop. Await approval before Week 2 Day 1.**
