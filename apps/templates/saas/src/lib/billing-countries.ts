/** Billing country catalog + client-side preference helpers. */

export type BillingCountry = {
  code: string;
  name: string;
  flag: string;
};

const STORAGE_KEY = "tht_billing_country";

function billingCountryStorage(): Storage | null {
  try {
    if (typeof globalThis === "undefined") return null;
    const storage = (globalThis as { localStorage?: Storage }).localStorage;
    return storage ?? null;
  } catch {
    return null;
  }
}

/** Common ISO countries for billing (India + intl → USD/Stripe). */
export const BILLING_COUNTRIES: BillingCountry[] = [
  { code: "IN", name: "India", flag: "🇮🇳" },
  { code: "US", name: "United States", flag: "🇺🇸" },
  { code: "GB", name: "United Kingdom", flag: "🇬🇧" },
  { code: "CA", name: "Canada", flag: "🇨🇦" },
  { code: "AU", name: "Australia", flag: "🇦🇺" },
  { code: "DE", name: "Germany", flag: "🇩🇪" },
  { code: "FR", name: "France", flag: "🇫🇷" },
  { code: "NL", name: "Netherlands", flag: "🇳🇱" },
  { code: "SG", name: "Singapore", flag: "🇸🇬" },
  { code: "AE", name: "United Arab Emirates", flag: "🇦🇪" },
  { code: "SA", name: "Saudi Arabia", flag: "🇸🇦" },
  { code: "JP", name: "Japan", flag: "🇯🇵" },
  { code: "KR", name: "South Korea", flag: "🇰🇷" },
  { code: "BR", name: "Brazil", flag: "🇧🇷" },
  { code: "MX", name: "Mexico", flag: "🇲🇽" },
  { code: "ZA", name: "South Africa", flag: "🇿🇦" },
  { code: "NG", name: "Nigeria", flag: "🇳🇬" },
  { code: "KE", name: "Kenya", flag: "🇰🇪" },
  { code: "PH", name: "Philippines", flag: "🇵🇭" },
  { code: "ID", name: "Indonesia", flag: "🇮🇩" },
  { code: "MY", name: "Malaysia", flag: "🇲🇾" },
  { code: "TH", name: "Thailand", flag: "🇹🇭" },
  { code: "VN", name: "Vietnam", flag: "🇻🇳" },
  { code: "NZ", name: "New Zealand", flag: "🇳🇿" },
  { code: "IE", name: "Ireland", flag: "🇮🇪" },
  { code: "ES", name: "Spain", flag: "🇪🇸" },
  { code: "IT", name: "Italy", flag: "🇮🇹" },
  { code: "SE", name: "Sweden", flag: "🇸🇪" },
  { code: "CH", name: "Switzerland", flag: "🇨🇭" },
  { code: "PL", name: "Poland", flag: "🇵🇱" }
].sort((a, b) => a.name.localeCompare(b.name));

export function countryCurrency(code: string | null | undefined): "INR" | "USD" {
  return String(code || "").toUpperCase() === "IN" ? "INR" : "USD";
}

export function findBillingCountry(code: string | null | undefined): BillingCountry | undefined {
  const normalized = String(code || "").trim().toUpperCase();
  if (!normalized) return undefined;
  return BILLING_COUNTRIES.find((c) => c.code === normalized);
}

export function readStoredBillingCountry(): string | null {
  const storage = billingCountryStorage();
  if (!storage) return null;
  try {
    const raw = storage.getItem(STORAGE_KEY);
    const code = String(raw || "").trim().toUpperCase();
    return code.length === 2 ? code : null;
  } catch {
    return null;
  }
}

export function writeStoredBillingCountry(code: string): void {
  const storage = billingCountryStorage();
  if (!storage) return;
  try {
    storage.setItem(STORAGE_KEY, code.toUpperCase());
  } catch {
    /* ignore quota / private mode */
  }
}

/** Map navigator.language (e.g. en-IN, hi-IN) → ISO-2 when present. */
export function countryFromBrowserLocale(language?: string | null): string | null {
  const lang =
    language ||
    (typeof navigator !== "undefined"
      ? navigator.language || navigator.languages?.[0]
      : null) ||
    "";
  const match = String(lang).match(/[-_]([A-Za-z]{2})\b/);
  if (!match) return null;
  return match[1].toUpperCase();
}

export function filterBillingCountries(query: string): BillingCountry[] {
  const q = query.trim().toLowerCase();
  if (!q) return BILLING_COUNTRIES;
  return BILLING_COUNTRIES.filter(
    (c) => c.name.toLowerCase().includes(q) || c.code.toLowerCase().includes(q)
  );
}

/**
 * Pick initial country after server billing-context loads.
 * Priority already applied server-side for preference/company/header;
 * client adds localStorage + browser locale before US default.
 */
export function resolveInitialBillingCountry(opts: {
  stored?: string | null;
  serverCountry?: string | null;
  serverSource?: string | null;
  browserCountry?: string | null;
}): string {
  const stored = String(opts.stored || "").trim().toUpperCase();
  if (stored.length === 2) return stored;

  const source = String(opts.serverSource || "").toLowerCase();
  const server = String(opts.serverCountry || "").trim().toUpperCase();
  if (server.length === 2 && source && source !== "default") {
    return server;
  }

  const browser = String(opts.browserCountry || "").trim().toUpperCase();
  if (browser.length === 2) return browser;

  if (server.length === 2) return server;
  return "US";
}
