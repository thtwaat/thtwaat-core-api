# Deployment Guide — THTWAAT AI SaaS Starter

## 1. Connect

1. Publish a THTWAAT agent (optional for public widget demos)
2. Copy API base URL + agent key
3. Create `.env.local`:

```env
NEXT_PUBLIC_API_URL=https://api.thtwaat.com
NEXT_PUBLIC_AGENT_API_KEY=tht_live_xxxxxxxxx
NEXT_PUBLIC_SITE_URL=https://app.yourdomain.com
NEXT_PUBLIC_SITE_NAME=Your SaaS
NEXT_PUBLIC_RAZORPAY_KEY_ID=rzp_live_xxx
```

Local:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

```bash
npm install
npm run dev
```

## 2. Deploy (Vercel)

- Root: `apps/templates/saas`
- Framework: Next.js
- Env vars: set the `NEXT_PUBLIC_*` values above
- Build: `npm run build`

```bash
cd apps/templates/saas
npx vercel
```

## 3. Docker

```bash
docker build \
  --build-arg NEXT_PUBLIC_API_URL=https://api.thtwaat.com \
  --build-arg NEXT_PUBLIC_AGENT_API_KEY=tht_live_xxx \
  --build-arg NEXT_PUBLIC_SITE_URL=https://app.yourdomain.com \
  -t thtwaat-saas .
docker run -p 3300:3300 thtwaat-saas
```

## 4. Publish

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
