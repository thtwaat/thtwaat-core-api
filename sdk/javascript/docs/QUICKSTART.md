# Quick Start

## 1. Publish an agent

Use the dashboard or:

```http
POST /api/v1/agents/{id}/publish
```

Copy the `tht_live_...` API key.

## 2. Install SDK

```bash
npm install @thtwaat/sdk
```

## 3. Chat in 5 lines

```ts
import { THTWAAT } from "@thtwaat/sdk";

const client = new THTWAAT({
  apiKey: process.env.THTWAAT_API_KEY!,
  apiUrl: process.env.THTWAAT_API_URL || "http://localhost:8000",
});

const { reply } = await client.chat("Hello");
console.log(reply);
```

## 4. Add widget to a website

```html
<script
  src="https://api.thtwaat.com/widget.js"
  data-api-key="tht_live_xxx"
  data-theme="light">
</script>
```

Or control it from the SDK in the browser:

```ts
client.widget.open();
```

## 5. Next steps

- Streaming responses
- Knowledge search/upload (JWT)
- Identify users for analytics metadata
