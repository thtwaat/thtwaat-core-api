import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  resetRazorpayCheckoutLock,
  runRazorpayCheckout,
  runRazorpaySubscriptionCheckout,
  type RazorpayCheckoutDeps,
  type RazorpaySubscriptionCheckoutDeps
} from "./razorpay-checkout";

function deps(overrides: Partial<RazorpayCheckoutDeps> = {}): RazorpayCheckoutDeps {
  return {
    razorpayKey: "rzp_test_key",
    createOrder: vi.fn(async () => ({ order_id: "order_123" })),
    verifyPayment: vi.fn(async () => ({ status: "active" })),
    loadCheckoutScript: vi.fn(async () => undefined),
    openCheckout: vi.fn(async () => ({
      razorpay_order_id: "order_123",
      razorpay_payment_id: "pay_123",
      razorpay_signature: "sig_123"
    })),
    ...overrides
  };
}

describe("runRazorpayCheckout", () => {
  beforeEach(() => {
    resetRazorpayCheckoutLock();
  });

  it("completes successful checkout: order → checkout → verify", async () => {
    const d = deps();
    const result = await runRazorpayCheckout({
      planId: "plan-1",
      customerName: "Ada Lovelace",
      customerEmail: "ada@example.com",
      planName: "Starter",
      deps: d
    });

    expect(result).toEqual({ status: "success" });
    expect(d.createOrder).toHaveBeenCalledWith({
      plan_id: "plan-1",
      customer_name: "Ada Lovelace",
      customer_email: "ada@example.com"
    });
    expect(d.loadCheckoutScript).toHaveBeenCalledOnce();
    expect(d.openCheckout).toHaveBeenCalledWith(
      expect.objectContaining({
        key: "rzp_test_key",
        order_id: "order_123",
        prefill: { name: "Ada Lovelace", email: "ada@example.com" }
      })
    );
    expect(d.verifyPayment).toHaveBeenCalledWith({
      razorpay_order_id: "order_123",
      razorpay_payment_id: "pay_123",
      razorpay_signature: "sig_123",
      plan_id: "plan-1"
    });
  });

  it("handles cancelled payment without calling verify", async () => {
    const d = deps({
      openCheckout: vi.fn(async () => ({ cancelled: true as const }))
    });

    const result = await runRazorpayCheckout({
      planId: "plan-1",
      customerName: "Ada Lovelace",
      customerEmail: "ada@example.com",
      deps: d
    });

    expect(result).toEqual({ status: "cancelled" });
    expect(d.createOrder).toHaveBeenCalledOnce();
    expect(d.verifyPayment).not.toHaveBeenCalled();
  });

  it("returns verify_failed when verification rejects", async () => {
    const d = deps({
      verifyPayment: vi.fn(async () => {
        throw new Error("Invalid Razorpay signature");
      })
    });

    const result = await runRazorpayCheckout({
      planId: "plan-1",
      customerName: "Ada Lovelace",
      customerEmail: "ada@example.com",
      deps: d
    });

    expect(result.status).toBe("verify_failed");
    if (result.status === "verify_failed") {
      expect(result.error.message).toMatch(/signature/i);
    }
  });

  it("blocks duplicate submit while checkout is in progress", async () => {
    let release!: (value: { cancelled: true }) => void;
    const openCheckout = vi.fn(
      () =>
        new Promise<{ cancelled: true }>((resolve) => {
          release = resolve;
        })
    );
    const d = deps({ openCheckout });

    const first = runRazorpayCheckout({
      planId: "plan-1",
      customerName: "Ada Lovelace",
      customerEmail: "ada@example.com",
      deps: d
    });

    // Allow createOrder + script load to finish and reach openCheckout
    await vi.waitFor(() => expect(openCheckout).toHaveBeenCalled());

    const second = await runRazorpayCheckout({
      planId: "plan-2",
      customerName: "Ada Lovelace",
      customerEmail: "ada@example.com",
      deps: d
    });

    expect(second).toEqual({ status: "blocked", reason: "in_progress" });
    expect(d.createOrder).toHaveBeenCalledOnce();

    release({ cancelled: true });
    await expect(first).resolves.toEqual({ status: "cancelled" });
  });

  it("does not open checkout when order creation fails", async () => {
    const d = deps({
      createOrder: vi.fn(async () => {
        throw new Error("network down");
      })
    });

    const result = await runRazorpayCheckout({
      planId: "plan-1",
      customerName: "Ada Lovelace",
      customerEmail: "ada@example.com",
      deps: d
    });

    expect(result.status).toBe("network_failed");
    expect(d.loadCheckoutScript).not.toHaveBeenCalled();
    expect(d.openCheckout).not.toHaveBeenCalled();
    expect(d.verifyPayment).not.toHaveBeenCalled();
  });
});

function subscriptionDeps(
  overrides: Partial<RazorpaySubscriptionCheckoutDeps> = {}
): RazorpaySubscriptionCheckoutDeps {
  return {
    razorpayKey: "rzp_test_key",
    createSubscription: vi.fn(async () => ({ razorpay_subscription_id: "sub_123" })),
    verifySubscriptionPayment: vi.fn(async () => ({ status: "incomplete" })),
    loadCheckoutScript: vi.fn(async () => undefined),
    openSubscriptionCheckout: vi.fn(async () => ({
      razorpay_subscription_id: "sub_123",
      razorpay_payment_id: "pay_123",
      razorpay_signature: "sig_123"
    })),
    ...overrides
  };
}

describe("runRazorpaySubscriptionCheckout", () => {
  beforeEach(() => {
    resetRazorpayCheckoutLock();
  });

  it("completes successful checkout: subscription → checkout → verify", async () => {
    const d = subscriptionDeps();
    const result = await runRazorpaySubscriptionCheckout({
      planId: "plan-1",
      customerName: "Ada Lovelace",
      customerEmail: "ada@example.com",
      planName: "Starter",
      deps: d
    });

    expect(result).toEqual({ status: "success" });
    expect(d.createSubscription).toHaveBeenCalledWith({
      plan_id: "plan-1",
      customer_name: "Ada Lovelace",
      customer_email: "ada@example.com"
    });
    expect(d.loadCheckoutScript).toHaveBeenCalledOnce();
    expect(d.openSubscriptionCheckout).toHaveBeenCalledWith(
      expect.objectContaining({
        key: "rzp_test_key",
        subscription_id: "sub_123",
        prefill: { name: "Ada Lovelace", email: "ada@example.com" }
      })
    );
    expect(d.verifySubscriptionPayment).toHaveBeenCalledWith({
      razorpay_subscription_id: "sub_123",
      razorpay_payment_id: "pay_123",
      razorpay_signature: "sig_123",
      plan_id: "plan-1"
    });
  });

  it("passes interval through to subscription creation when provided", async () => {
    const d = subscriptionDeps();
    await runRazorpaySubscriptionCheckout({
      planId: "plan-1",
      customerName: "Ada Lovelace",
      customerEmail: "ada@example.com",
      interval: "year",
      deps: d
    });

    expect(d.createSubscription).toHaveBeenCalledWith(
      expect.objectContaining({ interval: "year" })
    );
  });

  it("handles cancelled payment without calling verify", async () => {
    const d = subscriptionDeps({
      openSubscriptionCheckout: vi.fn(async () => ({ cancelled: true as const }))
    });

    const result = await runRazorpaySubscriptionCheckout({
      planId: "plan-1",
      customerName: "Ada Lovelace",
      customerEmail: "ada@example.com",
      deps: d
    });

    expect(result).toEqual({ status: "cancelled" });
    expect(d.createSubscription).toHaveBeenCalledOnce();
    expect(d.verifySubscriptionPayment).not.toHaveBeenCalled();
  });

  it("returns verify_failed when verification rejects", async () => {
    const d = subscriptionDeps({
      verifySubscriptionPayment: vi.fn(async () => {
        throw new Error("Invalid Razorpay signature");
      })
    });

    const result = await runRazorpaySubscriptionCheckout({
      planId: "plan-1",
      customerName: "Ada Lovelace",
      customerEmail: "ada@example.com",
      deps: d
    });

    expect(result.status).toBe("verify_failed");
    if (result.status === "verify_failed") {
      expect(result.error.message).toMatch(/signature/i);
    }
  });

  it("does not open checkout when subscription creation fails", async () => {
    const d = subscriptionDeps({
      createSubscription: vi.fn(async () => {
        throw new Error("network down");
      })
    });

    const result = await runRazorpaySubscriptionCheckout({
      planId: "plan-1",
      customerName: "Ada Lovelace",
      customerEmail: "ada@example.com",
      deps: d
    });

    expect(result.status).toBe("network_failed");
    expect(d.loadCheckoutScript).not.toHaveBeenCalled();
    expect(d.openSubscriptionCheckout).not.toHaveBeenCalled();
    expect(d.verifySubscriptionPayment).not.toHaveBeenCalled();
  });

  it("blocks duplicate submit while a subscription checkout is in progress", async () => {
    let release!: (value: { cancelled: true }) => void;
    const openSubscriptionCheckout = vi.fn(
      () =>
        new Promise<{ cancelled: true }>((resolve) => {
          release = resolve;
        })
    );
    const d = subscriptionDeps({ openSubscriptionCheckout });

    const first = runRazorpaySubscriptionCheckout({
      planId: "plan-1",
      customerName: "Ada Lovelace",
      customerEmail: "ada@example.com",
      deps: d
    });

    await vi.waitFor(() => expect(openSubscriptionCheckout).toHaveBeenCalled());

    const second = await runRazorpaySubscriptionCheckout({
      planId: "plan-2",
      customerName: "Ada Lovelace",
      customerEmail: "ada@example.com",
      deps: d
    });

    expect(second).toEqual({ status: "blocked", reason: "in_progress" });

    release({ cancelled: true });
    await expect(first).resolves.toEqual({ status: "cancelled" });
  });
});
