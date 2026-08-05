import { APIRequestContext, test } from "@playwright/test";
import { apiBaseUrl, siteBaseUrl } from "./env";

/** Return true when API TCP/HTTP responds. */
export async function isApiReachable(request: APIRequestContext): Promise<boolean> {
  try {
    const res = await request.get(`${apiBaseUrl()}/api/v1/status`, { timeout: 8_000 });
    return res.status() < 500;
  } catch {
    return false;
  }
}

/** Skip the current test when the API stack is down. */
export async function requireApi(request: APIRequestContext): Promise<void> {
  const ok = await isApiReachable(request);
  test.skip(!ok, `API unreachable at ${apiBaseUrl()}. Start the stack or set E2E_API_URL.`);
}

/** Skip UI tests when the SaaS site is down. */
export async function requireSite(page: import("@playwright/test").Page): Promise<void> {
  try {
    const res = await page.request.get(siteBaseUrl() + "/login", { timeout: 8_000 });
    test.skip(!res.ok() && res.status() >= 500, `Site unreachable at ${siteBaseUrl()}.`);
  } catch {
    test.skip(true, `Site unreachable at ${siteBaseUrl()}.`);
  }
}
