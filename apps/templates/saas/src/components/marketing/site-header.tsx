import Link from "next/link";
import { site } from "@/lib/config";
import { Button } from "@/components/ui/button";

const navLinks = [
  { href: "/platform", label: "Platform" },
  { href: "/pricing", label: "Pricing" }
];

/** Shared header for every indexable marketing page (/, /platform, /pricing). */
export function MarketingHeader() {
  return (
    <header className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5">
      <Link href="/" className="text-lg font-semibold text-ink">
        {site.name}
      </Link>
      <nav className="hidden items-center gap-6 sm:flex">
        {navLinks.map((link) => (
          <Link key={link.href} href={link.href} className="text-sm font-medium text-muted hover:text-ink">
            {link.label}
          </Link>
        ))}
      </nav>
      <div className="flex gap-3">
        <Link href="/login">
          <Button variant="secondary">Sign in</Button>
        </Link>
        <Link href="/signup">
          <Button>Start free</Button>
        </Link>
      </div>
    </header>
  );
}
