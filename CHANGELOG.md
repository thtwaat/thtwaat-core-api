# THTWAAT AI Platform — CHANGELOG

All notable changes for production releases are documented here.

## [1.0.0] — 2026-07-30

### Added
- **Enterprise** — org hierarchy, invites, custom RBAC, SSO (OIDC/SAML presets), MFA/session policy, IP allow lists, audit/compliance exports
- **Customer Onboarding Wizard** — 12-step flow with progress, autosave, resume, skip-optional, admin analytics
- **Monitoring & Admin Operations** — platform overview, health, observability links, job queue ops, alerts, audit timeline, reports
- **AI Copilot** — NLU → plan → tool orchestration over existing services (no duplicated domain logic)
- **White-label Branding** — draft/publish branding, assets, public branding API
- **Marketplace** — template catalog, install/connect/publish/update/rollback
- **Product Generator** — prompt analysis → provision → preview → publish
- **Domains + SSL** — custom domains, DNS verification, SSL manager, nginx vhost generation
- **Publish Engine** — agent publish, API keys, embed/widget URLs
- **Usage metering** — quotas, dashboards, daily aggregates
- **Developer Portal**, **Flutter SDK**, **Android Starter**, **iOS Starter**
- Prometheus instrumentation (`/metrics`) + Grafana/Prometheus compose stack
- Production compose (`docker-compose.prod.yml`) with nginx, worker, scheduler, backup

### Security
- JWT access + refresh (refresh persisted/revocable)
- RBAC permissions + enterprise custom roles
- Security headers middleware (HSTS, CSP, X-Frame-Options, …)
- Enterprise IP allow-list + audit middleware
- Rate limiting via FastAPI-Limiter + Redis
- OpenAPI/docs disabled when `APP_ENV=production`

### Known limitations (see Release Notes)
- Email/SMS/Push notification providers are stubs unless wired
- Grafana has datasource provisioning but no shipped dashboard JSON panels
- Default prod SSL mode may be `simulate` until certbot is configured
- CORS `*` + credentials is unsafe for production tenants (must set explicit origins)

[1.0.0]: https://github.com/thtwaat/thtwaat-core-api/releases/tag/v1.0.0
