import Link from "next/link";
import { getAllPosts, getCategories, searchPosts } from "@/lib/blog";
import { Card, Badge } from "@/components/ui/card";
import { buildMetadata } from "@/lib/seo";

export const metadata = buildMetadata({
  title: "Blog",
  description: "Insights from the THTWAAT AI Website Starter.",
  path: "/blog",
});

export default async function BlogPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; category?: string }>;
}) {
  const sp = await searchParams;
  let posts = sp.q ? searchPosts(sp.q) : getAllPosts();
  if (sp.category) posts = posts.filter((p) => p.category === sp.category);
  const categories = getCategories();

  return (
    <section className="container-page section space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-display text-4xl">Blog</h1>
          <p className="text-ink-muted">Markdown CMS — drop files in `src/content/blog`.</p>
        </div>
        <form className="flex gap-2">
          <input
            name="q"
            defaultValue={sp.q}
            placeholder="Search posts"
            className="h-10 rounded-xl border border-black/10 bg-surface-elevated px-3 text-sm"
          />
          <button className="rounded-xl bg-brand px-4 text-sm text-brand-foreground">Search</button>
        </form>
      </div>

      <div className="flex flex-wrap gap-2">
        <Link href="/blog" className="text-sm text-brand underline">
          All
        </Link>
        {categories.map((c) => (
          <Link key={c} href={`/blog?category=${encodeURIComponent(c)}`}>
            <Badge>{c}</Badge>
          </Link>
        ))}
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {posts.map((p) => (
          <Link key={p.slug} href={`/blog/${p.slug}`}>
            <Card className="h-full transition hover:-translate-y-0.5">
              <Badge>{p.category}</Badge>
              <h2 className="mt-3 font-display text-2xl">{p.title}</h2>
              <p className="mt-2 text-sm text-ink-muted">{p.description}</p>
              <p className="mt-4 text-xs text-ink-muted">
                {new Date(p.date).toLocaleDateString()} · {p.author}
              </p>
            </Card>
          </Link>
        ))}
      </div>
    </section>
  );
}
