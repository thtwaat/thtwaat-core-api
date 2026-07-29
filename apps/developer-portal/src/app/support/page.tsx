import Link from "next/link";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { site } from "@/lib/config";

export const metadata = {
  title: "Support",
  description: "Get help with THTWAAT API integrations."
};

export default function SupportPage() {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ label: "Support" }]} />
      <div>
        <h1 className="font-display text-3xl font-semibold">Support</h1>
        <p className="mt-2 max-w-2xl text-muted">
          Production integrations, SDK questions, and platform incidents — start with docs, then reach the team.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <h2 className="font-semibold">Documentation</h2>
          <p className="mt-2 text-sm text-muted">Quick start, auth, SDKs, errors, and rate limits.</p>
          <Link href="/docs/quick-start" className="mt-4 inline-block">
            <Button size="sm">Browse docs</Button>
          </Link>
        </Card>
        <Card>
          <h2 className="font-semibold">API Explorer</h2>
          <p className="mt-2 text-sm text-muted">Validate payloads and copy language samples before opening a ticket.</p>
          <Link href="/api-explorer" className="mt-4 inline-block">
            <Button size="sm" variant="secondary">
              Open explorer
            </Button>
          </Link>
        </Card>
        <Card>
          <h2 className="font-semibold">Contact</h2>
          <p className="mt-2 text-sm text-muted">Email developers@thtwaat.com with your company slug and request ID.</p>
          <a href="mailto:developers@thtwaat.com" className="mt-4 inline-block">
            <Button size="sm" variant="secondary">
              Email support
            </Button>
          </a>
        </Card>
      </div>

      <Card>
        <h2 className="font-semibold">Include in every ticket</h2>
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-muted">
          <li>Environment (local / staging / production)</li>
          <li>API base URL: {site.apiUrl}</li>
          <li>Endpoint path + HTTP status</li>
          <li>SDK package + version (if applicable)</li>
          <li>Redacted request/response samples (no live secrets)</li>
        </ul>
      </Card>
    </div>
  );
}
