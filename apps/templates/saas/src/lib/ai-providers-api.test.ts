/**
 * AI provider management client must use authenticated /api/v1/ai/* calls.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const ACCESS = "test-access-token";
const store: Record<string, string> = {};

function installBrowserStubs() {
  store["tht_access_token"] = ACCESS;
  store["tht_refresh_token"] = "test-refresh-token";

  vi.stubGlobal("localStorage", {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => {
      store[key] = value;
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      for (const key of Object.keys(store)) delete store[key];
    }
  });

  vi.stubGlobal("window", {
    localStorage: globalThis.localStorage
  });

  vi.stubGlobal("document", {
    cookie: ""
  });
}

describe("aiProvidersApi Authorization header", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    installBrowserStubs();
    fetchMock.mockReset();
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ providers: ["openai"], default: "openai" }),
      text: async () => JSON.stringify({ providers: ["openai"], default: "openai" })
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("sends Bearer token to /ai/providers, /ai/health, /ai/models", async () => {
    const { aiProvidersApi } = await import("./services");

    await aiProvidersApi.list();
    await aiProvidersApi.health();
    await aiProvidersApi.models("openai");

    expect(fetchMock).toHaveBeenCalledTimes(3);
    for (const call of fetchMock.mock.calls) {
      const [url, init] = call as [string, RequestInit];
      expect(String(url)).toContain("/api/v1/ai/");
      const headers = init.headers as Record<string, string>;
      expect(headers.Authorization).toBe(`Bearer ${ACCESS}`);
    }
    expect(String(fetchMock.mock.calls[2][0])).toContain("provider=openai");
  });
});
