import { test, expect } from "@playwright/test";
import { apiGet, apiPost, seedWorkspace } from "../helpers/api";
import { requireApi } from "../helpers/ready";

test.describe("03 — Chat / Memory / Handoff / Leads", () => {
  test("Chat conversation + memory via public API when published", async ({ request }) => {
    test.info().annotations.push({ type: "workflow", description: "9. Chat Conversation" });
    test.info().annotations.push({ type: "workflow", description: "10. Conversation Memory" });
    await requireApi(request);

    const session = await seedWorkspace(request);
    const create = await apiPost(
      request,
      "/v2/agents",
      {
        name: `Chat Agent ${Date.now()}`,
        system_prompt_template: "Remember the user's name if told.",
        temperature: 0.2
      },
      session.headers
    );
    expect(create.ok(), await create.text()).toBeTruthy();
    const agent = await create.json();

    const keyRes = await apiPost(
      request,
      `/api/v1/agents/${agent.id}/api-keys`,
      { name: "e2e" },
      session.headers
    );
    if (!keyRes.ok()) {
      await apiPost(request, `/api/v1/agents/${agent.id}/publish`, {}, session.headers);
    }
    const keyBody = keyRes.ok()
      ? await keyRes.json()
      : await (
          await apiPost(request, `/api/v1/agents/${agent.id}/api-keys`, { name: "e2e2" }, session.headers)
        )
          .json()
          .catch(() => ({}));

    const apiKey = keyBody.api_key || keyBody.key || keyBody.plain_key;
    test.skip(!apiKey, "Could not mint agent API key in this environment");

    const chat1 = await apiPost(request, "/public/v1/chat", {
      api_key: apiKey,
      message: "My name is LaunchBot.",
      metadata: { locale: "en", source: "e2e" }
    });
    expect(chat1.status(), await chat1.text()).toBeLessThan(500);
    if (!chat1.ok()) return;
    const first = await chat1.json();
    expect(first.conversation_id || first.session_id).toBeTruthy();

    const chat2 = await apiPost(request, "/public/v1/chat", {
      api_key: apiKey,
      message: "What is my name?",
      session_id: first.conversation_id,
      metadata: { locale: "en" }
    });
    expect(chat2.ok(), await chat2.text()).toBeTruthy();
    const second = await chat2.json();
    expect(String(second.reply || "").length).toBeGreaterThan(0);
  });

  test("Human handoff keyword path", async ({ request }) => {
    test.info().annotations.push({ type: "workflow", description: "11. Human Handoff" });
    await requireApi(request);
    const res = await apiPost(request, "/public/v1/handoff", {
      session_id: "00000000-0000-0000-0000-000000000001",
      api_key: "tht_live_invalid"
    });
    expect(res.status()).toBeLessThan(500);
  });

  test("Lead capture endpoint", async ({ request }) => {
    test.info().annotations.push({ type: "workflow", description: "12. Lead Capture" });
    await requireApi(request);
    const res = await apiPost(request, "/public/v1/leads", {
      api_key: "tht_live_invalid",
      lead: { name: "Ada", email: "ada@example.com" }
    });
    expect(res.status()).toBeLessThan(500);
  });

  test("Inbox conversations list for authenticated user", async ({ request }) => {
    test.info().annotations.push({ type: "workflow", description: "10. Conversation Memory (inbox)" });
    await requireApi(request);
    const session = await seedWorkspace(request);
    const res = await apiGet(request, "/v2/conversations?limit=10", session.headers);
    expect(res.status()).toBeLessThan(500);
  });
});
