import Link from "next/link";
import { site } from "@/lib/config";

/** Shared footer for every indexable marketing page (/, /platform, /pricing). */
export function MarketingFooter() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-5 py-8 text-sm text-muted sm:flex-row sm:items-center sm:justify-between">
        <p>
          &copy; {new Date().getFullYear()} {site.name}
        </p>
        <div className="flex flex-wrap gap-5">
          <Link href="/platform" className="hover:text-ink">
            Platform
          </Link>
          <Link href="/pricing" className="hover:text-ink">
            Pricing
          </Link>
          <Link href="/login" className="hover:text-ink">
            Sign in
          </Link>
          <Link href="/signup" className="hover:text-ink">
            Create workspace
          </Link>
          <a href={site.developerPortalUrl} className="hover:text-ink">
            Developer docs
          </a>
        </div>
      </div>
    </footer>
  );
}
