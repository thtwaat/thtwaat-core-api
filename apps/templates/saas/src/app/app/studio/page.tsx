"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import {
  ArrowRight,
  Eraser,
  LayoutTemplate,
  Lightbulb,
  Loader2,
  Sparkles,
  Trash2
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { canDeleteStudioProjects } from "@/lib/permissions";
import { studioApi } from "@/lib/services";
import {
  STUDIO_PROMPT_PLACEHOLDER,
  STUDIO_TIPS,
  studioStatusLabel,
  studioStatusTone,
  type StudioProject
} from "@/lib/studio";
import { Button, buttonVariants } from "@/components/ui/button";
import { Badge, Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/misc";
import { cn } from "@/lib/utils";

function formatWhen(iso: string) {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function StudioPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [prompt, setPrompt] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const canDelete = canDeleteStudioProjects(user?.role);

  const listQ = useQuery({
    queryKey: ["studio-projects"],
    queryFn: () => studioApi.list()
  });

  const createM = useMutation({
    mutationFn: () => studioApi.create({ prompt }),
    onSuccess: (project) => {
      toast.success("Prompt saved — blueprint generation comes in Phase 2");
      setSelectedId(project.id);
      setPrompt("");
      void qc.invalidateQueries({ queryKey: ["studio-projects"] });
    },
    onError: (err) => {
      toast.error(err instanceof ApiError ? err.message : "Could not save prompt");
    }
  });

  const deleteM = useMutation({
    mutationFn: (id: string) => studioApi.remove(id),
    onSuccess: (_, id) => {
      toast.success("Project deleted");
      if (selectedId === id) setSelectedId(null);
      void qc.invalidateQueries({ queryKey: ["studio-projects"] });
    },
    onError: (err) => {
      toast.error(err instanceof ApiError ? err.message : "Delete failed");
    }
  });

  const items = listQ.data?.items || [];
  const selected = items.find((p) => p.id === selectedId) || items[0] || null;

  function onGenerate() {
    if (prompt.trim().length < 8) {
      toast.message("Describe your product in at least a short sentence");
      return;
    }
    createM.mutate();
  }

  return (
    <div className="-mx-4 -mt-4 min-h-[calc(100vh-4rem)] bg-slate-950 px-4 py-6 text-slate-100 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-3xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-950 to-teal-950 p-6 sm:p-10">
        <div className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-teal-500/20 blur-3xl" />
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-300/80">
          THTWAAT Studio
        </p>
        <h1 className="mt-2 max-w-2xl text-3xl font-semibold tracking-tight text-white sm:text-4xl">
          Describe your product. We&apos;ll blueprint it next.
        </h1>
        <p className="mt-3 max-w-xl text-sm text-slate-300 sm:text-base">
          Phase 1 saves every prompt into your workspace. Code generation, deploy, and marketplace
          publish arrive in later phases — reusing Agents, Knowledge, Billing, and Marketplace.
        </p>
      </section>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        {/* Prompt editor */}
        <section className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5 sm:p-6">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-white">Prompt Editor</h2>
              <p className="text-sm text-slate-400">Describe industry, modules, AI, and website needs.</p>
            </div>
            <Badge tone="neutral">Save only</Badge>
          </div>
          <label className="sr-only" htmlFor="studio-prompt">
            Describe your product
          </label>
          <textarea
            id="studio-prompt"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={STUDIO_PROMPT_PLACEHOLDER}
            rows={10}
            className="w-full resize-y rounded-2xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/30"
          />
          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              onClick={onGenerate}
              disabled={createM.isPending}
              className="bg-teal-600 text-white hover:bg-teal-500"
            >
              {createM.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving…
                </>
              ) : (
                <>
                  <Sparkles className="mr-2 h-4 w-4" />
                  Generate Blueprint
                </>
              )}
            </Button>
            <Button variant="secondary" onClick={() => setPrompt("")} disabled={!prompt || createM.isPending}>
              <Eraser className="mr-2 h-4 w-4" />
              Clear
            </Button>
            <Link
              href="/app/templates"
              className={cn(buttonVariants({ variant: "secondary" }), "inline-flex")}
            >
              <LayoutTemplate className="mr-2 h-4 w-4" />
              Templates
            </Link>
          </div>
          <p className="mt-3 text-xs text-slate-500">
            Generate Blueprint saves your prompt as a draft. Architect / codegen is Phase 2+.
          </p>
        </section>

        <div className="space-y-6">
          {/* AI tips */}
          <section className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5">
            <div className="mb-3 flex items-center gap-2">
              <Lightbulb className="h-4 w-4 text-amber-300" />
              <h2 className="text-sm font-semibold text-white">AI Tips</h2>
            </div>
            <ul className="space-y-2 text-sm text-slate-300">
              {STUDIO_TIPS.map((tip) => (
                <li key={tip} className="flex gap-2">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-400" />
                  <span>{tip}</span>
                </li>
              ))}
            </ul>
          </section>

          {/* Templates coming soon */}
          <section className="rounded-3xl border border-dashed border-slate-700 bg-slate-900/40 p-5">
            <h2 className="text-sm font-semibold text-white">Templates</h2>
            <p className="mt-1 text-sm text-slate-400">
              Auto template selection lands in Phase 3. Browse the Marketplace meanwhile.
            </p>
            <Link
              href="/app/templates"
              className={cn(buttonVariants({ variant: "secondary" }), "mt-3 inline-flex")}
            >
              Open Marketplace
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </section>
        </div>
      </div>

      {/* History + recent */}
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <section className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5 sm:p-6">
          <div className="mb-4">
            <h2 className="text-base font-semibold text-white">Generation History</h2>
            <p className="mt-1 text-sm text-slate-400">Every saved prompt in this workspace</p>
          </div>
          {listQ.isLoading ? (
            <div className="flex items-center gap-2 py-10 text-sm text-slate-400">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading projects…
            </div>
          ) : listQ.isError ? (
            <EmptyState
              title="Could not load history"
              description={(listQ.error as Error)?.message}
            />
          ) : items.length === 0 ? (
            <EmptyState
              title="No projects yet"
              description="Write a product description and click Generate Blueprint to save it."
            />
          ) : (
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[28rem] text-left text-sm">
                <thead className="text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="pb-2 font-medium">Project</th>
                    <th className="pb-2 font-medium">Created</th>
                    <th className="pb-2 font-medium">Status</th>
                    <th className="pb-2 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {items.map((p) => (
                    <HistoryRow
                      key={p.id}
                      project={p}
                      active={selected?.id === p.id}
                      canDelete={canDelete}
                      deleting={deleteM.isPending && deleteM.variables === p.id}
                      onOpen={() => setSelectedId(p.id)}
                      onDelete={() => {
                        if (confirm(`Delete “${p.title}”?`)) deleteM.mutate(p.id);
                      }}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5 sm:p-6">
          <div className="mb-4">
            <h2 className="text-base font-semibold text-white">Recent Projects</h2>
            <p className="mt-1 text-sm text-slate-400">Open a draft to review the prompt</p>
          </div>
          {!selected ? (
            <EmptyState title="Nothing selected" description="Save a prompt to see it here." />
          ) : (
            <Card className="mt-3 border-slate-700 bg-slate-950/80">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <h3 className="font-semibold text-white">{selected.title}</h3>
                  <p className="mt-1 text-xs text-slate-500">{formatWhen(selected.created_at)}</p>
                </div>
                <Badge tone={studioStatusTone(selected.status)}>
                  {studioStatusLabel(selected.status)}
                </Badge>
              </div>
              <pre className="mt-4 whitespace-pre-wrap rounded-xl border border-slate-800 bg-slate-900 p-3 text-xs text-slate-300">
                {selected.prompt}
              </pre>
            </Card>
          )}
        </section>
      </div>
    </div>
  );
}

function HistoryRow({
  project,
  active,
  canDelete,
  deleting,
  onOpen,
  onDelete
}: {
  project: StudioProject;
  active: boolean;
  canDelete: boolean;
  deleting: boolean;
  onOpen: () => void;
  onDelete: () => void;
}) {
  return (
    <tr className={active ? "bg-slate-800/40" : undefined}>
      <td className="py-3 pr-3 font-medium text-slate-100">{project.title}</td>
      <td className="py-3 pr-3 text-slate-400">{formatWhen(project.created_at)}</td>
      <td className="py-3 pr-3">
        <Badge tone={studioStatusTone(project.status)}>{studioStatusLabel(project.status)}</Badge>
      </td>
      <td className="py-3">
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" className="h-8 px-2 text-xs" onClick={onOpen}>
            Open
          </Button>
          {canDelete && (
            <Button
              variant="secondary"
              className="h-8 px-2 text-xs text-red-300"
              disabled={deleting}
              onClick={onDelete}
            >
              {deleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
            </Button>
          )}
        </div>
      </td>
    </tr>
  );
}
