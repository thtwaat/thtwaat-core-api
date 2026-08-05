# Production Launch Readiness

Automated verification pack for the 20 public-launch workflows.

## Quick start

```bash
# API smoke (pytest)
E2E_BASE_URL=https://api.thtwaat.com pytest -m e2e -q

# SaaS Playwright (from apps/templates/saas)
cd apps/templates/saas
npm i
npx playwright install chromium
export E2E_API_URL=https://api.thtwaat.com
export PLAYWRIGHT_BASE_URL=https://app.thtwaat.com
# optional authenticated flows:
# export E2E_EMAIL=... E2E_PASSWORD=...
# export E2E_SUPER_ADMIN_EMAIL=... E2E_SUPER_ADMIN_PASSWORD=...
npm run test:e2e
npm run report:launch
```

Reports are written to `apps/templates/saas/e2e-reports/` (gitignored) and mirrored to `docs/launch/reports/` by `npm run report:launch`.

Committed snapshot: [docs/launch/reports/](./reports/).

## Workflows covered

1. User Registration  
2. Email Verification  
3. Workspace Creation  
4. AI Provider Selection  
5. AI Agent Creation  
6. Knowledge Upload  
7. Widget Generation  
8. Widget Installation  
9. Chat Conversation  
10. Conversation Memory  
11. Human Handoff  
12. Lead Capture  
13. Billing Upgrade  
14. Razorpay Checkout  
15. Stripe Checkout  
16. Subscription Activation  
17. Usage Quotas  
18. Marketplace Purchase  
19. Publisher Flow  
20. Super Admin Analytics  

## Ops gates before wide public launch

1. `CORS_ORIGINS` explicit (no `*`)  
2. `SSL_MODE=certbot` or edge TLS  
3. `/metrics` network ACL or token  
4. Backup restore drill evidence  
5. Real email provider for OTP  
