# Developer Guide — v1.0.0

## Repo layout

```
app/                 # Domain modules (router → service → repository)
alembic/versions/    # Schema migrations (head: a7b8c9d0e1f2)
scripts/             # worker.py, scheduler.py
sdk/                 # REST / JS / widget SDKs
packages/flutter_sdk
apps/                # developer-portal, android-starter, ios-starter, templates
docs/release/v1.0.0/ # This release package
tests/               # pytest
```

## Local setup

```bash
python -m venv .venv
.\.venv\Scripts\activate   # Windows
pip install -r requirements.txt
# Configure .env (JWT secrets, DB, Redis)
alembic upgrade head
uvicorn main:app --reload
```

Requires **PostgreSQL** and **Redis** for full TestClient / rate-limiter stack.

## Coding rules

- Do **not** duplicate business logic across facades (Onboarding, Copilot, Monitoring, Enterprise dashboards delegate).
- New tables → Alembic revision linear from current head.
- RBAC: use `RequirePermission(Permission.…)` for company APIs; `PLATFORM_ADMIN` for platform ops.
- Prefer service-layer validation + Pydantic schemas.

## Module READMEs

| Module | Path |
|--------|------|
| Enterprise | `app/enterprise/README.md` |
| Onboarding | `app/onboarding/README.md` |
| Monitoring | `app/monitoring/README.md` |
| Copilot | `app/copilot/README.md` |
| Branding | `app/branding/README.md` |
| Flutter SDK | `packages/flutter_sdk/README.md` |
| Android | `apps/android-starter/README.md` |
| iOS | `apps/ios-starter/README.md` |
| Developer portal | `apps/developer-portal/README.md` |

## Testing

```bash
# Fast unit (no Redis) — preferred in CI smoke
pytest tests/copilot tests/enterprise tests/onboarding tests/monitoring -q -m "not integration"

# Full suite needs Redis + Postgres
pytest -q
```

## SDKs

- REST docs: `sdk/rest/docs/`
- JavaScript: `sdk/javascript/`
- Widget: `sdk/widget/`
- Flutter: `packages/flutter_sdk/`

## Copilot tools

Copilot does not embed LLM business logic for domain actions — it maps intents to existing services. Extend tools in `app/copilot/tools.py` + workflows in `app/copilot/intents.py` only.
