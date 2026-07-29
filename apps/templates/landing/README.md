# THTWAAT AI Landing Page Starter

High-converting single-page landing experience connected to the THTWAAT backend with **zero backend changes**.

## Stack

- Next.js 15
- TypeScript
- Tailwind CSS
- Shadcn-style UI primitives

## Zero-config connection

```bash
cd apps/templates/landing
cp .env.example .env.local
```

Required:

```env
NEXT_PUBLIC_API_URL=https://api.thtwaat.com
NEXT_PUBLIC_AGENT_API_KEY=tht_live_xxxxxxxxx
```

Then:

```bash
npm install
npm run dev
```

Open [http://localhost:3200](http://localhost:3200).

## Sections

1. Hero
2. AI Chat CTA (inline streaming assistant)
3. Features
4. Benefits
5. Pricing
6. Testimonials
7. FAQ (AI-powered)
8. Book Demo
9. Contact / Quote / Newsletter
10. Footer

## AI integrations (existing APIs only)

| Feature | Integration |
|---|---|
| Floating widget | `${API_URL}/widget.js` |
| Inline assistant | `/api/chat/stream` → `/public/v1/chat/stream` |
| Streaming fallback | `/public/v1/chat` |
| Suggested questions | Preloaded prompts + widget prompts |
| Knowledge search | `/api/knowledge` via published agent RAG |

## Lead capture

`POST /api/leads` supports:

- `contact`
- `newsletter`
- `demo`
- `quote`

Set `LEADS_WEBHOOK_URL` to forward events into an existing THTWAAT webhook / CRM automation.

## SEO included

- Metadata
- Open Graph
- Twitter cards
- `robots.ts`
- `sitemap.ts`
- JSON-LD (`Organization` + `SoftwareApplication`)

## One-click publish flow

See [DEPLOYMENT.md](./DEPLOYMENT.md) for the full guide.

1. **Connect** — publish a THTWAAT agent and set the two env vars
2. **Deploy** — Vercel import this folder, or build the included Dockerfile
3. **Publish** — attach a custom domain in THTWAAT Domain Manager

```bash
# Docker
docker build \
  --build-arg NEXT_PUBLIC_API_URL=https://api.thtwaat.com \
  --build-arg NEXT_PUBLIC_AGENT_API_KEY=tht_live_xxx \
  --build-arg NEXT_PUBLIC_SITE_URL=https://yourdomain.com \
  -t thtwaat-landing .
docker run -p 3200:3200 thtwaat-landing
```

## Project layout

```text
src/app/                 # Landing page + SEO + API proxies
src/components/          # Inline assistant, FAQ, lead forms, publish strip
src/components/ui/       # Shadcn-style primitives (Button, Card, Input)
src/lib/config.ts        # Brand + API config
public/og.svg            # Social preview
Dockerfile
DEPLOYMENT.md
.env.example
components.json
vercel.json
```
