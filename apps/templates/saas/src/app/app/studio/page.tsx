"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { toast } from "sonner";
import {
  ArrowRight,
  Boxes,
  Eraser,
  History,
  LayoutTemplate,
  Lightbulb,
  Loader2,
  RotateCcw,
  Save,
  Sparkles,
  Trash2
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { canDeleteStudioProjects } from "@/lib/permissions";
import { studioApi } from "@/lib/services";
import {
  EMPTY_BLUEPRINT,
  STUDIO_PROMPT_PLACEHOLDER,
  STUDIO_TIPS,
  listFieldToText,
  moduleKindLabel,
  moduleKindTone,
  parseListField,
  studioStatusLabel,
  studioStatusTone,
  warningTone,
  type ProductBlueprint,
  type StudioBlueprint,
  type StudioBuildPlan
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

function ListEditor({
  label,
  value,
  onChange
}: {
  label: string;
  value: string[];
  onChange: (next: string[]) => void;
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</span>
      <textarea
        value={listFieldToText(value)}
        onChange={(e) => onChange(parseListField(e.target.value))}
        rows={4}
        className="w-full resize-y rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/30"
        placeholder="One item per line"
      />
    </label>
  );
}

export default function StudioPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [prompt, setPrompt] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<ProductBlueprint>(EMPTY_BLUEPRINT);
  const canDelete = canDeleteStudioProjects(user?.role);

  const listQ = useQuery({
    queryKey: ["studio-projects"],
    queryFn: () => studioApi.list()
  });

  const items = listQ.data?.items || [];
  const selected = useMemo(() => {
    if (!items.length) return null;
    return items.find((p) => p.id === selectedId) || items[0];
  }, [items, selectedId]);

  const blueprintQ = useQuery({
    queryKey: ["studio-blueprint", selected?.id],
    queryFn: () => studioApi.getBlueprint(selected!.id),
    enabled: Boolean(selected?.id),
    retry: false
  });

  const versionsQ = useQuery({
    queryKey: ["studio-versions", selected?.id],
    queryFn: () => studioApi.versions(selected!.id),
    enabled: Boolean(selected?.id)
  });

  const buildPlanQ = useQuery({
    queryKey: ["studio-build-plan", selected?.id],
    queryFn: () => studioApi.getBuildPlan(selected!.id),
    enabled: Boolean(selected?.id),
    retry: false
  });

  useEffect(() => {
    if (blueprintQ.data?.blueprint) {
      setDraft(blueprintQ.data.blueprint);
    } else if (blueprintQ.isError) {
      setDraft(EMPTY_BLUEPRINT);
    }
  }, [blueprintQ.data, blueprintQ.isError, selected?.id]);

  const createM = useMutation({
    mutationFn: () => studioApi.create({ prompt }),
    onSuccess: (project) => {
      toast.success("Prompt saved");
      setSelectedId(project.id);
      setPrompt(project.prompt);
      void qc.invalidateQueries({ queryKey: ["studio-projects"] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Could not save prompt")
  });

  const analyzeM = useMutation({
    mutationFn: async () => {
      let projectId = selected?.id;
      const text = prompt.trim() || selected?.prompt || "";
      if (text.length < 8) throw new Error("Describe your product first");
      if (!projectId || (prompt.trim() && prompt.trim() !== selected?.prompt)) {
        const created = await studioApi.create({ prompt: text });
        projectId = created.id;
        setSelectedId(created.id);
      }
      return studioApi.analyze(projectId, true);
    },
    onSuccess: (result) => {
      toast.success(`Blueprint v${result.blueprint.version} ready (${result.blueprint.source})`);
      setDraft(result.blueprint.blueprint);
      setPrompt(result.project.prompt);
      void qc.invalidateQueries({ queryKey: ["studio-projects"] });
      void qc.invalidateQueries({ queryKey: ["studio-blueprint", result.project.id] });
      void qc.invalidateQueries({ queryKey: ["studio-versions", result.project.id] });
    },
    onError: (err) =>
      toast.error(err instanceof ApiError || err instanceof Error ? err.message : "Analyze failed")
  });

  const saveM = useMutation({
    mutationFn: () => {
      if (!selected?.id) throw new Error("Select a project first");
      return studioApi.saveBlueprint(selected.id, draft);
    },
    onSuccess: (bp) => {
      toast.success(`Saved as version v${bp.version}`);
      setDraft(bp.blueprint);
      void qc.invalidateQueries({ queryKey: ["studio-blueprint", selected?.id] });
      void qc.invalidateQueries({ queryKey: ["studio-versions", selected?.id] });
      void qc.invalidateQueries({ queryKey: ["studio-projects"] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Save failed")
  });

  const restoreM = useMutation({
    mutationFn: (version: number) => {
      if (!selected?.id) throw new Error("No project");
      return studioApi.restore(selected.id, version);
    },
    onSuccess: (bp) => {
      toast.success(`Restored v${bp.version - 1} → new v${bp.version}`);
      setDraft(bp.blueprint);
      void qc.invalidateQueries({ queryKey: ["studio-blueprint", selected?.id] });
      void qc.invalidateQueries({ queryKey: ["studio-versions", selected?.id] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Restore failed")
  });

  const composeM = useMutation({
    mutationFn: () => {
      if (!selected?.id) throw new Error("Select a project first");
      return studioApi.compose(selected.id);
    },
    onSuccess: (result) => {
      toast.success(
        `Build plan v${result.build_plan.version} · ${result.build_plan.summary.reuse_percent}% reuse`
      );
      void qc.invalidateQueries({ queryKey: ["studio-projects"] });
      void qc.invalidateQueries({ queryKey: ["studio-build-plan", result.project.id] });
    },
    onError: (err) =>
      toast.error(err instanceof ApiError || err instanceof Error ? err.message : "Compose failed")
  });

  const deleteM = useMutation({
    mutationFn: (id: string) => studioApi.remove(id),
    onSuccess: (_, id) => {
      toast.success("Project deleted");
      if (selectedId === id) setSelectedId(null);
      void qc.invalidateQueries({ queryKey: ["studio-projects"] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Delete failed")
  });

  const currentBlueprint: StudioBlueprint | undefined = blueprintQ.data;
  const buildPlan: StudioBuildPlan | undefined = buildPlanQ.data;
  const warnings = currentBlueprint?.warnings || [];
  const recommendations = currentBlueprint?.recommendations;
  const composeWarnings = buildPlan?.summary?.warnings || [];

  function patchDraft(partial: Partial<ProductBlueprint>) {
    setDraft((prev) => ({ ...prev, ...partial }));
  }

  return (
    <div className="-mx-4 -mt-4 min-h-[calc(100vh-4rem)] bg-slate-950 px-4 py-6 text-slate-100 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
      <section className="relative overflow-hidden rounded-3xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-950 to-teal-950 p-6 sm:p-8">
        <div className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-teal-500/20 blur-3xl" />
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-300/80">
          THTWAAT Studio · Phase 3
        </p>
        <h1 className="mt-2 max-w-3xl text-3xl font-semibold tracking-tight text-white sm:text-4xl">
          Template Registry & Module Composer
        </h1>
        <p className="mt-3 max-w-2xl text-sm text-slate-300">
          Map an approved blueprint onto existing Auth, Billing, AI Gateway, Marketplace, Knowledge,
          Agents, Publisher, and Admin — no frontend/backend codegen, no deploy.
        </p>
      </section>

      {/* Split screen */}
      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <section className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5 sm:p-6">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-white">Prompt</h2>
              <p className="text-sm text-slate-400">Describe the product you want to blueprint.</p>
            </div>
            {selected && (
              <Badge tone={studioStatusTone(selected.status)}>
                {studioStatusLabel(selected.status)}
              </Badge>
            )}
          </div>
          <textarea
            id="studio-prompt"
            value={prompt || selected?.prompt || ""}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={STUDIO_PROMPT_PLACEHOLDER}
            rows={12}
            className="w-full resize-y rounded-2xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/30"
          />
          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              onClick={() => analyzeM.mutate()}
              disabled={analyzeM.isPending}
              className="bg-teal-600 text-white hover:bg-teal-500"
            >
              {analyzeM.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Analyzing…
                </>
              ) : (
                <>
                  <Sparkles className="mr-2 h-4 w-4" />
                  Generate Blueprint
                </>
              )}
            </Button>
            <Button
              variant="secondary"
              onClick={() => createM.mutate()}
              disabled={createM.isPending || prompt.trim().length < 8}
            >
              Save Prompt
            </Button>
            <Button
              onClick={() => composeM.mutate()}
              disabled={!selected || !currentBlueprint || composeM.isPending}
              className="bg-cyan-700 text-white hover:bg-cyan-600"
            >
              {composeM.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Composing…
                </>
              ) : (
                <>
                  <Boxes className="mr-2 h-4 w-4" />
                  Compose Modules
                </>
              )}
            </Button>
            <Button variant="secondary" onClick={() => setPrompt("")} disabled={!prompt}>
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

          <div className="mt-6">
            <h3 className="mb-2 text-sm font-semibold text-white">Generation History</h3>
            {listQ.isLoading ? (
              <p className="flex items-center gap-2 text-sm text-slate-400">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading…
              </p>
            ) : items.length === 0 ? (
              <EmptyState title="No projects yet" description="Save or analyze a prompt to begin." />
            ) : (
              <ul className="max-h-56 space-y-2 overflow-y-auto">
                {items.map((p) => (
                  <li
                    key={p.id}
                    className={cn(
                      "flex items-center justify-between gap-2 rounded-xl border px-3 py-2 text-sm",
                      selected?.id === p.id
                        ? "border-teal-600/50 bg-slate-800/80"
                        : "border-slate-800 bg-slate-950/60"
                    )}
                  >
                    <button
                      type="button"
                      className="min-w-0 flex-1 text-left"
                      onClick={() => {
                        setSelectedId(p.id);
                        setPrompt(p.prompt);
                      }}
                    >
                      <p className="truncate font-medium text-slate-100">{p.title}</p>
                      <p className="text-xs text-slate-500">{formatWhen(p.created_at)}</p>
                    </button>
                    <Badge tone={studioStatusTone(p.status)}>{studioStatusLabel(p.status)}</Badge>
                    {canDelete && (
                      <button
                        type="button"
                        className="text-red-300 hover:text-red-200"
                        onClick={() => {
                          if (confirm(`Delete “${p.title}”?`)) deleteM.mutate(p.id);
                        }}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        <section className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5 sm:p-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-white">Blueprint editor</h2>
              <p className="text-sm text-slate-400">
                {currentBlueprint
                  ? `v${currentBlueprint.version} · ${currentBlueprint.source}`
                  : "Run Generate Blueprint to populate"}
              </p>
            </div>
            <Button
              onClick={() => saveM.mutate()}
              disabled={!selected || saveM.isPending}
              className="bg-teal-600 text-white hover:bg-teal-500"
            >
              {saveM.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Save className="mr-2 h-4 w-4" />
              )}
              Save version
            </Button>
          </div>

          {!selected ? (
            <EmptyState title="Select a project" description="Analyze a prompt to edit its blueprint." />
          ) : (
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <Field
                  label="Industry"
                  value={draft.industry}
                  onChange={(v) => patchDraft({ industry: v })}
                />
                <Field
                  label="Product type"
                  value={draft.product_type}
                  onChange={(v) => patchDraft({ product_type: v })}
                />
                <Field
                  label="Marketplace category"
                  value={draft.marketplace_category}
                  onChange={(v) => patchDraft({ marketplace_category: v })}
                />
                <Field
                  label="Complexity"
                  value={draft.estimated_complexity}
                  onChange={(v) => patchDraft({ estimated_complexity: v })}
                />
                <Field
                  label="Build time"
                  value={draft.estimated_build_time}
                  onChange={(v) => patchDraft({ estimated_build_time: v })}
                />
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <ListEditor
                  label="Pages"
                  value={draft.pages}
                  onChange={(pages) => patchDraft({ pages })}
                />
                <ListEditor
                  label="Dashboard modules"
                  value={draft.dashboard_modules}
                  onChange={(dashboard_modules) => patchDraft({ dashboard_modules })}
                />
                <ListEditor
                  label="Backend modules"
                  value={draft.backend_modules}
                  onChange={(backend_modules) => patchDraft({ backend_modules })}
                />
                <ListEditor
                  label="Database tables"
                  value={draft.database_tables}
                  onChange={(database_tables) => patchDraft({ database_tables })}
                />
                <ListEditor
                  label="Roles"
                  value={draft.roles}
                  onChange={(roles) => patchDraft({ roles })}
                />
                <ListEditor
                  label="AI features"
                  value={draft.ai_features}
                  onChange={(ai_features) => patchDraft({ ai_features })}
                />
                <ListEditor
                  label="Integrations"
                  value={draft.integrations}
                  onChange={(integrations) => patchDraft({ integrations })}
                />
                <ListEditor
                  label="Workflows"
                  value={draft.workflows}
                  onChange={(workflows) => patchDraft({ workflows })}
                />
              </div>
            </div>
          )}

          <div className="mt-6">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-white">
              <History className="h-4 w-4" />
              Version history
            </div>
            {(versionsQ.data?.items || []).length === 0 ? (
              <p className="text-sm text-slate-500">No versions yet.</p>
            ) : (
              <ul className="space-y-2">
                {versionsQ.data!.items.map((v) => (
                  <li
                    key={v.id}
                    className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/50 px-3 py-2 text-sm"
                  >
                    <div>
                      <span className="font-medium text-slate-100">v{v.version}</span>
                      <span className="ml-2 text-xs text-slate-500">
                        {v.source} · {formatWhen(v.created_at)}
                        {v.is_current ? " · current" : ""}
                      </span>
                    </div>
                    {!v.is_current && (
                      <Button
                        variant="secondary"
                        className="h-8 px-2 text-xs"
                        disabled={restoreM.isPending}
                        onClick={() => restoreM.mutate(v.version)}
                      >
                        <RotateCcw className="mr-1 h-3.5 w-3.5" />
                        Restore
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      </div>

      {/* Warnings + recommendations */}
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card className="border-slate-800 bg-slate-900/80">
          <h2 className="text-base font-semibold text-white">Warnings</h2>
          <p className="mt-1 text-sm text-slate-400">Missing auth, billing, admin, AI, storage, deploy</p>
          {warnings.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">No warnings for the current blueprint.</p>
          ) : (
            <ul className="mt-4 space-y-2">
              {warnings.map((w) => (
                <li
                  key={`${w.code}-${w.message}`}
                  className="flex items-start gap-2 rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2 text-sm"
                >
                  <Badge tone={warningTone(w.severity)}>{w.severity}</Badge>
                  <span className="text-slate-200">{w.message}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="border-slate-800 bg-slate-900/80">
          <h2 className="text-base font-semibold text-white">AI Recommendations</h2>
          <p className="mt-1 text-sm text-slate-400">
            Templates, marketplace assets, agents, knowledge packs
          </p>
          {!recommendations ? (
            <p className="mt-4 text-sm text-slate-500">Generate a blueprint to see recommendations.</p>
          ) : (
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <RecBlock title="Templates" items={recommendations.templates} />
              <RecBlock title="Marketplace" items={recommendations.marketplace_assets} />
              <RecBlock title="Agents" items={recommendations.agents} />
              <RecBlock title="Knowledge packs" items={recommendations.knowledge_packs} />
              <RecBlock title="Integrations" items={recommendations.integrations} />
            </div>
          )}
          <Link
            href="/app/templates"
            className={cn(buttonVariants({ variant: "secondary" }), "mt-4 inline-flex")}
          >
            Browse Marketplace
            <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
        </Card>
      </div>

      {/* Module compose / build plan */}
      <section className="mt-6 rounded-3xl border border-slate-800 bg-slate-900/80 p-5 sm:p-6">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-white">Module plan</h2>
            <p className="text-sm text-slate-400">
              {buildPlan
                ? `v${buildPlan.version} · blueprint v${buildPlan.blueprint_version} · ${buildPlan.summary.reuse_percent}% reuse · custom work: ${buildPlan.summary.estimated_custom_work}`
                : "Compose Modules after a blueprint is ready"}
            </p>
          </div>
          {buildPlan && (
            <div className="flex flex-wrap gap-2">
              <Badge tone="success">{buildPlan.summary.existing_count} existing</Badge>
              <Badge tone="neutral">{buildPlan.summary.marketplace_count} marketplace</Badge>
              <Badge tone="warn">{buildPlan.summary.custom_count} custom</Badge>
            </div>
          )}
        </div>

        {!buildPlan ? (
          <EmptyState
            title="No build plan yet"
            description="Generate a blueprint, then click Compose Modules to map Auth, Billing, AI, and more."
          />
        ) : (
          <div className="grid gap-6 xl:grid-cols-3">
            <div>
              <h3 className="mb-2 text-sm font-semibold text-white">Modules</h3>
              <ul className="max-h-80 space-y-2 overflow-y-auto">
                {buildPlan.modules.map((m) => (
                  <li
                    key={m.key}
                    className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2 text-sm"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-slate-100">{m.label}</span>
                      <Badge tone={moduleKindTone(m.kind)}>{moduleKindLabel(m.kind)}</Badge>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">
                      {m.platform_ref || m.marketplace_template || "custom"} · {m.reason}
                    </p>
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h3 className="mb-2 text-sm font-semibold text-white">Dependencies</h3>
              <ul className="max-h-80 space-y-2 overflow-y-auto font-mono text-xs text-slate-300">
                {buildPlan.dependency_graph.map((e) => (
                  <li key={e.key} className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2">
                    <span className="text-teal-300">{e.label}</span>
                    {e.depends_on.length > 0 ? (
                      <div className="mt-1 text-slate-500">
                        ← {e.depends_on.join(", ")}
                      </div>
                    ) : (
                      <div className="mt-1 text-slate-600">root</div>
                    )}
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h3 className="mb-2 text-sm font-semibold text-white">Build plan</h3>
              <ol className="max-h-80 space-y-2 overflow-y-auto">
                {buildPlan.build_plan.map((s) => (
                  <li
                    key={`${s.order}-${s.key}`}
                    className="flex gap-3 rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2 text-sm"
                  >
                    <span className="font-mono text-teal-400">{s.order}.</span>
                    <div>
                      <p className="font-medium text-slate-100">
                        {s.label}{" "}
                        <span className="text-xs font-normal text-slate-500">({s.phase})</span>
                      </p>
                      {s.note && <p className="text-xs text-amber-200/80">{s.note}</p>}
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        )}

        {composeWarnings.length > 0 && (
          <ul className="mt-4 space-y-2">
            {composeWarnings.map((w) => (
              <li
                key={`compose-${w.code}-${w.message}`}
                className="flex items-start gap-2 rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2 text-sm"
              >
                <Badge tone={warningTone(w.severity)}>{w.severity}</Badge>
                <span className="text-slate-200">{w.message}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="mt-6 rounded-3xl border border-slate-800 bg-slate-900/60 p-5">
        <div className="mb-3 flex items-center gap-2">
          <Lightbulb className="h-4 w-4 text-amber-300" />
          <h2 className="text-sm font-semibold text-white">AI Tips</h2>
        </div>
        <ul className="grid gap-2 text-sm text-slate-300 sm:grid-cols-2">
          {STUDIO_TIPS.map((tip) => (
            <li key={tip} className="flex gap-2">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-400" />
              {tip}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function Field({
  label,
  value,
  onChange
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/30"
      />
    </label>
  );
}

function RecBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</p>
      <ul className="mt-2 space-y-1 text-sm text-slate-200">
        {(items || []).length === 0 ? (
          <li className="text-slate-500">—</li>
        ) : (
          items.map((item) => <li key={item}>{item}</li>)
        )}
      </ul>
    </div>
  );
}
