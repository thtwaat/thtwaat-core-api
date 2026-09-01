# Embed Documentation

## Dashboard copy endpoints

```http
GET /api/v1/agents/{agent_id}/embed
Authorization: Bearer <jwt>
```

Returns `script`, `iframe`, `preview_url`, and `config`.

```http
GET /api/v1/agents/{agent_id}/widget
PATCH /api/v1/agents/{agent_id}/widget
```

Update theme, welcome message, prompts, logo, position.

## Vanilla HTML

```html
<!doctype html>
<html>
  <body>
    <h1>My Site</h1>
    <script
      src="http://localhost:8000/widget.js"
      data-api-key="tht_live_xxx"
      data-theme="light"
      data-position="bottom-right">
    </script>
  </body>
</html>
```

## React

```tsx
import { useEffect } from "react";

export function ThtwaatChat({ apiKey }: { apiKey: string }) {
  useEffect(() => {
    const s = document.createElement("script");
    s.src = "https://api.thtwaat.com/widget.js";
    s.async = true;
    s.dataset.apiKey = apiKey;
    s.dataset.theme = "light";
    s.dataset.position = "bottom-right";
    document.body.appendChild(s);
    return () => {
      window.THTWAAT?.destroy?.();
      s.remove();
    };
  }, [apiKey]);
  return null;
}
```

## Next.js (App Router)

```tsx
"use client";
import Script from "next/script";

export default function ChatWidget({ apiKey }: { apiKey: string }) {
  return (
    <Script
      src={`${process.env.NEXT_PUBLIC_API_URL}/widget.js`}
      data-api-key={apiKey}
      data-theme="auto"
      data-position="bottom-right"
      strategy="afterInteractive"
    />
  );
}
```

## Vue 3

```vue
<script setup>
import { onMounted, onBeforeUnmount } from "vue";
const props = defineProps({ apiKey: String });
onMounted(() => {
  const s = document.createElement("script");
  s.src = "https://api.thtwaat.com/widget.js";
  s.dataset.apiKey = props.apiKey;
  document.body.appendChild(s);
});
onBeforeUnmount(() => window.THTWAAT?.destroy?.());
</script>
<template><div /></template>
```

## Angular

```ts
import { Injectable } from "@angular/core";

@Injectable({ providedIn: "root" })
export class ThtwaatWidgetService {
  load(apiKey: string) {
    const s = document.createElement("script");
    s.src = "https://api.thtwaat.com/widget.js";
    s.dataset["apiKey"] = apiKey;
    document.body.appendChild(s);
  }
  destroy() {
    (window as any).THTWAAT?.destroy?.();
  }
}
```

## iframe

Live API keys (`tht_live_*`) are rejected in iframe URLs — the endpoint requires a
`widget_id` + short-lived `embed_token` instead (P0 hardening: no long-lived keys in
URLs). Don't hand-build this URL; use the ready-made `iframe` string from
`GET /api/v1/agents/{agent_id}/embed` (dashboard-authenticated), which mints a fresh
token for you:

```http
GET /api/v1/agents/{agent_id}/embed
Authorization: Bearer <jwt>
```

```json
{
  "iframe": "<iframe src=\"https://api.thtwaat.com/public/v1/widget/embed?widget_id=wgt_...&embed_token=...\" width=\"380\" height=\"600\" style=\"border:0;border-radius:16px;\" allow=\"clipboard-write\"></iframe>",
  ...
}
```

If you need to construct the URL yourself, the shape is:

```html
<iframe
  src="https://api.thtwaat.com/public/v1/widget/embed?widget_id=wgt_xxx&embed_token=<short-lived-token>"
  width="380"
  height="600"
  style="border:0;border-radius:16px"
></iframe>
```

`embed_token` is short-lived and signed — mint a fresh one server-side per page load
rather than hardcoding it (it expires; re-fetch `/embed` when it does).

## Voice / vision / image generation

These UI controls only appear if you declare them — there is no public endpoint
that exposes an agent's capability flags, so the embed script mirrors what you've
already enabled on the agent (`web_config.capabilities`), the same way
`data-handoff`/`data-lead-capture` already work:

```html
<script
  src="https://api.thtwaat.com/widget.js"
  data-api-key="tht_live_xxx"
  data-agent-slug="viral-awaaz-assistant"
  data-voice="true"
  data-vision="true"
  data-image-generation="true">
</script>
```

- `data-agent-slug` — required for the mic and image-generation actions (they
  call the by-slug endpoints, `POST /public/v1/agents/{slug}/voice|image`).
  Text chat and image *input* don't need it.
- `data-voice="true"` — shows a mic button; only renders if the browser also
  supports `MediaRecorder`/`getUserMedia`.
- `data-vision="true"` — shows an image-attach button in the composer.
- `data-image-generation="true"` — shows a "generate image" action that turns
  whatever's typed in the composer into an image-generation prompt.

Turning one of these on when the agent's matching backend capability is
**not** enabled doesn't break anything — the request just comes back with a
400 ("does not have the X capability enabled"), which renders as a normal
error bubble.

## Security notes

- Only **PUBLISHED** agents accept public chat.
- API key validated server-side (SHA256).
- Prefer HTTPS in production.
- Set `PUBLIC_API_BASE_URL` so embed scripts point at your API domain.
