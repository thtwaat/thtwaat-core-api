"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BarChart3,
  Bot,
  CreditCard,
  Cpu,
  Globe2,
  LayoutDashboard,
  Library,
  LogOut,
  Menu,
  Rocket,
  Settings,
  Shield,
  Sparkles,
  Store,
  Webhook,
  X
} from "lucide-react";
import { useMemo, useState } from "react";
import { useAuth } from "@/lib/auth";
import { canAccessAdmin, canManageWebhooks, canViewProviders } from "@/lib/permissions";
import { site } from "@/lib/config";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const baseNav = [
  { href: "/app", label: "Overview", icon: LayoutDashboard },
  { href: "/app/create", label: "Create Product", icon: Sparkles },
  { href: "/app/agents", label: "Agents", icon: Bot },
  { href: "/app/knowledge", label: "Knowledge", icon: Library },
  { href: "/app/templates", label: "Marketplace", icon: Store },
  { href: "/app/providers", label: "AI Providers", icon: Cpu, requireProviders: true as const },
  { href: "/app/domains", label: "Domains", icon: Globe2 },
  { href: "/app/webhooks", label: "Webhooks", icon: Webhook, requireWebhooks: true as const },
  { href: "/app/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/app/billing", label: "Billing", icon: CreditCard },
  { href: "/app/publish", label: "Publish", icon: Rocket },
  { href: "/app/settings", label: "Settings", icon: Settings }
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout, loading } = useAuth();
  const [open, setOpen] = useState(false);

  const nav = useMemo(() => {
    const filtered = baseNav.filter((item) => {
      if ("requireWebhooks" in item && item.requireWebhooks) {
        return canManageWebhooks(user?.role);
      }
      if ("requireProviders" in item && item.requireProviders) {
        return canViewProviders(user?.role);
      }
      return true;
    });
    if (!canAccessAdmin(user?.role)) return filtered;
    const insertAt = filtered.findIndex((i) => i.href === "/app/settings");
    const withAdmin = [...filtered];
    withAdmin.splice(insertAt < 0 ? withAdmin.length : insertAt, 0, {
      href: "/app/admin",
      label: "Admin",
      icon: Shield
    });
    return withAdmin;
  }, [user?.role]);

  if (loading) {
    return (
      <div className="grid min-h-screen place-items-center bg-canvas text-sm text-muted">Loading workspace…</div>
    );
  }

  if (!user) {
    if (typeof window !== "undefined") router.replace("/login");
    return null;
  }

  async function onLogout() {
    await logout();
    router.replace("/login");
  }

  const Sidebar = (
    <aside className="flex h-full w-64 flex-col border-r border-line bg-panel">
      <div className="border-b border-line px-5 py-4">
        <Link href="/app" className="text-lg font-semibold text-ink">
          {site.name}
        </Link>
        <p className="mt-1 truncate text-xs text-muted">{user.email}</p>
      </div>
      <nav className="flex-1 space-y-1 p-3">
        {nav.map((item) => {
          const active = pathname === item.href || (item.href !== "/app" && pathname.startsWith(item.href));
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setOpen(false)}
              className={cn(
                "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition",
                active ? "bg-brand-soft text-brand-dark" : "text-muted hover:bg-canvas hover:text-ink"
              )}
            >
              <Icon size={17} />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-line p-3">
        <Button variant="ghost" className="w-full justify-start" onClick={onLogout}>
          <LogOut size={16} /> Sign out
        </Button>
      </div>
    </aside>
  );

  return (
    <div className="min-h-screen bg-canvas lg:flex">
      <div className="hidden lg:block">{Sidebar}</div>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-ink/40" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 z-50">{Sidebar}</div>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-line bg-panel px-4 py-3 lg:px-8">
          <button className="rounded-lg p-2 hover:bg-canvas lg:hidden" onClick={() => setOpen(true)}>
            {open ? <X size={18} /> : <Menu size={18} />}
          </button>
          <div className="ml-auto flex items-center gap-3 text-sm">
            <span className="hidden text-muted sm:inline">
              {user.first_name} {user.last_name}
            </span>
            <span className="rounded-full bg-brand-soft px-2.5 py-1 text-xs font-semibold text-brand-dark">
              {user.role}
            </span>
          </div>
        </header>
        <main className="flex-1 px-4 py-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
