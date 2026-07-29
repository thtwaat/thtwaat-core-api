# THTWAAT White Label Platform

Every company can brand the platform as its own — web, mobile, widget, email, and custom domains — **without duplicating** Domain Manager, Storage, Publish, or Deploy logic.

## What it reuses

| Concern | Existing service |
|---------|------------------|
| File upload / URLs | `StorageService` |
| Custom domains, DNS, SSL | `DomainService` + `SslManager` + Deploy nginx |
| Widget theme cascade | `PublishService.widget_config_from_agent` |
| Company logo sync | `CompanyRepository` / `Company.logo_url` |
| Notification company name | `NotificationEventBus` + `BrandingService.resolve_email_context` |

## API

Authenticated (`/api/v1/branding`):

| Method | Path | Permission |
|--------|------|------------|
| `GET` | `/branding` | `branding:read` |
| `PATCH` | `/branding` | `branding:manage` |
| `POST` | `/branding/assets` | `branding:manage` |
| `GET` | `/branding/preview` | `branding:read` |
| `POST` | `/branding/publish` | `branding:manage` |
| `POST` | `/branding/reset` | `branding:manage` |

Public (published snapshot):

```
GET /public/v1/branding?slug={company_slug}
GET /public/v1/branding?company_id={uuid}
GET /public/v1/branding?hostname={custom-domain}
```

### Asset types (`POST /branding/assets`)

`logo` · `dark_logo` · `favicon` · `splash` · `launcher_icon` · `email_logo` · `login_background` · `widget_launcher` · `widget_header`

Multipart form: `asset_type` + `file`. Assets are versioned; previous active version is deactivated.

## Branding surface

- **Identity:** company name, footer, copyright  
- **Theme:** primary / secondary / accent, typography, dashboard theme, login background  
- **Assets:** logos, favicon, splash, launcher icons (validated MIME + size)  
- **Email:** sender name/email, logo, welcome / password reset / invoice / notification templates  
- **Mobile:** app name, Android package, iOS bundle ID, splash, icon, colors  
- **Widget defaults:** launcher, bubble color, header logo, suggested prompts (cascaded under per-agent overrides)  
- **Domains:** `domain_roles.app|api|chat` hostname hints — SSL/verification via Domain Manager  

## Zero-downtime publish

1. Editors mutate **draft** (`PATCH`, asset uploads bump `draft_version`).  
2. `POST /publish` writes an atomic `published_snapshot` and bumps `published_version`.  
3. Public clients read the snapshot only — no partial applies.  
4. `POST /reset` resets **draft** only; live snapshot stays until the next publish.

## Migration

```bash
alembic upgrade head
# revision: c3d4e5f6a7b8_add_white_label_branding
```

## Tests

```bash
pytest tests/branding/ -q
```

## Production notes

- Point `app.` / `api.` / `chat.` hostnames at Domain Manager, then request SSL as today.  
- Frontends load `GET /public/v1/branding?hostname=…` for CSS variables and assets.  
- Agent widgets inherit company defaults for empty keys only; explicit agent widget config wins.
