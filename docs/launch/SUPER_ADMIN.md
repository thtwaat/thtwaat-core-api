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

- `/admin` — dashboard
- `/admin/companies`
- `/admin/users`
- `/admin/plans`
- `/admin/health`

Access: authenticated `super_admin` only.

## Key APIs reused

- `GET /api/v1/admin/overview`
- `POST /api/v1/admin/impersonate/company` *(new thin facade)*
- `GET /api/v1/monitoring/health`
- `GET /api/v1/companies/?q=&status=&plan=&include_inactive=`
- `PATCH /api/v1/companies/{id}/admin`
- `GET /api/v1/users/?q=&role=&include_inactive=`
- `PATCH|DELETE /api/v1/users/{id}`
- `GET|PATCH /api/v1/payments/plans/`

## Plan naming

Company enum uses `growth` for the Pro tier. UI labels it **Pro**. Billing plan rows remain editable by name (Free / Starter / Pro / Enterprise).

## Tests

```bash
cd apps/templates/saas && npm test -- --run src/lib/super-admin.test.ts
pytest tests/monitoring/test_monitoring.py tests/companies -q
```

## Notes

- Impersonation stores the admin token backup in `localStorage` (`tht_admin_session_backup_v1`) so **Exit login-as** can restore the Super Admin session.
- Plans mutations now require platform admin.
