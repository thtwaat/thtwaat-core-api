export const site = {
  name: process.env.NEXT_PUBLIC_SITE_NAME || "THTWAAT SaaS",
  url: process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3300",
  apiUrl: (process.env.NEXT_PUBLIC_API_URL || "https://api.thtwaat.com").replace(/\/$/, ""),
  agentApiKey: process.env.NEXT_PUBLIC_AGENT_API_KEY || "",
  brandColor: process.env.NEXT_PUBLIC_BRAND_COLOR || "#0f766e",
  razorpayKey: process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID || ""
};

export const apiPaths = {
  v1: `${site.apiUrl}/api/v1`,
  v2: `${site.apiUrl}/v2`,
  public: `${site.apiUrl}/public/v1`
} as const;
