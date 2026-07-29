# Migration Guide

## From raw `fetch` / curl

Before:

```ts
await fetch("/public/v1/chat", {
  method: "POST",
  headers: { Authorization: `Bearer ${key}` },
  body: JSON.stringify({ api_key: key, message: "hi" }),
});
```

After:

```ts
const client = new THTWAAT({ apiKey: key, apiUrl });
await client.chat("hi");
```

## From Widget-only embeds

Widget.js remains the drop-in script.

Use `@thtwaat/sdk` when you need programmatic chat, streaming, knowledge, or server-side Node usage.

Both can coexist:

1. Load `/widget.js` for UI
2. Use `THTWAAT` SDK for API calls / events

## Breaking changes

`v1.0.0` is the first public SDK release — no prior migration needed.
