# Deployment Guide — THTWAAT AI SaaS Starter

## Production (Docker + nginx on VPS)

Target: **https://app.thtwaat.com** → `web_app:3300`  
API: **https://api.thtwaat.com** (browser calls only; never bake a server IP)

### 1. Env (compose build args)

Add to `.env` / `.env.prod` (see also `.env.frontends.example`):

```env
NEXT_PUBLIC_API_URL=https://api.thtwaat.com
NEXT_PUBLIC_SITE_URL=https://app.thtwaat.com
NEXT_PUBLIC_SITE_NAME=THTWAAT
NEXT_PUBLIC_AGENT_API_KEY=tht_live_xxxxxxxxx
CORS_ORIGINS=["https://app.thtwaat.com","https://admin.thtwaat.com","https://thtwaat.com"]
PUBLIC_API_BASE_URL=https://api.thtwaat.com
```

### 2. Build & start `web_app`

```bash
cd ~/thtwaat-core-api
docker-compose -f docker-compose.prod.yml build web_app
docker-compose -f docker-compose.prod.yml up -d web_app
# rebuild nginx image if nginx.conf upstreams changed
docker-compose -f docker-compose.prod.yml up -d --build nginx
docker-compose -f docker-compose.prod.yml exec nginx nginx -t
docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

Ensure `nginx/ssl/domains/app.thtwaat.com/{fullchain,privkey}.pem` exist (Let's Encrypt copy).

### 3. Verify

```bash
curl -sfI https://app.thtwaat.com/ | head -n5
curl -sf https://api.thtwaat.com/live && echo
# HTML from Next — not API welcome JSON
curl -sf https://app.thtwaat.com/ | head -c 200; echo
```

Browser: login / signup / dashboard; DevTools Network must show `https://api.thtwaat.com/...` only.

### Rollback

Point `app.thtwaat.com` `proxy_pass` back to `http://api_backend;` and reload nginx, then `docker-compose -f docker-compose.prod.yml stop web_app`.

---

## Local connect

1. Publish a THTWAAT agent (optional for public widget demos)
2. Copy API base URL + agent key
3. Create `.env.local`:

```env
NEXT_PUBLIC_API_URL=https://api.thtwaat.com
NEXT_PUBLIC_AGENT_API_KEY=tht_live_xxxxxxxxx
NEXT_PUBLIC_SITE_URL=http://localhost:3300
NEXT_PUBLIC_SITE_NAME=THTWAAT
NEXT_PUBLIC_RAZORPAY_KEY_ID=rzp_live_xxx
```

Local API:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

```bash
npm install
npm run dev
```

## Deploy (Vercel)

- Root: `apps/templates/saas`
- Framework: Next.js
- Env vars: set the `NEXT_PUBLIC_*` values above
- Build: `npm run build`

```bash
cd apps/templates/saas
npx vercel
```

## Docker (standalone image)

```bash
docker build \
  --build-arg NEXT_PUBLIC_API_URL=https://api.thtwaat.com \
  --build-arg NEXT_PUBLIC_AGENT_API_KEY=tht_live_xxx \
  --build-arg NEXT_PUBLIC_SITE_URL=https://app.thtwaat.com \
  --build-arg NEXT_PUBLIC_SITE_NAME=THTWAAT \
  -t thtwaat-saas .
docker run --rm -p 3300:3300 thtwaat-saas
```

## Publish

1. Sign up → create company + owner
2. Create agent → Publish → copy API key / embed
3. Upload knowledge
4. Add domain → Verify DNS → Request SSL
5. Confirm usage + billing plan

## Post-deploy checklist

- [ ] Login / signup / forgot password work
- [ ] `/app` loads usage overview
- [ ] Agent publish + embed snippet available
- [ ] Knowledge upload + search
- [ ] Domain verify + SSL status
- [ ] Billing plans / invoices visible
- [ ] Analytics charts render
- [ ] No CORS errors; API host is `api.thtwaat.com`
