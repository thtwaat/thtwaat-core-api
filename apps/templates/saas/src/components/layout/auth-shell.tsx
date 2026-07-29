import Link from "next/link";
import { site } from "@/lib/config";

export function AuthShell({
  title,
  subtitle,
  children
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid min-h-screen place-items-center bg-canvas px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <Link href="/" className="text-xl font-semibold text-ink">
            {site.name}
          </Link>
          <h1 className="mt-4 text-2xl font-semibold text-ink">{title}</h1>
          {subtitle && <p className="mt-2 text-sm text-muted">{subtitle}</p>}
        </div>
        <div className="rounded-2xl border border-line bg-panel p-6 shadow-soft">{children}</div>
      </div>
    </div>
  );
}
