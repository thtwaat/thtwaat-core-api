"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { toast } from "sonner";
import {
  ArrowRight,
  Bot,
  Boxes,
  Cloud,
  Database,
  Eraser,
  History,
  LayoutTemplate,
  Lightbulb,
  Loader2,
  MonitorSmartphone,
  RotateCcw,
  Save,
  Server,
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
  type AiManifest,
  type BackendManifest,
  type FrontendManifest,
  type InfraManifest,
  type ProductBlueprint,
  type StudioAi,
  type StudioBackend,
  type StudioBlueprint,
  type StudioBuildPlan,
  type StudioFrontend,
  type StudioInfrastructure
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

  const frontendQ = useQuery({
    queryKey: ["studio-frontend", selected?.id],
    queryFn: () => studioApi.getFrontend(selected!.id),
    enabled: Boolean(selected?.id),
    retry: false
  });

  const backendQ = useQuery({
    queryKey: ["studio-backend", selected?.id],
    queryFn: () => studioApi.getBackend(selected!.id),
    enabled: Boolean(selected?.id),
    retry: false
  });

  const aiQ = useQuery({
    queryKey: ["studio-ai", selected?.id],
    queryFn: () => studioApi.getAi(selected!.id),
    enabled: Boolean(selected?.id),
    retry: false
  });

  const infraQ = useQuery({
    queryKey: ["studio-infrastructure", selected?.id],
    queryFn: () => studioApi.getInfrastructure(selected!.id),
    enabled: Boolean(selected?.id),
    retry: false
  });

  const [frontendDraft, setFrontendDraft] = useState<FrontendManifest | null>(null);
  const [backendDraft, setBackendDraft] = useState<BackendManifest | null>(null);
  const [aiDraft, setAiDraft] = useState<AiManifest | null>(null);
  const [infraDraft, setInfraDraft] = useState<InfraManifest | null>(null);

  useEffect(() => {
    if (blueprintQ.data?.blueprint) {
      setDraft(blueprintQ.data.blueprint);
    } else if (blueprintQ.isError) {
      setDraft(EMPTY_BLUEPRINT);
    }
  }, [blueprintQ.data, blueprintQ.isError, selected?.id]);

  useEffect(() => {
    if (frontendQ.data?.manifest) {
      setFrontendDraft(frontendQ.data.manifest);
    } else if (frontendQ.isError) {
      setFrontendDraft(null);
    }
  }, [frontendQ.data, frontendQ.isError, selected?.id]);

  useEffect(() => {
    if (backendQ.data?.manifest) {
      setBackendDraft(backendQ.data.manifest);
    } else if (backendQ.isError) {
      setBackendDraft(null);
    }
  }, [backendQ.data, backendQ.isError, selected?.id]);

  useEffect(() => {
    if (aiQ.data?.manifest) {
      setAiDraft(aiQ.data.manifest);
    } else if (aiQ.isError) {
      setAiDraft(null);
    }
  }, [aiQ.data, aiQ.isError, selected?.id]);

  useEffect(() => {
    if (infraQ.data?.manifest) {
      setInfraDraft(infraQ.data.manifest);
    } else if (infraQ.isError) {
      setInfraDraft(null);
    }
  }, [infraQ.data, infraQ.isError, selected?.id]);

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

  const generateFrontendM = useMutation({
    mutationFn: () => {
      if (!selected?.id) throw new Error("Select a project first");
      return studioApi.generateFrontend(selected.id);
    },
    onSuccess: (result) => {
      toast.success(
        `Frontend v${result.frontend.version} · ${result.frontend.manifest.summary.reuse_percent}% UI reuse`
      );
      setFrontendDraft(result.frontend.manifest);
      void qc.invalidateQueries({ queryKey: ["studio-projects"] });
      void qc.invalidateQueries({ queryKey: ["studio-frontend", result.project.id] });
    },
    onError: (err) =>
      toast.error(
        err instanceof ApiError || err instanceof Error ? err.message : "Frontend generate failed"
      )
  });

  const saveFrontendM = useMutation({
    mutationFn: (status?: string) => {
      if (!selected?.id || !frontendDraft) throw new Error("No frontend to save");
      return studioApi.saveFrontend(selected.id, { manifest: frontendDraft, status });
    },
    onSuccess: (row) => {
      toast.success(`Frontend saved as v${row.version} (${row.status})`);
      setFrontendDraft(row.manifest);
      void qc.invalidateQueries({ queryKey: ["studio-frontend", selected?.id] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Save frontend failed")
  });

  const generateBackendM = useMutation({
    mutationFn: () => {
      if (!selected?.id) throw new Error("Select a project first");
      return studioApi.generateBackend(selected.id);
    },
    onSuccess: (result) => {
      toast.success(
        `Backend v${result.backend.version} · ${result.backend.manifest.summary.reuse_percent}% reuse`
      );
      setBackendDraft(result.backend.manifest);
      void qc.invalidateQueries({ queryKey: ["studio-projects"] });
      void qc.invalidateQueries({ queryKey: ["studio-backend", result.project.id] });
    },
    onError: (err) =>
      toast.error(
        err instanceof ApiError || err instanceof Error ? err.message : "Backend generate failed"
      )
  });

  const saveBackendM = useMutation({
    mutationFn: (status?: string) => {
      if (!selected?.id || !backendDraft) throw new Error("No backend to save");
      return studioApi.saveBackend(selected.id, { manifest: backendDraft, status });
    },
    onSuccess: (row) => {
      toast.success(`Backend saved as v${row.version} (${row.status})`);
      setBackendDraft(row.manifest);
      void qc.invalidateQueries({ queryKey: ["studio-backend", selected?.id] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Save backend failed")
  });

  const generateAiM = useMutation({
    mutationFn: () => {
      if (!selected?.id) throw new Error("Select a project first");
      return studioApi.generateAi(selected.id);
    },
    onSuccess: (result) => {
      toast.success(
        `AI v${result.ai.version} · ${result.ai.manifest.summary.reuse_percent}% reuse · ~$${result.ai.manifest.cost.estimated_monthly_usd}/mo`
      );
      setAiDraft(result.ai.manifest);
      void qc.invalidateQueries({ queryKey: ["studio-projects"] });
      void qc.invalidateQueries({ queryKey: ["studio-ai", result.project.id] });
    },
    onError: (err) =>
      toast.error(err instanceof ApiError || err instanceof Error ? err.message : "AI generate failed")
  });

  const saveAiM = useMutation({
    mutationFn: (status?: string) => {
      if (!selected?.id || !aiDraft) throw new Error("No AI manifest to save");
      return studioApi.saveAi(selected.id, { manifest: aiDraft, status });
    },
    onSuccess: (row) => {
      toast.success(`AI saved as v${row.version} (${row.status})`);
      setAiDraft(row.manifest);
      void qc.invalidateQueries({ queryKey: ["studio-ai", selected?.id] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Save AI failed")
  });

  const generateInfraM = useMutation({
    mutationFn: () => {
      if (!selected?.id) throw new Error("Select a project first");
      return studioApi.generateInfrastructure(selected.id);
    },
    onSuccess: (result) => {
      toast.success(
        `Infra v${result.infrastructure.version} · ${result.infrastructure.manifest.summary.reuse_percent}% reuse · ~$${result.infrastructure.manifest.cost.monthly_total_usd}/mo`
      );
      setInfraDraft(result.infrastructure.manifest);
      void qc.invalidateQueries({ queryKey: ["studio-projects"] });
      void qc.invalidateQueries({
        queryKey: ["studio-infrastructure", result.project.id]
      });
    },
    onError: (err) =>
      toast.error(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : "Infrastructure generate failed"
      )
  });

  const saveInfraM = useMutation({
    mutationFn: (status?: string) => {
      if (!selected?.id || !infraDraft) throw new Error("No infrastructure to save");
      return studioApi.saveInfrastructure(selected.id, { manifest: infraDraft, status });
    },
    onSuccess: (row) => {
      toast.success(`Infrastructure saved as v${row.version} (${row.status})`);
      setInfraDraft(row.manifest);
      void qc.invalidateQueries({ queryKey: ["studio-infrastructure", selected?.id] });
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "Save infrastructure failed")
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
  const frontendRow: StudioFrontend | undefined = frontendQ.data;
  const backendRow: StudioBackend | undefined = backendQ.data;
  const aiRow: StudioAi | undefined = aiQ.data;
  const infraRow: StudioInfrastructure | undefined = infraQ.data;
  const frontend = frontendDraft;
  const backend = backendDraft;
  const ai = aiDraft;
  const infra = infraDraft;
  const warnings = currentBlueprint?.warnings || [];
  const recommendations = currentBlueprint?.recommendations;
  const composeWarnings = buildPlan?.summary?.warnings || [];
  const frontendWarnings = frontend?.warnings || frontend?.summary?.warnings || [];
  const backendWarnings = backend?.warnings || backend?.summary?.warnings || [];
  const aiWarnings = ai?.warnings || ai?.summary?.warnings || [];
  const infraWarnings = infra?.warnings || infra?.summary?.warnings || [];

  function patchDraft(partial: Partial<ProductBlueprint>) {
    setDraft((prev) => ({ ...prev, ...partial }));
  }

  return (
    <div className="-mx-4 -mt-4 min-h-[calc(100vh-4rem)] bg-slate-950 px-4 py-6 text-slate-100 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
      <section className="relative overflow-hidden rounded-3xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-950 to-teal-950 p-6 sm:p-8">
        <div className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-teal-500/20 blur-3xl" />
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-300/80">
          THTWAAT Studio · Phase 7
        </p>
        <h1 className="mt-2 max-w-3xl text-3xl font-semibold tracking-tight text-white sm:text-4xl">
          Infrastructure Generator
        </h1>
        <p className="mt-3 max-w-2xl text-sm text-slate-300">
          Plan Docker, Compose, Nginx, Redis, Postgres, Workers, Scheduler, env/secrets, monitoring,
          and cost on the existing production stack. Planning only — no deploy, no app source.
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
            <Button
              onClick={() => generateFrontendM.mutate()}
              disabled={!selected || !buildPlan || generateFrontendM.isPending}
              className="bg-indigo-700 text-white hover:bg-indigo-600"
            >
              {generateFrontendM.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Generating…
                </>
              ) : (
                <>
                  <MonitorSmartphone className="mr-2 h-4 w-4" />
                  Generate Frontend
                </>
              )}
            </Button>
            <Button
              onClick={() => generateBackendM.mutate()}
              disabled={!selected || !frontend || generateBackendM.isPending}
              className="bg-violet-700 text-white hover:bg-violet-600"
            >
              {generateBackendM.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Generating…
                </>
              ) : (
                <>
                  <Server className="mr-2 h-4 w-4" />
                  Generate Backend
                </>
              )}
            </Button>
            <Button
              onClick={() => generateAiM.mutate()}
              disabled={!selected || !backend || generateAiM.isPending}
              className="bg-fuchsia-700 text-white hover:bg-fuchsia-600"
            >
              {generateAiM.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Generating…
                </>
              ) : (
                <>
                  <Bot className="mr-2 h-4 w-4" />
                  Generate AI
                </>
              )}
            </Button>
            <Button
              onClick={() => generateInfraM.mutate()}
              disabled={!selected || !ai || generateInfraM.isPending}
              className="bg-emerald-700 text-white hover:bg-emerald-600"
            >
              {generateInfraM.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Generating…
                </>
              ) : (
                <>
                  <Cloud className="mr-2 h-4 w-4" />
                  Generate Infrastructure
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

      {/* Frontend preview */}
      <section className="mt-6 rounded-3xl border border-slate-800 bg-slate-900/80 p-5 sm:p-6">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-white">Frontend preview</h2>
            <p className="text-sm text-slate-400">
              {frontend && frontendRow
                ? `v${frontendRow.version} · ${frontendRow.status} · ${frontend.summary.reuse_percent}% UI reuse · custom: ${frontend.summary.estimated_custom_work}`
                : "Compose Modules, then Generate Frontend for a live preview manifest"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              disabled={!frontend || saveFrontendM.isPending}
              onClick={() => saveFrontendM.mutate("draft")}
            >
              <Save className="mr-2 h-4 w-4" />
              Save draft
            </Button>
            <Button
              className="bg-teal-600 text-white hover:bg-teal-500"
              disabled={!frontend || saveFrontendM.isPending}
              onClick={() => saveFrontendM.mutate("approved")}
            >
              Approve frontend
            </Button>
          </div>
        </div>

        {!frontend ? (
          <EmptyState
            title="No frontend yet"
            description="Generate Frontend after a build plan to preview nav, routes, cards, and CRUD screens."
          />
        ) : (
          <div className="space-y-6">
            {/* Responsive preview chrome */}
            <div className="overflow-hidden rounded-2xl border border-slate-700 bg-slate-950">
              <div className="flex items-center gap-2 border-b border-slate-800 px-4 py-2 text-xs text-slate-400">
                <MonitorSmartphone className="h-3.5 w-3.5" />
                Preview · AppShell · sm/md/lg responsive
              </div>
              <div className="grid md:grid-cols-[200px_1fr]">
                <aside className="border-b border-slate-800 bg-slate-900/80 p-3 md:border-b-0 md:border-r">
                  <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                    Navigation
                  </p>
                  <ul className="space-y-1">
                    {frontend.nav.map((item) => (
                      <li key={item.id}>
                        <div className="flex items-center justify-between rounded-lg px-2 py-1.5 text-sm text-slate-200 hover:bg-slate-800">
                          <span>{item.label}</span>
                          {item.reuse && <Badge tone="success">reuse</Badge>}
                        </div>
                      </li>
                    ))}
                  </ul>
                </aside>
                <div className="p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Dashboard cards
                  </p>
                  <div className="mt-2 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {frontend.dashboard_cards.map((card) => (
                      <div
                        key={String(card.id)}
                        className="rounded-xl border border-slate-800 bg-slate-900/70 p-3"
                      >
                        <p className="text-xs text-slate-500">{String(card.type || "card")}</p>
                        <p className="mt-1 font-medium text-slate-100">{String(card.title)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <div className="grid gap-6 xl:grid-cols-3">
              <div>
                <h3 className="mb-2 text-sm font-semibold text-white">Pages</h3>
                <ul className="max-h-72 space-y-2 overflow-y-auto">
                  {frontend.pages.map((p) => (
                    <li
                      key={p.id}
                      className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2 text-sm"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium text-slate-100">{p.title}</span>
                        <Badge tone={p.kind === "reuse" ? "success" : "warn"}>
                          {p.kind === "reuse" ? "Existing" : "CRUD"}
                        </Badge>
                      </div>
                      <p className="mt-1 font-mono text-xs text-slate-500">{p.route}</p>
                      <input
                        className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-200"
                        value={p.title}
                        onChange={(e) => {
                          const title = e.target.value;
                          setFrontendDraft((prev) =>
                            prev
                              ? {
                                  ...prev,
                                  pages: prev.pages.map((x) =>
                                    x.id === p.id ? { ...x, title } : x
                                  ),
                                  nav: prev.nav.map((n) =>
                                    n.page_id === p.id ? { ...n, label: title } : n
                                  )
                                }
                              : prev
                          );
                        }}
                      />
                    </li>
                  ))}
                </ul>
              </div>

              <div>
                <h3 className="mb-2 text-sm font-semibold text-white">Routes</h3>
                <ul className="max-h-72 space-y-2 overflow-y-auto font-mono text-xs text-slate-300">
                  {frontend.routes.map((r) => (
                    <li
                      key={r.path}
                      className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2"
                    >
                      <span className="text-teal-300">{r.path}</span>
                      <div className="mt-1 text-slate-500">
                        {r.layout} · {r.auth}
                        {r.reuse ? " · reuse" : " · generated"}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>

              <div>
                <h3 className="mb-2 text-sm font-semibold text-white">Forms / CRUD</h3>
                <ul className="max-h-72 space-y-2 overflow-y-auto text-sm">
                  {frontend.pages
                    .filter((p) => p.crud)
                    .map((p) => (
                      <li
                        key={`crud-${p.id}`}
                        className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2"
                      >
                        <p className="font-medium text-slate-100">{p.title}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          {p.crud?.operations.join(", ")} · {p.crud?.table}
                        </p>
                        <p className="mt-1 text-xs text-slate-400">
                          Fields: {(p.crud?.table_columns || []).join(", ") || "—"}
                        </p>
                      </li>
                    ))}
                  {frontend.pages.every((p) => !p.crud) && (
                    <li className="text-sm text-slate-500">No custom CRUD — full UI reuse.</li>
                  )}
                </ul>
              </div>
            </div>
          </div>
        )}

        {frontendWarnings.length > 0 && (
          <ul className="mt-4 space-y-2">
            {frontendWarnings.map((w) => (
              <li
                key={`fe-${w.code}-${w.message}`}
                className="flex items-start gap-2 rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2 text-sm"
              >
                <Badge tone={warningTone(w.severity)}>{w.severity}</Badge>
                <span className="text-slate-200">{w.message}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Backend preview */}
      <section className="mt-6 rounded-3xl border border-slate-800 bg-slate-900/80 p-5 sm:p-6">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-white">Backend preview</h2>
            <p className="text-sm text-slate-400">
              {backend && backendRow
                ? `v${backendRow.version} · ${backendRow.status} · ${backend.summary.reuse_percent}% reuse · custom: ${backend.summary.estimated_custom_work}`
                : "Generate Frontend first, then Generate Backend for API/DB/RBAC manifests"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              disabled={!backend || saveBackendM.isPending}
              onClick={() => saveBackendM.mutate("draft")}
            >
              <Save className="mr-2 h-4 w-4" />
              Save draft
            </Button>
            <Button
              className="bg-teal-600 text-white hover:bg-teal-500"
              disabled={!backend || saveBackendM.isPending}
              onClick={() => saveBackendM.mutate("approved")}
            >
              Approve backend
            </Button>
          </div>
        </div>

        {!backend ? (
          <EmptyState
            title="No backend yet"
            description="Generate Backend after frontend to preview APIs, tables, RBAC, queues, and OpenAPI."
          />
        ) : (
          <div className="grid gap-6 xl:grid-cols-2">
            <div>
              <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-white">
                <Server className="h-4 w-4 text-violet-300" />
                API Explorer
              </h3>
              <ul className="max-h-72 space-y-2 overflow-y-auto font-mono text-xs">
                {backend.api.endpoints.slice(0, 40).map((ep) => (
                  <li
                    key={ep.id}
                    className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span>
                        <span className="text-amber-300">{ep.method}</span>{" "}
                        <span className="text-teal-300">{ep.path}</span>
                      </span>
                      <Badge tone={ep.reuse ? "success" : "warn"}>
                        {ep.reuse ? "reuse" : "custom"}
                      </Badge>
                    </div>
                    <p className="mt-1 text-slate-500">
                      {ep.operation}
                      {ep.pagination ? " · page" : ""}
                      {ep.search ? " · search" : ""}
                      {ep.permissions[0] ? ` · ${ep.permissions[0]}` : ""}
                    </p>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-slate-500">
                OpenAPI {backend.openapi.openapi} · {Object.keys(backend.openapi.paths || {}).length}{" "}
                paths
              </p>
            </div>

            <div>
              <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-white">
                <Database className="h-4 w-4 text-cyan-300" />
                Database diagram
              </h3>
              <ul className="max-h-72 space-y-2 overflow-y-auto text-sm">
                {backend.database.tables.map((t) => (
                  <li
                    key={t.name}
                    className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-teal-200">{t.name}</span>
                      <Badge tone={t.reuse ? "success" : "warn"}>
                        {t.reuse ? "reuse" : "custom"}
                      </Badge>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">
                      {(t.columns || []).map((c) => c.name).slice(0, 6).join(", ")}
                      {(t.columns || []).length > 6 ? "…" : ""}
                    </p>
                  </li>
                ))}
              </ul>
              {(backend.database.relationships || []).length > 0 && (
                <ul className="mt-2 space-y-1 font-mono text-xs text-slate-500">
                  {backend.database.relationships.slice(0, 8).map((r, idx) => (
                    <li key={`${r.from_table}-${r.to_table}-${idx}`}>
                      {r.from_table} → {r.to_table} ({r.type})
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div>
              <h3 className="mb-2 text-sm font-semibold text-white">RBAC preview</h3>
              <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-sm">
                <p className="text-slate-400">Roles</p>
                <div className="mt-1 flex flex-wrap gap-1">
                  {backend.rbac.roles.map((role) => (
                    <Badge key={role} tone="neutral">
                      {role}
                    </Badge>
                  ))}
                </div>
                <p className="mt-3 text-slate-400">
                  {backend.rbac.permissions.length} permissions ·{" "}
                  {backend.rbac.policies.length} policies
                </p>
                <p className="mt-1 text-xs text-slate-500">{backend.rbac.note}</p>
              </div>
            </div>

            <div>
              <h3 className="mb-2 text-sm font-semibold text-white">Services · Queues · Storage</h3>
              <div className="grid gap-2 text-sm">
                <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Services</p>
                  <ul className="mt-1 space-y-1">
                    {backend.services.slice(0, 8).map((s) => (
                      <li key={s.id} className="flex justify-between gap-2">
                        <span className="text-slate-200">{s.name}</span>
                        <Badge tone={s.reuse ? "success" : "warn"}>{s.kind}</Badge>
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Queues</p>
                  <p className="mt-1 text-slate-300">
                    {backend.queues.map((q) => q.name).join(", ") || "—"}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Storage</p>
                  <p className="mt-1 text-slate-300">
                    {backend.storage.map((s) => s.kind).join(", ") || "—"}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {backendWarnings.length > 0 && (
          <ul className="mt-4 space-y-2">
            {backendWarnings.map((w) => (
              <li
                key={`be-${w.code}-${w.message}`}
                className="flex items-start gap-2 rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2 text-sm"
              >
                <Badge tone={warningTone(w.severity)}>{w.severity}</Badge>
                <span className="text-slate-200">{w.message}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* AI preview */}
      <section className="mt-6 rounded-3xl border border-slate-800 bg-slate-900/80 p-5 sm:p-6">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-white">AI architecture</h2>
            <p className="text-sm text-slate-400">
              {ai && aiRow
                ? `v${aiRow.version} · ${aiRow.status} · ${ai.summary.reuse_percent}% reuse · ~$${ai.cost.estimated_monthly_usd}/mo`
                : "Generate Backend first, then Generate AI for providers/agents/prompts"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              disabled={!ai || saveAiM.isPending}
              onClick={() => saveAiM.mutate("draft")}
            >
              <Save className="mr-2 h-4 w-4" />
              Save draft
            </Button>
            <Button
              className="bg-teal-600 text-white hover:bg-teal-500"
              disabled={!ai || saveAiM.isPending}
              onClick={() => saveAiM.mutate("approved")}
            >
              Approve AI
            </Button>
          </div>
        </div>

        {!ai ? (
          <EmptyState
            title="No AI manifest yet"
            description="Generate AI after backend to preview providers, agents, prompts, tools, and cost."
          />
        ) : (
          <div className="grid gap-6 xl:grid-cols-2">
            <div>
              <h3 className="mb-2 text-sm font-semibold text-white">Provider recommendation</h3>
              <ul className="max-h-56 space-y-2 overflow-y-auto text-sm">
                {ai.providers.map((p) => (
                  <li
                    key={p.provider}
                    className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2"
                  >
                    <div>
                      <p className="font-medium text-slate-100">
                        #{p.rank} {p.provider}
                        {p.recommended_primary ? " · primary" : ""}
                      </p>
                      <p className="text-xs text-slate-500">
                        {p.default_model} · {p.reason}
                      </p>
                    </div>
                    <Badge tone={p.recommended_primary ? "success" : "neutral"}>{p.score}</Badge>
                  </li>
                ))}
              </ul>
              <div className="mt-3 rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-sm">
                <p className="text-xs uppercase tracking-wide text-slate-500">Estimated AI cost</p>
                <p className="mt-1 text-2xl font-semibold text-teal-300">
                  ${ai.cost.estimated_monthly_usd}
                  <span className="text-sm font-normal text-slate-500"> / mo</span>
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {ai.cost.monthly_requests.toLocaleString()} req · {ai.cost.provider}
                </p>
              </div>
            </div>

            <div>
              <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-white">
                <Bot className="h-4 w-4 text-fuchsia-300" />
                Agents
              </h3>
              <ul className="max-h-72 space-y-2 overflow-y-auto text-sm">
                {ai.agents.map((a) => (
                  <li
                    key={a.id}
                    className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-slate-100">{a.name}</span>
                      <Badge tone={a.reuse ? "success" : "warn"}>{a.kind}</Badge>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">
                      {a.provider}/{a.model}
                      {a.streaming ? " · stream" : ""}
                      {a.knowledge ? " · RAG" : ""}
                      {a.human_handoff ? " · handoff" : ""}
                      {a.voice_plan ? " · voice(plan)" : ""}
                      {a.vision_plan ? " · vision(plan)" : ""}
                    </p>
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h3 className="mb-2 text-sm font-semibold text-white">Prompt library</h3>
              <ul className="max-h-64 space-y-2 overflow-y-auto text-sm">
                {ai.prompts.map((p) => (
                  <li
                    key={p.id}
                    className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-slate-100">{p.name}</span>
                      <Badge tone="neutral">{p.category}</Badge>
                    </div>
                    <p className="mt-1 line-clamp-2 text-xs text-slate-500">{p.template}</p>
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h3 className="mb-2 text-sm font-semibold text-white">Tool list</h3>
              <ul className="max-h-64 space-y-2 overflow-y-auto text-sm">
                {ai.tools.map((t) => (
                  <li
                    key={t.id}
                    className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2"
                  >
                    <div>
                      <p className="font-medium text-slate-100">{t.name}</p>
                      <p className="text-xs text-slate-500">{t.description}</p>
                    </div>
                    <Badge tone={t.reuse ? "success" : "warn"}>
                      {t.reuse ? "reuse" : "custom"}
                    </Badge>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-slate-500">
                Workflows: {ai.workflows.map((w) => w.name).join(" · ") || "—"}
              </p>
            </div>
          </div>
        )}

        {aiWarnings.length > 0 && (
          <ul className="mt-4 space-y-2">
            {aiWarnings.map((w) => (
              <li
                key={`ai-${w.code}-${w.message}`}
                className="flex items-start gap-2 rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2 text-sm"
              >
                <Badge tone={warningTone(w.severity)}>{w.severity}</Badge>
                <span className="text-slate-200">{w.message}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Infrastructure preview */}
      <section className="mt-6 rounded-3xl border border-slate-800 bg-slate-900/80 p-5 sm:p-6">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-white">Infrastructure plan</h2>
            <p className="text-sm text-slate-400">
              {infra && infraRow
                ? `v${infraRow.version} · ${infraRow.status} · ${infra.summary.reuse_percent}% reuse · ~$${infra.cost.monthly_total_usd}/mo`
                : "Generate AI first, then Generate Infrastructure for compose/targets/env/cost"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              disabled={!infra || saveInfraM.isPending}
              onClick={() => saveInfraM.mutate("draft")}
            >
              <Save className="mr-2 h-4 w-4" />
              Save draft
            </Button>
            <Button
              className="bg-teal-600 text-white hover:bg-teal-500"
              disabled={!infra || saveInfraM.isPending}
              onClick={() => saveInfraM.mutate("approved")}
            >
              Approve Infrastructure
            </Button>
          </div>
        </div>

        {!infra ? (
          <EmptyState
            title="No infrastructure yet"
            description="Generate Infrastructure after AI to preview stack, targets, env vars, warnings, and cost."
          />
        ) : (
          <div className="grid gap-6 xl:grid-cols-2">
            <div>
              <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-white">
                <Cloud className="h-4 w-4 text-emerald-300" />
                Components
              </h3>
              <ul className="max-h-72 space-y-2 overflow-y-auto text-sm">
                {infra.components.map((c) => (
                  <li
                    key={c.id}
                    className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2"
                  >
                    <div>
                      <p className="font-medium text-slate-100">{c.name}</p>
                      <p className="text-xs text-slate-500">
                        {c.category}
                        {c.platform_ref ? ` · ${c.platform_ref}` : ""}
                      </p>
                    </div>
                    <Badge tone={c.reuse ? "success" : "warn"}>
                      {c.reuse ? "reuse" : "plan"}
                    </Badge>
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h3 className="mb-2 text-sm font-semibold text-white">Deployment targets</h3>
              <ul className="max-h-72 space-y-2 overflow-y-auto text-sm">
                {infra.targets.map((t) => (
                  <li
                    key={t.id}
                    className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2"
                  >
                    <div>
                      <p className="font-medium text-slate-100">
                        {t.name}
                        {t.recommended ? " · recommended" : ""}
                      </p>
                      <p className="text-xs text-slate-500">{t.reason}</p>
                    </div>
                    <Badge tone={t.recommended ? "success" : "neutral"}>{t.score}</Badge>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-slate-500">Planning only — Phase 7 does not deploy.</p>
            </div>

            <div>
              <h3 className="mb-2 text-sm font-semibold text-white">Environment variables</h3>
              <ul className="max-h-56 space-y-1 overflow-y-auto font-mono text-xs">
                {infra.environment.slice(0, 24).map((e) => (
                  <li
                    key={e.key}
                    className="flex items-center justify-between gap-2 rounded-lg border border-slate-800 bg-slate-950/60 px-2 py-1.5"
                  >
                    <span className="text-teal-200">{e.key}</span>
                    <span className="text-slate-500">
                      {e.required ? "required" : "optional"}
                      {e.secret ? " · secret" : ""}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-slate-500">
                Required secrets: {(infra.secrets.required || []).join(", ") || "—"}
              </p>
            </div>

            <div>
              <h3 className="mb-2 text-sm font-semibold text-white">Cost estimate</h3>
              <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-sm">
                <p className="text-xs uppercase tracking-wide text-slate-500">Monthly total</p>
                <p className="mt-1 text-2xl font-semibold text-teal-300">
                  ${infra.cost.monthly_total_usd}
                  <span className="text-sm font-normal text-slate-500"> / mo</span>
                </p>
                <ul className="mt-3 space-y-1 text-xs text-slate-400">
                  <li>Infrastructure · ${infra.cost.infrastructure_usd}</li>
                  <li>AI · ${infra.cost.ai_usd}</li>
                  <li>Storage · ${infra.cost.storage_usd}</li>
                  <li>Bandwidth · ${infra.cost.bandwidth_usd}</li>
                </ul>
              </div>
            </div>
          </div>
        )}

        {infraWarnings.length > 0 && (
          <ul className="mt-4 space-y-2">
            {infraWarnings.map((w) => (
              <li
                key={`infra-${w.code}-${w.message}`}
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
