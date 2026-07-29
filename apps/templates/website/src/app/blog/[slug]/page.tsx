import { notFound } from "next/navigation";
import ReactMarkdown from "react-markdown";
import { getAllPosts, getPost } from "@/lib/blog";
import { buildMetadata } from "@/lib/seo";
import { Badge } from "@/components/ui/card";

export async function generateStaticParams() {
  return getAllPosts().map((p) => ({ slug: p.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const post = getPost(slug);
  if (!post) return {};
  return buildMetadata({
    title: post.title,
    description: post.description,
    path: `/blog/${post.slug}`,
  });
}

export default async function BlogPostPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const post = getPost(slug);
  if (!post) notFound();

  return (
    <article className="container-page section prose prose-slate mx-auto max-w-3xl dark:prose-invert">
      <Badge>{post.category}</Badge>
      <h1>{post.title}</h1>
      <p className="text-sm text-ink-muted">
        {new Date(post.date).toLocaleDateString()} · {post.author}
      </p>
      <ReactMarkdown>{post.content}</ReactMarkdown>
    </article>
  );
}
