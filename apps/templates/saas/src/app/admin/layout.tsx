"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { canPlatformAdmin } from "@/lib/permissions";
import { SUPER_ADMIN_NAV, clearAdminSessionBackup, loadAdminSessionBackup } from "@/lib/super-admin";
import { setTokens } from "@/lib/api";
import { site } from "@/lib/config";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, logout, refreshProfile } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const backup = typeof window !== "undefined" ? loadAdminSessionBackup() : null;

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace(`/login?next=${encodeURIComponent(pathname || "/admin")}`);
      return;
    }
    if (!canPlatformAdmin(user.role)) {
      router.replace("/app");
    }
  }, [user, loading, router, pathname]);

  async function exitImpersonation() {
    const tokens = loadAdminSessionBackup();
    if (!tokens) return;
    setTokens(tokens);
    clearAdminSessionBackup();
    await refreshProfile();
    router.replace("/admin/companies");
  }

  if (loading || !user || !canPlatformAdmin(user.role)) {
    return (
      <div className="grid min-h-screen place-items-center bg-canvas text-sm text-muted">
        Loading Super Admin…
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-canvas lg:flex">
      <aside className="w-full border-b border-line bg-panel lg:w-56 lg:border-b-0 lg:border-r">
        <div className="border-b border-line px-4 py-4">
          <Link href="/admin" className="text-sm font-semibold text-ink">
            {site.name} Admin
          </Link>
          <p className="mt-1 truncate text-xs text-muted">{user.email}</p>
        </div>
        <nav className="flex flex-wrap gap-1 p-3 lg:flex-col" aria-label="Super Admin">
          {SUPER_ADMIN_NAV.map((item) => {
            const active = item.exact
              ? pathname === item.href
              : pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "rounded-xl px-3 py-2 text-sm font-medium",
                  active ? "bg-brand-soft text-brand-dark" : "text-muted hover:bg-canvas hover:text-ink"
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="space-y-2 border-t border-line p-3">
          {backup && (
            <Button className="w-full" variant="secondary" onClick={() => void exitImpersonation()}>
              Exit login-as
            </Button>
          )}
          <Button
            className="w-full"
            variant="ghost"
            onClick={async () => {
              await logout();
              router.replace("/login");
            }}
          >
            Sign out
          </Button>
          <Link className="block px-3 text-xs text-muted hover:text-ink" href="/app">
            Customer app →
          </Link>
        </div>
      </aside>
      <main className="min-w-0 flex-1 px-4 py-6 lg:px-8">{children}</main>
    </div>
  );
}
