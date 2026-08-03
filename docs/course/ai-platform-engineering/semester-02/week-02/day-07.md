# Semester 02 · Week 2 · Day 7 — Code review + tag `sem02-w2-completions`

**Depends on:** Day 6 DoD  
**Unlocks:** Semester 02 Week 3 (async edge / webhooks)

---

## Ceremony

1. Fill [REVIEW.md](./REVIEW.md) — blockers must be none  
2. Fix only Week 2 blockers  
3. Re-run `pytest tests/unit/openai_compat/ -q`  
4. Annotated tag + push `sem02-w2-completions`  
5. File [RETRO.md](./RETRO.md)

---

## Tag commands

```bash
git status
python -m pytest tests/unit/openai_compat/ -q
git tag -a sem02-w2-completions -m "Sem02 W2: OpenAI-compatible completions plane"
git push origin sem02-w2-completions
git push origin main   # if commits pending
```

---

## Exit ticket (Week 2 complete)

1. Tag + SHA  
2. `REVIEW.md` → blockers: none  
3. `RETRO.md` path  
4. Ready for **Week 3 Day 1** when asked  
