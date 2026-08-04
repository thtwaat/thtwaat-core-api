# Super Admin Foundation (Launch Module A)

Minimum production Super Admin Console for THTWAAT Cloud.

## Audit summary

| Requirement | Backend | SaaS UI |
|-------------|---------|---------|
| Role `super_admin` | **Exists** (`EnterpriseRole.SUPER_ADMIN` → `platform:admin`) | Gate via `canPlatformAdmin` |
| Route `/admin` | APIs under `/api/v1/admin/*` | **Added** `/admin` console (separate from customer `/app`) |
| Dashboard stats | `GET /admin/overview` + `/monitoring/observability` | Dashboard page |
| Companies | `GET/PATCH /companies…/admin` | Search, filter, suspend, activate, plan, quotas, login-as |
| Users | `GET/PATCH/DELETE /users` | Search, roles, enable/disable |
| Plans | `GET/PATCH /payments/plans` | Editable limits (PLATFORM_ADMIN gated) |
| System health | `GET /monitoring/health` | PostgreSQL / Redis / Workers / AI Providers |
| Login as company | **Added** thin `POST /admin/impersonate/company` (reuses AuthService JWTs) | Companies → Login as |
| Quota override | Extends existing `PATCH /companies/{id}/admin` → `UsageService.override_quotas` | Companies panel |

Customer `/app` UI was not redesigned. Marketplace remains at `/app/admin`.

## Routes (SaaS)

- `/admin` — executive dashboard
- `/admin/companies` — workspaces (suspend/activate/delete, quotas, billing/AI ops)
- `/admin/users` — invite, roles, disable, reset password
- `/admin/ai` — AI analytics
- `/admin/marketplace` — catalog + publisher moderation
- `/admin/logs` — unified ops logs
- `/admin/operations` — jobs / queues
- `/admin/plans` — plan limits
- `/admin/health` — system health

Access: authenticated `super_admin` only.

## Key APIs reused / added (Phase 7)

- `GET /api/v1/admin/overview`
- `GET /api/v1/admin/executive` *(Phase 7)*
- `GET /api/v1/admin/ai-analytics` *(Phase 7)*
- `GET /api/v1/admin/workspaces/{id}/ops` *(Phase 7)*
- `GET /api/v1/admin/logs` *(Phase 7)*
- `GET /api/v1/admin/marketplace-analytics` *(Phase 7)*
- `POST /api/v1/admin/users/invite` *(Phase 7)*
- `POST /api/v1/admin/users/{id}/reset-password` *(Phase 7)*
- `POST /api/v1/admin/export` *(Phase 7 — csv|xlsx|pdf)*
- `POST /api/v1/admin/impersonate/company`
- `GET /api/v1/monitoring/health`
- `GET /api/v1/operations/jobs`
- `GET/PATCH /companies…/admin`
- `GET/PATCH/DELETE /users`
- Agent-store moderation + marketplace admin analytics

## Plan naming

Company enum uses `growth` for the Pro tier. UI labels it **Pro**. Billing plan rows remain editable by name (Free / Starter / Pro / Enterprise).

## Tests

```bash
cd apps/templates/saas && npm test -- --run src/lib/super-admin.test.ts
pytest tests/monitoring/test_monitoring.py tests/unit/monitoring/test_enterprise_ops.py -q
```

## Notes

- Impersonation stores the admin token backup in `localStorage` (`tht_admin_session_backup_v1`) so **Exit login-as** can restore the Super Admin session.
- Plans mutations now require platform admin.
