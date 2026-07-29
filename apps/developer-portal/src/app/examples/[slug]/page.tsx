import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { Mdx } from "@/components/mdx";
import { getExample, listExamples } from "@/lib/docs";

export function generateStaticParams() {
  return listExamples().map((d) => ({ slug: d.slug }));
}

export async function generateMetadata({
  params
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const doc = getExample(slug);
  if (!doc) return { title: "Example not found" };
  return { title: doc.title, description: doc.description };
}

export default async function ExamplePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const doc = getExample(slug);
  if (!doc) notFound();
  return (
    <div>
      <Breadcrumbs items={[{ label: "Examples", href: "/examples" }, { label: doc.title }]} />
      <header className="mb-8 border-b border-line pb-6">
        <h1 className="font-display text-3xl font-semibold">{doc.title}</h1>
        {doc.description && <p className="mt-2 text-muted">{doc.description}</p>}
      </header>
      <Mdx source={doc.content} />
    </div>
  );
}
