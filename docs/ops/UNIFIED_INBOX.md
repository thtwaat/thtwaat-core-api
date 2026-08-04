# Unified Inbox (Messaging)

**Status:** Implemented  
**Surface:** SaaS → **Inbox** (`/app/inbox`)  
**Store:** Existing `agent_conversations` / `agent_messages` via `/v2/conversations` + `/public/v1/chat`

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
