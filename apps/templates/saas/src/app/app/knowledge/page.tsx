"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { knowledgeApi } from "@/lib/services";
import { formatDate } from "@/lib/utils";
import { PageHeader, EmptyState } from "@/components/ui/misc";
import { Card, CardHeader, Badge } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";

export default function KnowledgePage() {
  const qc = useQueryClient();
  const bases = useQuery({ queryKey: ["knowledge-bases"], queryFn: knowledgeApi.listBases });
  const [selected, setSelected] = useState<string>("");
  const [name, setName] = useState("");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Array<{ text: string; document_name?: string; score?: number }>>([]);

  const baseId = selected || bases.data?.[0]?.id || "";

  const docs = useQuery({
    queryKey: ["knowledge-docs", baseId],
    queryFn: () => knowledgeApi.listDocuments(baseId),
    enabled: Boolean(baseId)
  });

  const createBase = useMutation({
    mutationFn: () => knowledgeApi.createBase({ name }),
    onSuccess: () => {
      toast.success("Knowledge base created");
      setName("");
      qc.invalidateQueries({ queryKey: ["knowledge-bases"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const removeDoc = useMutation({
    mutationFn: (docId: string) => knowledgeApi.deleteDocument(baseId, docId),
    onSuccess: () => {
      toast.success("Document deleted");
      qc.invalidateQueries({ queryKey: ["knowledge-docs", baseId] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  async function onUpload(file?: File | null) {
    if (!file || !baseId) return;
    try {
      await knowledgeApi.upload(baseId, file);
      toast.success("Upload started");
      qc.invalidateQueries({ queryKey: ["knowledge-docs", baseId] });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Upload failed");
    }
  }

  async function onSearch() {
    if (!baseId || !query.trim()) return;
    try {
      const data = await knowledgeApi.search(baseId, query);
      setResults(data.results || []);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Search failed");
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Knowledge" description="Upload, search, delete, and review document history." />

      <div className="grid gap-6 lg:grid-cols-3">
        <Card>
          <CardHeader title="Bases" />
          <div className="mb-4 flex gap-2">
            <Input placeholder="New base name" value={name} onChange={(e) => setName(e.target.value)} />
            <Button onClick={() => createBase.mutate()} disabled={!name}>Add</Button>
          </div>
          <div className="space-y-2">
            {(bases.data || []).map((b) => (
              <button
                key={b.id}
                onClick={() => setSelected(b.id)}
                className={`w-full rounded-xl border px-3 py-2 text-left text-sm ${
                  baseId === b.id ? "border-brand bg-brand-soft" : "border-line"
                }`}
              >
                <p className="font-medium">{b.name}</p>
                <p className="text-xs text-muted">{b.document_count ?? 0} documents</p>
              </button>
            ))}
            {!bases.data?.length && <EmptyState title="No knowledge bases" />}
          </div>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Documents" description="History for the selected base" />
          <div className="mb-4">
            <Label>Upload file</Label>
            <Input type="file" onChange={(e) => void onUpload(e.target.files?.[0])} disabled={!baseId} />
          </div>
          <div className="space-y-2">
            {(docs.data || []).map((doc) => (
              <div key={doc.id} className="flex items-center justify-between rounded-xl border border-line px-3 py-2.5">
                <div>
                  <p className="text-sm font-medium">{doc.name}</p>
                  <p className="text-xs text-muted">{formatDate(doc.created_at)}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge>{doc.status || "ready"}</Badge>
                  <Button size="sm" variant="danger" onClick={() => removeDoc.mutate(doc.id)}>
                    Delete
                  </Button>
                </div>
              </div>
            ))}
            {!docs.data?.length && <EmptyState title="No documents" description="Upload a PDF, DOCX, or TXT file." />}
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader title="Search" description="Query the selected knowledge base" />
        <div className="flex gap-2">
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ask about your docs…" />
          <Button onClick={onSearch}>Search</Button>
        </div>
        <div className="mt-4 space-y-2">
          {results.map((r, i) => (
            <div key={i} className="rounded-xl border border-line p-3 text-sm">
              {r.document_name && <p className="mb-1 text-xs font-semibold text-brand">{r.document_name}</p>}
              <p className="text-muted">{r.text}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
