import { describe, it, expect, vi } from "vitest";
import { RestClient, RestError, normalizePage, iteratePages } from "../src";

function mockFetch(handlers: Array<(url: string, init?: RequestInit) => Promise<Response> | Response>) {
  let i = 0;
  return vi.fn(async (url: string, init?: RequestInit) => {
    const handler = handlers[Math.min(i, handlers.length - 1)];
    i += 1;
    return handler(String(url), init);
  });
}

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
  } as Response;
}

describe("normalizePage", () => {
  it("handles arrays and objects", () => {
    expect(normalizePage([{ id: 1 }]).items).toHaveLength(1);
    const page = normalizePage({ items: [{ a: 1 }], total: 10, limit: 1, offset: 0, has_more: true });
    expect(page.total).toBe(10);
    expect(page.hasMore).toBe(true);
  });
});

describe("iteratePages", () => {
  it("walks offset pages", async () => {
    const pages = [
      { items: [1, 2], hasMore: true, offset: 0, limit: 2, raw: null },
      { items: [3], hasMore: false, offset: 2, limit: 2, raw: null },
    ];
    let n = 0;
    const out: number[] = [];
    for await (const item of iteratePages(async () => pages[n++])) {
      out.push(item as number);
    }
    expect(out).toEqual([1, 2, 3]);
  });
});

describe("RestClient", () => {
  it("logs in and stores bearer usage", async () => {
    const fetchImpl = mockFetch([
      () => jsonResponse(200, { access_token: "jwt", token_type: "bearer" }),
      () => jsonResponse(200, { id: "u1", email: "a@b.com", role: "admin", company_id: "c1" }),
    ]);

    const client = new RestClient({
      apiUrl: "https://api.example.com",
      fetch: fetchImpl as unknown as typeof fetch,
      maxRetries: 0,
    });

    const tokens = await client.auth.login({
      email: "a@b.com",
      password: "secret",
    } as any);
    expect((tokens as any).access_token).toBe("jwt");

    client.setBearerToken((tokens as any).access_token);
    const me = await client.auth.me();
    expect((me as any).email).toBe("a@b.com");
    expect(String(fetchImpl.mock.calls[1][0])).toContain("/api/v1/auth/me");
  });

  it("retries 503 then succeeds", async () => {
    const fetchImpl = mockFetch([
      () => jsonResponse(503, { detail: "busy" }),
      () => jsonResponse(200, { reply: "hi", conversation_id: "c1", usage: {} }),
    ]);

    const client = new RestClient({
      apiKey: "tht_live_x",
      fetch: fetchImpl as unknown as typeof fetch,
      maxRetries: 1,
    });

    const res = await client.agents.chat({ message: "hello" } as any);
    expect((res as any).reply).toBe("hi");
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  it("normalizes errors", async () => {
    const fetchImpl = mockFetch([() => jsonResponse(401, { detail: "bad key" })]);
    const client = new RestClient({
      apiKey: "bad",
      fetch: fetchImpl as unknown as typeof fetch,
      maxRetries: 0,
    });

    await expect(client.agents.chat({ message: "x" } as any)).rejects.toMatchObject({
      name: "RestError",
      status: 401,
      code: "unauthorized",
      message: "bad key",
    } satisfies Partial<RestError>);
  });

  it("streams SSE events", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(c) {
        c.enqueue(encoder.encode(`event: token\ndata: {"text":"A"}\n\n`));
        c.enqueue(encoder.encode(`event: done\ndata: {"reply":"A"}\n\n`));
        c.close();
      },
    });

    const fetchImpl = vi.fn(async () => ({
      ok: true,
      status: 200,
      body: stream,
      text: async () => "",
    }));

    const client = new RestClient({
      apiKey: "tht_live_x",
      fetch: fetchImpl as unknown as typeof fetch,
      maxRetries: 0,
    });

    const events: string[] = [];
    for await (const ev of client.agents.streamChat({ message: "hi" } as any)) {
      events.push(ev.event);
    }
    expect(events).toEqual(["token", "done"]);
  });
});
