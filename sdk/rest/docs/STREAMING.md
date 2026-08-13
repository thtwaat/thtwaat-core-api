# Streaming Guide

```ts
const ac = new AbortController();

for await (const ev of api.agents.streamChat(
  { message: "Hello", api_key: "tht_live_xxx" },
  { signal: ac.signal }
)) {
  if (ev.event === "thinking") {
    // Server-side progress before the first token (e.g. "searching knowledge…").
    // Purely informational — safe to ignore.
    console.log((ev.data as any).stage, (ev.data as any).message);
  }
  if (ev.event === "token") {
    process.stdout.write((ev.data as any).text || "");
  }
  if (ev.event === "done") {
    console.log("\n", ev.data);
  }
  if (ev.event === "error") {
    console.error(ev.data);
  }
}
```

Event kinds emitted by `/public/v1/chat/stream`, in order: `thinking` (zero or
more) → `token` (zero or more) → exactly one of `done` / `error`.

Low-level:

```ts
for await (const ev of api.streamSSE("/public/v1/chat/stream", body, { signal })) {
  console.log(ev.event, ev.data);
}
```
