import { describe, expect, it } from "vitest";
import {
  pickBillingCheckoutProvider,
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

  it("falls back to site key when API omits key_id", () => {
    expect(
      resolveRazorpayCheckoutKey({ razorpay: { available: true, key_id: null } }, "rzp_site")
    ).toBe("rzp_site");
  });

  it("selects razorpay when available with key even without site key", () => {
    expect(
      pickBillingCheckoutProvider(
        {
          stripe: { available: false },
          razorpay: { available: true, key_id: "rzp_live_x" },
          default: "auto"
        },
        ""
      )
    ).toBe("razorpay");
  });

  it("does not select razorpay when available but no checkout key", () => {
    expect(
      pickBillingCheckoutProvider(
        {
          stripe: { available: false },
          razorpay: { available: true, key_id: null },
          default: "auto"
        },
        ""
      )
    ).toBeNull();
  });

  it("falls back to stripe when razorpay unavailable", () => {
    expect(
      pickBillingCheckoutProvider(
        {
          stripe: { available: true },
          razorpay: { available: false },
          default: "auto"
        },
        ""
      )
    ).toBe("stripe");
  });
});
