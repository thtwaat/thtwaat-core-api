import type { Metadata } from "next";
import { site } from "@/lib/config";

/**
 * Metadata for private/utility pages (auth flows) that must never be indexed.
 * `path` should be the clean route with no query string — canonical strips
 * any `?next=...` variant so search engines only ever see one URL per page.
 */
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
