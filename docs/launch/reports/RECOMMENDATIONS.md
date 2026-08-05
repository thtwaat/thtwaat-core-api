# Recommendations

Generated: 2026-08-05T13:50:00.000Z

## Launch decision

**CONDITIONAL GO** for a controlled / invite-only launch after ops sign-off on CORS, SSL, metrics ACL, and backups.

**NO-GO for wide public marketing launch** until:

1. Staging Playwright run converts the 23 skipped workflow tests to green with credentials.
2. Real email provider is wired for OTP / email verification.
3. Stripe + Razorpay checkout smoke succeeds on staging with test keys.
4. Backup restore drill evidence is attached to the release record.

## Priority actions

1. Run Playwright on staging (preferred) or approved prod window:
   ```bash
   cd apps/templates/saas
   export E2E_API_URL=https://api.thtwaat.com
   export PLAYWRIGHT_BASE_URL=https://app.thtwaat.com
   export E2E_EMAIL=...
   export E2E_PASSWORD=...
   export E2E_SUPER_ADMIN_EMAIL=...
   export E2E_SUPER_ADMIN_PASSWORD=...
   npm run test:e2e && npm run report:launch
   ```
2. Lock `CORS_ORIGINS` to explicit app origins on VPS `.env.prod`.
3. Set `SSL_MODE=certbot` (or confirm edge TLS) and ACL `/metrics`.
4. Execute DB backup restore drill; store evidence under `docs/ops/`.
5. Wire production SMTP / email provider before opening public signup.
6. Keep this suite in CI against staging on every release candidate.

## Auto-fixes applied in this pack

- Playwright E2E suite covering all 20 launch workflows
- Launch / failed / performance / security / recommendations reporters
- `docker-compose.prod.yml` CORS ops comments
- `.env.prod.example` SSL + metrics guidance
- Corrected E2E paths (`send-email-verification`, `agent-store/publisher/me`, payments under `/api/v1/...`)
