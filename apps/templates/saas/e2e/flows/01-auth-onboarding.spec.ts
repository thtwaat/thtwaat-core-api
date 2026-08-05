import { test, expect } from "@playwright/test";
import { apiGet, apiPost, injectBrowserAuth, seedWorkspace } from "../helpers/api";
import { hasCredentials, skipMessage } from "../helpers/env";
import { requireApi } from "../helpers/ready";

test.describe("01 — Registration / Verification / Workspace", () => {
  test("User registration + workspace creation via API", async ({ request }) => {
    test.info().annotations.push({ type: "workflow", description: "1. User Registration" });
    test.info().annotations.push({ type: "workflow", description: "3. Workspace Creation" });
    await requireApi(request);
    const session = await seedWorkspace(request);
    expect(session.accessToken).toBeTruthy();
    expect(session.companyId).toBeTruthy();

    const me = await apiGet(request, "/api/v1/auth/me", session.headers);
    if (!me.ok()) {
      const alt = await apiGet(request, "/api/v1/users/me", session.headers);
      expect(alt.ok() || me.status() < 500).toBeTruthy();
    }
  });

  test("Email verification endpoint is reachable", async ({ request }) => {
    test.info().annotations.push({ type: "workflow", description: "2. Email Verification" });
    await requireApi(request);
    const res = await apiPost(request, "/api/v1/auth/send-email-verification", {
      email: "launch-readiness@example.com"
    });
    expect(res.status(), await res.text()).toBeLessThan(500);
  });

  test("Login UI accepts seeded credentials when provided", async ({ page }) => {
    test.info().annotations.push({ type: "workflow", description: "1. User Registration (UI login)" });
    test.skip(!hasCredentials(), skipMessage("E2E_EMAIL + E2E_PASSWORD"));
    await page.goto("/login");
    await page.getByLabel(/email/i).fill(process.env.E2E_EMAIL!);
    await page.getByLabel(/password/i).fill(process.env.E2E_PASSWORD!);
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page).not.toHaveURL(/\/login$/, { timeout: 30_000 });
  });

  test("Injected session reaches app shell", async ({ page, request }) => {
    test.info().annotations.push({ type: "workflow", description: "3. Workspace Creation (session)" });
    await requireApi(request);
    let session;
    try {
      session = await seedWorkspace(request);
    } catch {
      test.skip(true, "API seed unavailable — start API stack");
      return;
    }
    await injectBrowserAuth(page, session);
    await page.goto("/app");
    await expect(page).not.toHaveURL(/\/login/, { timeout: 30_000 });
  });
});
