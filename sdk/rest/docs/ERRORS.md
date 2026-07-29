# Error Guide

All failures throw `RestError`:

| Field | Meaning |
|-------|---------|
| `status` | HTTP status |
| `code` | `unauthorized`, `forbidden`, `not_found`, `rate_limited`, `server_error`, ... |
| `message` | Human-readable |
| `details` | Raw API payload |
| `retryable` | Safe to retry |

```ts
import { RestError } from "@thtwaat/rest";

try {
  await api.agents.chat({ message: "hi" });
} catch (e) {
  if (e instanceof RestError && e.status === 429) {
    // backoff
  }
}
```

Automatic retries (default): **429, 502, 503, 504** with exponential backoff.
