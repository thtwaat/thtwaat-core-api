# THTWAAT Enterprise Module

Tenant-isolated enterprise administration under `/api/v1/enterprise/*`.

## Reuse boundaries

This module owns governance data only. Existing platform services remain the
single source of truth:

- Members are created, updated, suspended, and deactivated through `UserService`.
- Sessions are existing `RefreshToken` records managed through `AuthRepository`.
- 2FA enrollment and verification remain under `/api/v1/auth/mfa/*`.
- Usage reports delegate to `UsageService`.
- Billing reports delegate to `SubscriptionService` and `InvoiceService`.
- Enterprise dashboard branding delegates to `BrandingService`.
- Marketplace metrics delegate to `MarketplaceService`.
- Published-agent status uses the existing publish model.
- CSV/JSON exports are stored by `StorageService`.
- Company privacy preferences remain inside `Company.settings["privacy"]`.

## Capabilities

### Organizations

`EnterpriseUnit` provides a validated hierarchy:

`organization → business unit / department → team`

Endpoints:

- `GET/POST /enterprise/units`
- `PATCH /enterprise/units/{id}`
- `GET /enterprise/organizations`
- `GET /enterprise/business-units`
- `GET /enterprise/departments`
- `GET /enterprise/teams`
- `POST/DELETE /enterprise/units/{id}/members`

### Members

- Single and bulk invitations (tokens are hashed at rest)
- Invitation acceptance delegates account creation to `UserService`
- Activate, suspend, and deactivate members
- Suspension/deactivation revokes all existing refresh sessions

### Fine-grained RBAC

Built-in permissions remain in `app/rbac`. Enterprise custom roles add:

- Role templates
- Permission groups
- Company-scoped custom roles
- Optional unit-scoped role assignments
- Effective permission resolution combining built-in and custom grants

Enterprise API authorization checks both built-in and custom permissions.

### SSO

- OIDC authorization-code flow with signed state, nonce, redirect allow-list,
  token exchange, JWKS signature verification, domain enforcement, and JIT users
- Google Workspace presets
- Microsoft Entra ID presets
- SAML connection metadata and IdP initiation configuration
- Password login is blocked when enforced SSO matches a member email domain
- Client secrets are encrypted at rest using a key derived from
  `JWT_SECRET_KEY`

SAML XML assertion validation should terminate at the deployment's trusted SAML
gateway (for example, an ingress identity proxy). The module owns tenant
configuration and routing while the gateway owns XML signature processing.

### Security

- Existing TOTP/OTP 2FA integration
- Session listing and revocation using refresh tokens
- Maximum concurrent sessions and company session TTL
- CIDR-aware IP allow lists enforced by middleware
- Tenant API policies: read-only, blocked path prefixes, request-size limit
- Trusted device fingerprints (SHA-256 only; raw fingerprints are not stored)

### Audit and compliance

- Immutable tenant-scoped audit events with before/after snapshots
- Cross-module mutation capture through `EnterpriseAuditMiddleware`
- Filtered logs and resource activity timelines
- Retention policies and legal hold flags
- Privacy settings
- Append-only consent logs
- Audit, member, consent, usage, security, and billing exports

## Main API

```text
GET    /enterprise/dashboard
POST   /enterprise/members/invite
POST   /enterprise/members/bulk-invite
POST   /enterprise/invitations/accept
PATCH  /enterprise/members/{id}/status

GET    /enterprise/rbac/permissions
GET    /enterprise/rbac/role-templates
GET/POST /enterprise/rbac/permission-groups
GET/POST/PATCH /enterprise/rbac/roles
POST   /enterprise/rbac/assignments
GET    /enterprise/rbac/effective/{member_id}

GET/POST/PATCH /enterprise/sso/connections
GET    /enterprise/sso/{connection_id}/initiate
POST   /enterprise/sso/oidc/callback

GET/PATCH /enterprise/security/policy
GET/DELETE /enterprise/security/sessions
GET/POST /enterprise/security/trusted-devices

GET    /enterprise/audit/logs
GET    /enterprise/audit/timeline/{resource_type}/{resource_id}
GET/PUT /enterprise/compliance/retention
POST   /enterprise/compliance/retention/apply
GET/PATCH /enterprise/compliance/privacy
GET/POST /enterprise/compliance/consents

GET    /enterprise/reports/{usage|security|billing}
POST   /enterprise/exports
```

## Migration

```bash
alembic upgrade head
```

Revision: `d4e5f6a7b8c9_add_enterprise_module`

## Tests

```bash
# No external services
pytest tests/enterprise -m "not integration" -q

# Redis + PostgreSQL stack running, migration applied
pytest tests/enterprise -m integration -q
```

## Production checklist

1. Set strong `JWT_SECRET_KEY` and `JWT_REFRESH_SECRET_KEY`.
2. Run the migration before deploying application instances.
3. Configure exact OIDC redirect URI allow-lists.
4. Put SAML XML verification behind the trusted identity gateway.
5. Enable `EnterpriseSecurityMiddleware` (registered in `main.py`).
6. Configure S3/MinIO storage for durable export artifacts.
7. Run the existing `scripts/scheduler.py`; it applies retention daily.
