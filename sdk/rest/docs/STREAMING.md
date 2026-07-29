# Streaming Guide

```ts
const ac = new AbortController();

for await (const ev of api.agents.streamChat(
  { message: "Hello", api_key: "tht_live_xxx" },
  { signal: ac.signal }
)) {
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

Low-level:

```ts
for await (const ev of api.streamSSE("/public/v1/chat/stream", body, { signal })) {
  console.log(ev.event, ev.data);
}
```
