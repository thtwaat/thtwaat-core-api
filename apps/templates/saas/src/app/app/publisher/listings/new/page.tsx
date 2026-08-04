"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { agentStoreApi } from "@/lib/services";
import { PageHeader } from "@/components/ui/misc";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PublisherNav, slugify } from "@/components/publisher/nav";
import { cn } from "@/lib/utils";

const STEPS = [
  "Basic Info",
  "Branding",
  "Configuration",
  "Pricing",
  "Verification",
  "Preview",
  "Submit"
] as const;

type FormState = {
  title: string;
  slug: string;
  short_description: string;
  long_description: string;
  category: string;
  tags: string;
  language: string;
  version: string;
  logo_url: string;
  cover_url: string;
  gallery: string;
  demo_url: string;
  prompt: string;
  knowledge: string;
  widget: string;
  agent: string;
  api_notes: string;
  env_vars: string;
  pricing_model: string;
  pricing_tier: string;
  price_amount: string;
  permissions_ok: boolean;
  dependencies_ok: boolean;
  compatibility_ok: boolean;
  security_ok: boolean;
  checklist_ok: boolean;
};

const initial: FormState = {
  title: "",
  slug: "",
  short_description: "",
  long_description: "",
  category: "ai_agents",
  tags: "",
  language: "en",
  version: "1.0.0",
  logo_url: "",
  cover_url: "",
  gallery: "",
  demo_url: "",
  prompt: "",
  knowledge: "",
  widget: "",
  agent: "",
  api_notes: "",
  env_vars: "",
  pricing_model: "free",
  pricing_tier: "free",
  price_amount: "0",
  permissions_ok: false,
  dependencies_ok: false,
  compatibility_ok: false,
  security_ok: false,
  checklist_ok: false
};

export default function PublishWizardPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<FormState>(initial);
  const [aiBusy, setAiBusy] = useState(false);

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const canNext = useMemo(() => {
    if (step === 0) return form.title.trim().length >= 2 && form.slug.trim().length >= 2;
    if (step === 4)
      return (
        form.permissions_ok &&
        form.dependencies_ok &&
        form.compatibility_ok &&
        form.security_ok
      );
    if (step === 5) return form.checklist_ok;
    return true;
  }, [step, form]);

  const createMut = useMutation({
    mutationFn: async (mode: "draft" | "private" | "review") => {
      const screenshots = form.gallery
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean);
      const tags = form.tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      const envPairs = form.env_vars
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean)
        .map((line) => {
          const [k, ...rest] = line.split("=");
          return [k.trim(), rest.join("=").trim()] as const;
        })
        .filter(([k]) => k);
      const env_object = Object.fromEntries(envPairs);

      return agentStoreApi.createListing({
        title: form.title.trim(),
        slug: form.slug.trim(),
        short_description: form.short_description,
        long_description: form.long_description,
        screenshots,
        demo_url: form.demo_url || null,
        cover_url: form.cover_url || null,
        logo_url: form.logo_url || null,
        supported_languages: [form.language || "en"],
        knowledge_requirements: form.knowledge || null,
        categories: [form.category],
        tags,
        pricing_model: form.pricing_model,
        price_amount: Number(form.price_amount || 0),
        currency: "USD",
        pricing_tier: form.pricing_tier,
        marketplace_category: form.category,
        version: form.version || "1.0.0",
        release_notes: "Initial release",
        submit_for_review: mode === "review",
        as_private: mode === "private",
        default_config: {
          store: {
            prompt: form.prompt,
            knowledge: form.knowledge,
            widget: form.widget,
            agent: form.agent,
            api: form.api_notes,
            env: env_object,
            pricing_tier: form.pricing_tier
          }
        }
      });
    },
    onSuccess: (listing, mode) => {
      toast.success(
        mode === "review"
          ? "Submitted for review"
          : mode === "private"
            ? "Saved as private"
            : "Draft saved"
      );
      router.push(`/app/publisher/listings/${listing.id}`);
    },
    onError: (e: Error) => toast.error(e.message)
  });

  async function runAi(kind: string) {
    setAiBusy(true);
    try {
      const res = await agentStoreApi.aiGenerate({
        kind,
        title: form.title || "Untitled",
        short_description: form.short_description,
        long_description: form.long_description,
        categories: [form.category],
        tags: form.tags.split(",").map((t) => t.trim()).filter(Boolean),
        language: form.language
      });
      if (kind === "summary") set("short_description", res.result);
      else if (kind === "tags") set("tags", res.tags.join(", ") || res.result);
      else if (kind === "documentation") set("long_description", res.result);
      else if (kind === "seo_description") set("short_description", res.result);
      else if (kind === "screenshots_description") {
        toast.message(res.result);
      }
      toast.success(`Generated ${kind.replace(/_/g, " ")}`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "AI generate failed");
    } finally {
      setAiBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Publish Wizard"
        description="Seven steps from draft to marketplace review."
      />
      <PublisherNav />

      <ol className="flex flex-wrap gap-2">
        {STEPS.map((label, i) => (
          <li key={label}>
            <button
              type="button"
              onClick={() => setStep(i)}
              className={cn(
                "rounded-full px-3 py-1 text-xs font-medium",
                i === step ? "bg-ink text-white" : i < step ? "bg-teal-50 text-teal-800" : "bg-slate-100 text-muted"
              )}
            >
              {i + 1}. {label}
            </button>
          </li>
        ))}
      </ol>

      <Card className="space-y-4 p-6">
        {step === 0 && (
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Name">
              <Input
                value={form.title}
                onChange={(e) => {
                  const title = e.target.value;
                  setForm((prev) => ({
                    ...prev,
                    title,
                    slug: prev.slug && prev.slug !== slugify(prev.title) ? prev.slug : slugify(title)
                  }));
                }}
              />
            </Field>
            <Field label="Slug">
              <Input value={form.slug} onChange={(e) => set("slug", slugify(e.target.value))} />
            </Field>
            <Field label="Short description" className="md:col-span-2">
              <Input
                value={form.short_description}
                onChange={(e) => set("short_description", e.target.value)}
              />
            </Field>
            <Field label="Long description" className="md:col-span-2">
              <textarea
                className="min-h-28 w-full rounded-xl border border-line bg-panel px-3 py-2 text-sm"
                value={form.long_description}
                onChange={(e) => set("long_description", e.target.value)}
              />
            </Field>
            <Field label="Category">
              <Input value={form.category} onChange={(e) => set("category", e.target.value)} />
            </Field>
            <Field label="Tags (comma-separated)">
              <Input value={form.tags} onChange={(e) => set("tags", e.target.value)} />
            </Field>
            <Field label="Language">
              <Input value={form.language} onChange={(e) => set("language", e.target.value)} />
            </Field>
            <Field label="Version">
              <Input value={form.version} onChange={(e) => set("version", e.target.value)} />
            </Field>
            <div className="md:col-span-2 flex flex-wrap gap-2">
              <Button type="button" size="sm" variant="secondary" disabled={aiBusy} onClick={() => runAi("summary")}>
                AI: Summary
              </Button>
              <Button type="button" size="sm" variant="secondary" disabled={aiBusy} onClick={() => runAi("tags")}>
                AI: Tags
              </Button>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                disabled={aiBusy}
                onClick={() => runAi("documentation")}
              >
                AI: Documentation
              </Button>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                disabled={aiBusy}
                onClick={() => runAi("seo_description")}
              >
                AI: SEO
              </Button>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Logo URL">
              <Input value={form.logo_url} onChange={(e) => set("logo_url", e.target.value)} />
            </Field>
            <Field label="Cover URL">
              <Input value={form.cover_url} onChange={(e) => set("cover_url", e.target.value)} />
            </Field>
            <Field label="Gallery (one URL per line)" className="md:col-span-2">
              <textarea
                className="min-h-24 w-full rounded-xl border border-line bg-panel px-3 py-2 text-sm"
                value={form.gallery}
                onChange={(e) => set("gallery", e.target.value)}
              />
            </Field>
            <Field label="Demo / video URL" className="md:col-span-2">
              <Input value={form.demo_url} onChange={(e) => set("demo_url", e.target.value)} />
            </Field>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              disabled={aiBusy}
              onClick={() => runAi("screenshots_description")}
            >
              AI: Screenshot descriptions
            </Button>
          </div>
        )}

        {step === 2 && (
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Prompt" className="md:col-span-2">
              <textarea
                className="min-h-20 w-full rounded-xl border border-line bg-panel px-3 py-2 text-sm"
                value={form.prompt}
                onChange={(e) => set("prompt", e.target.value)}
              />
            </Field>
            <Field label="Knowledge">
              <Input value={form.knowledge} onChange={(e) => set("knowledge", e.target.value)} />
            </Field>
            <Field label="Widget">
              <Input value={form.widget} onChange={(e) => set("widget", e.target.value)} />
            </Field>
            <Field label="Agent">
              <Input value={form.agent} onChange={(e) => set("agent", e.target.value)} />
            </Field>
            <Field label="API notes">
              <Input value={form.api_notes} onChange={(e) => set("api_notes", e.target.value)} />
            </Field>
            <Field label="Environment variables (KEY=value per line)" className="md:col-span-2">
              <textarea
                className="min-h-24 w-full rounded-xl border border-line bg-panel px-3 py-2 text-sm font-mono"
                value={form.env_vars}
                onChange={(e) => set("env_vars", e.target.value)}
              />
            </Field>
          </div>
        )}

        {step === 3 && (
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Pricing model">
              <select
                className="h-11 w-full rounded-xl border border-line bg-panel px-3 text-sm"
                value={form.pricing_model}
                onChange={(e) => set("pricing_model", e.target.value)}
              >
                <option value="free">Free</option>
                <option value="one_time">One-time</option>
                <option value="subscription">Subscription</option>
              </select>
            </Field>
            <Field label="Plan badge">
              <select
                className="h-11 w-full rounded-xl border border-line bg-panel px-3 text-sm"
                value={form.pricing_tier}
                onChange={(e) => set("pricing_tier", e.target.value)}
              >
                <option value="free">Free</option>
                <option value="pro">Pro</option>
                <option value="enterprise">Enterprise</option>
              </select>
            </Field>
            <Field label="Price amount (USD)">
              <Input
                type="number"
                min="0"
                step="0.01"
                value={form.price_amount}
                onChange={(e) => set("price_amount", e.target.value)}
              />
            </Field>
          </div>
        )}

        {step === 4 && (
          <div className="space-y-3">
            <Check
              label="Permissions reviewed (scopes, data access)"
              checked={form.permissions_ok}
              onChange={(v) => set("permissions_ok", v)}
            />
            <Check
              label="Dependencies declared and compatible"
              checked={form.dependencies_ok}
              onChange={(v) => set("dependencies_ok", v)}
            />
            <Check
              label="THTWAAT Cloud compatibility confirmed"
              checked={form.compatibility_ok}
              onChange={(v) => set("compatibility_ok", v)}
            />
            <Check
              label="Security scan / secrets check completed"
              checked={form.security_ok}
              onChange={(v) => set("security_ok", v)}
            />
          </div>
        )}

        {step === 5 && (
          <div className="space-y-4">
            <div className="rounded-xl border border-line bg-canvas p-4">
              <p className="text-lg font-semibold text-ink">{form.title || "Untitled"}</p>
              <p className="text-sm text-muted">{form.short_description || "No short description"}</p>
              <p className="mt-2 text-xs text-muted">
                {form.pricing_tier.toUpperCase()} · {form.pricing_model} · v{form.version} ·{" "}
                {form.category}
              </p>
            </div>
            <Check
              label="Review checklist complete (preview + install test mentally verified)"
              checked={form.checklist_ok}
              onChange={(v) => set("checklist_ok", v)}
            />
          </div>
        )}

        {step === 6 && (
          <div className="space-y-4">
            <p className="text-sm text-muted">
              Choose how to save this listing. Publishing to the public store requires admin approval
              after “Submit for Review”.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="secondary"
                disabled={createMut.isPending}
                onClick={() => createMut.mutate("draft")}
              >
                Save draft
              </Button>
              <Button
                variant="secondary"
                disabled={createMut.isPending}
                onClick={() => createMut.mutate("private")}
              >
                Save private
              </Button>
              <Button disabled={createMut.isPending} onClick={() => createMut.mutate("review")}>
                Submit for review
              </Button>
            </div>
          </div>
        )}

        <div className="flex justify-between border-t border-line pt-4">
          <Button
            type="button"
            variant="ghost"
            disabled={step === 0}
            onClick={() => setStep((s) => Math.max(0, s - 1))}
          >
            Back
          </Button>
          {step < STEPS.length - 1 ? (
            <Button type="button" disabled={!canNext} onClick={() => setStep((s) => s + 1)}>
              Continue
            </Button>
          ) : null}
        </div>
      </Card>
    </div>
  );
}

function Field({
  label,
  children,
  className
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <label className={cn("block space-y-1.5", className)}>
      <span className="text-xs font-medium uppercase tracking-wide text-muted">{label}</span>
      {children}
    </label>
  );
}

function Check({
  label,
  checked,
  onChange
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-start gap-3 rounded-xl border border-line px-3 py-3 text-sm">
      <input
        type="checkbox"
        className="mt-0.5"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span>{label}</span>
    </label>
  );
}
