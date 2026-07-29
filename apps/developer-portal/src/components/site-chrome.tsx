"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { BookOpen, Download, Menu, Search, Terminal, X } from "lucide-react";
import { useState } from "react";
import { docsNav, site } from "@/lib/config";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ThemeToggle } from "@/components/theme-toggle";
import { Badge } from "@/components/ui/card";

export function SiteHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);

  function onSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    router.push(`/search?q=${encodeURIComponent(q.trim())}`);
    setOpen(false);
  }

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-panel/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4 sm:px-6">
        <button className="lg:hidden" onClick={() => setOpen((v) => !v)} aria-label="Menu">
          {open ? <X size={18} /> : <Menu size={18} />}
        </button>
        <Link href="/" className="flex items-center gap-2 font-display text-lg font-semibold text-ink">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand text-sm text-white">T</span>
          <span className="hidden sm:inline">THTWAAT Docs</span>
        </Link>
        <nav className="ml-4 hidden items-center gap-1 md:flex">
          {[
            { href: "/docs/quick-start", label: "Docs", icon: BookOpen },
            { href: "/api-explorer", label: "API Explorer", icon: Terminal },
            { href: "/downloads", label: "Downloads", icon: Download }
          ].map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium",
                pathname.startsWith(item.href) ? "bg-brand-soft text-brand" : "text-muted hover:text-ink"
              )}
            >
              <item.icon size={14} />
              {item.label}
            </Link>
          ))}
        </nav>
        <form onSubmit={onSearch} className="ml-auto flex max-w-xs flex-1 items-center gap-2">
          <div className="relative hidden w-full sm:block">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search docs…"
              className="pl-9"
            />
          </div>
          <ThemeToggle />
        </form>
      </div>

      {open && (
        <div className="border-t border-line bg-panel px-4 py-4 lg:hidden">
          <form onSubmit={onSearch} className="mb-4">
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search docs…" />
          </form>
          {docsNav.map((section) => (
            <div key={section.title} className="mb-4">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">{section.title}</p>
              <div className="space-y-1">
                {section.items.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setOpen(false)}
                    className="flex items-center justify-between rounded-lg px-2 py-1.5 text-sm text-ink hover:bg-canvas"
                  >
                    {item.title}
                    {item.badge && <Badge tone="warn">{item.badge}</Badge>}
                  </Link>
                ))}
              </div>
            </div>
          ))}
          <p className="text-xs text-muted">API: {site.apiUrl}</p>
        </div>
      )}
    </header>
  );
}

export function DocsSidebar() {
  const pathname = usePathname();
  return (
    <aside className="hidden w-64 shrink-0 lg:block">
      <div className="sticky top-20 max-h-[calc(100vh-6rem)] space-y-6 overflow-y-auto pr-2">
        {docsNav.map((section) => (
          <div key={section.title}>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">{section.title}</p>
            <ul className="space-y-0.5">
              {section.items.map((item) => {
                const active = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className={cn(
                        "flex items-center justify-between rounded-lg px-2.5 py-1.5 text-sm",
                        active ? "bg-brand-soft font-semibold text-brand" : "text-muted hover:bg-canvas hover:text-ink"
                      )}
                    >
                      {item.title}
                      {item.badge && <Badge tone="warn">{item.badge}</Badge>}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>
    </aside>
  );
}

export function SiteFooter() {
  return (
    <footer className="mt-16 border-t border-line py-10">
      <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 text-sm text-muted sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <p>© {new Date().getFullYear()} THTWAAT · Developer Portal v{site.version}</p>
        <div className="flex gap-4">
          <Link href="/docs/changelog" className="hover:text-ink">Changelog</Link>
          <Link href="/support" className="hover:text-ink">Support</Link>
          <Link href="/downloads" className="hover:text-ink">Downloads</Link>
          <a href={`${site.apiUrl}/docs`} target="_blank" rel="noreferrer" className="hover:text-ink">
            Live OpenAPI
          </a>
        </div>
      </div>
    </footer>
  );
}
