import { describe, expect, it } from "vitest";
import {
  formatPlanPrice,
  pickBillingCheckoutProvider,
  resolvePlanDisplayAmount,
  resolveRazorpayCheckoutKey
} from "./billing-providers";

describe("billing provider detection", () => {
  it("uses API key_id over NEXT_PUBLIC site key", () => {
    expect(
      resolveRazorpayCheckoutKey(
        { razorpay: { available: true, key_id: "rzp_live_api" } },
        "rzp_build_time"
      )
    ).toBe("rzp_live_api");
  });

  it("selects razorpay for India region context", () => {
    expect(
      pickBillingCheckoutProvider(
        {
          stripe: { available: true },
          razorpay: { available: true, key_id: "rzp_live_x" },
          default: "auto"
        },
        "",
        { region: "IN", currency: "INR", provider: "razorpay" }
      )
    ).toBe("razorpay");
  });

  it("selects stripe for international region", () => {
    expect(
      pickBillingCheckoutProvider(
        {
          stripe: { available: true },
          razorpay: { available: true, key_id: "rzp_live_x" },
          default: "auto",
          region: { code: "INTL", currency: "USD", provider: "stripe" }
        },
        "",
        { region: "INTL", currency: "USD", provider: "stripe" }
      )
    ).toBe("stripe");
  });

  it("formats INR and USD prices", () => {
    expect(formatPlanPrice(999, "INR")).toMatch(/999/);
    expect(formatPlanPrice(29, "USD")).toMatch(/29/);
  });

  it("resolves display amount by currency", () => {
    const plan = { price_inr: 999, price_usd: 29, amount: 29 };
    expect(resolvePlanDisplayAmount(plan, "INR")).toBe(999);
    expect(resolvePlanDisplayAmount(plan, "USD")).toBe(29);
    expect(resolvePlanDisplayAmount({ is_custom_pricing: true }, "USD")).toBeNull();
  });
});
