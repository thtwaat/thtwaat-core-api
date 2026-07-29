# End-to-End Verification Checklist — v1.0.0

Use against a staging stack with Redis + Postgres. Mark Pass / Fail / N/A.

## Authentication
- [ ] Login with valid credentials → access + refresh
- [ ] Login invalid → 401
- [ ] Refresh token works; revoked refresh fails after logout
- [ ] MFA challenge path (if enabled)
- [ ] Email verification send + verify OTP
- [ ] Multi-tenant email → `company_slug` required (409)

## Companies & Users
- [ ] Create company (unique slug)
- [ ] Create owner user in company
- [ ] Update company profile
- [ ] List/get users with auth

## Agents & Knowledge
- [ ] Create agent (quota enforced)
- [ ] List agents (tenant isolation)
- [ ] Create knowledge base + upload document
- [ ] Attach KB to agent

## Marketplace
- [ ] List published templates
- [ ] Install template
- [ ] Connect installation
- [ ] Uninstall / update / rollback (as applicable)

## Product Generator
- [ ] Analyze prompt
- [ ] Generate product (agent + KB + install)
- [ ] Preview URL present
- [ ] Publish product

## Publish
- [ ] Publish agent → PUBLISHED + widget/embed
- [ ] Unpublish → DRAFT
- [ ] API key create for agent

## Domains & SSL
- [ ] Create domain + DNS records returned
- [ ] Verify DNS (staging TXT)
- [ ] SSL request (simulate or certbot)
- [ ] Primary domain / CORS origin updates

## Branding
- [ ] GET/PATCH branding draft
- [ ] Upload asset
- [ ] Publish branding
- [ ] Public branding endpoint

## Enterprise
- [ ] Create organization unit
- [ ] Invite member + accept/revoke
- [ ] Security policy update
- [ ] Audit log entry for mutation
- [ ] SSO config create (OIDC/SAML fields)

## Onboarding
- [ ] `POST /onboarding/start` → tokens + session
- [ ] Verify email step
- [ ] Complete company / plan / agent steps
- [ ] Skip optional knowledge
- [ ] Pause / resume / autosave
- [ ] Admin analytics visible to platform admin

## Monitoring & Ops
- [ ] `/monitoring/health` (platform admin)
- [ ] `/monitoring/observability` links
- [ ] Evaluate alerts
- [ ] List jobs; enqueue backup; retry dead-letter (safe staging)
- [ ] Admin overview + daily report

## AI Copilot
- [ ] `GET /copilot/tools`
- [ ] Chat: “Create a customer support chatbot” → generate_product plan
- [ ] Destructive publish requires confirmation
- [ ] Task history + diagnostics on failure
- [ ] Replay task

## Billing
- [ ] List plans
- [ ] Stripe checkout session (test keys)
- [ ] Webhook payment success path (test)
- [ ] Usage dashboard reflects meters

## Developer Portal
- [ ] Portal builds / loads docs pages
- [ ] Auth + REST docs pages render

## Android Starter
- [ ] Project opens; configured API base URL
- [ ] Login smoke (device/emulator) against staging

## iOS Starter
- [ ] XcodeGen/project opens on macOS
- [ ] Login smoke against staging

## Flutter SDK
- [ ] Package analyzes (`dart analyze`)
- [ ] Auth + chat client smoke against staging

## Platform health gates
- [ ] `/live` 200
- [ ] `/ready` 200
- [ ] `/health` status healthy/degraded expected
- [ ] Prometheus scrapes `/metrics`
- [ ] Worker heartbeat present
