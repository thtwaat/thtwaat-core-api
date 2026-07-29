import { AdminThemePanel } from "@/components/admin/theme-panel";
import { buildMetadata } from "@/lib/seo";

export const metadata = buildMetadata({
  title: "Admin",
  description: "Theme, brand, and publish controls.",
  path: "/admin",
});

export default function AdminPage() {
  return (
    <section className="container-page section space-y-6">
      <div>
        <h1 className="font-display text-4xl">Admin</h1>
        <p className="text-ink-muted">
          Theme, logo, brand colors, navigation defaults, and one-click publish/connect.
        </p>
      </div>
      <AdminThemePanel />
    </section>
  );
}
