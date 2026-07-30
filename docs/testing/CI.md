# CI Guide

GitHub Actions workflow: `.github/workflows/test.yml`

## Pipeline stages

```text
Lint ──► Unit Tests ──► (artifacts)
  └────► Build Image ──► (docker artifact)
           └──────────► Integration Tests (Compose Postgres/Redis) ──► artifacts
```

| Job | What it does |
|-----|----------------|
| **Lint** | `ruff check` on test infrastructure / support code |
| **Unit** | `./scripts/test-unit.sh` — no Docker services |
| **Build** | `docker build` + upload gzipped image |
| **Integration** | Compose `db`+`redis`, Alembic migrate, `pytest -m integration` |

## Artifacts

Uploaded on every run (`if: always()`):

- `unit-test-reports` — coverage XML, JUnit, HTML
- `integration-test-reports` — same for integration
- `docker-image` — `thtwaat-core-api-ci.tar.gz` (3-day retention)

## Required secrets / env

CI sets non-production JWT secrets via `env:` (not repository secrets). Do **not** reuse these in production.

Integration job env:

- `DATABASE_URL=postgresql://thtwaat:thtwaat@localhost:5433/thtwaat_test`
- `REDIS_HOST=localhost` / `REDIS_PORT=6380`

## Local parity

```bash
pip install -r requirements-dev.txt
./scripts/test-unit.sh
./scripts/test-integration.sh
```

Same markers, same compose file (`docker-compose.test.yml`), same report paths under `reports/`.

## Related workflows

- `.github/workflows/docker.yml` — compose config + image lint/build
- `.github/workflows/security.yml` — security scanning (unchanged)

## Failure triage

1. **Lint** — fix ruff findings under `tests/support`, `tests/unit`, `tests/e2e`, `tests/conftest.py`
2. **Unit** — open `reports/report-unit.html` / JUnit; no infra needed
3. **Integration** — confirm compose health; check Postgres logs; ensure migrations apply (`alembic upgrade head`)
4. **Build** — Dockerfile or dependency install failure
