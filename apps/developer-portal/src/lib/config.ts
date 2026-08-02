export const site = {
  name: process.env.NEXT_PUBLIC_SITE_NAME || "THTWAAT Developer Portal",
  url: process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3400",
  apiUrl: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  version: process.env.NEXT_PUBLIC_DOCS_VERSION || "1.0.0",
  description:
    "Build AI products on THTWAAT — REST API, JavaScript SDK, Widget SDK, webhooks, and interactive API explorer."
};

export type NavItem = {
  title: string;
  href: string;
  badge?: string;
};

export type NavSection = {
  title: string;
  items: NavItem[];
};

export const docsNav: NavSection[] = [
  {
    title: "Getting started",
    items: [
      { title: "Home", href: "/" },
      { title: "Quick Start", href: "/docs/quick-start" },
      { title: "Authentication", href: "/docs/authentication" }
    ]
  },
  {
    title: "API",
    items: [
      { title: "REST API", href: "/docs/rest-api" },
      { title: "API Explorer", href: "/api-explorer" },
      { title: "Webhooks", href: "/docs/webhooks" },
      { title: "Rate Limits", href: "/docs/rate-limits" },
      { title: "Errors", href: "/docs/errors" }
    ]
  },
  {
    title: "SDKs",
    items: [
      { title: "JavaScript SDK", href: "/docs/javascript-sdk" },
      { title: "REST SDK", href: "/docs/rest-sdk" },
      { title: "Widget SDK", href: "/docs/widget-sdk" },
      { title: "Flutter SDK", href: "/docs/flutter-sdk", badge: "Soon" }
    ]
  },
  {
    title: "Guides",
    items: [
      { title: "Examples", href: "/examples" },
      { title: "Downloads", href: "/downloads" },
      { title: "Changelog", href: "/docs/changelog" },
      { title: "Release Notes", href: "/docs/release-notes" },
      { title: "FAQ", href: "/docs/faq" },
      { title: "Support", href: "/support" }
    ]
  }
];

export const examplePages = [
  { slug: "website", title: "Website Integration", stack: "Next.js / HTML" },
  { slug: "landing", title: "Landing Integration", stack: "Next.js" },
  { slug: "saas", title: "SaaS Integration", stack: "Next.js + JWT" },
  { slug: "react", title: "React", stack: "React 19" },
  { slug: "nextjs", title: "Next.js", stack: "App Router" },
  { slug: "nodejs", title: "Node.js", stack: "Node 20+" },
  { slug: "express", title: "Express", stack: "Express 4/5" },
  { slug: "fastapi", title: "FastAPI", stack: "Python 3.11+" }
];
