import Link from "next/link";
import { Download } from "lucide-react";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { Badge, Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { site } from "@/lib/config";

const downloads = [
  {
    title: "OpenAPI JSON",
    description: "Full machine-readable OpenAPI 3 specification used by the API Explorer.",
    href: "/openapi.json",
    badge: "JSON",
    version: site.version
  },
  {
    title: "OpenAPI YAML",
    description: "YAML conversion of the OpenAPI document for generators and CI.",
    href: "/api/downloads/openapi.yaml",
    badge: "YAML",
    version: site.version
  },
  {
    title: "Postman Collection",
    description: "Importable Postman collection generated from the OpenAPI paths.",
    href: "/api/downloads/postman",
    badge: "Postman",
    version: site.version
  }
];

const sdks = [
  { name: "@thtwaat/sdk", path: "sdk/javascript", href: "/docs/javascript-sdk" },
  { name: "@thtwaat/rest", path: "sdk/rest", href: "/docs/rest-sdk" },
  { name: "@thtwaat/widget", path: "sdk/widget", href: "/docs/widget-sdk" },
  { name: "Flutter SDK", path: "sdk/flutter", href: "/docs/flutter-sdk", soon: true }
];

export default function DownloadsPage() {
  return (
    <div className="space-y-8">
      <Breadcrumbs items={[{ label: "Downloads" }]} />
      <div>
        <h1 className="font-display text-3xl font-semibold">Downloads</h1>
        <p className="mt-2 text-muted">
          Specs, collections, and SDK packages for THTWAAT Core API v{site.version}.
        </p>
      </div>

      <section className="grid gap-4 md:grid-cols-3">
        {downloads.map((item) => (
          <Card key={item.href} className="flex flex-col">
            <div className="flex items-center justify-between gap-2">
              <h2 className="font-semibold">{item.title}</h2>
              <Badge tone="brand">{item.badge}</Badge>
            </div>
            <p className="mt-2 flex-1 text-sm text-muted">{item.description}</p>
            <p className="mt-3 text-xs text-muted">Version {item.version}</p>
            <a href={item.href} className="mt-4" download>
              <Button size="sm" className="w-full">
                <Download size={14} /> Download
              </Button>
            </a>
          </Card>
        ))}
      </section>

      <section>
        <h2 className="text-xl font-semibold">SDK packages</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {sdks.map((sdk) => (
            <Card key={sdk.name} className="flex items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold">{sdk.name}</h3>
                  {sdk.soon && <Badge tone="warn">Coming soon</Badge>}
                </div>
                <p className="mt-1 font-mono text-xs text-muted">{sdk.path}</p>
              </div>
              <Link href={sdk.href}>
                <Button size="sm" variant="secondary">
                  Docs
                </Button>
              </Link>
            </Card>
          ))}
        </div>
      </section>

      <Card>
        <h2 className="font-semibold">Install from source</h2>
        <pre className="mt-3 overflow-x-auto rounded-xl bg-slate-950 p-4 text-xs text-slate-100">{`cd sdk/javascript && npm install && npm run build
cd sdk/rest && npm install && npm run build
cd sdk/widget && npm install && npm run build`}</pre>
      </Card>
    </div>
  );
}
