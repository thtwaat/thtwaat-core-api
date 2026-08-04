# Agent Builder UX

**Status:** Implemented  
**Surface:** SaaS → **Agents → Create** (`/app/agents/new`)  
**Constraint:** No backend business-logic changes — composes existing APIs only.

## Wizard (7 steps)

1. Choose Template (marketplace `kind=agent` or blank)  
2. Basic Info  
3. Knowledge (drag/drop upload, progress, index status, search, remove)  
4. AI Provider (`auto` | `ollama` | `openai` | `gemini` | `anthropic` + models)  
5. Capabilities (stored in `web_config.capabilities`)  
6. Appearance (widget theme; live preview)  
7. Publish (review → create → live chat preview → publish)

## UX extras

- Progress indicator + step chips  
- Autosave draft (`localStorage` key `tht_agent_builder_draft_v1`)  
- Per-step validation + error alert  
- Empty / loading / error states  
- Responsive layout (preview sidebar on xl)  
- Keyboard-friendly controls + ARIA labels  

## Knowledge page

`/app/knowledge` also gets drag/drop, upload progress, and index-status badges.

## APIs reused

```http
GET  /api/v1/marketplace/templates?kind=agent
POST /v2/agents
POST /v2/knowledge/bases
POST /v2/knowledge/upload
POST /v2/knowledge/bases/{kb}/agents/{agent}
GET  /api/v1/ai/providers|health|models
PATCH /api/v1/agents/{id}/widget
POST /v2/conversations (+ /messages)   # live preview
POST /api/v1/agents/{id}/publish
```

## Tests

```bash
cd apps/templates/saas
npm test -- src/lib/agent-builder.test.ts
```

## Note

There is still **no** `PATCH /v2/agents/{id}` for prompt/provider after create. The wizard collects those fields before create; appearance can still be patched via widget API.
