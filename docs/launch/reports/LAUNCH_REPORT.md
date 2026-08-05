# Launch Report

Generated: 2026-08-05T13:50:00.000Z  
Overall: **CONDITIONAL PASS** (local Playwright + production GET smoke)

| Metric | Count |
|--------|------:|
| Playwright passed | 1 |
| Playwright failed | 0 |
| Playwright skipped | 23 |
| Production GET probes passed | 5 |
| Production GET probes failed | 0 |

## Production GET smoke (api.thtwaat.com / app.thtwaat.com)

| Endpoint | Status | Latency |
|----------|-------:|--------:|
| `GET /live` | 200 | 1330ms |
| `GET /api/v1/status` | 200 | 205ms |
| `GET /api/v1/payments/plans/?country=IN` | 200 | 228ms |
| `GET /widget.js` | 200 | 436ms |
| `GET https://app.thtwaat.com/login` | 200 | 1245ms |

## Playwright workflow coverage

Suite lives under `apps/templates/saas/e2e/`. Full authenticated flows skip when `E2E_API_URL` is unreachable or credentials are unset.

| # | Workflow | Coverage |
|---|----------|----------|
| 1 | User Registration | Playwright API seed (`seedWorkspace`) |
| 2 | Email Verification | `POST /api/v1/auth/send-email-verification` |
| 3 | Workspace Creation | Company create + session inject |
| 4 | AI Provider Selection | `GET /api/v1/ai/providers` |
| 5 | AI Agent Creation | `POST /v2/agents` |
| 6 | Knowledge Upload | `POST /v2/knowledge/bases` |
| 7 | Widget Generation | Publish + embed path |
| 8 | Widget Installation | `GET /widget.js` (prod verified) |
| 9 | Chat Conversation | `POST /public/v1/chat` |
| 10 | Conversation Memory | Multi-turn chat + inbox list |
| 11 | Human Handoff | `POST /public/v1/handoff` |
| 12 | Lead Capture | `POST /public/v1/leads` |
| 13 | Billing Upgrade | Plans + Billing UI |
| 14 | Razorpay Checkout | Providers + order endpoint |
| 15 | Stripe Checkout | Providers + checkout endpoint |
| 16 | Subscription Activation | Checkout safety probes |
| 17 | Usage Quotas | `GET /api/v1/usage/current` |
| 18 | Marketplace Purchase | `GET /api/v1/marketplace/templates` |
| 19 | Publisher Flow | `/api/v1/agent-store/publisher/me` + UI |
| 20 | Super Admin Analytics | `/api/v1/admin/executive` (credential gated) |

## How to run full suite against staging/prod

```bash
cd apps/templates/saas
export E2E_API_URL=https://api.thtwaat.com
export PLAYWRIGHT_BASE_URL=https://app.thtwaat.com
# optional:
# export E2E_EMAIL=... E2E_PASSWORD=...
# export E2E_SUPER_ADMIN_EMAIL=... E2E_SUPER_ADMIN_PASSWORD=...
npm run test:e2e
npm run report:launch
```

**Note:** Creating companies/users/agents on production requires explicit operator approval; prefer a staging stack for destructive E2E.
