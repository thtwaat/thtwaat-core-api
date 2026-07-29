import { MDXRemote } from "next-mdx-remote/rsc";
import remarkGfm from "remark-gfm";
import rehypeSlug from "rehype-slug";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

function Pre({ children, ...props }: React.HTMLAttributes<HTMLPreElement>) {
  return (
    <pre
      {...props}
      className={cn(
        "my-4 overflow-x-auto rounded-xl border border-line bg-slate-950 p-4 text-sm text-slate-100 dark:bg-black",
        props.className
      )}
    >
      {children}
    </pre>
  );
}

function Code({ children, className, ...props }: React.HTMLAttributes<HTMLElement>) {
  const isBlock = className?.includes("language-");
  if (isBlock) {
    return (
      <code className={cn("font-mono text-[13px]", className)} {...props}>
        {children}
      </code>
    );
  }
  return (
    <code
      className="rounded bg-canvas px-1.5 py-0.5 font-mono text-[13px] text-brand dark:bg-slate-800"
      {...props}
    >
      {children}
    </code>
  );
}

function H2({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h2 className="mb-3 mt-10 scroll-mt-24 font-display text-2xl font-semibold text-ink" {...props}>
      {children}
    </h2>
  );
}

function H3({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3 className="mb-2 mt-8 scroll-mt-24 text-lg font-semibold text-ink" {...props}>
      {children}
    </h3>
  );
}

function A({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) {
  return (
    <a href={href} className="font-medium text-brand underline-offset-2 hover:underline" {...props}>
      {children}
    </a>
  );
}

function Callout({ children, type = "info" }: { children: ReactNode; type?: "info" | "warn" }) {
  return (
    <div
      className={cn(
        "my-4 rounded-xl border px-4 py-3 text-sm",
        type === "warn"
          ? "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-100"
          : "border-brand/30 bg-brand-soft text-ink dark:border-teal-800 dark:bg-teal-950"
      )}
    >
      {children}
    </div>
  );
}

const components = {
  pre: Pre,
  code: Code,
  h2: H2,
  h3: H3,
  a: A,
  Callout,
  p: ({ children }: { children?: ReactNode }) => <p className="my-3 leading-7 text-muted">{children}</p>,
  ul: ({ children }: { children?: ReactNode }) => <ul className="my-3 list-disc space-y-1 pl-5 text-muted">{children}</ul>,
  ol: ({ children }: { children?: ReactNode }) => <ol className="my-3 list-decimal space-y-1 pl-5 text-muted">{children}</ol>,
  li: ({ children }: { children?: ReactNode }) => <li className="leading-7">{children}</li>,
  table: ({ children }: { children?: ReactNode }) => (
    <div className="my-4 overflow-x-auto">
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  th: ({ children }: { children?: ReactNode }) => (
    <th className="border border-line bg-canvas px-3 py-2 text-left font-semibold text-ink">{children}</th>
  ),
  td: ({ children }: { children?: ReactNode }) => (
    <td className="border border-line px-3 py-2 text-muted">{children}</td>
  )
};

export async function Mdx({ source }: { source: string }) {
  return (
    <article className="prose-docs max-w-none">
      <MDXRemote
        source={source}
        components={components}
        options={{
          mdxOptions: {
            remarkPlugins: [remarkGfm],
            rehypePlugins: [rehypeSlug]
          }
        }}
      />
    </article>
  );
}
