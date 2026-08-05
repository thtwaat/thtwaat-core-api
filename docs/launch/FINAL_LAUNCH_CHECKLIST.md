# Final Launch Checklist — Launch Freeze v1

**Release:** v1.0.0 (launch freeze)  
**Commit message:** `chore(release): launch freeze v1`  
**Date:** 2026-08-05

Use this as the go-live gate. Check items only after evidence exists.

## A. Critical code (must be green)

- [x] Billing webhook failures return **5xx** and stay **unprocessed** (Stripe/Razorpay retry)
- [x] Agent create quota check **fails closed** on metering errors
- [x] CORS wildcard never pairs with `allow_credentials=True`
- [x] Agent analytics router mounted + SQL aggregates collapsed
- [x] Legacy `/api/v1/ai-platform/*` marked **deprecated** (canonical: `/v2/agents`)
- [x] AI gateway RPM rate limit wired (Redis); cost estimate heuristics updated
- [x] Scheduler evaluates monitoring alerts every ~5 minutes
- [x] SaaS templates tab queries gated; admin charts dynamically imported
- [x] Next.js `optimizePackageImports` for lucide/recharts

## B. Security & limits

- [x] Security headers middleware present (HSTS, nosniff, CSP, frame deny except embed)
- [x] SaaS `next.config` security headers present
- [x] Auth OTP/login rate limits present (`app/auth/rate_limit.py`)
- [x] OpenAI-compat rate limits present (`app/openai_compat/rate_limit.py`)
- [ ] Ops: `CORS_ORIGINS` explicit on VPS `.env.prod`
- [ ] Ops: `METRICS_TOKEN` or private scrape ACL for `/metrics`
- [ ] Ops: `SSL_MODE=certbot` or confirmed edge TLS

## C. Reliability drills

- [ ] Backup restore drill: `CONFIRM_RESTORE=YES ./deploy/restore.sh --db …` on staging (+ `verify-restore.sh`)
- [ ] Evidence attached under `docs/ops/` or release folder
- [x] Outbound customer webhook retries covered by unit tests
- [x] Inbound billing webhook retry path fixed (this freeze)
- [x] AI provider failover loop in `AIService.chat` (+ stream tests)
- [x] Monitoring `evaluate_and_raise` callable via API + scheduler tick

## D. Product E2E (20 workflows)

See `docs/launch/PRODUCTION_LAUNCH_READINESS.md` and `docs/launch/reports/`.

- [ ] Staging Playwright with credentials (convert skips → pass)
- [x] Production GET smoke: `/live`, `/status`, plans, `widget.js`, login

## E. Release packaging

- [x] Release notes updated for launch freeze
- [x] Known issues / go-no-go refreshed
- [x] Tag `v1.0.0` points at launch-freeze commit
- [ ] Push tag + images; migrate prod; smoke

## Decision

| Mode | Criteria |
|------|----------|
| Controlled / invite launch | A green + B ops CORS/SSL/metrics signed + backup schedule running |
| Wide public launch | All of above + C restore drill evidence + D staging Playwright green + live email provider |
