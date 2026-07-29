# THTWAAT AI SaaS Starter

Production-ready Next.js 15 SaaS dashboard that consumes the existing THTWAAT Core API with **zero backend changes**.

## Stack

- Next.js 15 + TypeScript
- Tailwind CSS + Shadcn-style UI
- TanStack Query
- React Hook Form + Zod
- Recharts

## Quick start

```bash
cd apps/templates/saas
cp .env.example .env.local
npm install
npm run dev
```

Open [http://localhost:3300](http://localhost:3300).

Required env:

```env
NEXT_PUBLIC_API_URL=https://api.thtwaat.com
NEXT_PUBLIC_AGENT_API_KEY=tht_live_xxxxxxxxx
```

## Features

| Area | Routes | Backend |
|---|---|---|
| Auth | `/login` `/signup` `/forgot-password` `/otp` | `/api/v1/auth/*`, `/companies`, `/users` |
| Dashboard | `/app` | `/usage/current`, `/v2/conversations`, `/v2/agents` |
| Agents | `/app/agents` | `/v2/agents`, publish/unpublish, API keys, embed |
| Knowledge | `/app/knowledge` | `/v2/knowledge` upload/search/delete |
| Domains | `/app/domains` | `/api/v1/domains` verify/SSL/retry |
| Billing | `/app/billing` | plans, subscriptions, invoices, usage quotas |
| Analytics | `/app/analytics` | `/usage/history`, `/usage/dashboard` |
| Settings | `/app/settings` | profile, company, members, API keys |
| Publish | `/app/publish` | Connect → Deploy → Publish checklist |

## Auth model

- JWT Bearer tokens from `/api/v1/auth/login`
- Access + refresh stored in `localStorage`
- Session cookie `tht_session` for middleware-protected `/app/*`
- Auto refresh on `401`
- OTP + MFA-ready flows included

## Deploy

See [DEPLOYMENT.md](./DEPLOYMENT.md).

```bash
docker build \
  --build-arg NEXT_PUBLIC_API_URL=https://api.thtwaat.com \
  --build-arg NEXT_PUBLIC_AGENT_API_KEY=tht_live_xxx \
  --build-arg NEXT_PUBLIC_SITE_URL=https://app.yourdomain.com \
  -t thtwaat-saas .
docker run -p 3300:3300 thtwaat-saas
```

## Project layout

```text
src/app/                 Marketing + auth + /app modules
src/components/          Shell + Shadcn-style UI
src/lib/api.ts           Typed fetch client + refresh
src/lib/services.ts      Backend resource helpers
src/lib/auth.tsx         Auth provider
Dockerfile
.env.example
```
