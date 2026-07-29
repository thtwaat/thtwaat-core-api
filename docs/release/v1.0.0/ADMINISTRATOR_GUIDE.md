# Administrator Guide — v1.0.0

## Roles

| Role | Scope |
|------|-------|
| `super_admin` | Platform admin (`platform:admin`) — monitoring, ops jobs, onboarding analytics |
| `company_owner` / `admin` | Full tenant manage (agents, domains, branding, enterprise, templates) |
| `manager` / `developer` / `employee` / `viewer` | Progressive subsets per `app/rbac/policy.py` |
| Custom roles | Enterprise permission groups / assignments |

## Platform admin surfaces

| Need | Endpoint prefix |
|------|-----------------|
| Platform overview | `GET /api/v1/admin/overview` |
| Reports | `GET /api/v1/admin/reports/{daily\|weekly\|monthly}` |
| Audit timeline/export | `/api/v1/admin/audit/*` |
| System health | `GET /api/v1/monitoring/health` |
| Observability links | `GET /api/v1/monitoring/observability` |
| Alerts | `/api/v1/monitoring/alerts*` |
| Jobs | `/api/v1/operations/*` |
| Onboarding analytics | `/api/v1/onboarding/admin/*` |
| Copilot executions | `GET /api/v1/copilot/admin/executions` |
| Deploy dashboard | `/api/v1/deploy/*` |

## Tenant administration

### Enterprise
- Units hierarchy, invites, SSO, MFA policy, IP allow lists
- Audit logs + compliance exports
- See `app/enterprise/README.md`

### Branding
- Draft → publish white-label theme
- Public read: `/public/v1/branding`
- See `app/branding/README.md`

### Billing
- Plans / Stripe checkout / Razorpay via `/api/v1` payments routers
- Usage quotas via `/api/v1/usage/*`

### Onboarding
- Customers: `/api/v1/onboarding/start` then step complete/skip
- Admins: completion rate + drop-off analytics

## Security practices for admins

1. Enforce MFA for owners via enterprise security policy.
2. Prefer SSO with `enforce_sso` for corporate domains.
3. Keep IP allow lists updated for admin networks.
4. Review `/api/v1/admin/audit/timeline` weekly.
5. Acknowledge/resolve monitoring alerts; do not leave critical alerts open.
