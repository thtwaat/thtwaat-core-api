import type { MetadataRoute } from "next";
import { site } from "@/lib/config";

// Only routes that are actually server-rendered and indexable belong here —
// auth pages are noindex and /app, /admin are private/disallowed in robots.ts.
export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: site.url, lastModified: new Date(), changeFrequency: "weekly", priority: 1 },
    { url: `${site.url}/platform`, lastModified: new Date(), changeFrequency: "weekly", priority: 0.9 },
    { url: `${site.url}/pricing`, lastModified: new Date(), changeFrequency: "weekly", priority: 0.9 }
  ];
}
