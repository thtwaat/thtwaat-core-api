/**
 * Billing/usage calls must go through the shared authenticated api client
 * and include Authorization: Bearer <access_token>.
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

describe("billing/usage Authorization header", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    installBrowserStubs();
    fetchMock.mockReset();
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ([]),
      text: async () => "[]"
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  async function loadApis() {
    // Fresh module so api.ts reads stubbed window/localStorage
    const { billingApi, usageApi } = await import("./services");
    return { billingApi, usageApi };
  }

  function assertBearerOn(urlSubstring: string) {
    const call = fetchMock.mock.calls.find(([url]) => String(url).includes(urlSubstring));
    expect(call, `expected a fetch to ${urlSubstring}`).toBeTruthy();
    const init = call![1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe(`Bearer ${ACCESS}`);
  }

  it("GET /payments/plans includes Authorization Bearer", async () => {
    const { billingApi } = await loadApis();
    await billingApi.plans();
    assertBearerOn("/payments/plans");
  });

  it("GET /payments/subscriptions/me includes Authorization Bearer", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ id: "sub-1", status: "active" }),
      text: async () => "{}"
    });
    const { billingApi } = await loadApis();
    await billingApi.subscription();
    assertBearerOn("/payments/subscriptions/me");
  });

  it("GET /payments/invoices includes Authorization Bearer", async () => {
    const { billingApi } = await loadApis();
    await billingApi.invoices();
    assertBearerOn("/payments/invoices");
  });

  it("GET /usage/current includes Authorization Bearer", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ meters: [] }),
      text: async () => "{}"
    });
    const { usageApi } = await loadApis();
    await usageApi.current();
    assertBearerOn("/usage/current");
  });

  it("plans no longer opts out of auth (auth:false regression)", async () => {
    const { billingApi } = await loadApis();
    await billingApi.plans();
    const call = fetchMock.mock.calls.find(([url]) => String(url).includes("/payments/plans"));
    expect(call).toBeTruthy();
    const headers = (call![1] as RequestInit).headers as Record<string, string>;
    expect(headers.Authorization).toBeDefined();
    expect(headers.Authorization).not.toBe("");
  });
});
