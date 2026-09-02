import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Widget } from "./Widget";
import type { PublicWidgetConfigResponse } from "./types";

/**
 * Widget capability-discovery tests: the widget-config fetch introduced for
 * the Agent Capabilities platform feature (one fetch per init, additive to
 * the existing data-* attribute path — see Widget.ts loadCapabilitiesFromConfig).
 */

function stubMediaRecorder() {
  Object.defineProperty(window.navigator, "mediaDevices", {
    value: { getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [] }) },
    configurable: true,
  });
  class FakeMediaRecorder {
    static isTypeSupported() {
      return true;
    }
    start() {}
    stop() {}
    addEventListener() {}
  }
  (window as unknown as { MediaRecorder: unknown }).MediaRecorder = FakeMediaRecorder;
}

function mockConfigResponse(
  overrides: Partial<PublicWidgetConfigResponse["capabilities"]> = {}
): Response {
  const body: PublicWidgetConfigResponse = {
    agent_name: "Test Agent",
    slug: "test-agent",
    theme: "light",
    primary_color: "#111827",
    welcome_message: "Hi",
    logo: null,
    avatar: null,
    position: "bottom-right",
    border_radius: "16px",
    font_family: "Inter",
    suggested_prompts: [],
    capabilities: {
      voice: false,
      vision: false,
      image_generation: false,
      calling: false,
      memory: true,
      tools: false,
      knowledge: true,
      handoff: true,
      lead_capture: true,
      multilingual: true,
      ...overrides,
    },
    public_chat_url: "http://localhost:9999/public/v1/chat",
  };
  return { ok: true, json: async () => body } as Response;
}

/** loadCapabilitiesFromConfig does `await fetch(...)` then `await res.json()`
 * before synchronously updating options — a few microtask turns cover both. */
async function flushMicrotasks() {
  for (let i = 0; i < 5; i++) await Promise.resolve();
}

function shadowOf(widget: Widget): ShadowRoot {
  return (widget as unknown as { shadow: ShadowRoot }).shadow;
}

describe("Widget capability discovery", () => {
  beforeEach(() => {
    stubMediaRecorder();
    document.body.innerHTML = "";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("fetches widget-config once and renders the buttons for fetched capabilities", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(mockConfigResponse({ voice: true, vision: true, image_generation: true }));
    vi.stubGlobal("fetch", fetchMock);

    const widget = new Widget({
      apiKey: "tht_live_testkey",
      apiBaseUrl: "http://localhost:9999",
      agentSlug: "test-agent",
    });
    await flushMicrotasks();

    const shadow = shadowOf(widget);
    expect(shadow.querySelector(".tht-mic")).not.toBeNull();
    expect(shadow.querySelector(".tht-attach")).not.toBeNull();
    expect(shadow.querySelector(".tht-imagegen")).not.toBeNull();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0][0])).toContain("/public/v1/agents/test-agent/widget-config");

    widget.destroy();
  });

  it("keeps optional controls hidden when capability information is unavailable (fetch fails)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));

    const widget = new Widget({
      apiKey: "tht_live_testkey",
      apiBaseUrl: "http://localhost:9999",
      agentSlug: "test-agent",
    });
    await flushMicrotasks();

    const shadow = shadowOf(widget);
    expect(shadow.querySelector(".tht-mic")).toBeNull();
    expect(shadow.querySelector(".tht-attach")).toBeNull();
    expect(shadow.querySelector(".tht-imagegen")).toBeNull();

    // Text chat must keep working regardless of the failed fetch.
    expect(shadow.querySelector(".tht-input")).not.toBeNull();
    expect(shadow.querySelector(".tht-send")).not.toBeNull();

    widget.destroy();
  });

  it("keeps optional controls hidden when widget-config returns a non-OK response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, json: async () => ({}) } as Response)
    );

    const widget = new Widget({
      apiKey: "tht_live_testkey",
      apiBaseUrl: "http://localhost:9999",
      agentSlug: "test-agent",
    });
    await flushMicrotasks();

    const shadow = shadowOf(widget);
    expect(shadow.querySelector(".tht-mic")).toBeNull();
    expect(shadow.querySelector(".tht-input")).not.toBeNull();

    widget.destroy();
  });

  it("does not fetch widget-config when no agentSlug is set (old text-only embeds)", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const widget = new Widget({
      apiKey: "tht_live_testkey",
      apiBaseUrl: "http://localhost:9999",
    });
    await flushMicrotasks();

    expect(fetchMock).not.toHaveBeenCalled();
    widget.destroy();
  });

  it("does not fetch again once every capability option is already explicit", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const widget = new Widget({
      apiKey: "tht_live_testkey",
      apiBaseUrl: "http://localhost:9999",
      agentSlug: "test-agent",
      voiceEnabled: true,
      visionEnabled: false,
      imageGenerationEnabled: false,
    });
    await flushMicrotasks();

    expect(fetchMock).not.toHaveBeenCalled();
    widget.destroy();
  });

  it("explicit voiceEnabled=false (as set by legacy data-voice=\"false\") overrides a fetched voice=true", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockConfigResponse({ voice: true })));

    const widget = new Widget({
      apiKey: "tht_live_testkey",
      apiBaseUrl: "http://localhost:9999",
      agentSlug: "test-agent",
      voiceEnabled: false,
    });
    await flushMicrotasks();

    expect(shadowOf(widget).querySelector(".tht-mic")).toBeNull();
    widget.destroy();
  });

  it("Widget.fromScript: legacy embed with explicit data-* attributes and no data-agent-slug never fetches", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const script = document.createElement("script");
    script.setAttribute("data-api-key", "tht_live_testkey");
    script.setAttribute("data-api-url", "http://localhost:9999");
    script.setAttribute("data-voice", "true");
    script.setAttribute("data-vision", "false");
    document.body.appendChild(script);

    const widget = Widget.fromScript(script);
    const shadow = shadowOf(widget);

    expect(fetchMock).not.toHaveBeenCalled();
    expect(shadow.querySelector(".tht-mic")).not.toBeNull();
    expect(shadow.querySelector(".tht-attach")).toBeNull();

    widget.destroy();
  });

  it("Widget.fromScript: new embed with data-agent-slug and no data-voice/data-vision fetches and renders from config", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockConfigResponse({ voice: true, vision: true }))
    );

    const script = document.createElement("script");
    script.setAttribute("data-api-key", "tht_live_testkey");
    script.setAttribute("data-api-url", "http://localhost:9999");
    script.setAttribute("data-agent-slug", "test-agent");
    document.body.appendChild(script);

    const widget = Widget.fromScript(script);
    await flushMicrotasks();

    const shadow = shadowOf(widget);
    expect(shadow.querySelector(".tht-mic")).not.toBeNull();
    expect(shadow.querySelector(".tht-attach")).not.toBeNull();

    widget.destroy();
  });
});
