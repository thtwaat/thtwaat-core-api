# API Reference

## `new THTWAAT(config)`

| Option | Type | Description |
|--------|------|-------------|
| `apiKey` | string | Public agent key `tht_live_...` |
| `bearerToken` | string | JWT access token |
| `sessionToken` | string | Session JWT alias |
| `apiUrl` / `baseURL` | string | API origin |
| `timeoutMs` | number | Default 60000 |
| `maxRetries` | number | Default 2 |
| `headers` | object | Extra headers |
| `language` | string | Accept-Language |
| `theme` | string | Preferred theme |
| `debug` | boolean | Console logs |
| `fetch` | function | Custom fetch |

## Chat

- `client.chat(message | ChatRequestObject): Promise<ChatResponse>`
- `client.streamChat(...): AsyncGenerator<StreamEvent, ChatResponse>` — yields
  `StreamEvent`s of type `thinking` (server-side progress before the first token,
  e.g. `{stage: "searching", message: "Searching knowledge…"}` — safe to ignore),
  `token`, `done`, and `error`
- `client.streamChatWithCallbacks(input, callbacks)` — callbacks: `onThinking(stage, message)`,
  `onToken(text)`, `onDone(result)`, `onError(error)`, `onTyping(typing)`

## Knowledge

- `client.search({ query, kbId?, topK? })`
- `client.upload({ file, filename?, kbId? })`
- `client.history({ conversationId?, limit? })`

## Agent

- `client.setAgentId(id)`
- `client.agent.info(id?)`
- `client.agent.status(id?)`
- `client.agent.publish(id?)`
- `client.agent.embed(id?)`

## Widget

- `client.widget.open()`
- `client.widget.close()`
- `client.widget.toggle()`
- `client.widget.sendMessage(text)`
- `client.widget.setTheme(theme)`
- `client.widget.destroy()`

## Identity / Auth helpers

- `client.identify({ id, name, email, metadata })`
- `client.setApiKey(key)`
- `client.setBearerToken(jwt)`
- `client.setSessionToken(jwt)`

## Events

`ready | message | typing | stream | error | disconnect | reconnect`

```ts
const off = client.on("message", (m) => {});
off();
```

## Errors

`THTWAATError` with `status`, `code`, `retryable`, `details`.

Helpers: `parseApiError`, `isRateLimited`.
