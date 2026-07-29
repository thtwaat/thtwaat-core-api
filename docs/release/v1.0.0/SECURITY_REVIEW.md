# Security Review — v1.0.0

Review date: 2026-07-30  
Scope: authentication, authorization, transport headers, input validation, ops exposure.  
Method: static code review of `main.py`, auth, RBAC, enterprise middleware, CORS, limiter, backups.  
**No new product features introduced during this review.**

## Findings

| ID | Severity | Area | Finding | Recommendation | Status |
|----|----------|------|---------|----------------|--------|
| S1 | **High** | CORS | `CORS_ORIGINS` containing `*` with `allow_credentials=True` is browser-unsafe | Require explicit origin list in production | **Blocker until env fixed** |
| S2 | **High** | Secrets | Notification email/push providers are stubs — alerts may appear sent | Wire real providers or disable alert channels | Known limitation |
| S3 | **Medium** | Metrics | `/metrics` exposed on API without auth | Network ACL / nginx allowlist for Prometheus only | Must fix in prod net |
| S4 | **Medium** | SSL | Prod compose defaults `SSL_MODE=simulate` | Set `certbot` for live domains | Config gate |
| S5 | **Medium** | JWT | Access TTL 30m; refresh 7d; HS256 | Rotate secrets; consider shorter refresh + rotation enforcement | Acceptable with strong secrets |
| S6 | **Low** | CSRF | Cookie-based CSRF less relevant (Bearer tokens) | Keep Bearer-only; avoid cookie session APIs | OK |
| S7 | **Low** | XSS | API JSON; CSP header set | Ensure any HTML portal sanitizes | OK for API |
| S8 | **Info** | SQLi | SQLAlchemy ORM parameterized | Continue ban on raw string SQL with user input | OK |
| S9 | **Info** | SSRF | Worker/webhooks outbound HTTP | Validate webhook URLs; block link-local | Follow-up |
| S10 | **Info** | Audit | Enterprise audit middleware + ops admin activity | Retain exports | OK |

## Controls present

| Control | Implementation |
|---------|----------------|
| Authentication | JWT access + DB-backed refresh revoke |
| Password hashing | bcrypt |
| MFA | TOTP + backup codes (`/auth/mfa`) |
| Authorization | `Permission` enum + `ROLE_PERMISSIONS` + custom enterprise roles |
| Rate limiting | FastAPI-Limiter + Redis |
| Security headers | HSTS, X-Content-Type-Options, X-Frame-Options, CSP, Referrer-Policy, Permissions-Policy |
| Enterprise | IP allow list, SSO enforce, session TTL/max sessions |
| Input validation | Pydantic v2 schemas |
| Production docs lock | OpenAPI/Swagger off when `APP_ENV=production` |
| Tenant isolation | `company_id` scoping in services |

## AuthN / AuthZ checklist

- [x] Access/refresh separation
- [x] Refresh revocation on logout / password reset
- [x] Role → permission map
- [x] Platform admin gated ops routes
- [ ] Production CORS locked (ops responsibility)
- [ ] `/metrics` network restricted (ops responsibility)

## Verdict

**Conditionally ready** — code controls are largely in place; **production Go requires S1/S3/S4 configuration mitigations** before public traffic.
