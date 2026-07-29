import { describe, it, expect, vi, beforeEach } from "vitest";
import { THTWAAT, THTWAATError, parseApiError, isRateLimited } from "../src";

function mockFetchSequence(responses: Array<{ status: number; body: unknown }>) {
  let i = 0;
  return vi.fn(async () => {
    const item = responses[Math.min(i, responses.length - 1)];
    i += 1;
    return {
      ok: item.status >= 200 && item.status < 300,
      status: item.status,
      text: async () => JSON.stringify(item.body),
    } as Response;
  });
}

describe("parseApiError", () => {
  it("maps 429 as retryable rate limit", () => {
    const err = parseApiError(429, { detail: "too many" });
    expect(err).toBeInstanceOf(THTWAATError);
    expect(err.retryable).toBe(true);
    expect(isRateLimited(err)).toBe(true);
    expect(err.message).toBe("too many");
  });
});

describe("THTWAAT client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("requires auth credentials", () => {
    expect(() => new THTWAAT({})).toThrow(/apiKey|bearerToken|sessionToken/);
  });

  it("chats with string input", async () => {
    const fetchImpl = mockFetchSequence([
      {
        status: 200,
        body: {
          reply: "Hello!",
          conversation_id: "c1",
          usage: { input_tokens: 1, output_tokens: 2, total_tokens: 3, estimated_cost: 0 },
        },
      },
    ]);

    const client = new THTWAAT({
      apiKey: "tht_live_test",
      apiUrl: "https://api.example.com",
      fetch: fetchImpl as unknown as typeof fetch,
      maxRetries: 0,
    });

    const messages: unknown[] = [];
    client.on("message", (m) => messages.push(m));

    const res = await client.chat("Hello");
    expect(res.reply).toBe("Hello!");
    expect(res.conversationId).toBe("c1");
    expect(messages).toHaveLength(1);

    expect(fetchImpl).toHaveBeenCalled();
    const [url, init] = fetchImpl.mock.calls[0];
    expect(String(url)).toContain("/public/v1/chat");
    expect((init as RequestInit).method).toBe("POST");
    const body = JSON.parse(String((init as RequestInit).body));
    expect(body.message).toBe("Hello");
    expect(body.api_key).toBe("tht_live_test");
  });

  it("supports object chat + identify metadata", async () => {
    const fetchImpl = mockFetchSequence([
      {
        status: 200,
        body: {
          reply: "Price is $99",
          conversation_id: "c2",
          usage: {},
        },
      },
    ]);

    const client = new THTWAAT({
      apiKey: "tht_live_test",
      fetch: fetchImpl as unknown as typeof fetch,
      maxRetries: 0,
    });
    client.identify({ id: "u1", email: "a@b.com", metadata: { plan: "pro" } });

    await client.chat({ message: "Pricing?", sessionId: "c2", metadata: { page: "/" } });
    const body = JSON.parse(String(fetchImpl.mock.calls[0][1].body));
    expect(body.session_id).toBe("c2");
    expect(body.metadata.email).toBe("a@b.com");
    expect(body.metadata.plan).toBe("pro");
    expect(body.metadata.page).toBe("/");
  });

  it("retries retryable errors", async () => {
    const fetchImpl = mockFetchSequence([
      { status: 500, body: { detail: "boom" } },
      {
        status: 200,
        body: { reply: "ok", conversation_id: "c3", usage: {} },
      },
    ]);

    const client = new THTWAAT({
      apiKey: "tht_live_test",
      fetch: fetchImpl as unknown as typeof fetch,
      maxRetries: 1,
      timeoutMs: 5000,
    });

    const res = await client.chat("hi");
    expect(res.reply).toBe("ok");
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  it("streams tokens via SSE", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(
          encoder.encode(`event: token\ndata: {"text":"Hel"}\n\n`)
        );
        controller.enqueue(
          encoder.encode(`event: token\ndata: {"text":"lo"}\n\n`)
        );
        controller.enqueue(
          encoder.encode(
            `event: done\ndata: {"conversation_id":"c9","reply":"Hello","usage":{"total_tokens":3}}\n\n`
          )
        );
        controller.close();
      },
    });

    const fetchImpl = vi.fn(async () => {
      return {
        ok: true,
        status: 200,
        body: stream,
        text: async () => "",
      } as unknown as Response;
    });

    const client = new THTWAAT({
      apiKey: "tht_live_test",
      fetch: fetchImpl as unknown as typeof fetch,
      maxRetries: 0,
    });

    const tokens: string[] = [];
    let final = "";
    for await (const ev of client.streamChat("hi")) {
      if (ev.type === "token") tokens.push(ev.text);
      if (ev.type === "done") final = ev.result.reply;
    }
    expect(tokens.join("")).toBe("Hello");
    expect(final).toBe("Hello");
  });
});
