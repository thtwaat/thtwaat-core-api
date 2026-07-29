import Link from "next/link";
import { siteConfig } from "@/lib/config";

export function Footer() {
  return (
    <footer className="mt-auto border-t border-black/5 bg-surface-elevated/70">
      <div className="container-page grid gap-10 py-14 sm:grid-cols-2 lg:grid-cols-4">
        <div className="space-y-3">
          <p className="font-display text-lg">{siteConfig.logoText}</p>
          <p className="text-sm text-ink-muted">{siteConfig.description}</p>
        </div>
        <div>
          <p className="mb-3 text-sm font-semibold">Product</p>
          <ul className="space-y-2 text-sm text-ink-muted">
            {siteConfig.navigation.slice(0, 5).map((l) => (
              <li key={l.href}>
                <Link href={l.href} className="hover:text-ink">
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="mb-3 text-sm font-semibold">Company</p>
          <ul className="space-y-2 text-sm text-ink-muted">
            {siteConfig.footerLinks.map((l) => (
              <li key={l.href}>
                <Link href={l.href} className="hover:text-ink">
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="mb-3 text-sm font-semibold">Connect</p>
          <p className="text-sm text-ink-muted">{siteConfig.contactEmail}</p>
          <div className="mt-3 flex gap-3 text-sm">
            {siteConfig.social.twitter && (
              <a href={siteConfig.social.twitter} className="text-brand hover:underline">
                Twitter
              </a>
            )}
            {siteConfig.social.linkedin && (
              <a href={siteConfig.social.linkedin} className="text-brand hover:underline">
                LinkedIn
              </a>
            )}
          </div>
        </div>
      </div>
      <div className="border-t border-black/5 py-4 text-center text-xs text-ink-muted">
        © {new Date().getFullYear()} {siteConfig.name}. Powered by THTWAAT AI.
      </div>
    </footer>
  );
}
