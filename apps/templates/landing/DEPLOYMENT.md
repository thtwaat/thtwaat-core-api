# Deployment Guide — THTWAAT AI Landing Starter

## 1. Connect (one-click connect)

1. Open THTWAAT Platform → Agents → **Publish**
2. Copy your `tht_live_…` agent API key
3. Create `.env.local`:

```env
NEXT_PUBLIC_API_URL=https://api.thtwaat.com
NEXT_PUBLIC_AGENT_API_KEY=tht_live_xxxxxxxxx
NEXT_PUBLIC_SITE_URL=https://www.yourdomain.com
NEXT_PUBLIC_SITE_NAME=Your Brand
LEADS_WEBHOOK_URL=https://hooks.zapier.com/...
```

Local API:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Run locally:

```bash
cd apps/templates/landing
npm install
npm run dev
```

Open [http://localhost:3200](http://localhost:3200).

## 2. Vercel (one-click deploy)

```bash
npm i -g vercel
cd apps/templates/landing
vercel
```

Or: Vercel dashboard → Import → root `apps/templates/landing` → add env vars → Deploy.

**Build settings**

- Framework: Next.js
- Root directory: `apps/templates/landing`
- Build: `npm run build`
- Output: `.next`

## 3. Docker

```bash
docker build \
  --build-arg NEXT_PUBLIC_API_URL=https://api.thtwaat.com \
  --build-arg NEXT_PUBLIC_AGENT_API_KEY=tht_live_xxx \
  --build-arg NEXT_PUBLIC_SITE_URL=https://yourdomain.com \
  -t thtwaat-landing .
docker run -p 3200:3200 thtwaat-landing
```

## 4. Custom domain (one-click publish)

1. Deploy the landing page to Vercel, Netlify, or your VPS
2. In THTWAAT → **Domains** → add `www.yourdomain.com`
3. Verify DNS (TXT/CNAME) → request SSL → status **LIVE**
4. Point your marketing domain at the deployed site

## 5. Lead routing

`POST /api/leads` accepts `contact`, `newsletter`, `demo`, and `quote`.

Set `LEADS_WEBHOOK_URL` to an existing THTWAAT webhook, Zapier, Make, or CRM endpoint. Events are sent as:

```json
{
  "event": "lead.demo",
  "data": { "type": "demo", "email": "...", "name": "..." },
  "source": "ai-landing-starter",
  "received_at": "2026-07-29T12:00:00.000Z"
}
```

## 6. Post-deploy checklist

- [ ] Hero CTA opens inline assistant or floating widget
- [ ] Streaming chat works (`/public/v1/chat/stream`)
- [ ] Knowledge search returns grounded answers
- [ ] Demo / quote / newsletter / contact forms submit
- [ ] `robots.txt`, `sitemap.xml`, and OG image load
- [ ] Custom domain verified and SSL active in THTWAAT
