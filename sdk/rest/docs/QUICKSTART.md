# Quick Start

```ts
import { RestClient } from "@thtwaat/rest";

const api = new RestClient({
  apiUrl: process.env.THTWAAT_API_URL || "http://localhost:8000",
});

const tokens = await api.auth.login({
  email: "admin@example.com",
  password: "secret",
});

api.setBearerToken((tokens as any).access_token);

const agents = await api.agents.list();
console.log(agents);
```

Public chat with API key:

```ts
const publicApi = new RestClient({
  apiUrl: "http://localhost:8000",
  apiKey: "tht_live_xxx",
});

const res = await publicApi.agents.chat({ message: "Hello" });
console.log(res.reply);
```
