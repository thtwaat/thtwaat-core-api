# API Reference

## ThtwaatClient

Constructor options:

- `apiKey`
- `apiUrl`
- `accessToken`
- `refreshToken`
- `timeout`
- `maxRetries`
- `headers`
- `language`
- `debug`
- `tokenStorage`
- `http`

## Auth

- `login(LoginRequest)`
- `refresh([refreshToken])`
- `logout([refreshToken])`
- `me()`
- `sendOtp(...)`
- `verifyOtp(...)`
- `forgotPassword(email)`
- `resetPassword(...)`

## Chat

- `chat(ChatRequest)`
- `stream(ChatRequest, {cancelToken})`
- `history({limit})`
- `conversation(id)`

## Knowledge

- `listBases()`
- `createBase(...)`
- `search(...)`
- `uploadBytes(...)`
- `attachBaseToAgent(...)`

## Agents / Publish

- `list()` / `get(id)` / `create(...)`
- `publish(id)` / `unpublish(id)`
- `embed(id)`
- `widget(id)` / `updateWidget(id, patch)`
- `createApiKey(id)` / `listApiKeys(id)`

## Domains / Usage / Billing / Analytics

Standard wrappers around current `/api/v1` routes.

## Marketplace

- `dashboard()`
- `templates(...)`
- `template(idOrSlug)`
- `install(...)`
- `installed()`
- `updates()`
- `connect(...)`
- `publish(...)`
- `update(...)`
- `rollback(...)`
- `uninstall(...)`

## Product Generator

- `analyze(prompt)`
- `generate(...)`
- `list()`
- `get(id)`
- `output(id)`
- `publish(id, {hostname})`
