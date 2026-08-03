# Semester 02 · Week 1 — Multi-tenant API core + PostgreSQL

**Milestone tag:** `sem02-w1-api-core`  
**Outcome:** Tenants, API keys, Alembic, `GET /v1/models` (+ pagination/filter), Docker Compose Postgres.  
**Unlock next:** Week 2 (completions + Redis) after Sunday review.

| Day | File | Topic |
|-----|------|--------|
| 1 | [day-01.md](./day-01.md) | Multi-tenant API architecture & OpenAI surface |
| 2 | [day-02.md](./day-02.md) | SQLAlchemy 2 + Postgres modeling |
| 3 | [day-03.md](./day-03.md) | Alembic lab |
| 4 | [day-04.md](./day-04.md) | Debugging migrations & pools |
| 5 | [day-05.md](./day-05.md) | Authn keys + interview |
| 6 | [day-06.md](./day-06.md) | Milestone build Saturday |
| 7 | [day-07.md](./day-07.md) | Code review + tag |

When Day 7 exit ticket is done → [Week 2](../week-02/) (created when you ask for Week 2 Day 1).

---

## Week 1 Git-ready milestone (`sem02-w1-api-core`)

### Scope

- Repo `thtwaat-gateway` (new) **or** evolve `thtwaat-lab-api` → rename clearly in README
- Tables: `tenants`, `api_keys`, `models` (catalog)
- Alembic: initial revision
- Routes:
  - `GET /healthz`, `GET /readyz` (ready checks DB)
  - `GET /v1/models` — pagination (`limit`/`offset` or cursor), filter `owned=true|false`
  - `GET /v1/models/{id}`
  - Dev-only: `POST /v1/admin/tenants` (bootstrap)
- API key header: `Authorization: Bearer sk_...` (hash at rest)
- Compose: `gateway` + `postgres`
- Tests: create tenant → create key → list models as that tenant

### Out of scope this week

Completions, Redis, webhooks, streaming (Week 2+).

---

## Week 1 code review checklist (Sunday)

- [ ] Every query scoped by `tenant_id` where data is tenant-owned
- [ ] API keys stored as **hash** (e.g. SHA-256 / bcrypt); plaintext shown once
- [ ] Alembic `upgrade head` from empty DB works
- [ ] `/readyz` returns 503 if Postgres down
- [ ] Pagination contracts documented in OpenAPI
- [ ] Filter cannot leak other tenants’ private models
- [ ] CI runs pytest
- [ ] README: ER diagram + how to migrate
- [ ] Tag `sem02-w1-api-core` on main/passing commit
