# @thtwaat/sdk

Official JavaScript/TypeScript SDK for the THTWAAT AI Platform.

Works in **browser** and **Node.js 18+**.

## Install

```bash
npm install @thtwaat/sdk
```

## Quick Start

```ts
import { THTWAAT } from "@thtwaat/sdk";

const client = new THTWAAT({
  apiKey: "tht_live_xxxxxxxxx",
  apiUrl: "https://api.thtwaat.com",
});

const res = await client.chat("Hello");
console.log(res.reply, res.conversationId);
```

## Chat

```ts
await client.chat("Hello");

await client.chat({
  message: "Pricing?",
  sessionId: "optional-conversation-id",
  metadata: { page: "/pricing" },
});
```

## Streaming

```ts
// Async iterator
for await (const event of client.streamChat("Hello")) {
  if (event.type === "token") process.stdout.write(event.text);
  if (event.type === "done") console.log("\n", event.result.conversationId);
}

// Callbacks + AbortController
const ac = new AbortController();
await client.streamChatWithCallbacks(
  { message: "Hello", signal: ac.signal },
  {
    onToken: (t) => console.log(t),
    onDone: (r) => console.log(r.reply),
    onError: (e) => console.error(e),
  }
);
```

## Knowledge / Agent / Widget

```ts
await client.search({ query: "refund policy", topK: 5 });
await client.upload({ file, filename: "faq.pdf", kbId: "..." });
await client.history({ limit: 20 });

client.setAgentId("agent-uuid");
await client.agent.info();
await client.agent.status();

// Requires /widget.js loaded in browser
client.widget.open();
client.widget.toggle();
```

## Auth

```ts
new THTWAAT({ apiKey: "tht_live_..." });
new THTWAAT({ bearerToken: "<jwt>" });
new THTWAAT({ sessionToken: "<session jwt>" });
```

## Identify

```ts
client.identify({
  id: "user_123",
  name: "Ada",
  email: "ada@acme.com",
  metadata: { plan: "pro" },
});
```

## Events

```ts
client.on("ready", () => {});
client.on("message", (m) => {});
client.on("typing", (t) => {});
client.on("stream", (e) => {});
client.on("error", (e) => {});
```

## Docs

- [Quick Start](./docs/QUICKSTART.md)
- [API Reference](./docs/API.md)
- [Cookbook](./docs/COOKBOOK.md)
- [Migration Guide](./docs/MIGRATION.md)

## Build / Test

```bash
cd sdk/javascript
npm install
npm test
npm run build
```

## License

UNLICENSED — THTWAAT internal / customer SDK.
