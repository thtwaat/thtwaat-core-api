const fs = require("fs");
const path = require("path");
const root = path.join(__dirname, "..");
const docsDir = path.join(root, "content", "docs");
const exDir = path.join(root, "content", "examples");
fs.mkdirSync(docsDir, { recursive: true });
fs.mkdirSync(exDir, { recursive: true });

function write(dir, name, body) {
  fs.writeFileSync(path.join(dir, name), body.replace(/^\n/, ""));
}

const docs = {
  "authentication.mdx": `---
title: Authentication
description: API keys, JWT bearer tokens, OTP, and refresh flows.
order: 2
section: Getting started
---

## Auth modes

THTWAAT supports two primary credentials:

| Mode | Header | Use for |
|------|--------|---------|
| Agent API key | \`Authorization: Bearer tht_live_...\` or \`X-API-Key\` | Public chat, widget, streaming |
| User JWT | \`Authorization: Bearer <access_token>\` | Dashboard / admin routes |

## Login (JWT)

\`\`\`http
POST /api/v1/auth/login
Content-Type: application/json

{"email":"owner@acme.com","password":"••••••••"}
\`\`\`

Response includes \`access_token\` and \`refresh_token\`.

## Refresh

\`\`\`http
POST /api/v1/auth/refresh
{"refresh_token":"..."}
\`\`\`

## OTP

\`\`\`http
POST /api/v1/auth/send-otp
{"purpose":"login","email":"owner@acme.com"}

POST /api/v1/auth/verify-otp
{"purpose":"login","email":"owner@acme.com","code":"123456"}
\`\`\`

## JavaScript SDK

\`\`\`ts
import { THTWAAT } from "@thtwaat/sdk";

new THTWAAT({ apiKey: "tht_live_xxx" });
new THTWAAT({ bearerToken: "<jwt>" });
\`\`\`

## REST SDK

\`\`\`ts
import { RestClient } from "@thtwaat/rest";

const api = new RestClient({ apiUrl: process.env.THTWAAT_API_URL! });
const tokens = await api.auth.login({ email, password }) as any;
api.setBearerToken(tokens.access_token);
\`\`\`

## Security notes

- Never embed owner JWTs in public websites.
- Rotate published agent keys from the dashboard.
- Prefer HTTPS everywhere in production.
`,
  "rest-api.mdx": `---
title: REST API
description: Versioned HTTP API surface for the THTWAAT Core platform.
order: 3
section: API
---

## Base URLs

| Prefix | Purpose |
|--------|---------|
| \`/api/v1\` | Core platform (auth, companies, billing, marketplace, domains) |
| \`/v2\` | Agent platform (agents, knowledge, conversations) |
| \`/public/v1\` | Public chat & widget endpoints |

Base: \`https://api.thtwaat.com\` (or your self-hosted origin).

## Core resources

- Auth — login, refresh, OTP, MFA
- Companies / Users / Apps
- Agents — create, publish, embed, API keys
- Knowledge — bases, upload, search
- Domains — verify, SSL
- Marketplace — templates, install, versions
- Product Generator — analyze, generate, publish
- Usage & Billing — meters, plans, invoices

## OpenAPI

- Interactive explorer: [/api-explorer](/api-explorer)
- Download JSON: [/openapi.json](/openapi.json)
- Download YAML: [/api/downloads/openapi.yaml](/api/downloads/openapi.yaml)

## Conventions

- JSON request/response bodies
- UUID path params
- ISO-8601 timestamps
- Standard HTTP status codes (see [Errors](/docs/errors))
`,
  "javascript-sdk.mdx": `---
title: JavaScript SDK
description: Official browser and Node.js SDK (@thtwaat/sdk).
order: 4
section: SDKs
---

## Install

\`\`\`bash
npm install @thtwaat/sdk
\`\`\`

## Quick chat

\`\`\`ts
import { THTWAAT } from "@thtwaat/sdk";

const client = new THTWAAT({
  apiKey: process.env.THTWAAT_API_KEY!,
  apiUrl: process.env.THTWAAT_API_URL || "https://api.thtwaat.com",
});

const { reply, conversationId } = await client.chat("Hello");
console.log(reply, conversationId);
\`\`\`

## Streaming

\`\`\`ts
for await (const event of client.streamChat("Hello")) {
  if (event.type === "token") process.stdout.write(event.text);
  if (event.type === "done") console.log("\\n", event.result);
}
\`\`\`

## Knowledge / Agent / Widget

\`\`\`ts
await client.search({ query: "refund policy", topK: 5 });
client.setAgentId("agent-uuid");
await client.agent.info();
client.widget.open(); // browser + widget.js
\`\`\`

## Events

\`ready | message | typing | stream | error | disconnect | reconnect\`

Source: \`sdk/javascript\` in the monorepo.
`,
  "rest-sdk.mdx": `---
title: REST SDK
description: Typed OpenAPI-backed REST client (@thtwaat/rest).
order: 5
section: SDKs
---

## Install

\`\`\`bash
cd sdk/rest
npm install
npm run build
\`\`\`

## Create client

\`\`\`ts
import { RestClient } from "@thtwaat/rest";

const api = new RestClient({
  apiUrl: "https://api.thtwaat.com",
  apiKey: "tht_live_xxx",
});
\`\`\`

## Modules

\`\`\`ts
await api.auth.login({ email, password });
await api.agents.list();
await api.agents.publish(agentId);
await api.agents.chat({ message: "Hi" });
await api.knowledge.upload(file, { filename: "faq.pdf", kbId });
await api.domains.list();
await api.payments.list();
\`\`\`

## Streaming

\`\`\`ts
for await (const ev of api.agents.streamChat({ message: "Hello", api_key: "tht_live_xxx" })) {
  if (ev.event === "token") process.stdout.write((ev.data as any).text || "");
}
\`\`\`

## Regenerate types

\`\`\`bash
curl -o openapi.json http://localhost:8000/openapi.json
npm run generate
\`\`\`
`,
  "widget-sdk.mdx": `---
title: Widget SDK
description: Embeddable floating chat widget for any website.
order: 6
section: SDKs
---

## One-line embed

\`\`\`html
<script
  src="https://api.thtwaat.com/widget.js"
  data-api-key="tht_live_xxxxxxxxx"
  data-theme="light"
  data-position="bottom-right"
  data-primary-color="#111827"
  data-welcome="Hi! How can I help you today?"
  data-prompts="Pricing?|Book appointment|Contact support">
</script>
\`\`\`

## Programmatic API

\`\`\`js
const chat = window.THTWAAT.init({
  apiKey: "tht_live_xxx",
  apiBaseUrl: "https://api.thtwaat.com",
  theme: { mode: "dark", primaryColor: "#0f766e" },
  onMessage: (m) => console.log(m),
});

chat.open();
chat.sendMessage("Hello");
chat.setTheme("light");
chat.identifyUser({ email: "user@acme.com" });
chat.destroy();
\`\`\`

## Features

- Floating launcher with open/close animation
- Light / dark / auto theme
- Streaming via \`/public/v1/chat/stream\`
- Session persistence
- Shadow DOM isolation
- Keyboard accessibility

Package: \`sdk/widget\` builds \`widget.js\` served by Core API.
`,
  "flutter-sdk.mdx": `---
title: Flutter SDK
description: Native Flutter / Dart client — coming soon.
order: 7
section: SDKs
---

## Status

<Callout type="warn">
Flutter SDK is **Coming Soon** (Module 42). Use REST endpoints or the JavaScript SDK from Flutter Web today.
</Callout>

## Planned surface

- \`ThtwaatClient\` with API key / JWT auth
- Chat + streaming
- Knowledge search
- Widget bridge for Flutter WebView embeds

## Temporary workaround

\`\`\`dart
final res = await http.post(
  Uri.parse('\$apiUrl/public/v1/chat'),
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer \$apiKey',
  },
  body: jsonEncode({'message': 'Hello'}),
);
\`\`\`

Watch [Release Notes](/docs/release-notes) for Flutter SDK GA.
`,
  "webhooks.mdx": `---
title: Webhooks
description: Receive platform events in your backend.
order: 8
section: API
---

## Overview

Register webhook endpoints to receive signed JSON payloads for billing, domain, agent, and notification events.

## Create a webhook

\`\`\`http
POST /api/v1/webhooks
Authorization: Bearer <jwt>
Content-Type: application/json

{
  "url": "https://hooks.acme.com/thtwaat",
  "events": ["payment.succeeded", "domain.verified", "agent.published"],
  "secret": "whsec_..."
}
\`\`\`

## Payload shape

\`\`\`json
{
  "id": "evt_...",
  "type": "agent.published",
  "created_at": "2026-07-29T10:00:00Z",
  "data": { "agent_id": "..." }
}
\`\`\`

## Verification

Validate the signature header with your webhook secret before processing. Respond with \`2xx\` quickly; handlers should be idempotent on \`id\`.

## Delivery retries

Failed deliveries retry with exponential backoff for retryable statuses (5xx / timeouts).
`,
  "rate-limits.mdx": `---
title: Rate Limits
description: Quotas, usage meters, and HTTP 429 behavior.
order: 9
section: API
---

## Plan quotas

Usage is metered per company across dimensions such as:

- AI messages / tokens
- Agents, API keys, domains
- Knowledge storage / uploads
- Templates published
- Widget / API requests

Exceeding a hard quota returns **HTTP 429** with a structured error body.

## Headers

When present, inspect:

- \`X-RateLimit-Limit\`
- \`X-RateLimit-Remaining\`
- \`Retry-After\`

## SDK behavior

Both \`@thtwaat/sdk\` and \`@thtwaat/rest\` retry **429 / 502 / 503 / 504** with exponential backoff by default.

## Best practices

- Cache knowledge search results when possible
- Stream long answers instead of polling
- Use webhooks for async lifecycle events
`,
  "errors.mdx": `---
title: Errors
description: HTTP status codes and SDK error objects.
order: 10
section: API
---

## HTTP status map

| Status | Meaning |
|--------|---------|
| 400 | Validation / bad request |
| 401 | Missing or invalid credentials |
| 403 | Authenticated but not permitted |
| 404 | Resource not found |
| 409 | Conflict (duplicate slug/install) |
| 413 | Upload too large |
| 415 | Unsupported media type |
| 429 | Rate limited / quota exceeded |
| 5xx | Server / upstream failure |

## JavaScript SDK

\`\`\`ts
import { THTWAATError } from "@thtwaat/sdk";

try {
  await client.chat("hi");
} catch (e) {
  if (e instanceof THTWAATError && e.status === 429) {
    // backoff
  }
}
\`\`\`

## REST SDK

\`\`\`ts
import { RestError } from "@thtwaat/rest";

try {
  await api.agents.chat({ message: "hi" });
} catch (e) {
  if (e instanceof RestError) {
    console.log(e.status, e.code, e.retryable, e.details);
  }
}
\`\`\`

Fields: \`status\`, \`code\`, \`message\`, \`details\`, \`retryable\`.
`,
  "changelog.mdx": `---
title: Changelog
description: Chronological product and API changes.
order: 11
section: Guides
---

## 2026-07 — Platform foundation

- Publish Engine (agent publish, API keys, widget embed)
- Domain Manager + SSL automation
- Usage Meter + Billing plans/invoices
- Marketplace Template Registry (install / version / rollback)
- AI Product Generator orchestration
- Website / Landing / SaaS starters
- JavaScript, REST, and Widget SDKs
- Developer Portal (docs, explorer, downloads)

## Upcoming

- Flutter SDK (Module 42)
- Expanded webhook event catalog
- Additional marketplace categories
`,
  "release-notes.mdx": `---
title: Release Notes
description: Highlights for the current platform release.
order: 12
section: Guides
---

## THTWAAT AI Platform v1.0 Foundation

This release packages a production-ready AI product factory:

### Backend

- Core API with RBAC, usage quotas, billing, domains, marketplace, product generator

### SDKs

- \`@thtwaat/sdk\` — chat, stream, knowledge, widget bridge
- \`@thtwaat/rest\` — typed REST client from OpenAPI
- \`@thtwaat/widget\` — embeddable chat widget

### Templates

- Website, Landing, SaaS starters wired to existing APIs

### Developer experience

- OpenAPI explorer, Postman export, MDX docs, light/dark portal

### Upgrade notes

- Seed marketplace templates before using Product Generator
- Apply Alembic migrations through \`b2c3d4e5f6a7\`
`,
  "faq.mdx": `---
title: FAQ
description: Common questions from integrating developers.
order: 13
section: Guides
---

## Do I need to change the backend to use templates?

No. Website, Landing, and SaaS starters consume existing APIs with env vars only.

## API key vs JWT?

Use **API keys** for public chat/widget. Use **JWT** for dashboard CRUD (agents, domains, billing).

## Where is OpenAPI?

- Live (non-prod): \`{API}/openapi.json\`
- Portal: [/openapi.json](/openapi.json)
- Explorer: [/api-explorer](/api-explorer)

## Can I self-host?

Yes — Docker Compose / production compose ships with Core API, Nginx, Postgres, Redis, MinIO.

## Flutter SDK?

Coming soon. Use REST from Dart until Module 42 ships.

## How do I get support?

See [Support](/support). Include status codes, endpoint paths, and redacted payloads.
`,
  "support.mdx": `---
title: Support
description: How to get help with THTWAAT integrations.
order: 14
section: Guides
---

## Channels

1. Search this portal
2. Reproduce in [API Explorer](/api-explorer)
3. Email **developers@thtwaat.com**

## Ticket checklist

- Company slug / environment
- Endpoint + HTTP status
- SDK name + version
- Redacted request/response
- Whether issue is CORS, auth, quota, or payload

Also see the dedicated [Support page](/support).
`
};

const examples = {
  "website.mdx": `---
title: Website Integration
description: Connect the AI Website Starter to THTWAAT.
order: 1
---

## Env

\`\`\`bash
NEXT_PUBLIC_API_URL=https://api.thtwaat.com
NEXT_PUBLIC_AGENT_API_KEY=tht_live_xxx
\`\`\`

## Widget

Load \`/widget.js\` in \`layout.tsx\` with your API key (see \`apps/templates/website\`).

## Chat routes

Template routes under \`src/app/api/chat\` and \`src/app/api/knowledge\` proxy to Core API.
`,
  "landing.mdx": `---
title: Landing Integration
description: High-converting landing page with inline AI assistant.
order: 2
---

## Setup

\`\`\`bash
cd apps/templates/landing
cp .env.example .env.local
npm install
npm run dev
\`\`\`

## Leads

\`POST /api/leads\` forwards to your webhook or Core notifications endpoint.

## AI FAQ

\`AiFaq\` streams answers via \`/api/chat/stream\`.
`,
  "saas.mdx": `---
title: SaaS Integration
description: Full dashboard starter with JWT auth and marketplace.
order: 3
---

## Env

\`\`\`bash
NEXT_PUBLIC_API_URL=https://api.thtwaat.com
NEXT_PUBLIC_AGENT_API_KEY=tht_live_xxx
\`\`\`

## Auth flow

Login → optional MFA/OTP → session cookie \`tht_session\` → protected \`/app/*\` routes.

## Modules

Agents, Knowledge, Marketplace, Domains, Billing, Analytics, Product Generator (\`/app/create\`).
`,
  "react.mdx": `---
title: React
description: Embed chat in a React 19 SPA.
order: 4
---

\`\`\`tsx
import { useEffect } from "react";

export function ThtwaatChat({ apiKey }: { apiKey: string }) {
  useEffect(() => {
    const s = document.createElement("script");
    s.src = "https://api.thtwaat.com/widget.js";
    s.async = true;
    s.dataset.apiKey = apiKey;
    s.dataset.theme = "light";
    document.body.appendChild(s);
    return () => { s.remove(); };
  }, [apiKey]);
  return null;
}
\`\`\`
`,
  "nextjs.mdx": `---
title: Next.js
description: App Router integration patterns.
order: 5
---

## Client SDK

\`\`\`ts
import { THTWAAT } from "@thtwaat/sdk";

export const tht = new THTWAAT({
  apiKey: process.env.NEXT_PUBLIC_AGENT_API_KEY!,
  apiUrl: process.env.NEXT_PUBLIC_API_URL!,
});
\`\`\`

## Server route proxy

Prefer server routes when you must hide JWT secrets — never expose owner JWTs to the browser.
`,
  "nodejs.mdx": `---
title: Node.js
description: Server-side chat with the REST SDK.
order: 6
---

\`\`\`ts
import { RestClient } from "@thtwaat/rest";

const api = new RestClient({
  apiUrl: process.env.THTWAAT_API_URL!,
  apiKey: process.env.THTWAAT_API_KEY!,
});

const res = await api.agents.chat({ message: "Hello from Node" });
console.log(res);
\`\`\`
`,
  "express.mdx": `---
title: Express
description: Express middleware proxy for public chat.
order: 7
---

\`\`\`ts
import express from "express";
import { RestClient } from "@thtwaat/rest";

const app = express();
app.use(express.json());
const api = new RestClient({
  apiUrl: process.env.THTWAAT_API_URL!,
  apiKey: process.env.THTWAAT_API_KEY!,
});

app.post("/chat", async (req, res) => {
  try {
    const out = await api.agents.chat({ message: req.body.message });
    res.json(out);
  } catch (e: any) {
    res.status(e.status || 500).json({ error: e.message });
  }
});
\`\`\`
`,
  "fastapi.mdx": `---
title: FastAPI
description: Python proxy to THTWAAT public chat.
order: 8
---

\`\`\`python
import os, httpx
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()
API = os.environ["THTWAAT_API_URL"].rstrip("/")
KEY = os.environ["THTWAAT_API_KEY"]

class ChatIn(BaseModel):
    message: str

@app.post("/chat")
async def chat(body: ChatIn):
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{API}/public/v1/chat",
            headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
            json={"message": body.message},
        )
        r.raise_for_status()
        return r.json()
\`\`\`
`
};

for (const [name, body] of Object.entries(docs)) write(docsDir, name, body);
for (const [name, body] of Object.entries(examples)) write(exDir, name, body);
console.log("wrote", Object.keys(docs).length, "docs and", Object.keys(examples).length, "examples");
