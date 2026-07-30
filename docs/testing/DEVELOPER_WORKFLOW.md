# Developer test workflow

## One-time setup

```bash
python -m venv .venv
# Windows: .\.venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.test.example .env.test
```

## Day-to-day

| Intent | Command |
|--------|---------|
| Fast feedback while coding | `./scripts/test-unit.sh` or `pytest -m unit` |
| Before PR (full stack) | `./scripts/test-integration.sh` |
| Smoke after deploy | `E2E_BASE_URL=... ./scripts/test-e2e.sh` |
| Everything local | `./scripts/test-all.sh` |

Filter by path:

```bash
pytest -m unit tests/agent_store -q
pytest -m integration tests/marketplace -q
```

## Rules of thumb

1. Prefer unit tests for schemas, pure functions, and service facades with mocked collaborators.
2. Use integration for multi-module HTTP flows (auth → install → publish).
3. Keep e2e thin — liveness/status and a few critical paths against a real deploy.
4. Never commit `.env.test` secrets; commit only `.env.test.example`.
5. Application feature code is out of scope for test-infra PRs — fixtures and CI only.

## Reports

Open after a run:

- `reports/report-unit.html`
- `reports/htmlcov-unit/index.html`
- `reports/junit-unit.xml` (CI / IDE)

See [TESTING.md](./TESTING.md) and [CI.md](./CI.md) for details.
