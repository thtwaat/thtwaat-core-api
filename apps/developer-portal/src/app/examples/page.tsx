import Link from "next/link";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { Badge, Card } from "@/components/ui/card";
import { examplePages } from "@/lib/config";
import { listExamples } from "@/lib/docs";

export default function ExamplesIndexPage() {
  const written = new Set(listExamples().map((e) => e.slug));
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ label: "Examples" }]} />
      <div>
        <h1 className="font-display text-3xl font-semibold">Examples</h1>
        <p className="mt-2 text-muted">Copy-paste integrations for websites, SaaS apps, and backend services.</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {examplePages.map((ex) => (
          <Link key={ex.slug} href={`/examples/${ex.slug}`}>
            <Card className="h-full transition hover:border-brand/40">
              <div className="flex items-center justify-between gap-2">
                <h2 className="font-semibold">{ex.title}</h2>
                {written.has(ex.slug) ? <Badge tone="success">Ready</Badge> : <Badge tone="warn">Draft</Badge>}
              </div>
              <p className="mt-2 text-sm text-muted">{ex.stack}</p>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
