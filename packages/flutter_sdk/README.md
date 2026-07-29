# thtwaat_flutter

Official Flutter / Dart SDK for the **THTWAAT AI Platform**.

- Flutter 3.x / Dart 3.x
- Android / iOS / Web / Desktop
- Zero backend changes required
- API key + JWT auth
- Chat + streaming (SSE)
- Knowledge, Agents, Publish, Domains, Usage, Billing, Analytics, Marketplace, Product Generator

## Install

```yaml
dependencies:
  thtwaat_flutter:
    path: ../packages/flutter_sdk
```

## Quick start

```dart
final client = ThtwaatClient(
  apiKey: 'tht_live_xxx',
  apiUrl: 'https://api.example.com',
);
await client.initialize();

final res = await client.chat.chat(
  const ChatRequest(message: 'Hello'),
);
print(res.reply);
```

## JWT auth

```dart
final tokens = await client.auth.login(
  const LoginRequest(email: 'owner@acme.com', password: 'secret'),
);
print(tokens.accessToken);
```

## Streaming chat (SSE)

```dart
final cancel = CancelToken();
await for (final chunk in client.chat.stream(
  const ChatRequest(message: 'Stream this please'),
  cancelToken: cancel,
)) {
  if (chunk.event == 'token') {
    print(chunk.text);
  }
}
```

## Modules

- `client.auth`
- `client.chat`
- `client.knowledge`
- `client.agents`
- `client.publish`
- `client.domains`
- `client.usage`
- `client.billing`
- `client.analytics`
- `client.marketplace`
- `client.productGenerator`

## Token persistence

Implement `TokenStorage` to persist JWT / API key in secure storage.

## State management examples

See `example/state/` for Provider / Riverpod / Bloc samples.

## Docs

- `docs/API_REFERENCE.md`
- `docs/MIGRATION.md`
- example apps under `example/`
