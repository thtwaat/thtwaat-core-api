"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  type AnalysisResult,
  type ProductGeneration,
  productGeneratorApi
} from "@/lib/services";
import { formatDate } from "@/lib/utils";
import { PageHeader, EmptyState } from "@/components/ui/misc";
import { Badge, Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import {
  BarChart3,
  Bot,
  CheckCircle2,
  Circle,
  Cpu,
  ExternalLink,
  Library,
  LayoutDashboard,
  Rocket,
  Search,
  Sparkles
} from "lucide-react";

// ── Wizard steps ──────────────────────────────────────────────────────────────

type WizardStep = "prompt" | "analyze" | "generate" | "preview";

const STEP_LABELS: Record<WizardStep, string> = {
  prompt: "Describe your product",
  analyze: "Analyze & select template",
  generate: "Assemble components",
  preview: "Preview & publish"
};

const STEP_ORDER: WizardStep[] = ["prompt", "analyze", "generate", "preview"];

const STATUS_TONE: Record<string, "success" | "warn" | "neutral" | "brand" | "danger"> = {
  published: "success",
  preview_ready: "brand",
  publishing: "brand",
  provisioning: "warn",
  configuring: "warn",
  binding: "warn",
  analyzing: "warn",
  template_selected: "warn",
  failed: "danger",
  draft: "neutral"
};

const EXAMPLE_PROMPTS = [
  "Restaurant website with AI ordering and booking",
  "Clinic appointment booking SaaS with patient chat",
  "Real estate landing page with AI listings assistant",
  "School admission portal with AI FAQ",
  "Legal firm website with document assistant",
  "Ecommerce store with AI product search"
];

// ── Sub-components ────────────────────────────────────────────────────────────

function ChecklistItem({ item }: { item: { key: string; label: string; done: boolean; href?: string | null } }) {
  return (
    <li className="flex items-start gap-2 text-sm">
      {item.done
        ? <CheckCircle2 size={16} className="mt-0.5 text-emerald-500 flex-shrink-0" />
        : <Circle size={16} className="mt-0.5 text-slate-300 flex-shrink-0" />}
      <span className={item.done ? "text-ink" : "text-muted"}>{item.label}</span>
    </li>
  );
}

function AnalysisCard({ analysis, onProceed, generating }: {
  analysis: AnalysisResult;
  onProceed: () => void;
  generating: boolean;
}) {
  const pills = [
    { icon: LayoutDashboard, label: analysis.industry.replace("_", " ") },
    { icon: Cpu, label: analysis.product_type },
    { icon: Sparkles, label: analysis.brand_tone },
  ];
  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="font-semibold text-ink">{analysis.suggested_name}</h3>
          <p className="mt-1 text-sm text-muted">
            Confidence: {Math.round(analysis.confidence * 100)}%
          </p>
        </div>
        {analysis.recommended_template_name && (
          <Badge tone="brand">{analysis.recommended_template_name}</Badge>
        )}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {pills.map(({ icon: Icon, label }) => (
          <span key={label} className="flex items-center gap-1.5 rounded-full border border-line bg-canvas px-3 py-1 text-sm text-ink capitalize">
            <Icon size={12} />{label}
          </span>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap gap-1.5">
        {analysis.required_features.map((f) => (
          <span key={f} className="rounded-full bg-brand-soft px-2.5 py-1 text-xs font-medium text-brand-dark capitalize">
            {f.replace("_", " ")}
          </span>
        ))}
      </div>
      <div className="mt-6">
        <Button disabled={generating} onClick={onProceed} className="gap-2">
          <Rocket size={14} />
          {generating ? "Assembling…" : "Assemble product"}
        </Button>
      </div>
    </Card>
  );
}

function ProductCard({ gen, onPublish, publishing }: {
  gen: ProductGeneration;
  onPublish: (id: string) => void;
  publishing: boolean;
}) {
  const [apiKeyCopied, setApiKeyCopied] = useState(false);
  const tone = STATUS_TONE[gen.status] ?? "neutral";

  function copyKey() {
    if (!gen.api_key) return;
    navigator.clipboard.writeText(gen.api_key).then(() => {
      setApiKeyCopied(true);
      setTimeout(() => setApiKeyCopied(false), 2500);
    });
  }

  return (
    <div className="space-y-4">
      {/* Status bar */}
      <div className="flex flex-wrap items-center gap-3">
        <Badge tone={tone}>{gen.status.replace("_", " ")}</Badge>
        {gen.template_slug && <span className="text-sm text-muted">Template: {gen.template_slug}</span>}
        {gen.preview_url && (
          <a href={gen.preview_url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-sm text-brand hover:underline">
            <ExternalLink size={12} /> Preview
          </a>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {/* Left: resources */}
        <Card>
          <CardHeader title="Provisioned Resources" />
          <ul className="space-y-2">
            {[
              { icon: Bot, label: "AI Agent", value: gen.agent_id ? "Created" : "—", done: !!gen.agent_id, href: gen.agent_id ? "/app/agents" : null },
              { icon: Library, label: "Knowledge Base", value: gen.knowledge_base_id ? "Created" : "—", done: !!gen.knowledge_base_id, href: gen.knowledge_base_id ? "/app/knowledge" : null },
              { icon: Sparkles, label: "Widget", value: gen.widget_id || "—", done: !!gen.widget_id },
              { icon: BarChart3, label: "Template Install", value: gen.installation_id ? "Installed" : "—", done: !!gen.installation_id, href: "/app/templates" },
            ].map(({ icon: Icon, label, value, done, href }) => (
              <li key={label} className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-2 text-muted">
                  <Icon size={14} />{label}
                </span>
                <span className={done ? "font-medium text-emerald-600" : "text-muted"}>
                  {href && done
                    ? <a href={href} className="hover:underline">{value}</a>
                    : value}
                </span>
              </li>
            ))}
          </ul>
          {gen.api_key && (
            <div className="mt-4 rounded-lg bg-amber-50 p-3">
              <p className="text-xs font-semibold text-amber-700 mb-1">API Key — copy now!</p>
              <div className="flex items-center gap-2">
                <code className="flex-1 truncate font-mono text-xs">{gen.api_key}</code>
                <Button size="sm" variant="secondary" onClick={copyKey}>
                  {apiKeyCopied ? "Copied!" : "Copy"}
                </Button>
              </div>
            </div>
          )}
        </Card>

        {/* Right: checklist */}
        <Card>
          <CardHeader title="Deployment Checklist" />
          <ul className="space-y-2">
            {gen.deployment_checklist.map((item) => (
              <ChecklistItem key={item.key} item={item} />
            ))}
          </ul>
        </Card>
      </div>

      {/* Widget snippet */}
      {typeof gen.widget_snippet === "string" && gen.widget_snippet.length > 0 ? (
        <Card>
          <CardHeader title="Embed Snippet" description="Paste this into your site's <head> or before </body>." />
          <pre className="overflow-x-auto rounded-lg bg-slate-900 p-4 text-xs text-emerald-300">
            {gen.widget_snippet}
          </pre>
        </Card>
      ) : null}

      {/* Config preview */}
      {typeof gen.product_config.name === "string" && gen.product_config.name.length > 0 ? (
        <Card>
          <CardHeader title="Product Configuration" />
          <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
            {(
              [
                ["Name", gen.product_config.name],
                ["Industry", (gen.product_config.industry as string)?.replace("_", " ")],
                ["Theme", gen.product_config.theme],
                ["Brand tone", gen.product_config.brand_tone],
                ["Language", gen.product_config.language],
                [
                  "Primary color",
                  gen.product_config.colors
                    ? (gen.product_config.colors as Record<string, string>).primary
                    : "—"
                ]
              ] as Array<[string, unknown]>
            ).map(([label, value]) => (
              <div key={label}>
                <p className="text-xs text-muted capitalize">{label}</p>
                <p className="font-medium capitalize">{String(value ?? "—")}</p>
              </div>
            ))}
          </div>
        </Card>
      ) : null}

      {/* Publish CTA */}
      {gen.status === "preview_ready" && (
        <div className="flex justify-end">
          <Button disabled={publishing} onClick={() => onPublish(gen.id)} className="gap-2">
            <Rocket size={14} />
            {publishing ? "Publishing…" : "Publish product"}
          </Button>
        </div>
      )}
    </div>
  );
}

// ── Wizard stepper ────────────────────────────────────────────────────────────

function Stepper({ current }: { current: WizardStep }) {
  const currentIdx = STEP_ORDER.indexOf(current);
  return (
    <nav className="flex items-center gap-0">
      {STEP_ORDER.map((step, idx) => {
        const done = idx < currentIdx;
        const active = idx === currentIdx;
        return (
          <div key={step} className="flex items-center">
            <div className="flex flex-col items-center gap-1">
              <div className={`grid h-8 w-8 place-items-center rounded-full border-2 text-sm font-semibold transition ${
                done ? "border-emerald-500 bg-emerald-500 text-white"
                  : active ? "border-brand bg-brand text-white"
                  : "border-line bg-canvas text-muted"
              }`}>
                {done ? <CheckCircle2 size={14} /> : idx + 1}
              </div>
              <span className={`hidden text-xs sm:block ${active ? "text-brand font-medium" : "text-muted"}`}>
                {STEP_LABELS[step].split(" ")[0]}
              </span>
            </div>
            {idx < STEP_ORDER.length - 1 && (
              <div className={`h-0.5 w-10 flex-shrink-0 mx-1 ${done ? "bg-emerald-400" : "bg-line"}`} />
            )}
          </div>
        );
      })}
    </nav>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ProductGeneratorPage() {
  const qc = useQueryClient();
  const [step, setStep] = useState<WizardStep>("prompt");
  const [prompt, setPrompt] = useState("");
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [generation, setGeneration] = useState<ProductGeneration | null>(null);
  const [showHistory, setShowHistory] = useState(false);

  const history = useQuery({
    queryKey: ["gen-history"],
    queryFn: productGeneratorApi.list,
    enabled: showHistory
  });

  const analyzeMutation = useMutation({
    mutationFn: () => productGeneratorApi.analyze(prompt),
    onSuccess: (data) => {
      setAnalysis(data);
      setStep("analyze");
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const generateMutation = useMutation({
    mutationFn: () => productGeneratorApi.generate({
      prompt,
      template_slug: analysis?.recommended_template_slug ?? undefined,
    }),
    onSuccess: (data) => {
      setGeneration(data);
      setStep(data.status === "preview_ready" ? "preview" : "generate");
      if (data.api_key) toast.message(`API key — copy now: ${data.api_key}`, { duration: 20000 });
      qc.invalidateQueries({ queryKey: ["gen-history"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const publishMutation = useMutation({
    mutationFn: (id: string) => productGeneratorApi.publish(id),
    onSuccess: (data) => {
      setGeneration(data);
      toast.success("Product published!");
      qc.invalidateQueries({ queryKey: ["gen-history"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  function reset() {
    setStep("prompt");
    setPrompt("");
    setAnalysis(null);
    setGeneration(null);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Product Generator"
        description="Describe your product. We'll orchestrate the AI agent, knowledge base, widget, and template automatically."
        action={
          <Button variant="secondary" size="sm" onClick={() => setShowHistory(!showHistory)}>
            {showHistory ? "Hide history" : "View history"}
          </Button>
        }
      />

      {/* Stepper */}
      <div className="flex items-center justify-between">
        <Stepper current={step} />
        {step !== "prompt" && (
          <button onClick={reset} className="text-xs text-muted hover:text-ink">Start over</button>
        )}
      </div>

      {/* STEP 1 — Prompt */}
      {step === "prompt" && (
        <Card>
          <CardHeader title="Describe your product" description="Be specific about the industry, use-case, and AI features you need." />
          <Textarea
            placeholder="e.g. Restaurant website with AI ordering, menu search, and table booking..."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={4}
            className="mb-4"
          />
          <div className="mb-4 flex flex-wrap gap-2">
            {EXAMPLE_PROMPTS.map((ex) => (
              <button
                key={ex}
                onClick={() => setPrompt(ex)}
                className="rounded-full border border-line bg-canvas px-3 py-1 text-xs text-muted hover:border-brand hover:text-brand transition"
              >
                {ex}
              </button>
            ))}
          </div>
          <Button
            disabled={!prompt.trim() || analyzeMutation.isPending}
            onClick={() => analyzeMutation.mutate()}
            className="gap-2"
          >
            <Search size={14} />
            {analyzeMutation.isPending ? "Analyzing…" : "Analyze prompt"}
          </Button>
        </Card>
      )}

      {/* STEP 2 — Analysis result */}
      {step === "analyze" && analysis && (
        <>
          <Card>
            <CardHeader title="Prompt" />
            <p className="text-sm text-muted italic">"{prompt}"</p>
          </Card>
          <AnalysisCard
            analysis={analysis}
            generating={generateMutation.isPending}
            onProceed={() => generateMutation.mutate()}
          />
        </>
      )}

      {/* STEP 3 — Generating (in-progress) */}
      {step === "generate" && (
        <Card>
          <div className="flex flex-col items-center gap-4 py-8">
            <div className="animate-spin rounded-full h-12 w-12 border-4 border-line border-t-brand" />
            <p className="font-semibold text-ink">Assembling your product…</p>
            <p className="text-sm text-muted text-center max-w-xs">
              Creating AI agent, knowledge base, widget, API key, and installing template.
            </p>
          </div>
        </Card>
      )}

      {/* STEP 4 — Preview + publish */}
      {step === "preview" && generation && (
        <ProductCard
          gen={generation}
          publishing={publishMutation.isPending}
          onPublish={(id) => publishMutation.mutate(id)}
        />
      )}

      {/* History drawer */}
      {showHistory && (
        <Card>
          <CardHeader title="Generation History" />
          {history.isLoading && <p className="text-sm text-muted">Loading…</p>}
          {!history.data?.length && !history.isLoading && (
            <EmptyState title="No generations yet" />
          )}
          <ul className="space-y-3">
            {(history.data || []).map((gen) => (
              <li key={gen.id} className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm font-medium text-ink line-clamp-1">{gen.prompt}</p>
                  <p className="text-xs text-muted">{formatDate(gen.created_at)}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={STATUS_TONE[gen.status] ?? "neutral"}>{gen.status.replace("_", " ")}</Badge>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => {
                      setPrompt(gen.prompt);
                      setGeneration(gen);
                      setStep("preview");
                      setShowHistory(false);
                    }}
                  >
                    View
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
