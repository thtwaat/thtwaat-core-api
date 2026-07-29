"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function CodeBlock({
  code,
  language = "bash",
  className
}: {
  code: string;
  language?: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className={cn("relative overflow-hidden rounded-xl border border-line bg-slate-950", className)}>
      <div className="flex items-center justify-between border-b border-white/10 px-3 py-2 text-xs text-slate-400">
        <span>{language}</span>
        <Button size="sm" variant="ghost" className="h-7 text-slate-300 hover:text-white" onClick={copy}>
          {copied ? <Check size={14} /> : <Copy size={14} />}
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <pre className="overflow-x-auto p-4 text-[13px] leading-relaxed text-slate-100">
        <code>{code}</code>
      </pre>
    </div>
  );
}

export function SnippetTabs({ snippets }: { snippets: Record<string, string> }) {
  const tabs = Object.keys(snippets);
  const [tab, setTab] = useState(tabs[0] || "curl");
  return (
    <div>
      <div className="mb-2 flex flex-wrap gap-1">
        {tabs.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "rounded-lg px-3 py-1.5 text-xs font-semibold capitalize",
              tab === t ? "bg-brand text-white" : "bg-canvas text-muted hover:text-ink"
            )}
          >
            {t}
          </button>
        ))}
      </div>
      <CodeBlock code={snippets[tab] || ""} language={tab} />
    </div>
  );
}
