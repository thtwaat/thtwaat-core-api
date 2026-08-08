"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { toast } from "sonner";
import {
  ArrowRight,
  Bot,
  Boxes,
  CheckCircle2,
  Cloud,
  Database,
  Download,
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
import { ApiError, getAccessToken } from "@/lib/api";
import { apiPaths, site } from "@/lib/config";
import { canDeleteStudioProjects } from "@/lib/permissions";
import { domainsApi, studioApi } from "@/lib/services";
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
  type ReviewManifest,
  type StudioAi,
  type StudioBackend,
  type StudioBlueprint,
  type StudioBuild,
  type StudioBuildPlan,
  type StudioDeployment,
  type StudioExportResult,
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

function downloadExport(result: StudioExportResult) {
  let blob: Blob;
  if (result.encoding === "base64") {
    const binary = atob(result.content);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    blob = new Blob([bytes], { type: result.content_type });
  } else {
    blob = new Blob([result.content], { type: result.content_type });
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = result.filename;
  a.click();
  URL.revokeObjectURL(url);
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

  const reviewQ = useQuery({
    queryKey: ["studio-review", selected?.id],
    queryFn: () => studioApi.getReview(selected!.id),
    enabled: Boolean(selected?.id),
    retry: false
  });

  const buildQ = useQuery({
    queryKey: ["studio-build", selected?.id],
    queryFn: () => studioApi.getBuild(selected!.id),
    enabled: Boolean(selected?.id),
    retry: false,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status && ["queued", "planning", "generating", "validating"].includes(status)) {
        return 2000;
      }
      return false;
    }
  });

  const artifactsQ = useQuery({
    queryKey: ["studio-artifacts", selected?.id],
    queryFn: () => studioApi.getArtifacts(selected!.id),
    enabled: Boolean(selected?.id) && buildQ.data?.status === "completed",
    retry: false
  });

  const deploymentsQ = useQuery({
    queryKey: ["studio-deployments", selected?.id],
    queryFn: () => studioApi.listDeployments(selected!.id),
    enabled: Boolean(selected?.id),
    retry: false,
    refetchInterval: (query) => {
      const cur = query.state.data?.items?.find((d) => d.id === query.state.data?.current_id);
      if (
        cur &&
        ["queued", "deploying", "waiting_for_domain", "provisioning_ssl"].includes(cur.status)
      ) {
        return 2000;
      }
      return false;
    }
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
      void qc.invalidateQueries({ queryKey: ["studio-review", result.project.id] });
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
      void qc.invalidateQueries({ queryKey: ["studio-review", selected?.id] });
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "Save infrastructure failed")
  });

  const approveM = useMutation({
    mutationFn: () => {
      if (!selected?.id) throw new Error("Select a project first");
      return studioApi.approveBuild(selected.id, { notes: "Approved from Review Center" });
    },
    onSuccess: (result) => {
      toast.success(`Build approved · project ${result.project.status}`);
      void qc.invalidateQueries({ queryKey: ["studio-projects"] });
      void qc.invalidateQueries({ queryKey: ["studio-review", result.project.id] });
    },
    onError: (err) =>
      toast.error(err instanceof ApiError || err instanceof Error ? err.message : "Approve failed")
  });

  const exportM = useMutation({
    mutationFn: (opts: { kind: string; format: string }) => {
      if (!selected?.id) throw new Error("Select a project first");
      return studioApi.exportProject(selected.id, opts);
    },
    onSuccess: (result) => {
      downloadExport(result);
      toast.success(`Exported ${result.filename}`);
    },
    onError: (err) =>
      toast.error(err instanceof ApiError || err instanceof Error ? err.message : "Export failed")
  });

  const generateSourceM = useMutation({
    mutationFn: () => {
      if (!selected?.id) throw new Error("Select a project first");
      return studioApi.generateSource(selected.id, { sync: true });
    },
    onSuccess: (result) => {
      toast.success(
        result.build.status === "completed"
          ? `Source v${result.build.version} · ${result.build.file_count} files`
          : `Build ${result.build.status} · ${result.note}`
      );
      void qc.invalidateQueries({ queryKey: ["studio-projects"] });
      void qc.invalidateQueries({ queryKey: ["studio-build", result.project.id] });
      void qc.invalidateQueries({ queryKey: ["studio-artifacts", result.project.id] });
    },
    onError: (err) =>
      toast.error(
        err instanceof ApiError || err instanceof Error ? err.message : "Source generation failed"
      )
  });

  const retryBuildM = useMutation({
    mutationFn: () => {
      if (!selected?.id) throw new Error("Select a project first");
      return studioApi.retryBuild(selected.id, { sync: true });
    },
    onSuccess: (result) => {
      toast.success(`Retry v${result.build.version} · ${result.build.status}`);
      void qc.invalidateQueries({ queryKey: ["studio-build", result.project.id] });
      void qc.invalidateQueries({ queryKey: ["studio-artifacts", result.project.id] });
    },
    onError: (err) =>
      toast.error(err instanceof ApiError || err instanceof Error ? err.message : "Retry failed")
  });

  const [deployProvider, setDeployProvider] = useState("vps");
  const [deployDomain, setDeployDomain] = useState("");
  const [deployDomainMode, setDeployDomainMode] = useState<"free_subdomain" | "custom">(
    "free_subdomain"
  );
  const [deployEnv, setDeployEnv] = useState("production");
  const [showDeployLogs, setShowDeployLogs] = useState(false);
  const [liveLogLines, setLiveLogLines] = useState<string[]>([]);
  const [showDomainWizard, setShowDomainWizard] = useState(false);
  const [wizardHostname, setWizardHostname] = useState("");

  const domainsQ = useQuery({
    queryKey: ["domains"],
    queryFn: () => domainsApi.list(),
    staleTime: 60_000
  });

  const checklistQ = useQuery({
    queryKey: ["studio-launch-checklist", selected?.id],
    queryFn: () => studioApi.launchChecklist(selected!.id),
    enabled: Boolean(selected?.id),
    retry: false,
    refetchInterval: 30_000
  });

  const diagnosticsQ = useQuery({
    queryKey: ["studio-launch-diagnostics", selected?.id],
    queryFn: () => studioApi.launchDiagnostics(selected!.id),
    enabled: Boolean(selected?.id),
    retry: false,
    refetchInterval: 30_000
  });

  const wizardHost = wizardHostname || deployDomain || "";

  const domainWizardQ = useQuery({
    queryKey: ["studio-domain-wizard", selected?.id, wizardHost],
    queryFn: () => studioApi.domainWizard(selected!.id, wizardHost),
    enabled: Boolean(selected?.id && showDomainWizard && wizardHost.length >= 3),
    retry: false,
    refetchInterval: (q) => {
      const phase = q.state.data?.phase;
      if (phase === "ssl_active" || phase === "failed") return false;
      return 30_000;
    }
  });

  const deployM = useMutation({
    mutationFn: () => {
      if (!selected?.id) throw new Error("Select a project first");
      return studioApi.deploy(selected.id, {
        provider: deployProvider,
        domain_mode: deployDomainMode,
        domain: deployDomainMode === "custom" ? deployDomain || undefined : undefined,
        environment: deployEnv,
        sync: true
      });
    },
    onSuccess: (result) => {
      if (result.deployment.status === "waiting_for_domain") {
        toast.message(result.deployment.error || "Waiting for Domain", {
          description: "Deployment is not LIVE until DNS is reachable."
        });
      } else {
        toast.success(
          result.deployment.live
            ? `Live deploy v${result.deployment.version} · ${result.deployment.provider}`
            : `Deploy package v${result.deployment.version} · ${result.note}`
        );
      }
      setShowDeployLogs(true);
      void qc.invalidateQueries({ queryKey: ["studio-deployments", result.project.id] });
    },
    onError: (err) =>
      toast.error(err instanceof ApiError || err instanceof Error ? err.message : "Deploy failed")
  });

  const rollbackM = useMutation({
    mutationFn: () => {
      if (!selected?.id) throw new Error("Select a project first");
      return studioApi.rollback(selected.id, { sync: true });
    },
    onSuccess: (result) => {
      toast.success(result.note || "Rollback complete");
      setShowDeployLogs(true);
      void qc.invalidateQueries({ queryKey: ["studio-deployments", result.project.id] });
    },
    onError: (err) =>
      toast.error(err instanceof ApiError || err instanceof Error ? err.message : "Rollback failed")
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
  const review: ReviewManifest | undefined = reviewQ.data?.review;
  const reviewWarnings = review?.warnings || [];
  const build: StudioBuild | undefined = buildQ.data;
  const artifacts = artifactsQ.data;
  const deployments = deploymentsQ.data?.items || [];
  const currentDeploy: StudioDeployment | undefined =
    deployments.find((d) => d.id === deploymentsQ.data?.current_id) || deployments[0];

  useEffect(() => {
    if (!showDeployLogs || !selected?.id || !currentDeploy?.id) return;
    if (!["queued", "deploying"].includes(currentDeploy.status)) return;
    const token = getAccessToken();
    let es: EventSource | null = null;
    try {
      const streamPath = studioApi.deploymentStreamUrl(selected.id, currentDeploy.id);
      const qs = token ? `?access_token=${encodeURIComponent(token)}` : "";
      es = new EventSource(`${site.apiUrl}${streamPath}${qs}`);
      es.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          const line = `[${data.event || data.stage || "log"}] ${data.message || ""}`;
          setLiveLogLines((prev) => [...prev.slice(-200), line]);
        } catch {
          setLiveLogLines((prev) => [...prev.slice(-200), ev.data]);
        }
        void qc.invalidateQueries({ queryKey: ["studio-deployments", selected.id] });
      };
      es.onerror = () => {
        es?.close();
      };
    } catch {
      /* polling remains via deploymentsQ refetchInterval */
    }
    return () => {
      es?.close();
    };
  }, [showDeployLogs, selected?.id, currentDeploy?.id, currentDeploy?.status, qc]);

  function patchDraft(partial: Partial<ProductBlueprint>) {
    setDraft((prev) => ({ ...prev, ...partial }));
  }

  return (
    <div className="-mx-4 -mt-4 min-h-[calc(100vh-4rem)] bg-slate-950 px-4 py-6 text-slate-100 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
      <section className="relative overflow-hidden rounded-3xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-950 to-teal-950 p-6 sm:p-8">
        <div className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-teal-500/20 blur-3xl" />
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-300/80">
          THTWAAT Studio · Phase 10
        </p>
        <h1 className="mt-2 max-w-3xl text-3xl font-semibold tracking-tight text-white sm:text-4xl">
          One-Click Production Deployment
        </h1>
        <p className="mt-3 max-w-2xl text-sm text-slate-300">
          Deploy approved source builds only — never regenerate. VPS/Docker reuse the live platform
          stack; other targets export a planning package.
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

      {/* Review Center */}
      <section className="mt-6 rounded-3xl border border-teal-800/40 bg-gradient-to-br from-slate-900 via-slate-950 to-emerald-950/40 p-5 sm:p-6">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-white">Review Center</h2>
            <p className="text-sm text-slate-400">
              {review
                ? `${review.ready_to_approve ? "Ready to approve" : "Needs attention"} · ${review.estimate.complexity} · ~$${review.estimate.estimated_cost_usd} build · ~$${review.estimate.monthly_run_cost_usd}/mo run`
                : "Generate Infrastructure to unlock the full review dashboard"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              disabled={!selected || !review || exportM.isPending}
              onClick={() => exportM.mutate({ kind: "blueprint", format: "json" })}
            >
              <Download className="mr-2 h-4 w-4" />
              Export Blueprint
            </Button>
            <Button
              variant="secondary"
              disabled={!selected || !review || exportM.isPending}
              onClick={() => exportM.mutate({ kind: "build_plan", format: "markdown" })}
            >
              <Download className="mr-2 h-4 w-4" />
              Export Build Plan
            </Button>
            <Button
              variant="secondary"
              disabled={!selected || !review || exportM.isPending}
              onClick={() => exportM.mutate({ kind: "review", format: "pdf" })}
            >
              <Download className="mr-2 h-4 w-4" />
              Export PDF
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                const el = document.getElementById("studio-prompt");
                el?.scrollIntoView({ behavior: "smooth", block: "start" });
              }}
            >
              Back to Edit
            </Button>
            <Button
              className="bg-teal-600 text-white hover:bg-teal-500"
              disabled={!selected || !review?.ready_to_approve || approveM.isPending}
              onClick={() => approveM.mutate()}
            >
              {approveM.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Approving…
                </>
              ) : (
                <>
                  <CheckCircle2 className="mr-2 h-4 w-4" />
                  Approve Build
                </>
              )}
            </Button>
            <Button
              className="bg-emerald-600 text-white hover:bg-emerald-500"
              disabled={
                !selected ||
                selected.status !== "completed" ||
                generateSourceM.isPending ||
                (build?.status === "generating" || build?.status === "planning")
              }
              onClick={() => generateSourceM.mutate()}
            >
              {generateSourceM.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Generating…
                </>
              ) : (
                <>
                  <Sparkles className="mr-2 h-4 w-4" />
                  Generate Source
                </>
              )}
            </Button>
          </div>
        </div>

        {reviewQ.isLoading ? (
          <p className="flex items-center gap-2 text-sm text-slate-400">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading review…
          </p>
        ) : !review ? (
          <EmptyState
            title="Review not ready"
            description="Complete Blueprint → Compose → Frontend → Backend → AI → Infrastructure, then review here."
          />
        ) : (
          <div className="grid gap-6 xl:grid-cols-2">
            <div>
              <h3 className="mb-2 text-sm font-semibold text-white">Artifacts</h3>
              <ul className="space-y-2 text-sm">
                {review.artifacts.map((a) => (
                  <li
                    key={a.id}
                    className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2"
                  >
                    <span className="text-slate-100">
                      {a.label}
                      {a.version != null ? ` · v${a.version}` : ""}
                    </span>
                    <Badge tone={a.present ? "success" : "danger"}>
                      {a.present ? a.status : "missing"}
                    </Badge>
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h3 className="mb-2 text-sm font-semibold text-white">Build estimate</h3>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                  <p className="text-xs text-slate-500">Build time</p>
                  <p className="mt-1 font-medium text-teal-200">{review.estimate.estimated_build_time}</p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                  <p className="text-xs text-slate-500">Build cost</p>
                  <p className="mt-1 font-medium text-teal-200">${review.estimate.estimated_cost_usd}</p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                  <p className="text-xs text-slate-500">Files · Tables · APIs</p>
                  <p className="mt-1 text-slate-200">
                    {review.estimate.generated_files} · {review.estimate.database_tables} ·{" "}
                    {review.estimate.rest_apis}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                  <p className="text-xs text-slate-500">Workers · Jobs</p>
                  <p className="mt-1 text-slate-200">
                    {review.estimate.workers} · {review.estimate.background_jobs}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                  <p className="text-xs text-slate-500">AI / mo</p>
                  <p className="mt-1 text-slate-200">${review.estimate.ai_cost_monthly_usd}</p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                  <p className="text-xs text-slate-500">Infra / mo</p>
                  <p className="mt-1 text-slate-200">
                    ${review.estimate.infrastructure_cost_monthly_usd}
                  </p>
                </div>
              </div>
            </div>

            <div>
              <h3 className="mb-2 text-sm font-semibold text-white">Visual architecture</h3>
              <div className="space-y-2 rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-sm text-slate-300">
                <p>
                  <span className="text-slate-500">Pages · </span>
                  {review.architecture.pages.slice(0, 8).join(", ") || "—"}
                </p>
                <p>
                  <span className="text-slate-500">Routes · </span>
                  {review.architecture.routes.slice(0, 8).join(", ") || "—"}
                </p>
                <p>
                  <span className="text-slate-500">Database · </span>
                  {review.architecture.database.slice(0, 8).join(", ") || "—"}
                </p>
                <p>
                  <span className="text-slate-500">AI · </span>
                  {review.architecture.ai_providers.join(", ") || "—"}
                </p>
                <p>
                  <span className="text-slate-500">RBAC · </span>
                  {review.architecture.rbac.join(", ") || "—"}
                </p>
                <p>
                  <span className="text-slate-500">Deploy · </span>
                  {review.architecture.deployment_targets.join(", ") || "—"}
                </p>
                <p className="text-xs text-slate-500">
                  API endpoints: {review.architecture.api.length} · Knowledge:{" "}
                  {review.architecture.knowledge?.enabled ? "enabled" : "plan"}
                </p>
              </div>
              <ul className="mt-2 max-h-40 space-y-1 overflow-y-auto font-mono text-xs text-slate-500">
                {review.architecture.dependency_graph.slice(0, 12).map((e) => (
                  <li key={e.key}>
                    {e.label || e.key} ← {(e.depends_on || []).join(", ") || "root"}
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h3 className="mb-2 text-sm font-semibold text-white">Required secrets</h3>
              <ul className="max-h-64 space-y-2 overflow-y-auto text-sm">
                {review.required_secrets.map((s) => (
                  <li
                    key={s.id}
                    className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2"
                  >
                    <div>
                      <p className="font-medium text-slate-100">{s.label}</p>
                      <p className="text-xs text-slate-500">{s.keys.join(", ")}</p>
                    </div>
                    <Badge tone={s.required ? "warn" : "neutral"}>
                      {s.required ? "required" : "optional"}
                    </Badge>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {reviewWarnings.length > 0 && (
          <ul className="mt-4 space-y-2">
            {reviewWarnings.map((w) => (
              <li
                key={`rev-${w.code}-${w.message}`}
                className="flex items-start gap-2 rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2 text-sm"
              >
                <Badge tone={warningTone(w.severity)}>{w.severity}</Badge>
                <span className="text-slate-200">{w.message}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Software Factory */}
      <section className="mt-6 rounded-3xl border border-emerald-800/40 bg-gradient-to-br from-slate-900 via-slate-950 to-teal-950/50 p-5 sm:p-6">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-white">Software Factory</h2>
            <p className="text-sm text-slate-400">
              {build
                ? `v${build.version} · ${build.status} / ${build.stage} · ${build.file_count} files`
                : "Approve Build first, then Generate Source"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              disabled={!build?.retryable && build?.status !== "failed"}
              onClick={() => retryBuildM.mutate()}
            >
              Retry
            </Button>
            {artifacts?.download_available && selected?.id && (
              <Button
                variant="secondary"
                onClick={async () => {
                  try {
                    const token = getAccessToken();
                    const res = await fetch(
                      `${apiPaths.apiV2}/studio/projects/${selected.id}/artifacts/download`,
                      {
                        headers: token ? { Authorization: `Bearer ${token}` } : {}
                      }
                    );
                    if (!res.ok) throw new Error("Download failed");
                    const blob = await res.blob();
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = `${selected.title || "studio"}-source.zip`;
                    a.click();
                    URL.revokeObjectURL(url);
                  } catch (err) {
                    toast.error(err instanceof Error ? err.message : "Download failed");
                  }
                }}
              >
                <Download className="mr-2 h-4 w-4" />
                Download ZIP
              </Button>
            )}
          </div>
        </div>

        {!build ? (
          <EmptyState
            title="No source build yet"
            description="Complete Review Center approval, then click Generate Source."
          />
        ) : (
          <div className="grid gap-6 xl:grid-cols-2">
            <div>
              <h3 className="mb-2 text-sm font-semibold text-white">Agent status</h3>
              <ul className="max-h-72 space-y-2 overflow-y-auto text-sm">
                {Object.entries(build.agent_statuses || {}).map(([agent, st]) => (
                  <li
                    key={agent}
                    className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2"
                  >
                    <div>
                      <p className="font-medium capitalize text-slate-100">{agent}</p>
                      <p className="text-xs text-slate-500">{st.message || "—"}</p>
                    </div>
                    <Badge
                      tone={
                        st.status === "completed"
                          ? "success"
                          : st.status === "failed"
                            ? "danger"
                            : st.status === "running"
                              ? "warn"
                              : "neutral"
                      }
                    >
                      {st.status || "queued"}
                    </Badge>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="mb-2 text-sm font-semibold text-white">Logs</h3>
              <ul className="max-h-72 space-y-1 overflow-y-auto font-mono text-xs text-slate-400">
                {(build.logs || []).slice(-40).map((log, idx) => (
                  <li key={`${log.ts || idx}-${idx}`}>
                    [{String(log.event || log.message || "log")}]{" "}
                    {String(log.message || log.agent || "")}
                  </li>
                ))}
              </ul>
              {build.error && (
                <p className="mt-2 text-sm text-rose-300">{build.error}</p>
              )}
            </div>
            <div className="xl:col-span-2">
              <h3 className="mb-2 text-sm font-semibold text-white">Generated files</h3>
              <div className="mb-2 flex flex-wrap gap-1">
                {(artifacts?.tree_roots || []).map((root) => (
                  <Badge key={root} tone="neutral">
                    {root}
                  </Badge>
                ))}
              </div>
              <ul className="max-h-56 space-y-1 overflow-y-auto font-mono text-xs text-slate-400">
                {(build.file_manifest || []).slice(0, 80).map((f) => (
                  <li key={f.path} className="flex justify-between gap-2">
                    <span className="text-teal-200/90">{f.path}</span>
                    <span>
                      {f.agent}
                      {f.reuse ? " · reuse" : ""}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </section>

      {/* Deployment Center */}
      <section className="mt-6 rounded-3xl border border-cyan-800/40 bg-gradient-to-br from-slate-900 via-slate-950 to-cyan-950/40 p-5 sm:p-6">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-white">Deployment Center</h2>
            <p className="text-sm text-slate-400">
              {currentDeploy
                ? `v${currentDeploy.version} · ${currentDeploy.provider} · ${
                    currentDeploy.launch_status_label ||
                    (currentDeploy.live
                      ? "LIVE"
                      : currentDeploy.status === "waiting_for_domain"
                        ? "Waiting for DNS"
                        : currentDeploy.status === "provisioning_ssl"
                          ? "Provisioning SSL"
                          : currentDeploy.status === "failed"
                            ? "Failed"
                            : "Building")
                  }`
                : "Requires completed source build — Deploy never regenerates code"}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              className="bg-cyan-600 text-white hover:bg-cyan-500"
              disabled={!selected || build?.status !== "completed" || deployM.isPending || !canDelete}
              onClick={() => deployM.mutate()}
              title={!canDelete ? "Owners and admins only" : undefined}
            >
              {deployM.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Deploying…
                </>
              ) : (
                "Deploy"
              )}
            </Button>
            <Button
              variant="secondary"
              disabled={!currentDeploy || deployM.isPending || !canDelete}
              onClick={() => deployM.mutate()}
            >
              Redeploy
            </Button>
            <Button
              variant="secondary"
              disabled={deployments.length < 2 || rollbackM.isPending || !canDelete}
              onClick={() => rollbackM.mutate()}
            >
              Rollback
            </Button>
            <Button
              variant="secondary"
              disabled={!currentDeploy}
              onClick={() => {
                setShowDeployLogs(true);
                setLiveLogLines(
                  (currentDeploy?.logs || []).map(
                    (log) => `[${String(log.event || "log")}] ${String(log.message || "")}`
                  )
                );
              }}
            >
              View Logs
            </Button>
            {currentDeploy?.urls?.website && (
              <a
                href={currentDeploy.urls.website}
                target="_blank"
                rel="noreferrer"
                className={cn(buttonVariants({ variant: "secondary" }), "inline-flex")}
              >
                Open Website
              </a>
            )}
            {currentDeploy?.urls?.dashboard && (
              <a
                href={currentDeploy.urls.dashboard}
                target="_blank"
                rel="noreferrer"
                className={cn(buttonVariants({ variant: "secondary" }), "inline-flex")}
              >
                Open Dashboard
              </a>
            )}
            <Button
              variant="secondary"
              type="button"
              onClick={() => {
                setDeployDomainMode("custom");
                setWizardHostname(
                  currentDeploy?.domain ||
                    deployDomain ||
                    ""
                );
                setShowDomainWizard(true);
              }}
            >
              Connect Custom Domain
            </Button>
          </div>
        </div>

        <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <label className="block space-y-1">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Deployment Target
            </span>
            <select
              value={deployProvider}
              onChange={(e) => setDeployProvider(e.target.value)}
              className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
            >
              {[
                "vps",
                "docker",
                "coolify",
                "railway",
                "render",
                "digitalocean",
                "aws_ecs",
                "azure",
                "google_cloud_run",
                "kubernetes"
              ].map((p) => (
                <option key={p} value={p}>
                  {p === "vps" ? "Current VPS" : p === "docker" ? "Docker Compose" : p === "azure" ? "Azure Container Apps" : p}
                </option>
              ))}
            </select>
          </label>
          <label className="block space-y-1">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Environment
            </span>
            <select
              value={deployEnv}
              onChange={(e) => setDeployEnv(e.target.value)}
              className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
            >
              {["production", "staging", "preview"].map((e) => (
                <option key={e} value={e}>
                  {e}
                </option>
              ))}
            </select>
          </label>
          <label className="block space-y-1 sm:col-span-2 lg:col-span-1">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Domain
            </span>
            <div className="space-y-2 rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm">
              <label className="flex items-start gap-2 text-slate-200">
                <input
                  type="radio"
                  name="deploy-domain-mode"
                  checked={deployDomainMode === "free_subdomain"}
                  onChange={() => setDeployDomainMode("free_subdomain")}
                  className="mt-1"
                />
                <span>
                  Use a free *.thtwaat.com subdomain
                  <span className="mt-0.5 block text-xs text-slate-500">
                    {currentDeploy?.free_subdomain ||
                      (selected
                        ? `Auto: ${selected.title
                            .toLowerCase()
                            .replace(/[^a-z0-9]+/g, "-")
                            .slice(0, 28)}.thtwaat.com`
                        : "Allocated per project")}
                  </span>
                </span>
              </label>
              <label className="flex items-start gap-2 text-slate-200">
                <input
                  type="radio"
                  name="deploy-domain-mode"
                  checked={deployDomainMode === "custom"}
                  onChange={() => setDeployDomainMode("custom")}
                  className="mt-1"
                />
                <span>Connect an existing custom domain</span>
              </label>
              {deployDomainMode === "custom" && (
                <>
                  <select
                    value={deployDomain}
                    onChange={(e) => setDeployDomain(e.target.value)}
                    className="w-full rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-slate-100"
                  >
                    <option value="">Select from Domain Manager</option>
                    {(domainsQ.data || []).map((d) => (
                      <option key={d.id} value={d.hostname}>
                        {d.hostname} · {d.ssl_status || d.status}
                      </option>
                    ))}
                  </select>
                  <input
                    value={deployDomain}
                    onChange={(e) => setDeployDomain(e.target.value)}
                    placeholder="or type registered custom domain"
                    className="w-full rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-slate-100"
                  />
                </>
              )}
            </div>
          </label>
          <div className="rounded-xl border border-slate-800 bg-slate-950/50 px-3 py-2 text-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">SSL</p>
            <p className="mt-1 text-slate-200">
              {currentDeploy?.ssl?.ssl_enabled
                ? String(currentDeploy.ssl.status || "enabled")
                : currentDeploy?.status === "waiting_for_domain"
                  ? "Deferred until DNS validation"
                  : deployDomainMode === "custom"
                    ? "Enabled only after DNS validation"
                    : "After free subdomain DNS is reachable"}
            </p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-950/50 px-3 py-2 text-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Build Version</p>
            <p className="mt-1 text-slate-200">
              {currentDeploy?.build_version != null
                ? `build v${currentDeploy.build_version}`
                : build?.version != null
                  ? `build v${build.version}`
                  : "—"}
              {currentDeploy?.commit_sha
                ? ` · ${String(currentDeploy.commit_sha).slice(0, 12)}`
                : ""}
            </p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-950/50 px-3 py-2 text-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Health</p>
            <p className="mt-1 text-slate-200">
              {currentDeploy?.health
                ? Object.entries(currentDeploy.health)
                    .filter(([, v]) => v && typeof v === "object" && "ok" in (v as object))
                    .map(([k, v]) => `${k}:${(v as { ok?: boolean }).ok === false ? "fail" : "ok"}`)
                    .slice(0, 4)
                    .join(" · ") || "—"
                : "—"}
            </p>
          </div>
        </div>

        {!currentDeploy ? (
          <EmptyState
            title="No deployments yet"
            description="Generate Source, then Deploy to VPS/Docker (live overlay) or export a planning package for other providers."
          />
        ) : (
          <div className="grid gap-6 xl:grid-cols-2">
            <div>
              {(showDeployLogs || (currentDeploy.logs || []).length > 0) && (
                <>
                  <h3 className="mb-2 text-sm font-semibold text-white">Live Logs</h3>
                  <ul className="max-h-56 space-y-1 overflow-y-auto rounded-xl border border-slate-800 bg-black/40 p-3 font-mono text-xs text-slate-400">
                    {(liveLogLines.length
                      ? liveLogLines
                      : (currentDeploy.logs || []).map(
                          (log) => `[${String(log.event || "log")}] ${String(log.message || "")}`
                        )
                    )
                      .slice(-80)
                      .map((line, idx) => (
                        <li key={`${idx}-${line.slice(0, 24)}`}>{line}</li>
                      ))}
                  </ul>
                </>
              )}
              {currentDeploy.error && (
                <p className="mt-2 text-sm text-rose-300">{currentDeploy.error}</p>
              )}
              {currentDeploy.status === "waiting_for_domain" && (
                <div className="mt-3 rounded-xl border border-amber-700/50 bg-amber-950/40 p-3 text-sm text-amber-100">
                  <p className="font-medium">
                    {currentDeploy.error || "This domain is not registered."}
                  </p>
                  <ul className="mt-2 list-disc space-y-1 pl-4 text-amber-100/80">
                    <li>Use a free *.thtwaat.com subdomain</li>
                    <li>Connect an existing custom domain that already resolves in DNS</li>
                  </ul>
                  <p className="mt-2 text-xs text-amber-200/70">
                    SSL stays disabled until DNS validation succeeds. Status remains Waiting for
                    Domain until the hostname is reachable.
                  </p>
                </div>
              )}
            </div>
            <div>
              <h3 className="mb-2 text-sm font-semibold text-white">History</h3>
              <ul className="max-h-64 space-y-2 overflow-y-auto text-sm">
                {deployments.map((d) => (
                  <li
                    key={d.id}
                    className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2"
                  >
                    <div>
                      <p className="text-slate-100">
                        v{d.version} · {d.provider}
                        {d.is_current ? " · current" : ""}
                      </p>
                      <p className="text-xs text-slate-500">
                        {d.stage} · {d.duration_ms}ms
                        {d.live ? " · live" : ""}
                        {d.builder ? ` · ${d.builder}` : ""}
                        {d.commit_sha ? ` · ${String(d.commit_sha).slice(0, 8)}` : ""}
                      </p>
                    </div>
                    <Badge
                      tone={
                        d.status === "completed"
                          ? "success"
                          : d.status === "failed"
                            ? "danger"
                            : "warn"
                      }
                    >
                      {d.status}
                    </Badge>
                  </li>
                ))}
              </ul>
              {(currentDeploy.instructions || []).length > 0 && (
                <ul className="mt-3 space-y-1 text-xs text-slate-400">
                  {currentDeploy.instructions.slice(0, 6).map((line) => (
                    <li key={line}>• {line}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </section>

      {/* Launch Checklist */}
      <section className="mt-6 rounded-3xl border border-emerald-900/40 bg-gradient-to-br from-slate-900 via-slate-950 to-emerald-950/30 p-5 sm:p-6">
        <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 className="text-lg font-semibold text-white">Launch Checklist</h2>
            <p className="text-sm text-slate-400">
              {checklistQ.data
                ? `${checklistQ.data.passed}/${checklistQ.data.total} ready${
                    checklistQ.data.ready ? " · Ready to launch" : ""
                  }`
                : "Verify platform prerequisites before go-live"}
            </p>
          </div>
          <Button
            variant="secondary"
            disabled={!selected || checklistQ.isFetching}
            onClick={() => void checklistQ.refetch()}
          >
            Refresh
          </Button>
        </div>
        <ul className="grid gap-2 sm:grid-cols-2">
          {(checklistQ.data?.items || []).map((item) => (
            <li
              key={item.key}
              className="flex items-start gap-2 rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2 text-sm"
            >
              <span className={item.ok ? "text-emerald-400" : "text-amber-400"}>
                {item.ok ? "✓" : "○"}
              </span>
              <span>
                <span className="font-medium text-slate-100">{item.title}</span>
                {item.detail ? (
                  <span className="mt-0.5 block text-xs text-slate-500">{item.detail}</span>
                ) : null}
              </span>
            </li>
          ))}
          {!checklistQ.data && !checklistQ.isLoading ? (
            <li className="text-sm text-slate-500">Select a project to load checklist.</li>
          ) : null}
        </ul>
      </section>

      {/* Domain Wizard */}
      {showDomainWizard && (
        <section className="mt-6 rounded-3xl border border-violet-900/40 bg-gradient-to-br from-slate-900 via-slate-950 to-violet-950/30 p-5 sm:p-6">
          <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
            <div>
              <h2 className="text-lg font-semibold text-white">Domain Wizard</h2>
              <p className="text-sm text-slate-400">
                Pending DNS → DNS Verified → SSL Issuing → SSL Active · auto-refresh 30s
              </p>
            </div>
            <Button variant="secondary" onClick={() => setShowDomainWizard(false)}>
              Close
            </Button>
          </div>
          <div className="mb-3 flex flex-wrap gap-2">
            <input
              value={wizardHostname}
              onChange={(e) => setWizardHostname(e.target.value)}
              placeholder="custom.example.com"
              className="min-w-[240px] flex-1 rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
            />
            <Button
              disabled={!selected || wizardHostname.trim().length < 3}
              onClick={() => {
                void studioApi
                  .startDomainWizard(selected!.id, {
                    hostname: wizardHostname.trim(),
                    auto_verify: true
                  })
                  .then(() => domainWizardQ.refetch())
                  .catch((err) =>
                    toast.error(err instanceof Error ? err.message : "Domain wizard failed")
                  );
              }}
            >
              Verify now
            </Button>
          </div>
          {domainWizardQ.data && (
            <div className="space-y-3">
              <p className="text-sm text-slate-200">
                Status:{" "}
                <strong className="text-violet-300">{domainWizardQ.data.phase_label}</strong>
                {domainWizardQ.data.ssl_status
                  ? ` · SSL ${domainWizardQ.data.ssl_status}`
                  : ""}
              </p>
              {(domainWizardQ.data.dns_records || []).length > 0 && (
                <div className="overflow-x-auto rounded-xl border border-slate-800">
                  <table className="w-full text-left text-xs text-slate-300">
                    <thead className="bg-slate-950 text-slate-500">
                      <tr>
                        <th className="px-3 py-2">Type</th>
                        <th className="px-3 py-2">Host</th>
                        <th className="px-3 py-2">Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      {domainWizardQ.data.dns_records.map((rec, idx) => (
                        <tr key={idx} className="border-t border-slate-800">
                          <td className="px-3 py-2 font-mono">
                            {String(rec.type || rec.record_type || "—")}
                          </td>
                          <td className="px-3 py-2 font-mono">
                            {String(rec.host || rec.name || "—")}
                          </td>
                          <td className="px-3 py-2 font-mono break-all">
                            {String(rec.value || rec.content || "—")}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </section>
      )}

      {/* Launch Diagnostics */}
      <section className="mt-6 rounded-3xl border border-amber-900/40 bg-gradient-to-br from-slate-900 via-slate-950 to-amber-950/20 p-5 sm:p-6">
        <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 className="text-lg font-semibold text-white">Launch Diagnostics</h2>
            <p className="text-sm text-slate-400">
              Overall:{" "}
              <span
                className={
                  diagnosticsQ.data?.overall === "healthy"
                    ? "text-emerald-400"
                    : diagnosticsQ.data?.overall === "failed"
                      ? "text-rose-400"
                      : "text-amber-300"
                }
              >
                {diagnosticsQ.data?.overall || "—"}
              </span>
            </p>
          </div>
          <Button
            variant="secondary"
            disabled={!selected || diagnosticsQ.isFetching}
            onClick={() => void diagnosticsQ.refetch()}
          >
            Refresh
          </Button>
        </div>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {(diagnosticsQ.data?.components || []).map((c) => (
            <div
              key={c.key}
              className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2 text-sm"
            >
              <p className="text-xs uppercase tracking-wide text-slate-500">{c.title}</p>
              <p
                className={
                  c.status === "healthy"
                    ? "mt-1 font-semibold text-emerald-400"
                    : c.status === "failed"
                      ? "mt-1 font-semibold text-rose-400"
                      : "mt-1 font-semibold text-amber-300"
                }
              >
                {c.status === "healthy"
                  ? "Healthy"
                  : c.status === "failed"
                    ? "Failed"
                    : "Warning"}
              </p>
            </div>
          ))}
        </div>
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
