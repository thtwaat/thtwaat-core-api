# Migration Guide

## 1.0.0

Initial Flutter SDK release.

### Recommended migration path from raw HTTP

1. Replace your custom auth calls with `client.auth.login()` / `refresh()`.
2. Replace public chat POST calls with `client.chat.chat()`.
3. Replace SSE parsers with `client.chat.stream()`.
4. Move template install flows to `client.marketplace.*`.
5. Move product provisioning to `client.productGenerator.*`.

### Notes

- No backend changes required.
- Uses current platform paths under `/api/v1`, `/v2`, and `/public/v1`.
