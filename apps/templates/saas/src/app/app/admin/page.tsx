"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { canAccessAdmin, canManageTemplates, canPlatformAdmin } from "@/lib/permissions";
import {
  agentStoreApi,
  marketplaceApi,
  type AgentListing,
  type AbuseReport,
  type TemplateItem
} from "@/lib/services";
import { EmptyState, PageHeader, Stat } from "@/components/ui/misc";
import { Badge, Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";

type AdminTab = "registry" | "store";

const CATEGORIES = [
  "website",
  "landing",
  "saas",
  "writing",
  "coding",
  "marketing",
  "finance",
  "hr",
  "legal",
  "healthcare",
  "education",
  "research",
  "ai_agents",
  "business",
  "analytics"
];

function catalogTone(status: string): "success" | "warn" | "neutral" | "brand" {
  switch (status) {
    case "published":
      return "success";
    case "draft":
      return "warn";
    case "archived":
      return "neutral";
    default:
      return "brand";
  }
}

function DialogShell({
  open,
  title,
  children,
  onClose
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center">
      <button type="button" aria-label="Close" className="absolute inset-0 bg-ink/40" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        className="relative z-10 max-h-[90vh] w-full overflow-y-auto rounded-t-2xl border border-line bg-panel p-5 shadow-xl sm:max-w-lg sm:rounded-2xl"
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <h2 className="text-lg font-semibold text-ink">{title}</h2>
          <Button size="sm" variant="ghost" onClick={onClose}>
            Close
          </Button>
        </div>
        {children}
      </div>
    </div>
  );
}

function RegistryPanel() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("all");
  const [kind, setKind] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [versionFor, setVersionFor] = useState<TemplateItem | null>(null);
  const [form, setForm] = useState({
    slug: "",
    name: "",
    category: "writing",
    kind: "prompt",
    pricing_tier: "free",
    description: "",
    version: "1.0.0",
    publish: true,
    prompt: ""
  });
  const [versionForm, setVersionForm] = useState({ version: "", changelog: "" });

  const list = useQuery({
    queryKey: ["admin-registry", q, status, kind],
    queryFn: () =>
      marketplaceApi.adminList({
        q: q || undefined,
        status,
        kind: kind || undefined,
        sort: "updated",
        limit: 50
      })
  });

  const createMut = useMutation({
    mutationFn: () =>
      marketplaceApi.createTemplate({
        slug: form.slug.trim(),
        name: form.name.trim(),
        category: form.category,
        kind: form.kind,
        pricing_tier: form.pricing_tier,
        description: form.description,
        version: form.version,
        publish: form.publish,
        default_config:
          form.kind === "prompt" || form.kind === "agent"
            ? { prompt: form.prompt, temperature: 0.4, variables: [] }
            : {}
      }),
    onSuccess: () => {
      toast.success("Template created");
      setCreateOpen(false);
      qc.invalidateQueries({ queryKey: ["admin-registry"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const publishMut = useMutation({
    mutationFn: (id: string) => marketplaceApi.publishTemplate(id),
    onSuccess: () => {
      toast.success("Published");
      qc.invalidateQueries({ queryKey: ["admin-registry"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const archiveMut = useMutation({
    mutationFn: (id: string) => marketplaceApi.archiveTemplate(id),
    onSuccess: () => {
      toast.success("Archived");
      qc.invalidateQueries({ queryKey: ["admin-registry"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const featureMut = useMutation({
    mutationFn: ({ id, featured }: { id: string; featured: boolean }) =>
      marketplaceApi.updateTemplate(id, { is_featured: featured }),
    onSuccess: () => {
      toast.success("Updated featured flag");
      qc.invalidateQueries({ queryKey: ["admin-registry"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const versionMut = useMutation({
    mutationFn: () =>
      marketplaceApi.addVersion(versionFor!.id, {
        version: versionForm.version.trim(),
        changelog: versionForm.changelog || undefined,
        set_latest: true
      }),
    onSuccess: () => {
      toast.success("Version added");
      setVersionFor(null);
      qc.invalidateQueries({ queryKey: ["admin-registry"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const items = list.data?.items ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex flex-1 flex-col gap-2 sm:flex-row">
          <Input
            placeholder="Search slug, name…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="sm:max-w-xs"
          />
          <select
            className="rounded-xl border border-line bg-panel px-3 py-2 text-sm"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="all">All statuses</option>
            <option value="published">Published</option>
            <option value="draft">Draft</option>
            <option value="archived">Archived</option>
          </select>
          <select
            className="rounded-xl border border-line bg-panel px-3 py-2 text-sm"
            value={kind}
            onChange={(e) => setKind(e.target.value)}
          >
            <option value="">All kinds</option>
            <option value="package">Package</option>
            <option value="prompt">Prompt</option>
            <option value="agent">Agent</option>
          </select>
        </div>
        <Button onClick={() => setCreateOpen(true)}>New template</Button>
      </div>

      {list.isLoading ? (
        <p className="text-sm text-muted">Loading registry…</p>
      ) : items.length === 0 ? (
        <EmptyState title="No templates" description="Create a catalog entry or adjust filters." />
      ) : (
        <div className="space-y-3">
          {items.map((t) => (
            <Card key={t.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-semibold text-ink">{t.name}</p>
                  <Badge tone={catalogTone(t.status)}>{t.status}</Badge>
                  <Badge tone="neutral">{t.kind || "package"}</Badge>
                  {t.is_featured && <Badge tone="brand">featured</Badge>}
                </div>
                <p className="mt-1 truncate text-xs text-muted">
                  {t.slug} · v{t.version} · {t.category} · {t.pricing_tier || "free"} · installs {t.install_count}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {t.status !== "published" && (
                  <Button size="sm" variant="secondary" onClick={() => publishMut.mutate(t.id)}>
                    Publish
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => featureMut.mutate({ id: t.id, featured: !t.is_featured })}
                >
                  {t.is_featured ? "Unfeature" : "Feature"}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setVersionFor(t);
                    setVersionForm({ version: "", changelog: "" });
                  }}
                >
                  Add version
                </Button>
                {t.status !== "archived" && (
                  <Button size="sm" variant="ghost" onClick={() => archiveMut.mutate(t.id)}>
                    Archive
                  </Button>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      <DialogShell open={createOpen} title="Create template" onClose={() => setCreateOpen(false)}>
        <div className="space-y-3">
          <div>
            <Label>Slug</Label>
            <Input value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} placeholder="my-prompt" />
          </div>
          <div>
            <Label>Name</Label>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Category</Label>
              <select
                className="mt-1 w-full rounded-xl border border-line bg-panel px-3 py-2 text-sm"
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
              >
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label>Kind</Label>
              <select
                className="mt-1 w-full rounded-xl border border-line bg-panel px-3 py-2 text-sm"
                value={form.kind}
                onChange={(e) => setForm({ ...form, kind: e.target.value })}
              >
                <option value="prompt">prompt</option>
                <option value="agent">agent</option>
                <option value="package">package</option>
              </select>
            </div>
          </div>
          <div>
            <Label>Description</Label>
            <Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </div>
          {(form.kind === "prompt" || form.kind === "agent") && (
            <div>
              <Label>Prompt</Label>
              <textarea
                className="mt-1 min-h-[100px] w-full rounded-xl border border-line bg-panel px-3 py-2 text-sm"
                value={form.prompt}
                onChange={(e) => setForm({ ...form, prompt: e.target.value })}
              />
            </div>
          )}
          <label className="flex items-center gap-2 text-sm text-ink">
            <input
              type="checkbox"
              checked={form.publish}
              onChange={(e) => setForm({ ...form, publish: e.target.checked })}
            />
            Publish immediately
          </label>
          <Button
            className="w-full"
            disabled={!form.slug || !form.name || createMut.isPending}
            onClick={() => createMut.mutate()}
          >
            {createMut.isPending ? "Creating…" : "Create"}
          </Button>
        </div>
      </DialogShell>

      <DialogShell
        open={Boolean(versionFor)}
        title={`Add version${versionFor ? ` — ${versionFor.name}` : ""}`}
        onClose={() => setVersionFor(null)}
      >
        <div className="space-y-3">
          <div>
            <Label>Version</Label>
            <Input
              placeholder="1.1.0"
              value={versionForm.version}
              onChange={(e) => setVersionForm({ ...versionForm, version: e.target.value })}
            />
          </div>
          <div>
            <Label>Changelog</Label>
            <Input
              value={versionForm.changelog}
              onChange={(e) => setVersionForm({ ...versionForm, changelog: e.target.value })}
            />
          </div>
          <Button
            className="w-full"
            disabled={!versionForm.version || versionMut.isPending}
            onClick={() => versionMut.mutate()}
          >
            {versionMut.isPending ? "Saving…" : "Publish version"}
          </Button>
        </div>
      </DialogShell>
    </div>
  );
}

function StorePanel() {
  const qc = useQueryClient();
  const stats = useQuery({ queryKey: ["agent-store-stats"], queryFn: agentStoreApi.adminStats });
  const pending = useQuery({ queryKey: ["agent-store-pending"], queryFn: () => agentStoreApi.pending(50) });
  const abuse = useQuery({
    queryKey: ["agent-store-abuse"],
    queryFn: () => agentStoreApi.abuseReports({ status: "open", limit: 50 })
  });

  const moderateMut = useMutation({
    mutationFn: ({ id, action }: { id: string; action: string }) =>
      agentStoreApi.moderate(id, { action }),
    onSuccess: () => {
      toast.success("Moderation applied");
      qc.invalidateQueries({ queryKey: ["agent-store-pending"] });
      qc.invalidateQueries({ queryKey: ["agent-store-stats"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const resolveMut = useMutation({
    mutationFn: (id: string) => agentStoreApi.resolveAbuse(id, { status: "resolved" }),
    onSuccess: () => {
      toast.success("Report resolved");
      qc.invalidateQueries({ queryKey: ["agent-store-abuse"] });
      qc.invalidateQueries({ queryKey: ["agent-store-stats"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Listings" value={String(stats.data?.listings_total ?? "—")} />
        <Stat label="Pending review" value={String(stats.data?.pending_review ?? "—")} />
        <Stat label="Published" value={String(stats.data?.published ?? "—")} />
        <Stat label="Open abuse" value={String(stats.data?.open_abuse_reports ?? "—")} />
      </div>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">Pending listings</h3>
        {(pending.data ?? []).length === 0 ? (
          <EmptyState title="Queue empty" description="No listings awaiting moderation." />
        ) : (
          (pending.data as AgentListing[]).map((l) => (
            <Card key={l.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-semibold text-ink">{l.title}</p>
                <p className="text-xs text-muted">
                  {l.slug} · {l.publisher_name || "publisher"} · {l.status}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" onClick={() => moderateMut.mutate({ id: l.id, action: "approve" })}>
                  Approve
                </Button>
                <Button size="sm" variant="secondary" onClick={() => moderateMut.mutate({ id: l.id, action: "reject" })}>
                  Reject
                </Button>
                <Button size="sm" variant="ghost" onClick={() => moderateMut.mutate({ id: l.id, action: "feature" })}>
                  Feature
                </Button>
              </div>
            </Card>
          ))
        )}
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">Open abuse reports</h3>
        {(abuse.data ?? []).length === 0 ? (
          <EmptyState title="No open reports" />
        ) : (
          (abuse.data as AbuseReport[]).map((r) => (
            <Card key={r.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-semibold text-ink">{r.reason}</p>
                <p className="text-xs text-muted">
                  listing {r.listing_id.slice(0, 8)}… · {r.details || "no details"}
                </p>
              </div>
              <Button size="sm" variant="secondary" onClick={() => resolveMut.mutate(r.id)}>
                Resolve
              </Button>
            </Card>
          ))
        )}
      </section>
    </div>
  );
}

export default function AdminPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const manage = canManageTemplates(user?.role);
  const platform = canPlatformAdmin(user?.role);
  const allowed = canAccessAdmin(user?.role);

  const defaultTab: AdminTab = manage ? "registry" : "store";
  const [tab, setTab] = useState<AdminTab>(defaultTab);

  useEffect(() => {
    if (!loading && !allowed) router.replace("/app");
  }, [loading, allowed, router]);

  useEffect(() => {
    if (tab === "registry" && !manage && platform) setTab("store");
    if (tab === "store" && !platform && manage) setTab("registry");
  }, [tab, manage, platform]);

  const tabs = useMemo(() => {
    const items: { key: AdminTab; label: string }[] = [];
    if (manage) items.push({ key: "registry", label: "Registry" });
    if (platform) items.push({ key: "store", label: "Agent Store" });
    return items;
  }, [manage, platform]);

  if (loading || !allowed) {
    return <div className="text-sm text-muted">Checking access…</div>;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Admin"
        description="Marketplace registry curation and agent-store moderation."
      />

      <div className="flex flex-wrap gap-2 border-b border-line pb-3">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={
              tab === t.key
                ? "rounded-full bg-brand-soft px-3 py-1.5 text-sm font-semibold text-brand-dark"
                : "rounded-full px-3 py-1.5 text-sm text-muted hover:bg-canvas hover:text-ink"
            }
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "registry" && manage ? <RegistryPanel /> : null}
      {tab === "store" && platform ? <StorePanel /> : null}
    </div>
  );
}
