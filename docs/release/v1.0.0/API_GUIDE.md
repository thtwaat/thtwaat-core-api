# API Guide — v1.0.0

Base path: `/api/v1`  
Auth: `Authorization: Bearer <access_token>`  
Docs UI: disabled in production (`APP_ENV=production`). Use this guide + OpenAPI from a staging env.

## Auth

| Method | Path | Notes |
|--------|------|-------|
| POST | `/auth/login` | Returns tokens or MFA challenge |
| POST | `/auth/refresh` | Rotate/continue access |
| POST | `/auth/logout` | Revoke refresh |
| GET | `/auth/me` | Profile |
| POST | `/auth/verify-email` | OTP verify |
| `/auth/mfa/*` | MFA setup/verify |

## Core tenant

- Companies `/companies`
- Users `/users`
- Apps `/apps`, Products `/products`
- Storage `/storage`
- Notifications `/notifications`
- API keys `/api-keys`, Webhooks `/webhooks`

## AI & Agents

- AI gateway `/ai`
- Agents `POST/GET /v2/agents` (mounted outside `/api/v1` prefix in `main.py`)
- Knowledge `/v2/knowledge`
- Publish `/agents/{id}/publish` (agent_platform publish router under `/api/v1`)

## Growth / product

| Area | Prefix |
|------|--------|
| Marketplace | `/marketplace` |
| Product Generator | `/product-generator` |
| Domains | `/domains` |
| Branding | `/branding` + public `/public/v1/branding` |
| Usage | `/usage` |
| Billing | `/plans`, `/subscriptions`, `/invoices` |

## Facades (orchestration)

| Area | Prefix |
|------|--------|
| Onboarding | `/onboarding` |
| Enterprise | `/enterprise` |
| Monitoring | `/monitoring` |
| Admin | `/admin` |
| Operations | `/operations` |
| Copilot | `/copilot` |
| Deploy | `/deploy` |

## Health (unversioned)

| Path | Purpose |
|------|---------|
| `/live` | Liveness |
| `/ready` | Readiness (DB/Redis/storage) |
| `/health` | Full health JSON |
| `/metrics` | Prometheus scrape |

## Error model

HTTP exceptions return structured JSON via shared handlers in `app/api/exceptions.py`. Validation errors → 422.
