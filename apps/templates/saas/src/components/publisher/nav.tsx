"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

export { slugify, statusBadgeClass } from "./helpers";

const links = [
  { href: "/app/publisher", label: "Dashboard", exact: true },
  { href: "/app/publisher/listings", label: "My Templates" },
  { href: "/app/publisher/listings/new", label: "Publish" },
  { href: "/app/publisher/analytics", label: "Analytics" },
  { href: "/app/publisher/reviews", label: "Reviews" },
  { href: "/app/publisher/profile", label: "Profile" }
];

export function PublisherNav() {
  const pathname = usePathname();
  return (
    <nav className="flex flex-wrap gap-1 border-b border-border pb-3">
      {links.map((l) => {
        const active = l.exact
          ? pathname === l.href
          : pathname === l.href || pathname.startsWith(l.href + "/");
        const isListingsParent =
          l.href === "/app/publisher/listings" && pathname.startsWith("/app/publisher/listings/new");
        const on = isListingsParent ? false : active;
        return (
          <Link
            key={l.href}
            href={l.href}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              on ? "bg-ink text-white" : "text-muted hover:bg-surface hover:text-ink"
            )}
          >
            {l.label}
          </Link>
        );
      })}
    </nav>
  );
}
