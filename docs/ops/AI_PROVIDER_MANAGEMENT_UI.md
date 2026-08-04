# AI Provider Management UI

**Status:** Implemented (read-only status board)  
**Surface:** SaaS app → **AI Providers** (`/app/providers`)

## Scope

Closes the missing production visibility UX for platform AI gateway providers. Does **not** invent BYOK key editors or runtime routing-policy forms (those remain deployment env).

| Capability | Status |
|------------|--------|
| List providers | `GET /api/v1/ai/providers` |
| Health badges | `GET /api/v1/ai/health` |
| Expand models | `GET /api/v1/ai/models?provider=` |
| Nav (owner/admin/developer) | App shell → AI Providers |
| Tenant `/ai-platform/providers` CRUD UI | **Deferred** — API create path is not encryption-safe; not exposed |

## Auth

Same operator roles as webhooks/templates: `company_owner`, `admin`, `developer`, `super_admin` (`canViewProviders`).

## Ops configuration (not in UI)

```text
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
OPENROUTER_API_KEY=
OLLAMA_URL=
INFERENCE_ROUTING_POLICY=default
INFERENCE_DEFAULT_PROVIDER=ollama
INFERENCE_HEALTH_CACHE_TTL_SECONDS=30
```

## Tests

```bash
cd apps/templates/saas
npm test -- src/lib/provider-status.test.ts src/lib/ai-providers-api.test.ts
```

## Files

- `apps/templates/saas/src/app/app/providers/page.tsx`
- `apps/templates/saas/src/lib/provider-status.ts`
- `apps/templates/saas/src/lib/services.ts` → `aiProvidersApi`
- `apps/templates/saas/src/components/layout/app-shell.tsx`
