# Customer Onboarding Wizard

Production-ready 12-step customer onboarding for the THTWAAT AI Platform.

This module is an **orchestration facade**. It tracks progress, drafts, resume
tokens, and analytics — and **delegates all business operations** to existing
services (auth, users, companies, billing, agents, knowledge, marketplace,
product generator, publish, domains, branding, enterprise).

## Flow

| # | Step | Integration | Optional |
|---|------|-------------|----------|
| 1 | Create Account | Users | No |
| 2 | Verify Email | Auth | No |
| 3 | Create Company | Companies | No |
| 4 | Choose Plan | Billing | No (`stay_free` supported) |
| 5 | Create AI Agent | Agent Platform | No |
| 6 | Upload Knowledge | Knowledge | Yes |
| 7 | Choose Template | Marketplace | Yes |
| 8 | Generate Product | Product Generator | No |
| 9 | Preview | Product Generator | No |
| 10 | Publish | Publish / Product Generator | No |
| 11 | Connect Domain | Domains | Yes |
| 12 | Go Live | Branding + Enterprise | No |

> **Note on steps 1–3:** Users require a `company_id` in this codebase, so
> `POST /onboarding/start` creates the company tenant + owner account together,
> marks **Create Account** complete, and lands on **Verify Email**. Step 3 then
> refines the company profile via `CompanyService.update_company`.

## Features

- Progress tracker (`progress` on every session response)
- Resume later (`resume_token` + `GET /onboarding/resume/{token}` + pause/resume)
- Auto-save (`POST /onboarding/me/autosave`)
- Per-step validation (delegated services + step reachability checks)
- Skip optional steps (`POST /onboarding/me/steps/{step}/skip`)
- Estimated completion time (total + remaining minutes)
- Checklist (completed / skipped / pending)

## API

### Public

- `GET /api/v1/onboarding/flow` — step definition + ETA
- `POST /api/v1/onboarding/start` — signup + session + JWT
- `GET /api/v1/onboarding/resume/{resume_token}`

### Authenticated

- `GET /api/v1/onboarding/me`
- `POST /api/v1/onboarding/me/autosave`
- `POST /api/v1/onboarding/me/pause`
- `POST /api/v1/onboarding/me/resume`
- `POST /api/v1/onboarding/me/steps/{step}/complete` — body `{ "data": { ... } }`
- `POST /api/v1/onboarding/me/steps/{step}/skip`
- `POST /api/v1/onboarding/me/knowledge/upload` — multipart file helper for step 6

### Admin (`platform:admin`)

- `GET /api/v1/onboarding/admin/sessions`
- `GET /api/v1/onboarding/admin/sessions/{id}`
- `GET /api/v1/onboarding/admin/analytics` — completion rate, drop-off, funnel

## Step payloads (complete)

```json
// verify_email
{ "data": { "email": "owner@acme.com", "code": "123456" } }

// create_company
{ "data": { "display_name": "Acme", "industry": "SaaS", "website": "https://acme.com" } }

// choose_plan
{ "data": { "stay_free": true } }
// or
{ "data": { "plan_id": "...", "success_url": "https://...", "cancel_url": "https://..." } }

// create_ai_agent
{ "data": { "name": "Support Bot", "system_prompt_template": "You are..." } }

// upload_knowledge
{ "data": { "name": "Support Docs" } }

// choose_template
{ "data": { "template_id_or_slug": "customer-support" } }

// generate_product
{ "data": { "prompt": "Build a support chatbot for an ecommerce brand" } }

// preview
{ "data": {} }

// publish
{ "data": {} }

// connect_domain
{ "data": { "hostname": "chat.acme.com", "verify_now": false } }

// go_live
{ "data": { "publish_branding": true } }
```

## Migration

```bash
alembic upgrade head
```

Revision: `e5f6a7b8c9d0` (after enterprise `d4e5f6a7b8c9`).

## Tests

```bash
pytest tests/onboarding -q
```
