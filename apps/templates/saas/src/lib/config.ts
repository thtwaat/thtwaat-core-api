export const site = {
  name: process.env.NEXT_PUBLIC_SITE_NAME || "THTWAAT SaaS",
  tagline: "Ship your AI SaaS on the THTWAAT platform",
  description:
    "Build, publish, and run AI agents with chat, voice calling, and knowledge search — auth, billing, usage, and custom domains wired to the THTWAAT Core API.",
  url: process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3300",
  apiUrl: (process.env.NEXT_PUBLIC_API_URL || "https://api.thtwaat.com").replace(/\/$/, ""),
  developerPortalUrl: (
    process.env.NEXT_PUBLIC_DEVELOPER_PORTAL_URL || "https://developer.thtwaat.com"
  ).replace(/\/$/, ""),
  brandColor: process.env.NEXT_PUBLIC_BRAND_COLOR || "#0f766e",
  razorpayKey: process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID || ""
};

export const apiPaths = {
  v1: `${site.apiUrl}/api/v1`,
  v2: `${site.apiUrl}/v2`,
  apiV2: `${site.apiUrl}/api/v2`,
  public: `${site.apiUrl}/public/v1`
} as const;
