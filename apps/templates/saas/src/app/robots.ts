import type { MetadataRoute } from "next";
import { site } from "@/lib/config";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      // Authenticated app/admin surfaces carry no public content and are
      // already noindexed at the page level (login/signup/etc.) — disallow
      // the large /app and /admin trees outright to save crawl budget.
      disallow: ["/app", "/admin"]
    },
    sitemap: `${site.url}/sitemap.xml`,
    host: site.url
  };
}
