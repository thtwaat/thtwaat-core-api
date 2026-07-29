import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-lg py-20 text-center">
      <p className="text-sm font-semibold uppercase tracking-wide text-brand">404</p>
      <h1 className="mt-2 font-display text-3xl font-semibold">Page not found</h1>
      <p className="mt-3 text-muted">That route does not exist in the Developer Portal.</p>
      <div className="mt-6 flex justify-center gap-3">
        <Link href="/">
          <Button>Home</Button>
        </Link>
        <Link href="/docs/quick-start">
          <Button variant="secondary">Docs</Button>
        </Link>
        <Link href="/search">
          <Button variant="secondary">Search</Button>
        </Link>
      </div>
    </div>
  );
}
