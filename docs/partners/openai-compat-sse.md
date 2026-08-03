# Partner guide — OpenAI-compatible SSE streaming

**Audience:** SDK / agent integrators calling THTWAAT `POST /v1/chat/completions`  
**Related:** Idempotency-Key, usage metering, completion webhooks

---

## Streaming contract

```http
POST /v1/chat/completions
Authorization: Bearer tht_live_...
Content-Type: application/json
Idempotency-Key: <optional but recommended>

{"model":"thtwaat-stub-mini","messages":[...],"stream":true}
```

Response: `Content-Type: text/event-stream` with `data: {...chat.completion.chunk...}` frames, ending with `data: [DONE]`.

### Ordering (important)

THTWAAT prepares the **full** assistant message **before** the first SSE byte:

1. Run inference  
2. Persist audit log (`openai_completion_logs`)  
3. Record usage / estimated cost (once)  
4. Enqueue `completion.succeeded` webhooks (async)  
5. Emit SSE chunks (or replay chunks from stored JSON)

This means streaming is a **delivery format**, not a “bill as tokens leave the socket” meter.

---

## Client disconnect mid-stream

If your HTTP client cancels, times out, or drops the TCP connection **after** step 2–4 above:

| Effect | Happens? |
|--------|----------|
| Usage / spend recorded | **Yes** |
| Webhooks may deliver | **Yes** (at-least-once) |
| Partial text on your side | Possible — reconnect with care |

**Do not assume** “no full SSE ⇒ no charge.” Prefer:

- Generous read timeouts for long generations  
- `Idempotency-Key` on every completion so a retry is a **replay**, not a second bill  
- Server-side cancel APIs are **not** part of Sem02 `/v1` (future)

---

## Idempotent retries

| Situation | Result |
|-----------|--------|
| Same key + same body (incl. `stream`) after success | Replay; `Idempotent-Replayed: true`; **no** second usage |
| Same key while first in progress | `409` `idempotency_in_progress` |
| Same key + different body / `stream` flag | `409` `idempotency_key_reuse` |

Replay of `stream:true` re-emits SSE from the stored JSON completion.

---

## Webhooks

Events: `completion.succeeded`, `completion.failed`.  
Payload includes stable `delivery_id` (`whdel_…`). **Dedupe on that id** — deliveries are at-least-once.

Verify `X-THTWAAT-Signature` (`v1=…`) + `X-THTWAAT-Timestamp` within tolerance.

---

## Redis outages (platform note)

If Redis is unavailable, THTWAAT **fail-opens** cache / idempotency / rate limits so the API stays up. During that window, idempotent retries may not dedupe. Prefer still sending `Idempotency-Key`; behavior returns to normal when Redis recovers.
