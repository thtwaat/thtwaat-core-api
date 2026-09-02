"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { agentsApi, knowledgeApi } from "@/lib/services";
import { site } from "@/lib/config";
import { PageHeader } from "@/components/ui/misc";
import { Badge, Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Label, Select, Textarea } from "@/components/ui/input";

const PROVIDERS = ["openai", "anthropic", "gemini", "ollama", "openrouter"];

type AgentCapabilities = {
  rag: boolean;
  memory: boolean;
  tools: boolean;
  handoff: boolean;
  voice: boolean;
  vision: boolean;
  image_generation: boolean;
  calling: boolean;
};

const DEFAULT_CAPABILITIES: AgentCapabilities = {
  rag: true,
  memory: true,
  tools: false,
  handoff: true,
  voice: false,
  vision: false,
  image_generation: false,
  calling: false
};

const CAPABILITY_FIELDS: Array<{
  key: keyof AgentCapabilities;
  label: string;
  hint: string;
  note?: string;
}> = [
  { key: "rag", label: "Knowledge / RAG", hint: "Answer from attached knowledge bases" },
  { key: "memory", label: "Session memory", hint: "Remember prior turns in the conversation" },
  { key: "tools", label: "Tools", hint: "Allow the model to call registered tools" },
  { key: "handoff", label: "Human handoff", hint: "Detect \"talk to a human\" and route to Inbox" },
  { key: "voice", label: "Voice", hint: "Let users talk to the agent with voice." },
  { key: "vision", label: "Vision", hint: "Let users send images for the agent to analyze." },
  { key: "image_generation", label: "Image Generation", hint: "Allow the agent to generate images." },
  {
    key: "calling",
    label: "AI Calling",
    hint: "Enable phone-call interactions with the agent.",
    note: "Requires voice enabled, plus a telephony provider and phone number configured for this agent."
  }
];

const STATUS_TONE: Record<string, "success" | "neutral" | "warn"> = {
  PUBLISHED: "success",
  PAUSED: "warn",
  DRAFT: "neutral"
};

const STATUS_LABEL: Record<string, string> = {
  PUBLISHED: "LIVE",
  PAUSED: "PAUSED",
  DRAFT: "DRAFT"
};

export default function AgentDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const qc = useQueryClient();
  const agent = useQuery({ queryKey: ["agent", id], queryFn: () => agentsApi.get(id) });
  const embed = useQuery({
    queryKey: ["embed", id],
    queryFn: () => agentsApi.embed(id),
    enabled: Boolean(agent.data?.status === "PUBLISHED")
  });
  const toolsCatalog = useQuery({ queryKey: ["agent-tools-catalog"], queryFn: agentsApi.tools });
  const allBases = useQuery({ queryKey: ["kb-bases"], queryFn: knowledgeApi.listBases });
  const attachedBases = useQuery({
    queryKey: ["agent-kb", id],
    queryFn: () => knowledgeApi.listForAgent(id)
  });

  const [apiKeyName, setApiKeyName] = useState("Production");
  const [createdKey, setCreatedKey] = useState<string | null>(null);

  // Editable configuration form, seeded from the loaded agent.
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [provider, setProvider] = useState("openai");
  const [model, setModel] = useState("");
  const [temperature, setTemperature] = useState(0.7);
  const [selectedTools, setSelectedTools] = useState<string[]>([]);
  const [capabilities, setCapabilities] = useState<AgentCapabilities>(DEFAULT_CAPABILITIES);

  useEffect(() => {
    if (!agent.data) return;
    setName(agent.data.name);
    setDescription(agent.data.description || "");
    setSystemPrompt(agent.data.system_prompt_template);
    setProvider(agent.data.provider || (agent.data.web_config?.provider as string) || "openai");
    setModel(agent.data.model || (agent.data.web_config?.model as string) || "");
    setTemperature(agent.data.temperature);
    setSelectedTools(agent.data.allowed_tools || []);
    const rawCaps = (agent.data.web_config?.capabilities as Partial<AgentCapabilities>) || {};
    setCapabilities({ ...DEFAULT_CAPABILITIES, ...rawCaps });
  }, [agent.data]);

  async function copyText(value: string, label: string) {
    try {
      await navigator.clipboard.writeText(value);
      toast.success(`${label} copied`);
    } catch {
      toast.error("Could not copy to clipboard");
    }
  }

  const save = useMutation({
    mutationFn: () =>
      agentsApi.update(id, {
        name,
        description,
        system_prompt_template: systemPrompt,
        provider,
        model,
        temperature,
        allowed_tools: selectedTools,
        // Spread the agent's full existing web_config so unrelated keys
        // (widget, voice, calling, image_generation provider settings, ...)
        // survive this PATCH even if the backend ever stops merging.
        web_config: { ...(agent.data?.web_config || {}), capabilities }
      }),
    onSuccess: () => {
      toast.success("Agent updated");
      qc.invalidateQueries({ queryKey: ["agent", id] });
      qc.invalidateQueries({ queryKey: ["agents"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const publish = useMutation({
    mutationFn: () => agentsApi.publish(id),
    onSuccess: (data) => {
      toast.success("Published");
      if (data.api_key) setCreatedKey(data.api_key);
      qc.invalidateQueries({ queryKey: ["agent", id] });
      qc.invalidateQueries({ queryKey: ["agents"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const unpublish = useMutation({
    mutationFn: () => agentsApi.unpublish(id),
    onSuccess: () => {
      toast.success("Unpublished");
      qc.invalidateQueries({ queryKey: ["agent", id] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const pause = useMutation({
    mutationFn: () => agentsApi.pause(id),
    onSuccess: () => {
      toast.success("Agent paused");
      qc.invalidateQueries({ queryKey: ["agent", id] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const resume = useMutation({
    mutationFn: () => agentsApi.resume(id),
    onSuccess: () => {
      toast.success("Agent resumed");
      qc.invalidateQueries({ queryKey: ["agent", id] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const attachKb = useMutation({
    mutationFn: (kbId: string) => knowledgeApi.attach(kbId, id),
    onSuccess: () => {
      toast.success("Knowledge base attached");
      qc.invalidateQueries({ queryKey: ["agent-kb", id] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const detachKb = useMutation({
    mutationFn: (kbId: string) => knowledgeApi.detach(kbId, id),
    onSuccess: () => {
      toast.success("Knowledge base detached");
      qc.invalidateQueries({ queryKey: ["agent-kb", id] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const createKey = useMutation({
    mutationFn: () => agentsApi.createApiKey(id, apiKeyName),
    onSuccess: (data) => {
      const key = data.api_key || data.key;
      if (key) setCreatedKey(key);
      toast.success("API key created — copy it now");
    },
    onError: (e: Error) => toast.error(e.message)
  });

  if (agent.isLoading) return <p className="text-sm text-muted">Loading agent…</p>;
  if (!agent.data) return <p className="text-sm text-muted">Agent not found.</p>;

  const a = agent.data;
  const embedScript =
    embed.data?.script ||
    embed.data?.embed_script ||
    `<script src="${site.apiUrl}/widget.js" data-api-key="YOUR_KEY" async></script>`;

  const attachedIds = new Set((attachedBases.data || []).map((kb) => kb.id));
  const attachableBases = (allBases.data || []).filter((kb) => !attachedIds.has(kb.id));

  function toggleTool(toolName: string) {
    setSelectedTools((prev) =>
      prev.includes(toolName) ? prev.filter((t) => t !== toolName) : [...prev, toolName]
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={a.name}
        description={a.description || "Agent details, publish, widget, and API keys"}
        action={
          <Badge tone={STATUS_TONE[a.status] || "neutral"}>
            {STATUS_LABEL[a.status] || a.status}
          </Badge>
        }
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="lg:col-span-2">
          <CardHeader title="Configuration" description="Instructions, model, and personality" />
          <div className="space-y-3 text-sm">
            <div>
              <Label>Name</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div>
              <Label>Description</Label>
              <Input value={description} onChange={(e) => setDescription(e.target.value)} />
            </div>
            <div>
              <Label>System prompt / instructions</Label>
              <Textarea
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                rows={6}
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div>
                <Label>Provider</Label>
                <Select value={provider} onChange={(e) => setProvider(e.target.value)}>
                  {PROVIDERS.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label>Model</Label>
                <Input value={model} onChange={(e) => setModel(e.target.value)} placeholder="gpt-4o-mini" />
              </div>
              <div>
                <Label>Temperature</Label>
                <Input
                  type="number"
                  min={0}
                  max={2}
                  step={0.1}
                  value={temperature}
                  onChange={(e) => setTemperature(Number(e.target.value))}
                />
              </div>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <Button onClick={() => save.mutate()} disabled={save.isPending}>
              {save.isPending ? "Saving…" : "Save changes"}
            </Button>
            <Link
              href={`/app/agents/${id}/playground`}
              className="inline-flex items-center justify-center rounded-xl border border-line bg-white px-3 py-2 text-sm font-medium hover:bg-slate-50"
            >
              Open playground
            </Link>
            <Link
              href="/app/analytics"
              className="inline-flex items-center justify-center rounded-xl border border-line bg-white px-3 py-2 text-sm font-medium hover:bg-slate-50"
            >
              Usage &amp; analytics
            </Link>
            {a.status === "PUBLISHED" && (
              <>
                <Button variant="secondary" onClick={() => pause.mutate()} disabled={pause.isPending}>
                  Pause
                </Button>
                <Button variant="secondary" onClick={() => unpublish.mutate()}>
                  Unpublish
                </Button>
              </>
            )}
            {a.status === "PAUSED" && (
              <Button onClick={() => resume.mutate()} disabled={resume.isPending}>
                Resume
              </Button>
            )}
            {a.status === "DRAFT" && <Button onClick={() => publish.mutate()}>Publish</Button>}
          </div>
        </Card>

        <Card>
          <CardHeader title="Tools" description="Capabilities this agent is allowed to invoke" />
          <div className="space-y-2 text-sm">
            {(toolsCatalog.data || []).length === 0 && (
              <p className="text-muted">No registered tools available yet.</p>
            )}
            {(toolsCatalog.data || []).map((tool) => (
              <label key={tool.name} className="flex items-start gap-2">
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={selectedTools.includes(tool.name)}
                  onChange={() => toggleTool(tool.name)}
                />
                <span>
                  <span className="block font-medium text-ink">{tool.name}</span>
                  <span className="block text-xs text-muted">{tool.description}</span>
                </span>
              </label>
            ))}
          </div>
          <p className="mt-3 text-xs text-muted">Save Configuration to apply tool changes.</p>
        </Card>

        <Card>
          <CardHeader
            title="Capabilities"
            description="Optional capabilities this agent can use. Some require provider setup."
          />
          <div className="space-y-2 text-sm">
            {CAPABILITY_FIELDS.map(({ key, label, hint, note }) => (
              <label key={key} className="flex items-start gap-2">
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={capabilities[key]}
                  onChange={(e) =>
                    setCapabilities((prev) => ({ ...prev, [key]: e.target.checked }))
                  }
                />
                <span>
                  <span className="block font-medium text-ink">{label}</span>
                  <span className="block text-xs text-muted">{hint}</span>
                  {note && (
                    <span className="mt-0.5 block text-xs font-medium text-amber-600">{note}</span>
                  )}
                </span>
              </label>
            ))}
          </div>
          <p className="mt-3 text-xs text-muted">Save Configuration to apply capability changes.</p>
        </Card>

        <Card>
          <CardHeader title="Knowledge" description="Knowledge bases this agent can search" />
          <div className="space-y-2 text-sm">
            {(attachedBases.data || []).length === 0 && (
              <p className="text-muted">No knowledge bases attached.</p>
            )}
            {(attachedBases.data || []).map((kb) => (
              <div key={kb.id} className="flex items-center justify-between gap-2 rounded-lg border border-line px-3 py-2">
                <span>{kb.name}</span>
                <Button
                  variant="secondary"
                  onClick={() => detachKb.mutate(kb.id)}
                  disabled={detachKb.isPending}
                >
                  Detach
                </Button>
              </div>
            ))}
          </div>
          {attachableBases.length > 0 && (
            <div className="mt-3 flex gap-2">
              <Select
                onChange={(e) => {
                  if (e.target.value) attachKb.mutate(e.target.value);
                  e.target.value = "";
                }}
                defaultValue=""
              >
                <option value="" disabled>
                  Attach a knowledge base…
                </option>
                {attachableBases.map((kb) => (
                  <option key={kb.id} value={kb.id}>
                    {kb.name}
                  </option>
                ))}
              </Select>
            </div>
          )}
        </Card>

        <Card>
          <CardHeader title="API keys" description="Create agent keys for public chat / widget" />
          <div className="flex gap-2">
            <Input value={apiKeyName} onChange={(e) => setApiKeyName(e.target.value)} />
            <Button onClick={() => createKey.mutate()}>Create</Button>
          </div>
          {createdKey && (
            <div className="mt-4 space-y-3">
              <div className="rounded-xl bg-brand-soft p-3 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-semibold text-brand-dark">Copy this key now</p>
                  <Button variant="secondary" onClick={() => copyText(createdKey, "API key")}>
                    Copy
                  </Button>
                </div>
                <code className="mt-2 block break-all text-xs">{createdKey}</code>
              </div>
              <div className="rounded-xl border border-line bg-slate-900 p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold text-slate-300">Try it now</p>
                  <Button
                    variant="secondary"
                    onClick={() =>
                      copyText(
                        `curl -X POST ${site.apiUrl}/public/v1/agents/${a.slug || a.id}/chat \\\n  -H "Authorization: Bearer ${createdKey}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"message": "Hello!"}'`,
                        "curl example"
                      )
                    }
                  >
                    Copy
                  </Button>
                </div>
                <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-all text-xs text-slate-100">
{`curl -X POST ${site.apiUrl}/public/v1/agents/${a.slug || a.id}/chat \\
  -H "Authorization: Bearer ${createdKey}" \\
  -H "Content-Type: application/json" \\
  -d '{"message": "Hello!"}'`}
                </pre>
              </div>
            </div>
          )}
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Widget / Embed" />
          <Label>Embed snippet</Label>
          <Textarea readOnly className="font-mono text-xs" value={embedScript} />
          <p className="mt-3 text-sm text-muted">
            Public chat: <code>{site.apiUrl}/public/v1/chat</code> or{" "}
            <code>{site.apiUrl}/public/v1/agents/{a.slug || "{slug}"}/chat</code>
          </p>
        </Card>
      </div>
    </div>
  );
}
