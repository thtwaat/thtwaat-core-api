# THTWAAT Developer Portal

Production documentation site for the THTWAAT AI Platform — guides, SDKs, interactive OpenAPI explorer, downloads, and integration examples.

## Stack

- Next.js 15 + TypeScript
- Tailwind CSS + Shadcn-style UI
- MDX (`next-mdx-remote`)
- Swagger UI + guided API explorer
- Recharts
- Light / dark theme (`next-themes`)

## Quick start

```bash
cd apps/developer-portal
cp .env.example .env.local
npm install
npm run dev
```

Open [http://localhost:3400](http://localhost:3400).

## Environment

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_SITE_URL` | Portal public URL |
| `NEXT_PUBLIC_SITE_NAME` | Site title |
| `NEXT_PUBLIC_API_URL` | THTWAAT Core API origin |
| `NEXT_PUBLIC_DOCS_VERSION` | Docs version badge |

## Routes

| Path | Purpose |
|------|---------|
| `/` | Home |
| `/docs/[slug]` | MDX documentation |
| `/api-explorer` | OpenAPI + code samples + try-it |
| `/downloads` | OpenAPI JSON/YAML, Postman, SDK links |
| `/examples` | Integration recipes |
| `/search` | Full-text docs search |
| `/support` | Support contacts |

## Downloads

- `/openapi.json`
- `/api/downloads/openapi.yaml`
- `/api/downloads/postman`

## Content

- Docs: `content/docs/*.mdx`
- Examples: `content/examples/*.mdx`

Regenerate bundled pages (optional helper):

```bash
node scripts/generate-content.js
```

## Scripts

```bash
npm run dev
npm run build
npm run start
npm run typecheck
```

## Docker

```bash
docker build -t thtwaat-developer-portal .
docker run --rm -p 3400:3400 thtwaat-developer-portal
```

> The Dockerfile expects Next.js `output: "standalone"` (enabled in `next.config.ts`).

## Vercel

Import `apps/developer-portal` as the project root, or set Root Directory to that folder. `vercel.json` is included.

## Notes

- OpenAPI JSON is copied from `sdk/rest/openapi.json`.
- Browser try-it may be blocked by CORS depending on API config — use generated cURL locally when needed.
