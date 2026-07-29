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

```html
<iframe
  src="https://api.thtwaat.com/public/v1/widget/embed?api_key=tht_live_xxx"
  width="380"
  height="600"
  style="border:0;border-radius:16px"
></iframe>
```

## Security notes

- Only **PUBLISHED** agents accept public chat.
- API key validated server-side (SHA256).
- Prefer HTTPS in production.
- Set `PUBLIC_API_BASE_URL` so embed scripts point at your API domain.
