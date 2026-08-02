import fs from "fs";
import path from "path";
import matter from "gray-matter";

const DOCS_DIR = path.join(process.cwd(), "content", "docs");
const EXAMPLES_DIR = path.join(process.cwd(), "content", "examples");

export type DocMeta = {
  slug: string;
  title: string;
  description: string;
  order?: number;
  section?: string;
};

export type DocContent = DocMeta & {
  content: string;
};

function readMdxDir(dir: string): DocMeta[] {
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir)
    .filter((f) => f.endsWith(".mdx") || f.endsWith(".md"))
    .map((file) => {
      const raw = fs.readFileSync(path.join(dir, file), "utf8");
      const { data } = matter(raw);
      const slug = file.replace(/\.mdx?$/, "");
      return {
        slug,
        title: (data.title as string) || slug,
        description: (data.description as string) || "",
        order: (data.order as number) || 99,
        section: (data.section as string) || "Docs"
      };
    })
    .sort((a, b) => (a.order || 99) - (b.order || 99));
}

export function listDocs(): DocMeta[] {
  return readMdxDir(DOCS_DIR);
}

export function getDoc(slug: string): DocContent | null {
  for (const ext of [".mdx", ".md"]) {
    const file = path.join(DOCS_DIR, `${slug}${ext}`);
    if (!fs.existsSync(file)) continue;
    const raw = fs.readFileSync(file, "utf8");
    const { data, content } = matter(raw);
    return {
      slug,
      title: (data.title as string) || slug,
      description: (data.description as string) || "",
      order: data.order as number | undefined,
      section: data.section as string | undefined,
      content
    };
  }
  return null;
}

export function listExamples(): DocMeta[] {
  return readMdxDir(EXAMPLES_DIR);
}

export function getExample(slug: string): DocContent | null {
  for (const ext of [".mdx", ".md"]) {
    const file = path.join(EXAMPLES_DIR, `${slug}${ext}`);
    if (!fs.existsSync(file)) continue;
    const raw = fs.readFileSync(file, "utf8");
    const { data, content } = matter(raw);
    return {
      slug,
      title: (data.title as string) || slug,
      description: (data.description as string) || "",
      content
    };
  }
  return null;
}

export type SearchHit = {
  slug: string;
  title: string;
  description: string;
  href: string;
  kind: "doc" | "example";
  excerpt: string;
};

export function buildSearchIndex(): SearchHit[] {
  const docs = listDocs().map((d) => {
    const full = getDoc(d.slug)!;
    return {
      slug: d.slug,
      title: d.title,
      description: d.description,
      href: `/docs/${d.slug}`,
      kind: "doc" as const,
      excerpt: full.content.slice(0, 280).replace(/[#*`>\-\[\]()]/g, " ")
    };
  });
  const examples = listExamples().map((d) => {
    const full = getExample(d.slug)!;
    return {
      slug: d.slug,
      title: d.title,
      description: d.description,
      href: `/examples/${d.slug}`,
      kind: "example" as const,
      excerpt: full.content.slice(0, 280).replace(/[#*`>\-\[\]()]/g, " ")
    };
  });
  return [...docs, ...examples];
}

export function searchDocs(query: string): SearchHit[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const terms = q.split(/\s+/).filter(Boolean);
  return buildSearchIndex()
    .map((hit) => {
      const hay = `${hit.title} ${hit.description} ${hit.excerpt}`.toLowerCase();
      const score = terms.reduce((acc, t) => acc + (hay.includes(t) ? 1 : 0), 0);
      return { hit, score };
    })
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .map((x) => x.hit);
}
