import type { MetadataRoute } from "next";
import { site } from "@/lib/config";

// Only "/" is indexable — auth pages are noindex and /app, /admin are
// private, so none of them belong in the sitemap.
export default function sitemap(): MetadataRoute.Sitemap {
  return [{ url: site.url, lastModified: new Date(), changeFrequency: "weekly", priority: 1 }];
}
