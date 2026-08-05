/** Resolve which billing checkout provider to use from API status + site config. */

export type BillingRegionInfo = {
  code?: string;
  currency?: string;
  provider?: string;
  country_code?: string | null;
  source?: string;
};

export type BillingProvidersStatus = {
  stripe?: { available?: boolean; configured?: boolean; flag_enabled?: boolean };
  razorpay?: {
    available?: boolean;
    configured?: boolean;
    flag_enabled?: boolean;
    key_id?: string | null;
  };
  default?: string;
  region?: BillingRegionInfo;
};

export type BillingContext = {
  region: string;
  currency: string;
  provider: string;
  gateway?: string;
  country?: string | null;
  country_code?: string | null;
  source?: string;
  providers?: BillingProvidersStatus;
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
  siteRazorpayKey: string | null | undefined,
  billingContext?: BillingContext | null
): "razorpay" | "stripe" | null {
  const razorpayKey = resolveRazorpayCheckoutKey(providers, siteRazorpayKey);
  const razorpayOk = Boolean(providers?.razorpay?.available && razorpayKey);
  const stripeOk = Boolean(providers?.stripe?.available);

  const preferred = (
    billingContext?.provider ||
    providers?.region?.provider ||
    providers?.default ||
    "auto"
  ).toLowerCase();

  if (preferred === "razorpay" && razorpayOk) return "razorpay";
  if (preferred === "stripe" && stripeOk) return "stripe";

  // Region auto: India → Razorpay, else Stripe when both available.
  const region = (billingContext?.region || providers?.region?.code || "").toUpperCase();
  if (region === "IN" && razorpayOk) return "razorpay";
  if (region && region !== "IN" && stripeOk) return "stripe";

  if (razorpayOk) return "razorpay";
  if (stripeOk) return "stripe";
  return null;
}

export function formatPlanPrice(
  amount: number | null | undefined,
  currency: string | null | undefined
): string {
  if (amount == null || Number.isNaN(Number(amount))) return "—";
  const cur = (currency || "USD").toUpperCase();
  try {
    return new Intl.NumberFormat(cur === "INR" ? "en-IN" : "en-US", {
      style: "currency",
      currency: cur,
      maximumFractionDigits: cur === "INR" ? 0 : 2
    }).format(Number(amount));
  } catch {
    return `${cur} ${amount}`;
  }
}

export function resolvePlanDisplayAmount(
  plan: {
    amount?: number | null;
    price?: number | null;
    price_inr?: number | null;
    price_usd?: number | null;
    display_amount?: number | null;
    is_custom_pricing?: boolean;
  },
  currency: string
): number | null {
  if (plan.is_custom_pricing) return null;
  if (plan.display_amount != null) return Number(plan.display_amount);
  const cur = currency.toUpperCase();
  if (cur === "INR" && plan.price_inr != null) return Number(plan.price_inr);
  if (cur === "USD" && plan.price_usd != null) return Number(plan.price_usd);
  const fallback = plan.amount ?? plan.price;
  return fallback == null ? null : Number(fallback);
}
