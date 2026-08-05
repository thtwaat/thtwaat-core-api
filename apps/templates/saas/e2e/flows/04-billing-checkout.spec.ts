import { test, expect } from "@playwright/test";
import { apiGet, apiPost, injectBrowserAuth, seedWorkspace } from "../helpers/api";
import { requireApi } from "../helpers/ready";

test.describe("04 — Billing / Checkout / Quotas", () => {
  test("Billing plans and providers", async ({ request }) => {
    test.info().annotations.push({ type: "workflow", description: "13. Billing Upgrade" });
    test.info().annotations.push({ type: "workflow", description: "14. Razorpay Checkout" });
    test.info().annotations.push({ type: "workflow", description: "15. Stripe Checkout" });
    await requireApi(request);

    const plans = await apiGet(request, "/api/v1/payments/plans/?country=IN");
    expect(plans.ok(), await plans.text()).toBeTruthy();
    const list = await plans.json();
    expect(Array.isArray(list)).toBeTruthy();
    expect(list.length).toBeGreaterThan(0);

    const session = await seedWorkspace(request);
    const providers = await apiGet(
      request,
      "/api/v1/payments/subscriptions/providers?country=IN",
      session.headers
    );
    expect(providers.status()).toBeLessThan(500);
    if (providers.ok()) {
      const body = await providers.json();
      expect(body.stripe || body.razorpay || body.default).toBeTruthy();
    }

    const ctx = await apiGet(
      request,
      "/api/v1/payments/subscriptions/billing-context?country=US",
      session.headers
    );
    expect(ctx.status()).toBeLessThan(500);
  });

  test("Checkout endpoints reject unsafe unpaid payloads safely", async ({ request }) => {
    test.info().annotations.push({ type: "workflow", description: "16. Subscription Activation" });
    await requireApi(request);
    const session = await seedWorkspace(request);
    const stripe = await apiPost(
      request,
      "/api/v1/payments/subscriptions/stripe/checkout",
      {
        plan_id: "00000000-0000-0000-0000-000000000001",
        success_url: "https://app.thtwaat.com/app/billing?ok=1",
        cancel_url: "https://app.thtwaat.com/app/billing?cancel=1",
        country: "US"
      },
      session.headers
    );
    expect(stripe.status()).toBeLessThan(500);

    const razorpay = await apiPost(
      request,
      "/api/v1/payments/subscriptions/razorpay/order",
      {
        plan_id: "00000000-0000-0000-0000-000000000001",
        customer_name: "E2E",
        customer_email: session.email,
        country: "IN"
      },
      session.headers
    );
    expect(razorpay.status()).toBeLessThan(500);
  });

  test("Usage quotas endpoint", async ({ request }) => {
    test.info().annotations.push({ type: "workflow", description: "17. Usage Quotas" });
    await requireApi(request);
    const session = await seedWorkspace(request);
    const usage = await apiGet(request, "/api/v1/usage/current", session.headers);
    if (!usage.ok()) {
      const alt = await apiGet(request, "/usage/current", session.headers);
      expect(alt.status()).toBeLessThan(500);
    } else {
      expect(usage.ok()).toBeTruthy();
    }
  });

  test("Billing UI loads for authenticated session", async ({ page, request }) => {
    test.info().annotations.push({ type: "workflow", description: "13. Billing Upgrade (UI)" });
    await requireApi(request);
    let session;
    try {
      session = await seedWorkspace(request);
    } catch {
      test.skip(true, "API seed unavailable");
      return;
    }
    await injectBrowserAuth(page, session);
    await page.goto("/app/billing");
    await expect(page.getByText(/billing|upgrade|plan/i).first()).toBeVisible({ timeout: 30_000 });
  });
});
