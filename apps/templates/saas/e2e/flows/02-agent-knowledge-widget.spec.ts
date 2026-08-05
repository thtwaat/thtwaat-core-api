import { test, expect } from "@playwright/test";
import { apiGet, apiPost, seedWorkspace } from "../helpers/api";
import { requireApi } from "../helpers/ready";

test.describe("02 — Providers / Agent / Knowledge / Widget", () => {
  test("AI provider selection surface responds", async ({ request }) => {
    test.info().annotations.push({ type: "workflow", description: "4. AI Provider Selection" });
    await requireApi(request);
    let session;
    try {
      session = await seedWorkspace(request);
    } catch {
      test.skip(true, "API seed unavailable");
      return;
    }
    const res = await apiGet(request, "/api/v1/ai/providers", session.headers);
    expect([200, 401, 403].includes(res.status())).toBeTruthy();
    if (res.ok()) {
      const body = await res.json();
      expect(body).toBeTruthy();
    }
  });

  test("AI agent creation", async ({ request }) => {
    test.info().annotations.push({ type: "workflow", description: "5. AI Agent Creation" });
    await requireApi(request);
    const session = await seedWorkspace(request);
    const res = await apiPost(
      request,
      "/v2/agents",
      {
        name: `Launch Agent ${Date.now()}`,
        description: "E2E launch readiness agent",
        system_prompt_template: "You are a helpful launch-test assistant.",
        temperature: 0.2
      },
      session.headers
    );
    expect(res.ok(), await res.text()).toBeTruthy();
    const agent = await res.json();
    expect(agent.id).toBeTruthy();
  });

  test("Knowledge upload path exists", async ({ request }) => {
    test.info().annotations.push({ type: "workflow", description: "6. Knowledge Upload" });
    await requireApi(request);
    const session = await seedWorkspace(request);
    const kb = await apiPost(
      request,
      "/v2/knowledge/bases",
      { name: `KB ${Date.now()}`, description: "Launch readiness" },
      session.headers
    );
    expect(kb.ok(), await kb.text()).toBeTruthy();
    const base = await kb.json();
    expect(base.id).toBeTruthy();

    const list = await apiGet(request, "/v2/knowledge/documents", session.headers);
    expect(list.status()).toBeLessThan(500);
  });

  test("Widget generation via publish", async ({ request }) => {
    test.info().annotations.push({ type: "workflow", description: "7. Widget Generation" });
    test.info().annotations.push({ type: "workflow", description: "8. Widget Installation" });
    await requireApi(request);
    const session = await seedWorkspace(request);
    const create = await apiPost(
      request,
      "/v2/agents",
      {
        name: `Widget Agent ${Date.now()}`,
        system_prompt_template: "Help users.",
        temperature: 0.3
      },
      session.headers
    );
    expect(create.ok(), await create.text()).toBeTruthy();
    const agent = await create.json();

    const publish = await apiPost(request, `/api/v1/agents/${agent.id}/publish`, {}, session.headers);
    expect(publish.status(), await publish.text()).toBeLessThan(500);

    const widgetJs = await apiGet(request, "/widget.js");
    expect(widgetJs.ok(), await widgetJs.text()).toBeTruthy();
    const js = await widgetJs.text();
    expect(js.includes("THTWAAT") || js.includes("Widget")).toBeTruthy();
  });
});
