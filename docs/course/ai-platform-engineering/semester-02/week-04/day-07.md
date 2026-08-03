# Semester 02 · Week 4 · Day 7 — Code review + tags

**Depends on:** Day 6 DoD / SHIP_CHECKLIST  
**Unlocks:** Semester 02 complete → Sem 03 inference when curriculum starts

---

## Ceremony

1. Fill [REVIEW.md](./REVIEW.md) — blockers must be none  
2. Fix only Week 4 blockers  
3. Re-run openai_compat unit tests  
4. Annotated tags + push:
   - `sem02-w4-gateway-ship`
   - `sem02-v1.0.0`
5. File [RETRO.md](./RETRO.md)

---

## Tag commands

```bash
git status
python -m pytest tests/unit/openai_compat/ -q
git tag -a sem02-w4-gateway-ship -m "Sem02 W4: gateway harden (outbox, SSRF, ship gate)"
git tag -a sem02-v1.0.0 -m "Sem02 v1.0.0: OpenAI-compatible gateway in THTWAAT core"
git push origin sem02-w4-gateway-ship sem02-v1.0.0
git push origin main
```

---

## Exit ticket (Week 4 / Sem02 complete)

1. Tags + SHA  
2. `REVIEW.md` → blockers: none  
3. `RETRO.md` path  
4. Ready for **Semester 03** when asked  
