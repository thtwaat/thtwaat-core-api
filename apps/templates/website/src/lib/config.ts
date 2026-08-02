/**
 * Site + brand configuration (admin-editable defaults).
 * Override via env or /admin localStorage for demos.
 */

export type NavItem = { label: string; href: string };
export type SiteConfig = {
  name: string;
  tagline: string;
  description: string;
  url: string;
  logoText: string;
  brandColor: string;
  navigation: NavItem[];
  footerLinks: NavItem[];
  social: { twitter?: string; linkedin?: string; github?: string };
  contactEmail: string;
  suggestedQuestions: string[];
};

export const siteConfig: SiteConfig = {
  name: process.env.NEXT_PUBLIC_SITE_NAME || "THTWAAT Starter",
  tagline: "AI-powered websites that convert",
  description:
    "Production-ready Next.js starter with THTWAAT AI chat, knowledge search, leads, and SEO — almost zero configuration.",
  url: process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3100",
  logoText: process.env.NEXT_PUBLIC_SITE_NAME || "THTWAAT",
  brandColor: process.env.NEXT_PUBLIC_BRAND_COLOR || "#0F766E",
  navigation: [
    { label: "Home", href: "/" },
    { label: "About", href: "/about" },
    { label: "Services", href: "/services" },
    { label: "Pricing", href: "/pricing" },
    { label: "Blog", href: "/blog" },
    { label: "Chat", href: "/chat" },
    { label: "Contact", href: "/contact" },
  ],
  footerLinks: [
    { label: "Privacy", href: "/privacy" },
    { label: "Terms", href: "/terms" },
    { label: "Contact", href: "/contact" },
    { label: "Admin", href: "/admin" },
  ],
  social: {
    twitter: "https://twitter.com/thtwaat",
    linkedin: "https://linkedin.com/company/thtwaat",
  },
  contactEmail: "hello@thtwaat.com",
  suggestedQuestions: [
    "What can this AI assistant help me with?",
    "How do I connect my knowledge base?",
    "What pricing plans are available?",
    "Book a demo for my team",
  ],
};

export function getApiUrl() {
  return (
    process.env.API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "https://api.thtwaat.com"
  ).replace(/\/$/, "");
}

export function getAgentApiKey() {
  return (
    process.env.AGENT_API_KEY ||
    process.env.NEXT_PUBLIC_AGENT_API_KEY ||
    ""
  );
}
