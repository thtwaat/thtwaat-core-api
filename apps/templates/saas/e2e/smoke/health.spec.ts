import { test, expect } from "@playwright/test";
import { apiBaseUrl, siteBaseUrl } from "../helpers/env";
import { apiGet } from "../helpers/api";
import { requireApi, requireSite } from "../helpers/ready";

test.describe("Launch smoke — health", () => {
  test("API liveness and status", async ({ request }) => {
    test.info().annotations.push({ type: "workflow", description: "System Health / API Health" });
    await requireApi(request);
    let liveRes = await apiGet(request, "/live");
    if (!liveRes.ok()) {
      liveRes = await apiGet(request, "/liveness");
    }
    expect(liveRes.ok(), await liveRes.text()).toBeTruthy();

    const status = await apiGet(request, "/api/v1/status");
    expect(status.ok(), await status.text()).toBeTruthy();
    const body = await status.json();
    expect(body.status || body.state).toBeTruthy();
  });

  test("SaaS site responds", async ({ page }) => {
    test.info().annotations.push({ type: "workflow", description: "Website availability" });
    await requireSite(page);
    const res = await page.goto(siteBaseUrl() + "/login", { waitUntil: "domcontentloaded" });
    expect(res?.ok() || res?.status() === 200 || res?.status() === 304).toBeTruthy();
    await expect(page.getByRole("heading", { name: /sign in/i })).toBeVisible({ timeout: 20_000 });
  });

  test("API base URL is configured", async () => {
    expect(apiBaseUrl().length).toBeGreaterThan(8);
  });
});
