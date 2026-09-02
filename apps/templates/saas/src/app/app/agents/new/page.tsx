"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  agentsApi,
  aiProvidersApi,
  conversationsApi,
  knowledgeApi,
  marketplaceApi,
  type TemplateItem
} from "@/lib/services";
import {
  AGENT_BUILDER_STEPS,
  type AgentBuilderDraft,
  type AgentBuilderStepId,
  buildAgentCreatePayload,
  clearAgentBuilderDraft,
  defaultAgentBuilderDraft,
  docStatusTone,
  prefillFromTemplate,
  saveAgentBuilderDraft,
  stepProgressPercent,
  validateAgentBuilderStep
} from "@/lib/agent-builder";
import { cn, formatDate } from "@/lib/utils";
import { PageHeader, EmptyState, Progress } from "@/components/ui/misc";
import { Badge, Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Label, Select, Textarea } from "@/components/ui/input";

const PROVIDERS = [
  { value: "auto", label: "Auto (recommended)" },
  { value: "ollama", label: "Ollama" },
  { value: "openai", label: "OpenAI" },
  { value: "gemini", label: "Gemini" },
  { value: "anthropic", label: "Anthropic" }
] as const;

function WidgetPreview({ draft }: { draft: AgentBuilderDraft }) {
  const name = draft.widget.agent_name || draft.name || "Agent";
  return (
    <div
      className="overflow-hidden rounded-2xl border border-line shadow-soft"
      style={{ background: draft.widget.theme === "dark" ? "#0f172a" : "#fff" }}
      aria-label="Widget appearance preview"
    >
      <div
        className="flex items-center justify-between px-4 py-3 text-sm font-semibold text-white"
        style={{ background: draft.widget.primary_color }}
      >
        <span>{name}</span>
        <span className="text-xs opacity-80">{draft.widget.position}</span>
      </div>
      <div className={cn("space-y-3 p-4", draft.widget.theme === "dark" ? "text-slate-100" : "text-ink")}>
        <div
          className="max-w-[85%] rounded-2xl px-3 py-2 text-sm"
          style={{ background: `${draft.widget.primary_color}22` }}
        >
          {draft.widget.welcome_message}
        </div>
        <div className="flex flex-wrap gap-2">
          {draft.widget.suggested_prompts.map((p) => (
            <span
              key={p}
              className="rounded-full border border-line px-2.5 py-1 text-xs"
              style={{ borderColor: draft.widget.primary_color, color: draft.widget.primary_color }}
            >
              {p}
            </span>
          ))}
        </div>
        <div className="rounded-xl border border-dashed border-line px-3 py-2 text-xs text-muted">
          Live chat unlocks after the agent is created on the Publish step.
        </div>
      </div>
    </div>
  );
}

export default function NewAgentPage() {
  const router = useRouter();
  const [draft, setDraft] = useState<AgentBuilderDraft>(() => defaultAgentBuilderDraft());
  const [hydrated, setHydrated] = useState(false);
  const [saving, setSaving] = useState(false);
  const [busy, setBusy] = useState(false);
  const [stepErrors, setStepErrors] = useState<string[]>([]);
  const [uploadPct, setUploadPct] = useState<number | null>(null);
  const [kbSearch, setKbSearch] = useState("");
  const [kbResults, setKbResults] = useState<Array<{ text: string; document_name?: string }>>([]);
  const [dragOver, setDragOver] = useState(false);
  const [previewMessages, setPreviewMessages] = useState<Array<{ role: string; content: string }>>([]);
  const [previewInput, setPreviewInput] = useState("");
  const [previewConvId, setPreviewConvId] = useState<string | null>(null);
  const [publishKey, setPublishKey] = useState<string | null>(null);

  useEffect(() => {
    // Always start a genuinely new agent here: never resume a previous
    // session's draft, since a stale draft can carry a real agentId
    // (e.g. from a previously created/published agent) and silently
    // reuse/republish that agent instead of creating a new one.
    clearAgentBuilderDraft();
    setDraft(defaultAgentBuilderDraft());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    setSaving(true);
    const t = setTimeout(() => {
      saveAgentBuilderDraft(draft);
      setSaving(false);
    }, 400);
    return () => clearTimeout(t);
  }, [draft, hydrated]);

  const templatesQ = useQuery({
    queryKey: ["agent-templates"],
    queryFn: () => marketplaceApi.listPage({ kind: "agent", limit: 24 })
  });

  const basesQ = useQuery({
    queryKey: ["knowledge-bases"],
    queryFn: knowledgeApi.listBases
  });

  const docsQ = useQuery({
    queryKey: ["knowledge-docs", draft.knowledgeBaseId],
    queryFn: () => knowledgeApi.listDocuments(draft.knowledgeBaseId || undefined),
    enabled: Boolean(draft.knowledgeBaseId),
    refetchInterval: (q) => {
      const rows = q.state.data || [];
      const busyDoc = rows.some((d) => {
        const s = (d.status || "").toLowerCase();
        return s.includes("process") || s.includes("index") || s === "pending" || s === "queued";
      });
      return busyDoc ? 3000 : false;
    }
  });

  const modelsQ = useQuery({
    queryKey: ["ai-models", draft.provider],
    queryFn: () => aiProvidersApi.models(draft.provider === "auto" ? "openai" : draft.provider),
    enabled: draft.step === 4 && draft.provider !== "auto"
  });

  const healthQ = useQuery({
    queryKey: ["ai-health-builder"],
    queryFn: aiProvidersApi.health,
    enabled: draft.step === 4
  });

  const update = useCallback((patch: Partial<AgentBuilderDraft>) => {
    setDraft((d) => ({ ...d, ...patch }));
  }, []);

  const goTo = (step: AgentBuilderStepId) => {
    setStepErrors([]);
    update({ step });
  };

  const next = () => {
    const v = validateAgentBuilderStep(draft.step, draft);
    if (!v.ok) {
      setStepErrors(v.errors);
      toast.error(v.errors[0] || "Fix validation errors");
      return;
    }
    setStepErrors([]);
    goTo(Math.min(7, draft.step + 1) as AgentBuilderStepId);
  };

  const back = () => {
    setStepErrors([]);
    goTo(Math.max(1, draft.step - 1) as AgentBuilderStepId);
  };

  async function ensureKnowledgeBase() {
    if (draft.knowledgeBaseId) return draft.knowledgeBaseId;
    const name = `${draft.name || "Agent"} Knowledge`.trim();
    const kb = await knowledgeApi.createBase({ name });
    update({ knowledgeBaseId: kb.id, knowledgeBaseName: kb.name });
    await basesQ.refetch();
    return kb.id;
  }

  async function onUploadFiles(files: FileList | File[]) {
    const list = Array.from(files);
    if (!list.length) return;
    try {
      setBusy(true);
      const kbId = await ensureKnowledgeBase();
      for (const file of list) {
        setUploadPct(0);
        await knowledgeApi.uploadWithProgress(kbId, file, setUploadPct);
      }
      setUploadPct(null);
      toast.success("Upload complete — indexing in progress");
      await docsQ.refetch();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Upload failed");
      setUploadPct(null);
    } finally {
      setBusy(false);
    }
  }

  async function onSearchKb() {
    if (!draft.knowledgeBaseId || !kbSearch.trim()) return;
    try {
      const data = await knowledgeApi.search(draft.knowledgeBaseId, kbSearch.trim());
      setKbResults(data.results || []);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Search failed");
    }
  }

  async function createAgentFromDraft() {
    const v = validateAgentBuilderStep(7, draft);
    if (!v.ok) {
      setStepErrors(v.errors);
      throw new Error(v.errors[0]);
    }
    if (draft.agentId) return draft.agentId;

    setBusy(true);
    try {
      const payload = buildAgentCreatePayload(draft);
      const agent = await agentsApi.create(payload);
      if (draft.knowledgeBaseId) {
        try {
          await knowledgeApi.attach(draft.knowledgeBaseId, agent.id);
        } catch (e) {
          toast.error(e instanceof Error ? e.message : "Could not attach knowledge base");
        }
      }
      try {
        await agentsApi.updateWidget(agent.id, {
          theme: draft.widget.theme,
          primary_color: draft.widget.primary_color,
          welcome_message: draft.widget.welcome_message,
          position: draft.widget.position,
          agent_name: draft.widget.agent_name || draft.name,
          suggested_prompts: draft.widget.suggested_prompts
        });
      } catch {
        /* widget defaults already in web_config */
      }
      if (draft.templateSlug) {
        try {
          await marketplaceApi.install(draft.templateSlug, {
            agent_id: agent.id,
            create_api_key: false
          });
        } catch {
          /* install is optional linkage */
        }
      }
      update({ agentId: agent.id });
      toast.success("Agent draft created");
      return agent.id;
    } finally {
      setBusy(false);
    }
  }

  async function sendPreview() {
    if (!previewInput.trim()) return;
    try {
      setBusy(true);
      const agentId = await createAgentFromDraft();
      let convId = previewConvId;
      if (!convId) {
        const created = await conversationsApi.create({
          agent_id: agentId,
          title: "Builder preview",
          channel: "dashboard"
        });
        convId = created.id;
        setPreviewConvId(convId);
      }
      const userText = previewInput.trim();
      setPreviewMessages((m) => [...m, { role: "user", content: userText }]);
      setPreviewInput("");
      const result = await conversationsApi.sendMessage(convId, userText);
      const assistant =
        (result.assistant_message as { content?: string } | undefined)?.content || "No reply";
      setPreviewMessages((m) => [...m, { role: "assistant", content: String(assistant) }]);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Preview chat failed");
    } finally {
      setBusy(false);
    }
  }

  async function onPublish() {
    try {
      setBusy(true);
      const agentId = await createAgentFromDraft();
      const published = await agentsApi.publish(agentId);
      if (published.api_key) setPublishKey(published.api_key);
      update({ published: true });
      toast.success("Agent published");
      clearAgentBuilderDraft();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Publish failed");
    } finally {
      setBusy(false);
    }
  }

  const templateItems: TemplateItem[] = useMemo(() => {
    return templatesQ.data?.items || [];
  }, [templatesQ.data]);

  const models = useMemo(() => {
    const raw = modelsQ.data?.models || [];
    return raw.map((m) => (typeof m === "string" ? m : m.id || m.name || "")).filter(Boolean);
  }, [modelsQ.data]);

  if (!hydrated) {
    return <p className="text-sm text-muted" role="status">Loading builder…</p>;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Agent Builder"
        description="No-code wizard — template through publish. Draft autosaves in this browser."
        action={
          <div className="flex items-center gap-2 text-xs text-muted" aria-live="polite">
            {saving ? "Saving draft…" : `Draft saved ${formatDate(draft.updatedAt)}`}
            {draft.agentId && <Badge tone="brand">Saved</Badge>}
            {draft.published && <Badge tone="success">Published</Badge>}
          </div>
        }
      />

      {/* Progress */}
      <Card>
        <div className="mb-3 flex items-center justify-between gap-3">
          <p className="text-sm font-medium text-ink">
            Step {draft.step} of {AGENT_BUILDER_STEPS.length}:{" "}
            {AGENT_BUILDER_STEPS[draft.step - 1]?.title}
          </p>
          <span className="text-xs text-muted">{stepProgressPercent(draft.step)}%</span>
        </div>
        <Progress value={stepProgressPercent(draft.step)} />
        <ol className="mt-4 flex flex-wrap gap-2" aria-label="Builder steps">
          {AGENT_BUILDER_STEPS.map((s) => (
            <li key={s.id}>
              <button
                type="button"
                onClick={() => goTo(s.id)}
                className={cn(
                  "rounded-full px-3 py-1 text-xs font-semibold transition",
                  s.id === draft.step
                    ? "bg-brand text-white"
                    : s.id < draft.step
                      ? "bg-brand-soft text-brand-dark"
                      : "bg-canvas text-muted"
                )}
                aria-current={s.id === draft.step ? "step" : undefined}
              >
                {s.id}. {s.short}
              </button>
            </li>
          ))}
        </ol>
      </Card>

      {stepErrors.length > 0 && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
          <ul className="list-disc pl-5">
            {stepErrors.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[1fr_320px]">
        <Card>
          {/* Step 1 */}
          {draft.step === 1 && (
            <div className="space-y-4">
              <CardHeader
                title="Choose a template"
                description="Start from marketplace agent templates or blank."
              />
              <Button
                variant="secondary"
                onClick={() => {
                  update({
                    templateSlug: null,
                    templateName: null,
                    step: 2
                  });
                }}
              >
                Start from blank
              </Button>
              {templatesQ.isLoading && <p className="text-sm text-muted">Loading templates…</p>}
              {templatesQ.isError && (
                <p className="text-sm text-red-600">
                  Could not load templates: {(templatesQ.error as Error).message}
                </p>
              )}
              <div className="grid gap-3 sm:grid-cols-2">
                {templateItems.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setDraft((d) => prefillFromTemplate(d, t))}
                    className={cn(
                      "rounded-2xl border p-4 text-left transition hover:border-brand",
                      draft.templateSlug === t.slug ? "border-brand bg-brand-soft/40" : "border-line"
                    )}
                  >
                    <p className="font-semibold text-ink">{t.name}</p>
                    <p className="mt-1 line-clamp-2 text-xs text-muted">{t.description}</p>
                    <div className="mt-2 flex gap-2">
                      <Badge tone="neutral">{t.category}</Badge>
                      {t.installed && <Badge tone="success">Installed</Badge>}
                    </div>
                  </button>
                ))}
              </div>
              {!templatesQ.isLoading && !templateItems.length && (
                <EmptyState
                  title="No agent templates found"
                  description="Continue blank, or publish agent templates in Marketplace."
                />
              )}
            </div>
          )}

          {/* Step 2 */}
          {draft.step === 2 && (
            <div className="space-y-4">
              <CardHeader title="Basic info" description="Name, description, and system prompt." />
              {draft.templateName && (
                <p className="text-xs text-muted">
                  Prefilling from template <strong>{draft.templateName}</strong>
                </p>
              )}
              <div>
                <Label htmlFor="agent-name">Name</Label>
                <Input
                  id="agent-name"
                  value={draft.name}
                  onChange={(e) => update({ name: e.target.value })}
                  placeholder="Support Copilot"
                  aria-required
                />
              </div>
              <div>
                <Label htmlFor="agent-desc">Description</Label>
                <Input
                  id="agent-desc"
                  value={draft.description}
                  onChange={(e) => update({ description: e.target.value })}
                />
              </div>
              <div>
                <Label htmlFor="agent-prompt">System prompt</Label>
                <Textarea
                  id="agent-prompt"
                  value={draft.system_prompt_template}
                  onChange={(e) => update({ system_prompt_template: e.target.value })}
                  aria-required
                />
              </div>
              <div>
                <Label htmlFor="agent-temp">Temperature ({draft.temperature})</Label>
                <Input
                  id="agent-temp"
                  type="number"
                  step="0.1"
                  min={0}
                  max={2}
                  value={draft.temperature}
                  onChange={(e) => update({ temperature: Number(e.target.value) })}
                />
              </div>
            </div>
          )}

          {/* Step 3 Knowledge */}
          {draft.step === 3 && (
            <div className="space-y-4">
              <CardHeader
                title="Knowledge"
                description="Attach a knowledge base, upload docs, search, and remove files."
              />
              <div>
                <Label>Knowledge base</Label>
                <Select
                  value={draft.knowledgeBaseId || ""}
                  onChange={(e) => {
                    const id = e.target.value || null;
                    const name = basesQ.data?.find((b) => b.id === id)?.name || null;
                    update({ knowledgeBaseId: id, knowledgeBaseName: name });
                  }}
                >
                  <option value="">Create new on first upload</option>
                  {(basesQ.data || []).map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </Select>
              </div>

              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOver(false);
                  void onUploadFiles(e.dataTransfer.files);
                }}
                className={cn(
                  "rounded-2xl border border-dashed px-6 py-10 text-center transition",
                  dragOver ? "border-brand bg-brand-soft/30" : "border-line bg-canvas"
                )}
                role="region"
                aria-label="Drag and drop files to upload"
              >
                <p className="text-sm font-medium text-ink">Drag & drop PDF, DOCX, or TXT</p>
                <p className="mt-1 text-xs text-muted">or choose files</p>
                <Input
                  type="file"
                  multiple
                  className="mx-auto mt-4 max-w-xs"
                  onChange={(e) => e.target.files && void onUploadFiles(e.target.files)}
                  disabled={busy}
                  aria-label="Upload knowledge files"
                />
                {uploadPct != null && (
                  <div className="mx-auto mt-4 max-w-sm">
                    <Progress value={uploadPct} />
                    <p className="mt-1 text-xs text-muted">Uploading {uploadPct}%</p>
                  </div>
                )}
              </div>

              <div className="space-y-2">
                {(docsQ.data || []).map((doc) => (
                  <div
                    key={doc.id}
                    className="flex items-center justify-between rounded-xl border border-line px-3 py-2.5"
                  >
                    <div>
                      <p className="text-sm font-medium">{doc.name}</p>
                      <p className="text-xs text-muted">{formatDate(doc.created_at)}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge tone={docStatusTone(doc.status)}>{doc.status || "ready"}</Badge>
                      <Button
                        size="sm"
                        variant="danger"
                        onClick={async () => {
                          if (!draft.knowledgeBaseId) return;
                          try {
                            await knowledgeApi.deleteDocument(draft.knowledgeBaseId, doc.id);
                            toast.success("Removed");
                            await docsQ.refetch();
                          } catch (e) {
                            toast.error(e instanceof Error ? e.message : "Delete failed");
                          }
                        }}
                      >
                        Remove
                      </Button>
                    </div>
                  </div>
                ))}
                {draft.knowledgeBaseId && !docsQ.data?.length && !docsQ.isLoading && (
                  <EmptyState title="No documents yet" description="Upload files to index." />
                )}
              </div>

              <div>
                <Label>Search knowledge</Label>
                <div className="flex gap-2">
                  <Input
                    value={kbSearch}
                    onChange={(e) => setKbSearch(e.target.value)}
                    placeholder="Search indexed content…"
                    disabled={!draft.knowledgeBaseId}
                  />
                  <Button type="button" variant="secondary" onClick={() => void onSearchKb()}>
                    Search
                  </Button>
                </div>
                <div className="mt-2 space-y-2">
                  {kbResults.map((r, i) => (
                    <div key={i} className="rounded-xl border border-line p-3 text-sm">
                      {r.document_name && (
                        <p className="mb-1 text-xs font-semibold text-brand">{r.document_name}</p>
                      )}
                      <p className="text-muted">{r.text}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Step 4 Provider */}
          {draft.step === 4 && (
            <div className="space-y-4">
              <CardHeader
                title="AI Provider"
                description="Reuse Provider Management health + models. Auto uses platform routing defaults."
              />
              <div className="grid gap-3 sm:grid-cols-2">
                {PROVIDERS.map((p) => {
                  const health =
                    p.value === "auto"
                      ? null
                      : healthQ.data?.[p.value];
                  return (
                    <button
                      key={p.value}
                      type="button"
                      onClick={() =>
                        update({
                          provider: p.value,
                          model: p.value === "auto" ? "" : draft.model
                        })
                      }
                      className={cn(
                        "rounded-2xl border p-4 text-left",
                        draft.provider === p.value ? "border-brand bg-brand-soft/40" : "border-line"
                      )}
                      aria-pressed={draft.provider === p.value}
                    >
                      <p className="font-semibold">{p.label}</p>
                      {health && (
                        <p className="mt-1 text-xs text-muted">Status: {health}</p>
                      )}
                    </button>
                  );
                })}
              </div>
              {draft.provider !== "auto" && (
                <div>
                  <Label htmlFor="model">Model</Label>
                  {modelsQ.isLoading && <p className="text-xs text-muted">Loading models…</p>}
                  <Select
                    id="model"
                    value={draft.model}
                    onChange={(e) => update({ model: e.target.value })}
                  >
                    <option value="">Select model</option>
                    {models.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </Select>
                  <p className="mt-1 text-xs text-muted">
                    <a className="text-brand underline" href="/app/providers">
                      Open AI Providers
                    </a>{" "}
                    for full status.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Step 5 Capabilities */}
          {draft.step === 5 && (
            <div className="space-y-4">
              <CardHeader
                title="Capabilities"
                description="Stored in web_config for the agent. RAG uses attached knowledge at chat time."
              />
              {(
                [
                  ["rag", "Knowledge / RAG", "Answer from uploaded documents"],
                  ["tools", "Tools (planned)", "Reserved in config — no new backend"],
                  ["memory", "Session memory", "Reserved flag in web_config"],
                  ["handoff", "Human handoff ready", "Aligns with Inbox pending_human"],
                  ["voice", "Voice", "Requires a speech-to-text / text-to-speech provider — configure after creating the agent"],
                  ["vision", "Vision (image upload)", "Requires a vision-capable model (e.g. GPT-4o class)"],
                  ["image_generation", "Image generation", "Requires an image-generation provider/model"],
                  ["calling", "AI calling", "Requires voice + a telephony provider and phone number"]
                ] as const
              ).map(([key, label, hint]) => (
                <label
                  key={key}
                  className="flex cursor-pointer items-start gap-3 rounded-xl border border-line p-3"
                >
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={draft.capabilities[key]}
                    onChange={(e) =>
                      update({
                        capabilities: { ...draft.capabilities, [key]: e.target.checked }
                      })
                    }
                  />
                  <span>
                    <span className="block text-sm font-medium text-ink">{label}</span>
                    <span className="text-xs text-muted">{hint}</span>
                  </span>
                </label>
              ))}
            </div>
          )}

          {/* Step 6 Appearance */}
          {draft.step === 6 && (
            <div className="space-y-4">
              <CardHeader title="Appearance" description="Widget theme shown to website visitors." />
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <Label>Theme</Label>
                  <Select
                    value={draft.widget.theme}
                    onChange={(e) =>
                      update({
                        widget: {
                          ...draft.widget,
                          theme: e.target.value as "light" | "dark"
                        }
                      })
                    }
                  >
                    <option value="light">Light</option>
                    <option value="dark">Dark</option>
                  </Select>
                </div>
                <div>
                  <Label>Position</Label>
                  <Select
                    value={draft.widget.position}
                    onChange={(e) =>
                      update({
                        widget: {
                          ...draft.widget,
                          position: e.target.value as "bottom-right" | "bottom-left"
                        }
                      })
                    }
                  >
                    <option value="bottom-right">Bottom right</option>
                    <option value="bottom-left">Bottom left</option>
                  </Select>
                </div>
              </div>
              <div>
                <Label htmlFor="color">Primary color</Label>
                <Input
                  id="color"
                  value={draft.widget.primary_color}
                  onChange={(e) =>
                    update({ widget: { ...draft.widget, primary_color: e.target.value } })
                  }
                />
              </div>
              <div>
                <Label>Display name</Label>
                <Input
                  value={draft.widget.agent_name}
                  onChange={(e) =>
                    update({ widget: { ...draft.widget, agent_name: e.target.value } })
                  }
                  placeholder={draft.name || "Agent"}
                />
              </div>
              <div>
                <Label>Welcome message</Label>
                <Textarea
                  value={draft.widget.welcome_message}
                  onChange={(e) =>
                    update({ widget: { ...draft.widget, welcome_message: e.target.value } })
                  }
                />
              </div>
              <div>
                <Label>Suggested prompts (comma-separated)</Label>
                <Input
                  value={draft.widget.suggested_prompts.join(", ")}
                  onChange={(e) =>
                    update({
                      widget: {
                        ...draft.widget,
                        suggested_prompts: e.target.value
                          .split(",")
                          .map((s) => s.trim())
                          .filter(Boolean)
                      }
                    })
                  }
                />
              </div>
            </div>
          )}

          {/* Step 7 Publish */}
          {draft.step === 7 && (
            <div className="space-y-4">
              <CardHeader
                title="Review & publish"
                description="Create the agent (if needed), try live chat, then publish."
              />
              <dl className="grid gap-2 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-xs text-muted">Name</dt>
                  <dd className="font-medium">{draft.name || "—"}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">Provider</dt>
                  <dd className="font-medium">
                    {draft.provider}
                    {draft.model ? ` / ${draft.model}` : ""}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">Knowledge</dt>
                  <dd className="font-medium">
                    {draft.knowledgeBaseName || draft.knowledgeBaseId || "None"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">Template</dt>
                  <dd className="font-medium">{draft.templateName || "Blank"}</dd>
                </div>
              </dl>

              {!draft.agentId && (
                <Button disabled={busy} onClick={() => void createAgentFromDraft()}>
                  {busy ? "Creating…" : "Create agent draft"}
                </Button>
              )}

              {draft.agentId && (
                <div className="rounded-2xl border border-line bg-canvas p-4">
                  <p className="mb-2 text-sm font-semibold">Live chat preview</p>
                  <div className="mb-3 max-h-48 space-y-2 overflow-y-auto">
                    {previewMessages.map((m, i) => (
                      <div
                        key={i}
                        className={cn(
                          "rounded-xl px-3 py-2 text-sm",
                          m.role === "user" ? "ml-8 bg-brand text-white" : "mr-8 bg-panel"
                        )}
                      >
                        {m.content}
                      </div>
                    ))}
                    {!previewMessages.length && (
                      <p className="text-xs text-muted">Send a message to test the agent.</p>
                    )}
                  </div>
                  <form
                    className="flex gap-2"
                    onSubmit={(e) => {
                      e.preventDefault();
                      void sendPreview();
                    }}
                  >
                    <Input
                      value={previewInput}
                      onChange={(e) => setPreviewInput(e.target.value)}
                      placeholder="Try the agent…"
                      aria-label="Preview chat message"
                    />
                    <Button type="submit" disabled={busy || !previewInput.trim()}>
                      Send
                    </Button>
                  </form>
                </div>
              )}

              <div className="flex flex-wrap gap-2">
                <Button disabled={busy || draft.published} onClick={() => void onPublish()}>
                  {draft.published ? "Published" : busy ? "Publishing…" : "Publish agent"}
                </Button>
                {draft.agentId && (
                  <Button
                    variant="secondary"
                    onClick={() => router.push(`/app/agents/${draft.agentId}`)}
                  >
                    Open agent detail
                  </Button>
                )}
              </div>

              {publishKey && (
                <div className="rounded-xl bg-brand-soft p-3 text-sm" role="status">
                  <p className="font-semibold text-brand-dark">Copy API key now</p>
                  <code className="mt-2 block break-all text-xs">{publishKey}</code>
                </div>
              )}
            </div>
          )}

          <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
            <Button variant="ghost" onClick={back} disabled={draft.step === 1 || busy}>
              Back
            </Button>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                onClick={() => {
                  clearAgentBuilderDraft();
                  setDraft(defaultAgentBuilderDraft());
                  setPreviewMessages([]);
                  setPreviewConvId(null);
                  setPublishKey(null);
                  toast.success("Draft cleared");
                }}
              >
                Reset draft
              </Button>
              {draft.step < 7 ? (
                <Button onClick={next} disabled={busy}>
                  Continue
                </Button>
              ) : null}
            </div>
          </div>
        </Card>

        <div className="space-y-4 xl:sticky xl:top-4 xl:self-start">
          <Card>
            <CardHeader title="Preview" description="Appearance updates live." />
            <WidgetPreview draft={draft} />
          </Card>
        </div>
      </div>
    </div>
  );
}
