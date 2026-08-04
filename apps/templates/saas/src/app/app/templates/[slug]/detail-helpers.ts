/** Lightweight helpers for marketplace template detail UI (no extra deps). */

export function priceLabel(
  price: string | number | undefined,
  tier?: string,
  badge?: string | null
) {
  if (badge) return badge;
  const n = Number(price ?? 0);
  if (!(n > 0)) return tier && tier !== "free" ? String(tier) : "Free";
  return `$${n}`;
}

export function youtubeEmbedUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    if (u.hostname.includes("youtu.be")) {
      const id = u.pathname.replace("/", "");
      return id ? `https://www.youtube.com/embed/${id}` : null;
    }
    if (u.hostname.includes("youtube.com")) {
      const id = u.searchParams.get("v");
      if (id) return `https://www.youtube.com/embed/${id}`;
      const parts = u.pathname.split("/");
      const embedIdx = parts.indexOf("embed");
      if (embedIdx >= 0 && parts[embedIdx + 1]) {
        return `https://www.youtube.com/embed/${parts[embedIdx + 1]}`;
      }
    }
  } catch {
    return null;
  }
  return null;
}

/** Very small markdown → HTML (headings, lists, code, bold, links, paragraphs). */
export function renderSimpleMarkdown(source: string): string {
  const escaped = source
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  const lines = escaped.split(/\r?\n/);
  const html: string[] = [];
  let inUl = false;
  let inOl = false;
  let inCode = false;
  let codeBuf: string[] = [];

  const closeLists = () => {
    if (inUl) {
      html.push("</ul>");
      inUl = false;
    }
    if (inOl) {
      html.push("</ol>");
      inOl = false;
    }
  };

  const inline = (text: string) =>
    text
      .replace(/`([^`]+)`/g, "<code class=\"rounded bg-canvas px-1 py-0.5 text-[0.85em]\">$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(
        /\[([^\]]+)\]\((https?:[^)]+)\)/g,
        '<a class="text-brand underline" href="$2" target="_blank" rel="noreferrer">$1</a>'
      );

  for (const raw of lines) {
    const line = raw;
    if (line.startsWith("```")) {
      if (inCode) {
        html.push(
          `<pre class="overflow-x-auto rounded-xl border border-line bg-canvas p-3 text-xs"><code>${codeBuf.join("\n")}</code></pre>`
        );
        codeBuf = [];
        inCode = false;
      } else {
        closeLists();
        inCode = true;
      }
      continue;
    }
    if (inCode) {
      codeBuf.push(line);
      continue;
    }
    if (/^###\s+/.test(line)) {
      closeLists();
      html.push(`<h4 class="mt-4 text-sm font-semibold text-ink">${inline(line.replace(/^###\s+/, ""))}</h4>`);
      continue;
    }
    if (/^##\s+/.test(line)) {
      closeLists();
      html.push(`<h3 class="mt-4 text-base font-semibold text-ink">${inline(line.replace(/^##\s+/, ""))}</h3>`);
      continue;
    }
    if (/^#\s+/.test(line)) {
      closeLists();
      html.push(`<h2 class="mt-4 text-lg font-semibold text-ink">${inline(line.replace(/^#\s+/, ""))}</h2>`);
      continue;
    }
    if (/^[-*]\s+/.test(line)) {
      if (!inUl) {
        closeLists();
        html.push('<ul class="mt-2 list-disc space-y-1 pl-5 text-sm text-muted">');
        inUl = true;
      }
      html.push(`<li>${inline(line.replace(/^[-*]\s+/, ""))}</li>`);
      continue;
    }
    if (/^\d+\.\s+/.test(line)) {
      if (!inOl) {
        closeLists();
        html.push('<ol class="mt-2 list-decimal space-y-1 pl-5 text-sm text-muted">');
        inOl = true;
      }
      html.push(`<li>${inline(line.replace(/^\d+\.\s+/, ""))}</li>`);
      continue;
    }
    if (!line.trim()) {
      closeLists();
      continue;
    }
    closeLists();
    html.push(`<p class="mt-2 text-sm leading-relaxed text-muted">${inline(line)}</p>`);
  }
  closeLists();
  if (inCode) {
    html.push(
      `<pre class="overflow-x-auto rounded-xl border border-line bg-canvas p-3 text-xs"><code>${codeBuf.join("\n")}</code></pre>`
    );
  }
  return html.join("\n") || `<p class="text-sm text-muted">${escaped}</p>`;
}

export function starsLabel(rating: number | null | undefined) {
  if (rating == null) return "No ratings yet";
  return `${rating.toFixed(1)} / 5`;
}
