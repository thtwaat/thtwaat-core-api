# Testing Guide

THTWAAT Core API uses a three-tier pytest setup.

| Suite | Marker | Needs Docker? | Database | Redis |
|-------|--------|---------------|----------|-------|
| Unit | `@pytest.mark.unit` | No | SQLite / mocks | fakeredis |
| Integration | `@pytest.mark.integration` | Yes | PostgreSQL (pgvector) | Redis |
| E2E | `@pytest.mark.e2e` | Deployed stack | Live | Live |

## Quick start

```bash
pip install -r requirements-dev.txt

# Unit only (no Docker)
./scripts/test-unit.sh

# Integration (starts compose db+redis on :5433 / :6380)
cp .env.test.example .env.test   # optional overrides
./scripts/test-integration.sh

# E2E against a running API
E2E_BASE_URL=http://localhost:8000 ./scripts/test-e2e.sh
# or start API via compose:
START_E2E_STACK=1 ./scripts/test-e2e.sh

# All (unit + integration; e2e if RUN_E2E=1)
./scripts/test-all.sh
RUN_E2E=1 ./scripts/test-all.sh
```

On Windows use Git Bash / WSL for the `.sh` scripts, or call the same `pytest` commands below.

## Markers

Defined in `pytest.ini`:

- `unit` — fast, hermetic
- `integration` — app TestClient + Postgres + Redis
- `e2e` — HTTP against `E2E_BASE_URL`

Directory auto-marking (when no explicit marker):

- `tests/unit/` → unit
- `tests/integration/` → integration
- `tests/e2e/` → e2e
- other legacy modules → integration (they historically need the stack)

Prefer **explicit** `@pytest.mark.unit` / `integration` / `e2e` on new tests.

## Fixtures

Root `tests/conftest.py`:

- `client`, `db_session`, `redis_client` — integration only; skip if stack is down
- `tmp_storage`, `mock_payments`, `mock_ai` — reusable everywhere

`tests/unit/conftest.py`:

- `sqlite_engine`, `unit_db_session`, `fake_redis`

`tests/e2e/conftest.py`:

- `e2e_client` (httpx), `e2e_base_url`

Helpers live in `tests/support/`.

## Docker test stack

```bash
docker compose -f docker-compose.test.yml up -d db redis
# optional full API for e2e:
docker compose -f docker-compose.test.yml --profile e2e up -d --build
```

Defaults (see `.env.test.example`):

- Postgres: `localhost:5433` / `thtwaat` / `thtwaat` / db `thtwaat_test`
- Redis: `localhost:6380`

## Reports

Scripts write to `./reports/`:

- `coverage-*.xml` / `htmlcov-*`
- `junit-*.xml`
- `report-*.html` (pytest-html)

## Adding tests

1. Pure logic / schema / mocks → `tests/unit/` or `@pytest.mark.unit`
2. HTTP + DB + Redis → `@pytest.mark.integration`
3. Live deployed smoke → `tests/e2e/` + `@pytest.mark.e2e`

Do not duplicate business logic in tests; mock external gateways (payments, LLM) in unit tests.
