/** Resolve which billing checkout provider to use from API status + site config. */

export type BillingProvidersStatus = {
  stripe?: { available?: boolean; configured?: boolean; flag_enabled?: boolean };
  razorpay?: {
    available?: boolean;
    configured?: boolean;
    flag_enabled?: boolean;
    key_id?: string | null;
  };
  default?: string;
};

export function resolveRazorpayCheckoutKey(
  providers: BillingProvidersStatus | null | undefined,
  siteKey: string | null | undefined
): string {
  const fromApi = (providers?.razorpay?.key_id || "").trim();
  if (fromApi) return fromApi;
  return (siteKey || "").trim();
}

export function pickBillingCheckoutProvider(
  providers: BillingProvidersStatus | null | undefined,
  siteRazorpayKey: string | null | undefined
): "razorpay" | "stripe" | null {
  const razorpayKey = resolveRazorpayCheckoutKey(providers, siteRazorpayKey);
  const razorpayOk = Boolean(providers?.razorpay?.available && razorpayKey);
  const stripeOk = Boolean(providers?.stripe?.available);
  const preferred = (providers?.default || "auto").toLowerCase();

  if (preferred === "razorpay" && razorpayOk) return "razorpay";
  if (preferred === "stripe" && stripeOk) return "stripe";

  // Prefer Razorpay when both available (common India deploy) unless Stripe-only preferred.
  if (razorpayOk) return "razorpay";
  if (stripeOk) return "stripe";
  return null;
}
