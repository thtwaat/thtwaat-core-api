import type { Metadata } from "next";
import { site } from "@/lib/config";

/**
 * Metadata for private/utility pages (auth flows) that must never be indexed.
 * `path` should be the clean route with no query string — canonical strips
 * any `?next=...` variant so search engines only ever see one URL per page.
 */
/**
 * Metadata for indexable marketing pages. Fully self-contained (title, OG,
 * Twitter) so a page's metadata doesn't depend on ambiguous merge behavior
 * with the root layout's defaults.
 */
export function pageMetadata({
  title,
  description,
  path
}: {
  title: string;
  description: string;
  path: string;
}): Metadata {
  const url = `${site.url}${path}`;
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: { type: "website", url, title, description, siteName: site.name },
    twitter: { card: "summary_large_image", title, description }
  };
}

export function noIndexMetadata({
  title,
  description,
  path
}: {
  title: string;
  description: string;
  path: string;
}): Metadata {
  return {
    title,
    description,
    alternates: { canonical: `${site.url}${path}` },
    robots: { index: false, follow: false, googleBot: { index: false, follow: false } }
  };
}
