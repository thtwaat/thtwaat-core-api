# Cookbook

## Persist conversation across page loads

```ts
const saved = localStorage.getItem("tht_session");
const res = await client.chat({
  message: "Continue",
  sessionId: saved,
});
localStorage.setItem("tht_session", res.conversationId);
```

## Abort a long stream

```ts
const ac = new AbortController();
setTimeout(() => ac.abort(), 3000);
try {
  await client.streamChatWithCallbacks(
    { message: "Write a long essay", signal: ac.signal },
    { onToken: (t) => console.log(t) }
  );
} catch (e) {
  console.log("aborted");
}
```

## React hook sketch

```ts
function useThtwaat(apiKey: string) {
  const client = useMemo(
    () => new THTWAAT({ apiKey, apiUrl: process.env.NEXT_PUBLIC_API_URL }),
    [apiKey]
  );
  return client;
}
```

## Handle rate limits

```ts
import { isRateLimited } from "@thtwaat/sdk";

try {
  await client.chat("hi");
} catch (e) {
  if (isRateLimited(e)) {
    // backoff / show friendly message
  }
}
```

## Server-side Express proxy

Never expose company JWT to browsers for admin routes. Use API keys for public chat; proxy JWT routes on your backend.
