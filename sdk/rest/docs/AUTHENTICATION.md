# Authentication

## API Key (public agent chat / widget)

```ts
new RestClient({ apiKey: "tht_live_xxx" });
// Sends: Authorization: Bearer tht_live_xxx
```

## Bearer JWT (dashboard / admin routes)

```ts
const api = new RestClient({ apiUrl });
const { access_token } = await api.auth.login({ email, password }) as any;
api.setBearerToken(access_token);
```

## Session token

```ts
new RestClient({ sessionToken: "<jwt>" });
// Same Authorization header shape as bearer
```

## Switching at runtime

```ts
api.setApiKey("tht_live_...");
api.setBearerToken("eyJ...");
api.setSessionToken("eyJ...");
```
