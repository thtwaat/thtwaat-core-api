"use client";

import { Suspense, useEffect, useRef } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { trackEvent } from "@/lib/analytics";

/**
 * Fires GA4 page_view on initial load and on every App Router
 * pathname/searchParams change (client-side navigations don't trigger a
 * browser page load, so gtag's automatic page_view is disabled — see the
 * `send_page_view: false` config in layout.tsx — and this is the only
 * source of page_view events).
 *
 * page_location is rebuilt from pathname only (query string dropped) so
 * sensitive query params never reach GA4.
 */
function PageViewTrackerInner() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const lastKey = useRef<string | null>(null);

  useEffect(() => {
    if (!pathname) return;
    const key = `${pathname}?${searchParams?.toString() ?? ""}`;
    if (lastKey.current === key) return;
    lastKey.current = key;
    trackEvent("page_view", {
      page_path: pathname,
      page_location: `${window.location.origin}${pathname}`,
      page_title: document.title
    });
  }, [pathname, searchParams]);

  return null;
}

export function PageViewTracker() {
  return (
    <Suspense fallback={null}>
      <PageViewTrackerInner />
    </Suspense>
  );
}
