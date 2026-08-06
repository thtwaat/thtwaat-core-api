"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  agentsApi,
  aiProvidersApi,
  knowledgeApi,
  onboardingApi,
  type OnboardingSession
} from "@/lib/services";
import { mergeProviderRows, providerHealthLabel, providerHealthTone } from "@/lib/provider-status";
import {
  AGENT_STARTERS,
  INDUSTRY_OPTIONS,
  ONBOARDING_PROVIDER_OPTIONS,
  ONBOARDING_UI_STEPS,
  TEAM_SIZE_OPTIONS,
  type OnboardingLocalDraft,
  type OnboardingUiStepId,
  buildAgentWebConfig,
  buildGeneratePrompt,
  checklistFromSession,
  clearOnboardingDraft,
  defaultOnboardingDraft,
  loadOnboardingDraft,
  nextUiStep,
  onboardingProgressPercent,
  prevUiStep,
  saveOnboardingDraft,
  sessionStepDone,
  starterPrompt,
  uiStepFromBackendCurrent,
  validateOnboardingUiStep
} from "@/lib/onboarding";
import { cn } from "@/lib/utils";
import { EmptyState } from "@/components/ui/misc";
import { Badge, Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Label, Select, Textarea } from "@/components/ui/input";

type UploadRow = {
  name: string;
  progress: number;
  status: "uploading" | "indexing" | "ready" | "error";
  error?: string;
};

function toneClass(tone: string) {
  if (tone === "success") return "bg-emerald-100 text-emerald-800";
  if (tone === "warn") return "bg-amber-100 text-amber-900";
  if (tone === "danger") return "bg-red-100 text-red-800";
  return "bg-slate-100 text-slate-700";
}

export default function OnboardingWizardPage() {
  const router = useRouter();
  const [session, setSession] = useState<OnboardingSession | null>(null);
  const [draft, setDraft] = useState<OnboardingLocalDraft>(() => defaultOnboardingDraft());
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploads, setUploads] = useState<UploadRow[]>([]);
  const [docQuery, setDocQuery] = useState("");
  const [searchHits, setSearchHits] = useState<
    Array<{ text: string; score?: number; document_name?: string }>
  >([]);
  const [embedCode, setEmbedCode] = useState("");
  const [previewUrl, setPreviewUrl] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const autosaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const providersQ = useQuery({
    queryKey: ["onboarding-ai-providers"],
    queryFn: aiProvidersApi.list,
    enabled: draft.uiStep === 3
  });
  const healthQ = useQuery({
    queryKey: ["onboarding-ai-health"],
    queryFn: aiProvidersApi.health,
    enabled: draft.uiStep === 3,
    refetchInterval: 60_000
  });

  const providerRows = useMemo(
    () =>
      mergeProviderRows(
        providersQ.data?.providers || [],
        healthQ.data || {},
        providersQ.data?.default
      ),
    [providersQ.data, healthQ.data]
  );

  const recommendedProvider = providersQ.data?.default || "auto";

  const patchDraft = useCallback((partial: Partial<OnboardingLocalDraft>) => {
    setDraft((prev) => {
      const next = { ...prev, ...partial };
      saveOnboardingDraft(next);
      return next;
    });
  }, []);

  const applySession = useCallback(
    (next: OnboardingSession, preferUi?: OnboardingUiStepId) => {
      setSession(next);
      setDraft((prev) => {
        const companyDraft = (next.draft_data?.company || {}) as Record<string, unknown>;
        const uiDraft = (next.draft_data?.ui || {}) as Partial<OnboardingLocalDraft>;
        const merged: OnboardingLocalDraft = {
          ...prev,
          ...uiDraft,
          version: 1,
          displayName:
            (uiDraft.displayName as string) ||
            (companyDraft.display_name as string) ||
            (companyDraft.name as string) ||
            prev.displayName,
          industry: (uiDraft.industry as string) || (companyDraft.industry as string) || prev.industry,
          checklist: checklistFromSession(next),
          uiStep: preferUi || prev.uiStep || uiStepFromBackendCurrent(next.current_step)
        };
        saveOnboardingDraft(merged);
        return merged;
      });
      if (next.status === "completed") {
        clearOnboardingDraft();
      }
    },
    []
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      const local = loadOnboardingDraft();
      if (local) setDraft(local);
      try {
        let me = await onboardingApi.me();
        if (me.status === "paused") {
          me = await onboardingApi.resume();
        }
        if (cancelled) return;
        if (me.status === "completed") {
          clearOnboardingDraft();
          router.replace("/app");
          return;
        }
        applySession(me, local?.uiStep || uiStepFromBackendCurrent(me.current_step));
      } catch (err) {
        if (cancelled) return;
        const message = err instanceof Error ? err.message : "Could not load onboarding";
        // Legacy accounts without a session can continue via Agent Builder
        if (message.toLowerCase().includes("no onboarding") || message.includes("404")) {
          setError(null);
          setSession(null);
          if (local) setDraft(local);
        } else if (message.toLowerCase().includes("paused")) {
          try {
            const resumed = await onboardingApi.resume();
            if (!cancelled) applySession(resumed);
          } catch (resumeErr) {
            setError(resumeErr instanceof Error ? resumeErr.message : message);
          }
        } else {
          setError(message);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [applySession, router]);

  // Debounced server autosave of UI draft
  useEffect(() => {
    if (!session || session.status !== "in_progress") return;
    if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    autosaveTimer.current = setTimeout(() => {
      void onboardingApi
        .autosave({
          draft: {
            ui: {
              uiStep: draft.uiStep,
              provider: draft.provider,
              model: draft.model,
              industry: draft.industry,
              teamSize: draft.teamSize,
              logoUrl: draft.logoUrl,
              displayName: draft.displayName,
              agentStarterId: draft.agentStarterId,
              agentName: draft.agentName
            }
          }
        })
        .then((s) => setSession(s))
        .catch(() => {
          /* local draft still saved */
        });
    }, 800);
    return () => {
      if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    };
  }, [draft, session?.id, session?.status]);

  async function ensureStep(
    current: OnboardingSession,
    step: string,
    data: Record<string, unknown> = {}
  ): Promise<OnboardingSession> {
    if (sessionStepDone(current, step)) return current;
    const action = await onboardingApi.completeStep(step, data);
    setSession(action.session);
    return action.session;
  }

  async function ensureSkip(
    current: OnboardingSession,
    step: string,
    reason: string
  ): Promise<OnboardingSession> {
    if (sessionStepDone(current, step)) return current;
    const action = await onboardingApi.skipStep(step, reason);
    setSession(action.session);
    return action.session;
  }

  async function onSkipSetup() {
    setBusy(true);
    try {
      if (session && session.status === "in_progress") {
        await onboardingApi.pause();
      }
      patchDraft({ skipped: true });
      toast.message("You can resume setup anytime from Settings or /app/onboarding");
      router.replace("/app");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not pause onboarding");
    } finally {
      setBusy(false);
    }
  }

  async function goNext() {
    const validation = validateOnboardingUiStep(draft.uiStep, draft);
    if (!validation.ok) {
      toast.error(validation.errors[0] || "Please fix the form");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      let nextSession = session;

      if (draft.uiStep === 2 && nextSession) {
        nextSession = await ensureStep(nextSession, "create_company", {
          name: draft.displayName.trim(),
          display_name: draft.displayName.trim(),
          industry: draft.industry || null,
          logo_url: draft.logoUrl.trim() || null,
          settings: { team_size: draft.teamSize || null }
        });
        patchDraft({ checklist: { ...draft.checklist, workspace: true } });
        toast.success("Workspace saved");
      }

      if (draft.uiStep === 3 && nextSession) {
        nextSession = await ensureStep(nextSession, "choose_plan", { stay_free: true });
        await onboardingApi.autosave({
          step: "choose_plan",
          draft: { provider: draft.provider, model: draft.model }
        });
        patchDraft({ checklist: { ...draft.checklist, provider: true } });
        toast.success("Provider preference saved");
      }

      if (draft.uiStep === 4 && nextSession) {
        const starter = AGENT_STARTERS.find((s) => s.id === draft.agentStarterId);
        const name =
          draft.agentName.trim() ||
          `${draft.displayName.trim() || "My"} ${starter?.name || "Agent"}`.slice(0, 80);
        if (!sessionStepDone(nextSession, "create_ai_agent")) {
          const action = await onboardingApi.completeStep("create_ai_agent", {
            name,
            description: starter?.description,
            system_prompt_template: starterPrompt(draft.agentStarterId),
            web_config: buildAgentWebConfig({ ...draft, agentName: name })
          });
          nextSession = action.session;
          setSession(nextSession);
        }
        patchDraft({
          agentName: name,
          checklist: { ...draft.checklist, agent: true }
        });
        toast.success("First agent created");
      }

      if (draft.uiStep === 5 && nextSession) {
        if (uploads.some((u) => u.status === "ready" || u.status === "indexing")) {
          nextSession = await ensureStep(nextSession, "upload_knowledge", {
            knowledge_base_id: nextSession.resource_ids?.knowledge_base_id,
            name: `${draft.agentName || "Onboarding"} Knowledge`
          });
          patchDraft({ checklist: { ...draft.checklist, knowledge: true } });
          toast.success("Knowledge attached");
        } else {
          nextSession = await ensureSkip(nextSession, "upload_knowledge", "Skipped during first-time setup");
          toast.message("Knowledge step skipped — add docs anytime");
        }
      }

      if (draft.uiStep === 6 && nextSession) {
        nextSession = await ensureSkip(nextSession, "choose_template", "Using starter agent from onboarding");
        if (!sessionStepDone(nextSession, "generate_product")) {
          const gen = await onboardingApi.completeStep("generate_product", {
            prompt: buildGeneratePrompt(draft),
            auto_publish: false
          });
          nextSession = gen.session;
          setSession(nextSession);
          if (typeof gen.result.preview_url === "string") setPreviewUrl(gen.result.preview_url);
        }
        nextSession = await ensureStep(nextSession, "preview", {});
        let pubResult: Record<string, unknown> = {};
        if (!sessionStepDone(nextSession, "publish")) {
          const pub = await onboardingApi.completeStep("publish", {});
          nextSession = pub.session;
          pubResult = pub.result;
          setSession(nextSession);
        }

        const agentId = String(nextSession.resource_ids?.agent_id || "");
        if (agentId) {
          try {
            const embed = await agentsApi.embed(agentId);
            const code =
              (embed.embed_code as string) ||
              (embed.snippet as string) ||
              (embed.html as string) ||
              Object.values(embed).find((v) => typeof v === "string" && String(v).includes("<")) ||
              "";
            setEmbedCode(typeof code === "string" ? code : "");
            const widget = await agentsApi.widget(agentId).catch(() => null);
            if (widget && typeof widget.preview_url === "string") {
              setPreviewUrl(widget.preview_url as string);
            }
          } catch {
            /* embed optional if publish already returned snippet */
          }
        }
        if (!embedCode && typeof pubResult.widget_snippet === "string") {
          setEmbedCode(String(pubResult.widget_snippet));
        }
        patchDraft({ checklist: { ...draft.checklist, widget: true } });
        toast.success("Widget ready");
      }

      const nxt = nextUiStep(draft.uiStep);
      if (nxt) patchDraft({ uiStep: nxt });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Could not continue";
      setError(message);
      toast.error(message);
    } finally {
      setBusy(false);
    }
  }

  async function goBack() {
    const prev = prevUiStep(draft.uiStep);
    if (prev) patchDraft({ uiStep: prev });
  }

  async function finishGoLive() {
    setBusy(true);
    try {
      let nextSession = session;
      if (nextSession) {
        nextSession = await ensureSkip(nextSession, "connect_domain", "Using platform host for now");
        if (!sessionStepDone(nextSession, "go_live")) {
          const action = await onboardingApi.completeStep("go_live", {
            publish_branding: true,
            notes: "Completed via SaaS first-time wizard"
          });
          nextSession = action.session;
          setSession(nextSession);
        }
      }
      clearOnboardingDraft();
      toast.success("You're live — welcome to THTWAAT");
      router.replace("/app");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not finish onboarding");
    } finally {
      setBusy(false);
    }
  }

  async function handleFiles(files: FileList | File[]) {
    const list = Array.from(files);
    if (!list.length) return;
    for (const file of list) {
      setUploads((prev) => [...prev, { name: file.name, progress: 0, status: "uploading" }]);
      try {
        const kbId = session?.resource_ids?.knowledge_base_id
          ? String(session.resource_ids.knowledge_base_id)
          : undefined;
        const action = await onboardingApi.uploadKnowledgeWithProgress(
          file,
          (percent) => {
            setUploads((prev) =>
              prev.map((row) =>
                row.name === file.name && row.status === "uploading"
                  ? { ...row, progress: percent }
                  : row
              )
            );
          },
          kbId
        );
        setSession(action.session);
        setUploads((prev) =>
          prev.map((row) =>
            row.name === file.name
              ? {
                  ...row,
                  progress: 100,
                  status: action.result.document_status === "ready" ? "ready" : "indexing"
                }
              : row
          )
        );
        toast.success(`Uploaded ${file.name}`);
      } catch (err) {
        setUploads((prev) =>
          prev.map((row) =>
            row.name === file.name
              ? {
                  ...row,
                  status: "error",
                  error: err instanceof Error ? err.message : "Upload failed"
                }
              : row
          )
        );
        toast.error(err instanceof Error ? err.message : "Upload failed");
      }
    }
  }

  async function runKnowledgeSearch() {
    const kbId = session?.resource_ids?.knowledge_base_id;
    if (!kbId || !docQuery.trim()) {
      toast.message("Upload at least one document first");
      return;
    }
    try {
      const res = await knowledgeApi.search(String(kbId), docQuery.trim());
      setSearchHits(res.results || []);
      if (!(res.results || []).length) toast.message("No matches yet — indexing may still be running");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Search failed");
    }
  }

  async function copyEmbed() {
    if (!embedCode) {
      toast.error("Embed code not available yet");
      return;
    }
    await navigator.clipboard.writeText(embedCode);
    toast.success("Embed code copied");
  }

  if (loading) {
    return (
      <div className="grid min-h-screen place-items-center bg-canvas text-sm text-muted" role="status">
        Loading onboarding…
      </div>
    );
  }

  if (!session && error) {
    return (
      <div className="mx-auto max-w-lg space-y-4 px-4 py-16">
        <EmptyState title="Onboarding unavailable" description={error} />
        <div className="flex gap-2">
          <Button onClick={() => router.replace("/app")}>Go to Dashboard</Button>
          <Button variant="secondary" onClick={() => router.replace("/app/agents/new")}>
            Open Agent Builder
          </Button>
        </div>
      </div>
    );
  }

  const stepMeta = ONBOARDING_UI_STEPS[draft.uiStep - 1];
  const progress = onboardingProgressPercent(draft.uiStep);

  return (
    <div className="min-h-screen bg-canvas">
      <header className="border-b border-line bg-panel">
        <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-3 px-4 py-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted">THTWAAT setup</p>
            <h1 className="text-lg font-semibold text-ink">{stepMeta?.title}</h1>
          </div>
          <div className="flex items-center gap-2">
            {session?.progress && (
              <Badge tone="brand">
                Backend {Math.round(session.progress.percent_complete)}%
              </Badge>
            )}
            <Button variant="ghost" onClick={() => void onSkipSetup()} disabled={busy}>
              Skip for now
            </Button>
          </div>
        </div>
        <div className="mx-auto max-w-4xl px-4 pb-4">
          <div
            className="h-2 w-full overflow-hidden rounded-full bg-slate-100"
            role="progressbar"
            aria-valuenow={progress}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Onboarding progress"
          >
            <div className="h-full rounded-full bg-brand transition-all" style={{ width: `${progress}%` }} />
          </div>
          <ol className="mt-3 flex flex-wrap gap-2" aria-label="Setup steps">
            {ONBOARDING_UI_STEPS.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  className={cn(
                    "rounded-full px-2.5 py-1 text-xs font-medium",
                    s.id === draft.uiStep
                      ? "bg-brand text-white"
                      : s.id < draft.uiStep
                        ? "bg-brand-soft text-brand-dark"
                        : "bg-slate-100 text-muted"
                  )}
                  aria-current={s.id === draft.uiStep ? "step" : undefined}
                  onClick={() => s.id < draft.uiStep && patchDraft({ uiStep: s.id })}
                >
                  {s.id}. {s.short}
                </button>
              </li>
            ))}
          </ol>
        </div>
      </header>

      <main className="mx-auto max-w-4xl space-y-6 px-4 py-8" aria-live="polite">
        {error && (
          <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
            {error}
          </p>
        )}

        {!session && (
          <EmptyState
            title="No guided session yet"
            description="This account was created before onboarding. You can still configure providers and create an agent from the dashboard, or start fresh with a new signup."
          />
        )}

        {draft.uiStep === 1 && (
          <Card className="space-y-4 p-6">
            <CardHeader
              title="Welcome to THTWAAT"
              description="Launch a working AI agent for your website in about 10–15 minutes."
            />
            <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
              <li>Customer support, sales, and FAQ agents</li>
              <li>Knowledge-grounded answers from your docs</li>
              <li>Embeddable website widget</li>
            </ul>
            <p className="text-sm text-muted">
              Estimated setup time:{" "}
              <strong className="text-ink">
                {session?.progress?.estimated_minutes_remaining ?? 15} minutes
              </strong>
            </p>
            <p className="text-xs text-muted">
              Tip: progress autosaves. You can leave and resume later from this page.
            </p>
          </Card>
        )}

        {draft.uiStep === 2 && (
          <Card className="space-y-4 p-6">
            <CardHeader
              title="Workspace"
              description="Refine your company profile. Company was created at signup — this updates the same record."
            />
            <div>
              <Label htmlFor="company-name">Company name</Label>
              <Input
                id="company-name"
                value={draft.displayName}
                onChange={(e) => patchDraft({ displayName: e.target.value })}
                aria-required
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="industry">Industry</Label>
                <Select
                  id="industry"
                  value={draft.industry}
                  onChange={(e) => patchDraft({ industry: e.target.value })}
                >
                  <option value="">Select industry</option>
                  {INDUSTRY_OPTIONS.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label htmlFor="team-size">Team size</Label>
                <Select
                  id="team-size"
                  value={draft.teamSize}
                  onChange={(e) => patchDraft({ teamSize: e.target.value })}
                >
                  <option value="">Select size</option>
                  {TEAM_SIZE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
            <div>
              <Label htmlFor="logo-url">Logo URL (optional)</Label>
              <Input
                id="logo-url"
                type="url"
                placeholder="https://…"
                value={draft.logoUrl}
                onChange={(e) => patchDraft({ logoUrl: e.target.value })}
              />
            </div>
          </Card>
        )}

        {draft.uiStep === 3 && (
          <Card className="space-y-4 p-6">
            <CardHeader
              title="AI Provider"
              description="Choose how the gateway should route your first agent. Keys stay in the platform environment — BYOK is not part of onboarding."
            />
            <div className="grid gap-3 sm:grid-cols-2">
              {ONBOARDING_PROVIDER_OPTIONS.map((opt) => {
                const row = providerRows.find((r) => r.name === opt.value);
                const selected = draft.provider === opt.value;
                const recommended = opt.value === "auto" || opt.value === recommendedProvider;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => patchDraft({ provider: opt.value })}
                    className={cn(
                      "rounded-2xl border p-4 text-left transition",
                      selected ? "border-brand bg-brand-soft" : "border-line bg-panel hover:border-brand/40"
                    )}
                    aria-pressed={selected}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-ink">{opt.label}</span>
                      {recommended && <Badge tone="success">Recommended</Badge>}
                    </div>
                    {opt.value !== "auto" && (
                      <p className="mt-2 text-xs text-muted">
                        Health:{" "}
                        <span className={cn("rounded px-1.5 py-0.5", toneClass(providerHealthTone(row?.status)))}>
                          {providerHealthLabel(row?.status)}
                        </span>
                        {row?.isDefault ? " · Connected default" : ""}
                      </p>
                    )}
                    {opt.value === "auto" && (
                      <p className="mt-2 text-xs text-muted">
                        Uses the platform default ({recommendedProvider}) with health-aware routing.
                      </p>
                    )}
                  </button>
                );
              })}
            </div>
            {(providersQ.isError || healthQ.isError) && (
              <p className="text-sm text-amber-800">
                Provider status temporarily unavailable — you can still continue with Auto.
              </p>
            )}
            <p className="text-xs text-muted">
              Full status board:{" "}
              <Link className="text-brand" href="/app/providers">
                AI Providers
              </Link>
            </p>
          </Card>
        )}

        {draft.uiStep === 4 && (
          <Card className="space-y-4 p-6">
            <CardHeader
              title="Create your first agent"
              description="Starter templates reuse the same Agent Builder fields and create_ai_agent onboarding step."
            />
            <div className="grid gap-3 sm:grid-cols-2">
              {AGENT_STARTERS.map((starter) => (
                <button
                  key={starter.id}
                  type="button"
                  onClick={() =>
                    patchDraft({
                      agentStarterId: starter.id,
                      agentName: draft.agentName || starter.name
                    })
                  }
                  className={cn(
                    "rounded-2xl border p-4 text-left",
                    draft.agentStarterId === starter.id
                      ? "border-brand bg-brand-soft"
                      : "border-line hover:border-brand/40"
                  )}
                  aria-pressed={draft.agentStarterId === starter.id}
                >
                  <p className="font-medium text-ink">{starter.name}</p>
                  <p className="mt-1 text-xs text-muted">{starter.description}</p>
                </button>
              ))}
            </div>
            <div>
              <Label htmlFor="agent-name">Agent name</Label>
              <Input
                id="agent-name"
                value={draft.agentName}
                onChange={(e) => patchDraft({ agentName: e.target.value })}
                placeholder="Support Assistant"
              />
            </div>
            <Textarea
              readOnly
              aria-label="System prompt preview"
              value={starterPrompt(draft.agentStarterId)}
              className="min-h-[100px] text-sm"
            />
            <p className="text-xs text-muted">
              Need the full 7-step builder later?{" "}
              <Link className="text-brand" href="/app/agents/new">
                Open Agent Builder
              </Link>
            </p>
          </Card>
        )}

        {draft.uiStep === 5 && (
          <Card className="space-y-4 p-6">
            <CardHeader
              title="Knowledge"
              description="Optional. Drag & drop docs — uploads use the onboarding knowledge helper and Knowledge module APIs."
            />
            <div
              className={cn(
                "rounded-2xl border border-dashed px-6 py-10 text-center transition",
                dragOver ? "border-brand bg-brand-soft" : "border-line bg-canvas"
              )}
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                void handleFiles(e.dataTransfer.files);
              }}
              role="region"
              aria-label="Document upload dropzone"
            >
              <p className="font-medium text-ink">Drop files here</p>
              <p className="mt-1 text-sm text-muted">PDF, TXT, MD, DOCX</p>
              <Button
                className="mt-4"
                variant="secondary"
                type="button"
                onClick={() => fileInputRef.current?.click()}
              >
                Browse files
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                className="sr-only"
                multiple
                onChange={(e) => e.target.files && void handleFiles(e.target.files)}
                aria-label="Choose knowledge files"
              />
            </div>
            {uploads.length === 0 ? (
              <EmptyState
                title="No documents yet"
                description="You can skip this step and add knowledge later from /app/knowledge."
              />
            ) : (
              <ul className="space-y-2" aria-label="Upload progress">
                {uploads.map((row) => (
                  <li
                    key={`${row.name}-${row.status}`}
                    className="rounded-xl border border-line bg-panel px-3 py-2 text-sm"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate font-medium text-ink">{row.name}</span>
                      <Badge
                        tone={
                          row.status === "error"
                            ? "danger"
                            : row.status === "ready"
                              ? "success"
                              : "warn"
                        }
                      >
                        {row.status}
                      </Badge>
                    </div>
                    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
                      <div
                        className="h-full bg-brand transition-all"
                        style={{ width: `${row.progress}%` }}
                      />
                    </div>
                    {row.error && <p className="mt-1 text-xs text-red-700">{row.error}</p>}
                  </li>
                ))}
              </ul>
            )}
            <div className="flex flex-wrap gap-2">
              <Input
                placeholder="Search uploaded knowledge"
                value={docQuery}
                onChange={(e) => setDocQuery(e.target.value)}
                aria-label="Search uploaded files"
              />
              <Button variant="secondary" type="button" onClick={() => void runKnowledgeSearch()}>
                Search
              </Button>
            </div>
            {searchHits.length > 0 && (
              <ul className="space-y-2 text-sm">
                {searchHits.map((hit, idx) => (
                  <li key={idx} className="rounded-xl border border-line px-3 py-2">
                    <p className="text-xs text-muted">{hit.document_name || "Document"}</p>
                    <p className="text-ink">{hit.text}</p>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        )}

        {draft.uiStep === 6 && (
          <Card className="space-y-4 p-6">
            <CardHeader
              title="Website widget"
              description="Continuing generates preview assets, publishes the agent, and shows the embed snippet from existing Widget APIs."
            />
            {!embedCode ? (
              <EmptyState
                title="Widget not generated yet"
                description="Click Continue to run generate → preview → publish on the onboarding facade, then load embed code."
              />
            ) : (
              <>
                <Label htmlFor="embed">Embed code</Label>
                <Textarea id="embed" readOnly value={embedCode} className="min-h-[140px] font-mono text-xs" />
                <div className="flex flex-wrap gap-2">
                  <Button type="button" onClick={() => void copyEmbed()}>
                    Copy embed code
                  </Button>
                  <a
                    className="inline-flex h-11 items-center justify-center rounded-xl border border-line bg-panel px-5 text-sm font-semibold text-ink hover:bg-canvas"
                    href="https://docs.thtwaat.com"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Installation guide
                  </a>
                </div>
              </>
            )}
            <div
              className="overflow-hidden rounded-2xl border border-line bg-white shadow-soft"
              aria-label="Widget preview"
            >
              <div className="bg-brand px-4 py-3 text-sm font-semibold text-white">
                {draft.agentName || "Assistant"}
              </div>
              <div className="space-y-3 p-4">
                <div className="max-w-[85%] rounded-2xl bg-brand-soft px-3 py-2 text-sm text-ink">
                  Hi! How can I help you today?
                </div>
                {previewUrl ? (
                  <p className="text-xs text-muted">
                    Preview URL:{" "}
                    <a className="text-brand" href={previewUrl} target="_blank" rel="noreferrer">
                      {previewUrl}
                    </a>
                  </p>
                ) : (
                  <p className="text-xs text-muted">Live preview link appears after generation.</p>
                )}
              </div>
            </div>
          </Card>
        )}

        {draft.uiStep === 7 && (
          <Card className="space-y-4 p-6">
            <CardHeader
              title="You're ready"
              description="Checklist of what this guided setup completed via existing platform APIs."
            />
            <ul className="space-y-2 text-sm" aria-label="Setup checklist">
              {(
                [
                  ["workspace", "Workspace created"],
                  ["provider", "Provider ready"],
                  ["agent", "Agent created"],
                  ["knowledge", "Knowledge indexed"],
                  ["widget", "Widget generated"]
                ] as const
              ).map(([key, label]) => (
                <li key={key} className="flex items-center gap-2 rounded-xl border border-line px-3 py-2">
                  <span aria-hidden>{draft.checklist[key] ? "✓" : "○"}</span>
                  <span className={draft.checklist[key] ? "text-ink" : "text-muted"}>{label}</span>
                </li>
              ))}
            </ul>
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void finishGoLive()} disabled={busy}>
                {busy ? "Finishing…" : "Go to Dashboard"}
              </Button>
              <a
                className="inline-flex h-11 items-center justify-center rounded-xl border border-line bg-panel px-5 text-sm font-semibold text-ink hover:bg-canvas"
                href="https://docs.thtwaat.com"
                target="_blank"
                rel="noreferrer"
              >
                View Documentation
              </a>
            </div>
          </Card>
        )}

        {draft.uiStep < 7 && (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Button variant="secondary" onClick={() => void goBack()} disabled={busy || draft.uiStep === 1}>
              Back
            </Button>
            <Button onClick={() => void goNext()} disabled={busy || (!session && draft.uiStep > 1)}>
              {busy ? "Working…" : draft.uiStep === 6 ? "Generate widget" : "Continue"}
            </Button>
          </div>
        )}
      </main>
    </div>
  );
}
