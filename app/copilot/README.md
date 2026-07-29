# AI Copilot

Natural-language orchestration layer for the THTWAAT AI Platform.

The Copilot **understands intents, plans multi-step workflows, and calls existing
services**. It does **not** reimplement Marketplace, Product Generator, Branding,
Enterprise, Monitoring, Publish, Billing, Domains, or Knowledge business logic.

## Capabilities

- Deterministic NLU (intent + slot extraction)
- Task planning from workflow templates
- Multi-step tool execution with progress
- Conversation memory (agent/generation/domain ids)
- Confirmation gate for destructive tools
- Execution / prompt history, replay, failure diagnostics

## Example prompts

| Prompt | Intent | Tools |
|--------|--------|-------|
| Create a customer support chatbot | `generate_product` | analyze → generate |
| Create agent Support Bot | `create_agent` | create_agent |
| Install template customer-support | `install_template` | install_template |
| Publish my AI product | `publish_website` | publish_agent / publish_product |
| Connect my domain chat.acme.com | `connect_domain` | connect_domain |
| Show platform health | `show_health` | show_health |
| Why did deployment fail? | `view_monitoring` | show_monitoring + show_health |
| Retry failed job | `retry_failed_job` | list + retry (confirm) |

## API

```
POST /api/v1/copilot/chat
GET  /api/v1/copilot/tasks
GET  /api/v1/copilot/tasks/{id}
POST /api/v1/copilot/tasks/{id}/confirm
POST /api/v1/copilot/tasks/{id}/cancel
POST /api/v1/copilot/tasks/{id}/replay
GET  /api/v1/copilot/tasks/{id}/diagnostics
GET  /api/v1/copilot/history
GET  /api/v1/copilot/tools
GET  /api/v1/copilot/admin/executions   # platform admin
```

### Chat body

```json
{
  "message": "Create a customer support chatbot for ecommerce returns",
  "conversation_id": null,
  "auto_execute": true,
  "confirm": false
}
```

Destructive workflows (publish, connect domain, invite, retry job) return
`needs_confirmation: true`. Confirm with:

```json
{ "message": "yes", "conversation_id": "...", "confirm": true }
```

or `POST /copilot/tasks/{id}/confirm`.

## Architecture

```
User message
   → NLU (intents.py + nlu.py)
   → Plan (WORKFLOWS)
   → Confirm if destructive
   → CopilotToolRuntime (tools.py)
        → ProductGenerator / Marketplace / Publish / Domains / …
   → Progress + memory + notifications
```

## Migration

```bash
alembic upgrade head
```

Revision: `a7b8c9d0e1f2`.

## Tests

```bash
pytest tests/copilot -q -m "not integration"
```
