# Deployment Guide — THTWAAT Website Starter

## 1. Connect backend (one-click connect)

1. Open THTWAAT Platform → Agents → **Publish**
2. Copy `tht_live_…` API key and optional widget id
3. Set environment variables on your host:

```env
NEXT_PUBLIC_API_URL=https://api.thtwaat.com
NEXT_PUBLIC_AGENT_API_KEY=tht_live_xxxxxxxxx
NEXT_PUBLIC_SITE_URL=https://www.yourdomain.com
NEXT_PUBLIC_SITE_NAME=Your Brand
NEXT_PUBLIC_BRAND_COLOR=#0F766E
AGENT_API_KEY=tht_live_xxxxxxxxx
LEADS_WEBHOOK_URL=https://hooks.zapier.com/...
```

Local API:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 2. Vercel (one-click deploy)

```bash
npm i -g vercel
cd apps/templates/website
vercel
```

Or use the Vercel dashboard → Import → select this folder → add env vars → Deploy.

**Build settings**

- Framework: Next.js
- Root directory: `apps/templates/website`
- Build: `npm run build`
- Output: `.next`

## 3. Docker

```dockerfile
# apps/templates/website/Dockerfile (example)
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/public ./public
EXPOSE 3100
CMD ["npm", "start"]
```

```bash
docker build -t thtwaat-website .
docker run -p 3100:3100 --env-file .env.local thtwaat-website
```

## 4. Custom domain (one-click publish)

1. Deploy the site to Vercel/Netlify/your VPS
2. In THTWAAT → **Domains** → add `www.yourdomain.com` or `chat.yourdomain.com`
3. Verify DNS (TXT/CNAME) → request SSL
4. Optionally bind the domain to your published agent/widget

## 5. Post-deploy checklist

- [ ] `/chat` streams replies
- [ ] Floating widget appears (bottom-right)
- [ ] `/contact` lead posts to webhook or server logs
- [ ] `/sitemap.xml` and `/robots.txt` resolve
- [ ] Brand color set via env or `/admin`

## 6. Troubleshooting

| Symptom | Fix |
|---------|-----|
| Widget missing | Ensure `NEXT_PUBLIC_AGENT_API_KEY` is set and API allows CORS for your site origin |
| 401 on chat | Key revoked/expired — rotate in Publish → API Keys |
| Empty knowledge | Attach + index a knowledge base on the agent |
| CORS errors | Add site origin in THTWAAT Domain Manager (verified domains auto-allow) |
