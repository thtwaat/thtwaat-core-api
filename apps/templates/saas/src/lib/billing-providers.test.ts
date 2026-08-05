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

  it("selects stripe when user overrides India company to US", () => {
    expect(
      pickBillingCheckoutProvider(
        {
          stripe: { available: true },
          razorpay: { available: true, key_id: "rzp_live_x" },
          default: "stripe",
          region: { code: "INTL", currency: "USD", provider: "stripe", country_code: "US" }
        },
        "",
        { region: "INTL", currency: "USD", provider: "stripe", country: "US", gateway: "stripe" }
      )
    ).toBe("stripe");
  });

  it("selects razorpay when user overrides US to India", () => {
    expect(
      pickBillingCheckoutProvider(
        {
          stripe: { available: true },
          razorpay: { available: true, key_id: "rzp_live_x" },
          default: "razorpay"
        },
        "",
        { region: "IN", currency: "INR", provider: "razorpay", country: "IN", gateway: "razorpay" }
      )
    ).toBe("razorpay");
  });
});
