# AI Agent Marketplace & Store

Production Agent Store under `/api/v1/agent-store/*`.

## What it reuses (no duplication)

| Concern | Existing service |
|---------|------------------|
| Install / update / rollback / uninstall / API keys | `MarketplaceService` |
| Underlying package | `MarketplaceTemplate` + `TemplateVersion` + `TemplateInstallation` |
| Paid checkout | `PaymentService.create_payment` |
| Agent publish after install | `MarketplaceService.publish_installation` → Publish |
| Notifications | `NotificationEventBus` |

Listings always hold a required `template_id`. The store adds publisher identity, storefront discovery, ratings, monetization, moderation, and revenue share — not a second install engine.

## Capabilities

- **Storefront**: featured, trending, top rated, most installed, newest, recently updated, categories
- **Search / filters**: query, category, pricing, featured, verified, language, min rating, sort
- **Listing detail**: description, screenshots, demo, languages, knowledge requirements, pricing, publisher, versions, reviews, related + recommendations
- **Install**: one-click (free) or pay-then-install (one-time / subscription first charge); company-scoped via marketplace install; update / rollback / uninstall
- **Publisher portal**: profile, create/update listing, assets fields, versions, submit for review, analytics / revenue dashboard
- **Admin**: pending queue, approve/reject/suspend, feature/verify, abuse reports

## Monetization

- Free → install immediately
- Paid → `PaymentService` (manual/stripe/…); on success record `AgentStorePurchase` with publisher/platform share (`revenue_share_bps`, default 70%)
- Re-install after completed purchase does not re-charge

## Key routes

```
GET    /api/v1/agent-store/storefront
GET    /api/v1/agent-store/listings
GET    /api/v1/agent-store/listings/{id_or_slug}
POST   /api/v1/agent-store/listings/{id_or_slug}/install
GET    /api/v1/agent-store/installed
POST   /api/v1/agent-store/installations/{id}/update
POST   /api/v1/agent-store/installations/{id}/rollback
DELETE /api/v1/agent-store/installations/{id}
PUT    /api/v1/agent-store/publisher/me
POST   /api/v1/agent-store/publisher/listings
POST   /api/v1/agent-store/publisher/listings/{id}/submit
GET    /api/v1/agent-store/publisher/analytics
POST   /api/v1/agent-store/admin/listings/{id}/moderate   # platform:admin
```

Permissions: browse/review use `templates:read`; publish/install use `templates:manage`; moderation uses `platform:admin`.

## Migration

`alembic upgrade head` → revision `b8c9d0e1f2a3`.
