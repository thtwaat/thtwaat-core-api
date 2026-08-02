import fs from "fs";
import path from "path";
import matter from "gray-matter";

export type BlogPost = {
  slug: string;
  title: string;
  description: string;
  date: string;
  category: string;
  tags: string[];
  author: string;
  content: string;
};

const BLOG_DIR = path.join(process.cwd(), "src/content/blog");

export function getAllPosts(): BlogPost[] {
  if (!fs.existsSync(BLOG_DIR)) return [];
  return fs
    .readdirSync(BLOG_DIR)
    .filter((f) => f.endsWith(".md"))
    .map((file) => {
      const slug = file.replace(/\.md$/, "");
      const raw = fs.readFileSync(path.join(BLOG_DIR, file), "utf8");
      const { data, content } = matter(raw);
      return {
        slug,
        title: String(data.title || slug),
        description: String(data.description || ""),
        date: String(data.date || new Date().toISOString()),
        category: String(data.category || "General"),
        tags: Array.isArray(data.tags) ? data.tags.map(String) : [],
        author: String(data.author || "THTWAAT"),
        content,
      };
    })
    .sort((a, b) => +new Date(b.date) - +new Date(a.date));
}

export function getPost(slug: string): BlogPost | null {
  return getAllPosts().find((p) => p.slug === slug) || null;
}

export function getCategories(): string[] {
  return [...new Set(getAllPosts().map((p) => p.category))];
}

export function searchPosts(q: string): BlogPost[] {
  const query = q.trim().toLowerCase();
  if (!query) return getAllPosts();
  return getAllPosts().filter(
    (p) =>
      p.title.toLowerCase().includes(query) ||
      p.description.toLowerCase().includes(query) ||
      p.content.toLowerCase().includes(query) ||
      p.tags.some((t) => t.toLowerCase().includes(query))
  );
}
