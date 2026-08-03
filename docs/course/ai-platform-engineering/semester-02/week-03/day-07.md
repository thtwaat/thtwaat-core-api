# Semester 02 · Week 3 · Day 7 — Code review + tag `sem02-w3-async-edge`

**Depends on:** Day 6 DoD  
**Unlocks:** Semester 02 Week 4 (when curriculum starts)

---

## Ceremony

1. Fill [REVIEW.md](./REVIEW.md) — blockers must be none  
2. Fix only Week 3 blockers  
3. Re-run openai_compat unit tests  
4. Annotated tag + push `sem02-w3-async-edge`  
5. File [RETRO.md](./RETRO.md)

---

## Tag commands

```bash
git status
python -m pytest tests/unit/openai_compat/ -q
git tag -a sem02-w3-async-edge -m "Sem02 W3: async edge (webhooks, SSE, HMAC v1)"
git push origin sem02-w3-async-edge
git push origin main   # if commits pending
```

---

## Exit ticket (Week 3 complete)

1. Tag + SHA  
2. `REVIEW.md` → blockers: none  
3. `RETRO.md` path  
4. Ready for **Week 4 Day 1** when asked  
