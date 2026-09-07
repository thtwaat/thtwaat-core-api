/**
 * Razorpay Checkout orchestration for SaaS billing.
 * Keeps payment UI logic testable and separate from the billing page.
 */

export type RazorpayOrderRequest = {
  plan_id: string;
  customer_name: string;
  customer_email: string;
  customer_phone?: string;
  coupon_code?: string;
  interval?: string;
};

export type RazorpayOrderResponse = {
  order_id: string;
  subscription_id?: string;
  provider?: string;
};

export type RazorpayVerifyRequest = {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
  plan_id: string;
};

export type RazorpayPaymentSuccess = {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
};

export type RazorpayCheckoutResult =
  | { status: "success" }
  | { status: "cancelled" }
  | { status: "verify_failed"; error: Error }
  | { status: "network_failed"; error: Error }
  | { status: "blocked"; reason: "in_progress" };

export type OpenRazorpayCheckout = (options: {
  key: string;
  order_id: string;
  name?: string;
  description?: string;
  prefill: { name: string; email: string; contact?: string };
}) => Promise<RazorpayPaymentSuccess | { cancelled: true }>;

export type RazorpayCheckoutDeps = {
  razorpayKey: string;
  createOrder: (body: RazorpayOrderRequest) => Promise<RazorpayOrderResponse>;
  verifyPayment: (body: RazorpayVerifyRequest) => Promise<unknown>;
  openCheckout: OpenRazorpayCheckout;
  loadCheckoutScript?: () => Promise<void>;
};

let checkoutInFlight = false;

/** Test helper — reset duplicate-submit lock between cases. */
export function resetRazorpayCheckoutLock(): void {
  checkoutInFlight = false;
}

export function isRazorpayCheckoutInFlight(): boolean {
  return checkoutInFlight;
}

export async function loadRazorpayCheckoutScript(
  doc: Pick<Document, "querySelector" | "createElement" | "body"> = document
): Promise<void> {
  const existing = doc.querySelector("script[data-tht-razorpay-checkout]");
  if (existing) return;

  await new Promise<void>((resolve, reject) => {
    const script = doc.createElement("script") as HTMLScriptElement;
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;
    script.dataset.thtRazorpayCheckout = "1";
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Failed to load Razorpay Checkout"));
    doc.body.appendChild(script);
  });
}

type RazorpayConstructor = new (options: Record<string, unknown>) => {
  open: () => void;
};

declare global {
  interface Window {
    Razorpay?: RazorpayConstructor;
  }
}

export const openRazorpayCheckout: OpenRazorpayCheckout = (options) => {
  return new Promise((resolve, reject) => {
    const Razorpay = typeof window !== "undefined" ? window.Razorpay : undefined;
    if (!Razorpay) {
      reject(new Error("Razorpay Checkout is not available"));
      return;
    }

    const rzp = new Razorpay({
      key: options.key,
      order_id: options.order_id,
      name: options.name || "THTWAAT",
      description: options.description || "Subscription",
      prefill: options.prefill,
      handler: (response: RazorpayPaymentSuccess) => {
        resolve(response);
      },
      modal: {
        ondismiss: () => {
          resolve({ cancelled: true });
        }
      }
    });
    rzp.open();
  });
};

/**
 * Full Razorpay flow:
 * 1) create server order (with customer fields)
 * 2) load checkout script
 * 3) open Razorpay modal
 * 4) verify payment on success
 */
export async function runRazorpayCheckout(input: {
  planId: string;
  customerName: string;
  customerEmail: string;
  customerPhone?: string;
  planName?: string;
  deps: RazorpayCheckoutDeps;
}): Promise<RazorpayCheckoutResult> {
  if (checkoutInFlight) {
    return { status: "blocked", reason: "in_progress" };
  }

  checkoutInFlight = true;
  const { deps } = input;

  try {
    if (!deps.razorpayKey) {
      throw new Error("Razorpay key is not configured");
    }
    if (!input.customerName?.trim() || !input.customerEmail?.trim()) {
      throw new Error("Customer name and email are required for checkout");
    }

    let order: RazorpayOrderResponse;
    try {
      order = await deps.createOrder({
        plan_id: input.planId,
        customer_name: input.customerName.trim(),
        customer_email: input.customerEmail.trim(),
        ...(input.customerPhone ? { customer_phone: input.customerPhone } : {})
      });
    } catch (error) {
      return { status: "network_failed", error: error instanceof Error ? error : new Error(String(error)) };
    }

    if (!order?.order_id) {
      return {
        status: "network_failed",
        error: new Error("Order creation did not return an order_id")
      };
    }

    try {
      await (deps.loadCheckoutScript || loadRazorpayCheckoutScript)();
    } catch (error) {
      return { status: "network_failed", error: error instanceof Error ? error : new Error(String(error)) };
    }

    let payment: RazorpayPaymentSuccess | { cancelled: true };
    try {
      payment = await deps.openCheckout({
        key: deps.razorpayKey,
        order_id: order.order_id,
        name: "THTWAAT",
        description: input.planName ? `Upgrade to ${input.planName}` : "Subscription",
        prefill: {
          name: input.customerName.trim(),
          email: input.customerEmail.trim(),
          ...(input.customerPhone ? { contact: input.customerPhone } : {})
        }
      });
    } catch (error) {
      return { status: "network_failed", error: error instanceof Error ? error : new Error(String(error)) };
    }

    if ("cancelled" in payment) {
      return { status: "cancelled" };
    }

    try {
      await deps.verifyPayment({
        razorpay_order_id: payment.razorpay_order_id,
        razorpay_payment_id: payment.razorpay_payment_id,
        razorpay_signature: payment.razorpay_signature,
        plan_id: input.planId
      });
    } catch (error) {
      return { status: "verify_failed", error: error instanceof Error ? error : new Error(String(error)) };
    }

    return { status: "success" };
  } finally {
    checkoutInFlight = false;
  }
}

// ── Recurring Razorpay Subscriptions ────────────────────────────────────
// Distinct from the one-time Order flow above: this hands Checkout.js a
// `subscription_id` (not `order_id`), which puts it in Razorpay's recurring
// mode and triggers the e-mandate/UPI-Autopay authorization screen. See
// app/payments/subscriptions/service.py:create_razorpay_subscription and
// docs/billing/razorpay-recurring.md.

export type RazorpaySubscriptionCheckoutRequest = {
  plan_id: string;
  customer_name: string;
  customer_email: string;
  customer_phone?: string;
  interval?: string;
};

export type RazorpaySubscriptionCheckoutResponse = {
  razorpay_subscription_id: string;
  subscription_id?: string;
  provider?: string;
};

export type RazorpaySubscriptionVerifyRequest = {
  razorpay_subscription_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
  plan_id: string;
};

export type RazorpaySubscriptionPaymentSuccess = {
  razorpay_subscription_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
};

export type OpenRazorpaySubscriptionCheckout = (options: {
  key: string;
  subscription_id: string;
  name?: string;
  description?: string;
  prefill: { name: string; email: string; contact?: string };
}) => Promise<RazorpaySubscriptionPaymentSuccess | { cancelled: true }>;

export type RazorpaySubscriptionCheckoutDeps = {
  razorpayKey: string;
  createSubscription: (
    body: RazorpaySubscriptionCheckoutRequest
  ) => Promise<RazorpaySubscriptionCheckoutResponse>;
  verifySubscriptionPayment: (body: RazorpaySubscriptionVerifyRequest) => Promise<unknown>;
  openSubscriptionCheckout: OpenRazorpaySubscriptionCheckout;
  loadCheckoutScript?: () => Promise<void>;
};

export const openRazorpaySubscriptionCheckout: OpenRazorpaySubscriptionCheckout = (options) => {
  return new Promise((resolve, reject) => {
    const Razorpay = typeof window !== "undefined" ? window.Razorpay : undefined;
    if (!Razorpay) {
      reject(new Error("Razorpay Checkout is not available"));
      return;
    }

    const rzp = new Razorpay({
      key: options.key,
      subscription_id: options.subscription_id,
      recurring: 1,
      name: options.name || "THTWAAT",
      description: options.description || "Subscription",
      prefill: options.prefill,
      handler: (response: RazorpaySubscriptionPaymentSuccess) => {
        resolve(response);
      },
      modal: {
        ondismiss: () => {
          resolve({ cancelled: true });
        }
      }
    });
    rzp.open();
  });
};

/**
 * Recurring-subscription Razorpay flow:
 * 1) create server-side Razorpay Subscription
 * 2) load checkout script
 * 3) open Razorpay modal in subscription/recurring mode
 * 4) send the first-charge signature to the server for verification
 *
 * Verification here does NOT flip the subscription active on its own — the
 * backend treats the subscription.charged/activated webhook as the
 * authoritative source for entitlement changes. A "success" result here
 * means the payment was genuine and accepted; the plan/entitlement update
 * lands shortly after via webhook (see GET /payments/subscriptions/me).
 */
export async function runRazorpaySubscriptionCheckout(input: {
  planId: string;
  customerName: string;
  customerEmail: string;
  customerPhone?: string;
  planName?: string;
  interval?: string;
  deps: RazorpaySubscriptionCheckoutDeps;
}): Promise<RazorpayCheckoutResult> {
  if (checkoutInFlight) {
    return { status: "blocked", reason: "in_progress" };
  }

  checkoutInFlight = true;
  const { deps } = input;

  try {
    if (!deps.razorpayKey) {
      throw new Error("Razorpay key is not configured");
    }
    if (!input.customerName?.trim() || !input.customerEmail?.trim()) {
      throw new Error("Customer name and email are required for checkout");
    }

    let sub: RazorpaySubscriptionCheckoutResponse;
    try {
      sub = await deps.createSubscription({
        plan_id: input.planId,
        customer_name: input.customerName.trim(),
        customer_email: input.customerEmail.trim(),
        ...(input.customerPhone ? { customer_phone: input.customerPhone } : {}),
        ...(input.interval ? { interval: input.interval } : {})
      });
    } catch (error) {
      return { status: "network_failed", error: error instanceof Error ? error : new Error(String(error)) };
    }

    if (!sub?.razorpay_subscription_id) {
      return {
        status: "network_failed",
        error: new Error("Subscription creation did not return a razorpay_subscription_id")
      };
    }

    try {
      await (deps.loadCheckoutScript || loadRazorpayCheckoutScript)();
    } catch (error) {
      return { status: "network_failed", error: error instanceof Error ? error : new Error(String(error)) };
    }

    let payment: RazorpaySubscriptionPaymentSuccess | { cancelled: true };
    try {
      payment = await deps.openSubscriptionCheckout({
        key: deps.razorpayKey,
        subscription_id: sub.razorpay_subscription_id,
        name: "THTWAAT",
        description: input.planName ? `Subscribe to ${input.planName}` : "Subscription",
        prefill: {
          name: input.customerName.trim(),
          email: input.customerEmail.trim(),
          ...(input.customerPhone ? { contact: input.customerPhone } : {})
        }
      });
    } catch (error) {
      return { status: "network_failed", error: error instanceof Error ? error : new Error(String(error)) };
    }

    if ("cancelled" in payment) {
      return { status: "cancelled" };
    }

    try {
      await deps.verifySubscriptionPayment({
        razorpay_subscription_id: payment.razorpay_subscription_id,
        razorpay_payment_id: payment.razorpay_payment_id,
        razorpay_signature: payment.razorpay_signature,
        plan_id: input.planId
      });
    } catch (error) {
      return { status: "verify_failed", error: error instanceof Error ? error : new Error(String(error)) };
    }

    return { status: "success" };
  } finally {
    checkoutInFlight = false;
  }
}
