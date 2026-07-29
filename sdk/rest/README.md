# @thtwaat/rest

Official **REST SDK Client** for THTWAAT AI Platform.

- OpenAPI-generated TypeScript models (`npm run generate`)
- Reusable HTTP core (GET/POST/PUT/PATCH/DELETE, multipart, SSE)
- Works in Browser, Node.js 18+, Serverless, CLI

## Install

```bash
cd sdk/rest
npm install
npm run build
```

```ts
import { RestClient } from "@thtwaat/rest";

const client = new RestClient({
  apiUrl: "https://api.thtwaat.com",
  apiKey: "tht_live_xxx", // or bearerToken / sessionToken
});
```

## Modules

```ts
client.auth.login({ email, password })
client.companies.list()
client.users.create(...)
client.agents.publish(agentId)
client.agents.chat({ message: "Hi" })
client.knowledge.upload(file, { filename: "faq.pdf", kbId })
client.conversations.list()
client.payments.list()
client.billing.razorpayOrder(...)
client.widget.embed(agentId)
client.analytics.agent(agentId) // when mounted
client.domains.*                 // Phase 2 placeholder
```

## Regenerate types from OpenAPI

```bash
# refresh openapi.json from running API, then:
curl -o openapi.json http://localhost:8000/openapi.json
npm run generate
```

## Docs

- [Quick Start](./docs/QUICKSTART.md)
- [Authentication](./docs/AUTHENTICATION.md)
- [Errors](./docs/ERRORS.md)
- [Streaming](./docs/STREAMING.md)
- [Pagination](./docs/PAGINATION.md)
- [Examples](./examples)

## Test / Build

```bash
npm test
npm run build
```
