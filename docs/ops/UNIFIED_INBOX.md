# Unified Inbox (Messaging)

**Status:** Implemented  
**Surface:** SaaS → **Inbox** (`/app/inbox`)  
**Store:** Existing `agent_conversations` / `agent_messages` via `/v2/conversations` + `/public/v1/chat`

## Route location (do not invent a second page)

| Expected URL | Source file |
|--------------|-------------|
| `/app/inbox` | `apps/templates/saas/src/app/app/inbox/page.tsx` |

There is **no** `apps/templates/saas/app/inbox/page.tsx` (missing `src/` + nested `/app` segment). Next.js App Router maps `src/app/app/inbox/page.tsx` → `/app/inbox`.

Nav: `apps/templates/saas/src/components/layout/app-shell.tsx` → `{ href: "/app/inbox" }`.

Middleware (`src/middleware.ts`) only redirects unauthenticated `/app/*` → `/login` — it does **not** 404 Inbox.

## Production 404 checklist

If `https://app.thtwaat.com/app/inbox` returns **404** but git has the page:

1. Confirm `54dca07` (or later) is on the VPS `main` checkout — `git log -1 --oneline` should include Inbox.
2. Confirm you rebuilt **`web_app`**, not only **`api`**.  
   SaaS UI is image `thtwaat-web-app` from `apps/templates/saas`.  
   `docker compose ... up -d --build api` **never** refreshes `/app/inbox`.
3. Verify the running frontend image contains the route:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec web_app \
  ls -la /app/.next/server/app/app/inbox
```

Missing directory ⇒ stale `web_app` image.

### Exact fix (VPS)

```bash
cd ~/thtwaat-core-api
git pull origin main
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build web_app
# API + migration only needed for conversation schema (channel/status/read):
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build api
docker compose -f docker-compose.prod.yml --env-file .env.prod exec api alembic upgrade head
```

Or full stack: `./deploy/deploy.sh` (builds all services including `web_app`).

## Scope

Finishes the single conversation system already used by the website widget and JWT agent chat. Does **not** add WhatsApp, Telegram, Facebook, email, or voice.

| Requirement | Implementation |
|-------------|----------------|
| Widget conversations | `channel=widget` on public chat create |
| Agent / dashboard conversations | `channel=dashboard` on JWT create |
| List + search + filters | `GET /v2/conversations?q&channel&status&assigned_to&unread_only` |
| Conversation details | `GET /v2/conversations/{id}` (marks read by default) |
| Read / unread | `last_read_at` vs latest user message |
| Assignment-ready | `assigned_to_user_id` + PATCH |
| Handoff-ready | `status`: `open` \| `pending_human` \| `human` \| `closed` |
| Responsive UI | Split list/detail; mobile stack with back |

## API (reuse / extend)

```http
GET    /v2/conversations
GET    /v2/conversations/{id}?mark_read=true
PATCH  /v2/conversations/{id}
POST   /v2/conversations/{id}/messages
POST   /public/v1/chat   # widget → same tables, channel=widget
```

## Migration

`alembic/versions/h2b3c4d5e6f7_unified_inbox_conversation_fields.py`

## Tests

```bash
.venv/Scripts/python.exe -m pytest tests/unit/agent_platform/test_unified_inbox.py -q
cd apps/templates/saas && npm test -- src/lib/inbox.test.ts
```

## Out of scope (intentionally)

- Social / email / voice channels  
- Second messaging product (`ai_conversations`, notifications inbox)  
- Full human-agent live chat protocol (architecture fields only)
