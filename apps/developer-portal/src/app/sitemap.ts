import type { MetadataRoute } from "next";
import { site, examplePages } from "@/lib/config";
import { listDocs } from "@/lib/docs";

export default function sitemap(): MetadataRoute.Sitemap {
  const docs = listDocs().map((d) => ({
    url: `${site.url}/docs/${d.slug}`,
    lastModified: new Date(),
    changeFrequency: "weekly" as const,
    priority: 0.8
  }));
  const examples = examplePages.map((e) => ({
    url: `${site.url}/examples/${e.slug}`,
    lastModified: new Date(),
    changeFrequency: "monthly" as const,
    priority: 0.6
  }));
  return [
    { url: site.url, lastModified: new Date(), changeFrequency: "weekly", priority: 1 },
    { url: `${site.url}/api-explorer`, lastModified: new Date(), changeFrequency: "weekly", priority: 0.9 },
    { url: `${site.url}/downloads`, lastModified: new Date(), changeFrequency: "monthly", priority: 0.7 },
    { url: `${site.url}/examples`, lastModified: new Date(), changeFrequency: "monthly", priority: 0.7 },
    { url: `${site.url}/support`, lastModified: new Date(), changeFrequency: "monthly", priority: 0.5 },
    { url: `${site.url}/search`, lastModified: new Date(), changeFrequency: "monthly", priority: 0.4 },
    ...docs,
    ...examples
  ];
}
