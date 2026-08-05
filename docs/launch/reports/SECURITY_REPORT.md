# Security Report

Generated: 2026-08-05T13:50:00.000Z

## Production configuration gates

| Control | Status | Notes |
|---------|--------|-------|
| Explicit CORS (no `*`) | **REQUIRED OPS** | Settings refuse `CORS_ORIGINS=*` when `APP_ENV=production`; confirmed in code + `.env.prod.example` |
| Distinct JWT secrets | **REQUIRED OPS** | Access + refresh secrets must differ |
| OpenAPI disabled in prod | **PASS (code)** | Hardened env gates docs |
| Metrics ACL / token | **REQUIRED OPS** | Prefer private scrape or `METRICS_TOKEN` (documented in `.env.prod.example`) |
| SSL mode | **REQUIRED OPS** | Prefer `SSL_MODE=certbot` or edge TLS; `simulate` only for dry-runs |
| Widget keys in URLs | **PASS (code)** | Live keys rejected from iframe query strings |
| Public agent routes allowlisted | **PASS (code)** | `INTENTIONAL_PUBLIC_OPERATIONS` |

## Findings from this run

- Playwright overall: **PASSED** (1 pass / 0 fail / 23 skip)
- Production GET smoke: **PASS** (live, status, plans, widget.js, login)
- No automated security-sensitive test failures

## Residual risks

1. Email/SMS providers may still be stubs — OTP/email verification needs real provider keys for public signup.
2. Backup restore drill must be signed off operationally (not covered by Playwright).
3. Razorpay/Stripe live keys required for paid checkout E2E on staging.
4. Full write-path E2E against production was not executed in this pack (operator approval required for data-creating flows).
