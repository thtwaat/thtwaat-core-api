import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { Mdx } from "@/components/mdx";
import { getDoc, listDocs } from "@/lib/docs";

export function generateStaticParams() {
  return listDocs().map((d) => ({ slug: d.slug }));
}

export async function generateMetadata({
  params
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const doc = getDoc(slug);
  if (!doc) return { title: "Not found" };
  return { title: doc.title, description: doc.description };
}

export default async function DocPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const doc = getDoc(slug);
  if (!doc) notFound();

  return (
    <div>
      <Breadcrumbs items={[{ label: "Docs", href: "/docs/quick-start" }, { label: doc.title }]} />
      <header className="mb-8 border-b border-line pb-6">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">{doc.section || "Docs"}</p>
        <h1 className="mt-2 font-display text-3xl font-semibold text-ink">{doc.title}</h1>
        {doc.description && <p className="mt-2 max-w-2xl text-muted">{doc.description}</p>}
      </header>
      <Mdx source={doc.content} />
    </div>
  );
}
