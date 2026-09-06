import Link from "next/link";
import type { Metadata } from "next";
import { site } from "@/lib/config";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Page not found",
  robots: { index: false, follow: false }
};

export default function NotFound() {
  return (
    <main className="grid min-h-screen place-items-center bg-canvas px-4 text-center">
      <div>
        <p className="text-sm font-semibold uppercase tracking-wide text-brand">404</p>
        <h1 className="mt-2 text-3xl font-semibold text-ink">Page not found</h1>
        <p className="mt-3 text-muted">
          That page doesn&apos;t exist on {site.name}.
        </p>
        <div className="mt-6 flex justify-center gap-3">
          <Link href="/">
            <Button>Back home</Button>
          </Link>
          <Link href="/login">
            <Button variant="secondary">Sign in</Button>
          </Link>
        </div>
      </div>
    </main>
  );
}
