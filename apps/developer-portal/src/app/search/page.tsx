import Link from "next/link";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { Badge, Card } from "@/components/ui/card";
import { searchDocs } from "@/lib/docs";

export default async function SearchPage({
  searchParams
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q = "" } = await searchParams;
  const hits = q ? searchDocs(q) : [];

  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ label: "Search" }]} />
      <div>
        <h1 className="font-display text-3xl font-semibold">Search</h1>
        <p className="mt-2 text-muted">
          {q ? (
            <>
              Results for <span className="font-semibold text-ink">“{q}”</span>
            </>
          ) : (
            "Use the header search box or add ?q= to this URL."
          )}
        </p>
      </div>

      {!q && (
        <Card className="text-sm text-muted">
          Try queries like <code>webhook</code>, <code>api key</code>, or <code>widget</code>.
        </Card>
      )}

      {q && !hits.length && (
        <Card>
          <p className="font-semibold">No results</p>
          <p className="mt-1 text-sm text-muted">Try a different keyword or browse the docs sidebar.</p>
          <Link href="/docs/quick-start" className="mt-3 inline-block text-sm font-semibold text-brand">
            Go to Quick Start →
          </Link>
        </Card>
      )}

      <div className="space-y-3">
        {hits.map((hit) => (
          <Link key={`${hit.kind}:${hit.slug}`} href={hit.href}>
            <Card className="transition hover:border-brand/40">
              <div className="flex items-center gap-2">
                <Badge tone={hit.kind === "doc" ? "brand" : "success"}>{hit.kind}</Badge>
                <h2 className="font-semibold">{hit.title}</h2>
              </div>
              <p className="mt-2 text-sm text-muted">{hit.description || hit.excerpt}</p>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
