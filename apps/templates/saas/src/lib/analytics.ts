/**
 * Minimal GA4 (gtag.js) wrapper.
 *
 * Safe to import anywhere: no-ops when gtag hasn't loaded (missing
 * NEXT_PUBLIC_GA_MEASUREMENT_ID, ad blockers, SSR, tests). Never pass PII
 * (email, name, phone, user id, tokens) in `params` — GA4 policy prohibits it
 * and this wrapper does not scrub payloads for you.
 */

declare global {
  interface Window {
    gtag?: (...args: unknown[]) => void;
  }
}

export type AnalyticsEventName =
  | "page_view"
  | "sign_up_started"
  | "workspace_created"
  | "agent_published"
  | "template_installed"
  | "checkout_completed";

export type AnalyticsEventParams = Record<string, string | number | boolean>;

export function trackEvent(name: AnalyticsEventName, params?: AnalyticsEventParams): void {
  if (typeof window === "undefined") return;
  if (typeof window.gtag !== "function") return;
  window.gtag("event", name, params);
}
