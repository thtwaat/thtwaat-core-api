import { test, expect } from "@playwright/test";
import { apiGet, apiPost, injectBrowserAuth, seedWorkspace } from "../helpers/api";
import { hasSuperAdminCredentials, skipMessage } from "../helpers/env";
import { requireApi } from "../helpers/ready";

test.describe("05 — Marketplace / Publisher / Super Admin", () => {
  test("Marketplace catalog browse", async ({ request }) => {
    test.info().annotations.push({ type: "workflow", description: "18. Marketplace Purchase" });
    await requireApi(request);
    const res = await apiGet(request, "/api/v1/marketplace/templates?limit=5");
    expect(res.status()).toBeLessThan(500);
  });

  test("Publisher profile endpoints for authenticated user", async ({ request }) => {
    test.info().annotations.push({ type: "workflow", description: "19. Publisher Flow" });
    await requireApi(request);
    const session = await seedWorkspace(request);
    const res = await apiGet(request, "/api/v1/agent-store/publisher/me", session.headers);
    expect(res.status()).toBeLessThan(500);
  });

  test("Super Admin analytics APIs", async ({ request }) => {
    test.info().annotations.push({ type: "workflow", description: "20. Super Admin Analytics" });
    test.skip(!hasSuperAdminCredentials(), skipMessage("E2E_SUPER_ADMIN_EMAIL + E2E_SUPER_ADMIN_PASSWORD"));
    await requireApi(request);

    const login = await apiPost(request, "/api/v1/auth/login", {
      email: process.env.E2E_SUPER_ADMIN_EMAIL,
      password: process.env.E2E_SUPER_ADMIN_PASSWORD
    });
    expect(login.ok(), await login.text()).toBeTruthy();
    const tokens = await login.json();
    const headers = { Authorization: `Bearer ${tokens.access_token}` };

    const exec = await apiGet(request, "/api/v1/admin/executive", headers);
    expect(exec.ok(), await exec.text()).toBeTruthy();
    const body = await exec.json();
    expect(body).toHaveProperty("revenue");
    expect(body).toHaveProperty("active_users");
    expect(body.active_companies !== undefined || body.workspaces !== undefined).toBeTruthy();

    const health = await apiGet(request, "/api/v1/monitoring/health", headers);
    expect(health.ok(), await health.text()).toBeTruthy();

    const billing = await apiGet(request, "/api/v1/payments/admin/analytics", headers);
    expect(billing.status()).toBeLessThan(500);
  });

  test("Super Admin UI route exists", async ({ page, request }) => {
    test.info().annotations.push({ type: "workflow", description: "20. Super Admin Analytics (UI)" });
    test.skip(!hasSuperAdminCredentials(), skipMessage("E2E_SUPER_ADMIN_EMAIL + E2E_SUPER_ADMIN_PASSWORD"));
    await requireApi(request);
    const login = await apiPost(request, "/api/v1/auth/login", {
      email: process.env.E2E_SUPER_ADMIN_EMAIL,
      password: process.env.E2E_SUPER_ADMIN_PASSWORD
    });
    expect(login.ok()).toBeTruthy();
    const tokens = await login.json();
    await injectBrowserAuth(page, {
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
      email: process.env.E2E_SUPER_ADMIN_EMAIL!,
      password: process.env.E2E_SUPER_ADMIN_PASSWORD!,
      headers: { Authorization: `Bearer ${tokens.access_token}` }
    });
    await page.goto("/admin");
    await expect(page.getByText(/super admin|executive|revenue|health/i).first()).toBeVisible({
      timeout: 30_000
    });
  });

  test("Publisher UI route loads when authenticated", async ({ page, request }) => {
    test.info().annotations.push({ type: "workflow", description: "19. Publisher Flow (UI)" });
    await requireApi(request);
    let session;
    try {
      session = await seedWorkspace(request);
    } catch {
      test.skip(true, "API seed unavailable");
      return;
    }
    await injectBrowserAuth(page, session);
    await page.goto("/app/publisher");
    await expect(page.locator("body")).toBeVisible();
    const content = await page.content();
    expect(content.toLowerCase()).not.toContain("internal server error");
  });
});
