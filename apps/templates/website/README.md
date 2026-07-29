# THTWAAT AI Website Starter

Production-ready **Next.js 15** marketing site with THTWAAT AI chat, floating widget, leads, SEO, and a markdown blog — **almost zero configuration**.

## Stack

- Next.js 15 (App Router) · React 19 · TypeScript
- Tailwind CSS · Shadcn-style UI primitives
- THTWAAT `widget.js` + `/public/v1/chat` (+ stream)

## Quick start

```bash
cd apps/templates/website
cp .env.example .env.local
# edit NEXT_PUBLIC_API_URL + NEXT_PUBLIC_AGENT_API_KEY
npm install
npm run dev
```

Open [http://localhost:3100](http://localhost:3100).

### Required env

```env
NEXT_PUBLIC_API_URL=https://api.thtwaat.com   # or http://localhost:8000
NEXT_PUBLIC_AGENT_API_KEY=tht_live_xxxxxxxxx
```

Optional: `AGENT_API_KEY` (server), `LEADS_WEBHOOK_URL`, brand/site vars — see `.env.example`.

## Pages

| Route | Purpose |
|-------|---------|
| `/` | Home + live chat preview |
| `/about` `/services` `/pricing` | Marketing |
| `/blog` `/blog/[slug]` | Markdown CMS |
| `/contact` | Contact + newsletter + quote |
| `/chat` | Full AI chat + knowledge search |
| `/privacy` `/terms` | Legal |
| `/admin` | Theme, logo color, deploy/connect |

## AI features

- Floating widget (`AiWidget` → `widget.js`)
- Full-page streaming chat (`/chat`)
- Suggested questions
- Knowledge search panel (agent-backed)
- Server proxies: `/api/chat`, `/api/chat/stream`, `/api/knowledge`

## Leads

`POST /api/leads` supports `contact` | `newsletter` | `demo` | `quote`.

## SEO

Metadata, Open Graph, Twitter cards, `robots.ts`, `sitemap.ts`, schema.org JSON-LD.

## One-click publish flow

1. **Connect** — publish agent in THTWAAT → copy API key into `.env.local`
2. **Deploy** — Vercel/Netlify or Docker (see `DEPLOYMENT.md`)
3. **Publish** — set custom domain in THTWAAT Domain Manager; point DNS

Admin UI at `/admin` links these actions.

## Project layout

```
src/app/           # routes + API
src/components/    # ui, layout, ai, leads, admin
src/content/blog/  # markdown posts
src/lib/           # config, thtwaat client, seo, blog
```

## License

MIT — part of the THTWAAT AI Platform templates.
