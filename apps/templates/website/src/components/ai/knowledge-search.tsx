"use client";

import { useState } from "react";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

type Result = { text?: string; document_name?: string; score?: number };

export function KnowledgeSearch() {
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<Result[]>([]);

  async function onSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/knowledge?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      setResults(data.results || []);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card className="space-y-4">
      <div>
        <h3 className="font-display text-lg">Knowledge Search</h3>
        <p className="text-sm text-ink-muted">Semantic search across your THTWAAT knowledge base.</p>
      </div>
      <form onSubmit={onSearch} className="flex gap-2">
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search docs…" />
        <Button type="submit" disabled={loading}>
          <Search className="h-4 w-4" />
        </Button>
      </form>
      <div className="space-y-3">
        {results.length === 0 && !loading && (
          <p className="text-sm text-ink-muted">No results yet — upload docs in the THTWAAT platform.</p>
        )}
        {results.map((r, i) => (
          <div key={i} className="rounded-xl border border-black/5 bg-surface p-3 text-sm">
            {r.document_name && (
              <p className="mb-1 text-xs font-medium text-brand">{r.document_name}</p>
            )}
            <p className="text-ink-muted">{r.text}</p>
          </div>
        ))}
      </div>
    </Card>
  );
}
