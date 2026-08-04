"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { canAccessAdmin, canManageTemplates, canPlatformAdmin } from "@/lib/permissions";
import {
  agentStoreApi,
  billingApi,
  marketplaceApi,
  type AgentListing,
  type AbuseReport,
  type BillingAdminAnalytics,
  type TemplateItem,
  type TemplateVersion
} from "@/lib/services";
import { formatDate } from "@/lib/utils";
import { EmptyState, PageHeader, Stat } from "@/components/ui/misc";
import { Badge, Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";

type AdminTab = "registry" | "store" | "analytics" | "billing";

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
        className="relative z-10 max-h-[90vh] w-full overflow-y-auto rounded-t-2xl border border-line bg-panel p-5 shadow-xl sm:max-w-xl sm:rounded-2xl"
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
  const [versionForm, setVersionForm] = useState({ version: "", release_notes: "" });
  const [editingNotes, setEditingNotes] = useState<Record<string, string>>({});

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

  const versionsQuery = useQuery({
    queryKey: ["admin-versions", versionFor?.id],
    enabled: Boolean(versionFor?.id),
    queryFn: () => marketplaceApi.versions(versionFor!.id)
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
        release_notes: versionForm.release_notes || undefined,
        set_latest: true
      }),
    onSuccess: () => {
      toast.success("Version published");
      setVersionForm({ version: "", release_notes: "" });
      qc.invalidateQueries({ queryKey: ["admin-registry"] });
      qc.invalidateQueries({ queryKey: ["admin-versions", versionFor?.id] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const notesMut = useMutation({
    mutationFn: ({ version, notes }: { version: string; notes: string }) =>
      marketplaceApi.updateVersion(versionFor!.id, version, { release_notes: notes }),
    onSuccess: () => {
      toast.success("Release notes saved");
      qc.invalidateQueries({ queryKey: ["admin-versions", versionFor?.id] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const promoteMut = useMutation({
    mutationFn: (version: string) => marketplaceApi.promoteVersion(versionFor!.id, version),
    onSuccess: () => {
      toast.success("Promoted to latest");
      qc.invalidateQueries({ queryKey: ["admin-registry"] });
      qc.invalidateQueries({ queryKey: ["admin-versions", versionFor?.id] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const items = list.data?.items ?? [];
  const history = (versionsQuery.data || []) as TemplateVersion[];

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
                    setVersionForm({ version: "", release_notes: "" });
                    setEditingNotes({});
                  }}
                >
                  Versions
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
        title={`Versions${versionFor ? ` — ${versionFor.name}` : ""}`}
        onClose={() => setVersionFor(null)}
      >
        <div className="space-y-5">
          <section className="space-y-3 rounded-xl border border-line bg-canvas p-3">
            <p className="text-sm font-semibold text-ink">Publish new release</p>
            <div>
              <Label>Version</Label>
              <Input
                placeholder="1.1.0"
                value={versionForm.version}
                onChange={(e) => setVersionForm({ ...versionForm, version: e.target.value })}
              />
            </div>
            <div>
              <Label>Release notes</Label>
              <textarea
                className="mt-1 min-h-[80px] w-full rounded-xl border border-line bg-panel px-3 py-2 text-sm"
                placeholder="- Fix …&#10;- Improve …"
                value={versionForm.release_notes}
                onChange={(e) => setVersionForm({ ...versionForm, release_notes: e.target.value })}
              />
            </div>
            <Button
              className="w-full"
              disabled={!versionForm.version || versionMut.isPending}
              onClick={() => versionMut.mutate()}
            >
              {versionMut.isPending ? "Publishing…" : "Publish as latest"}
            </Button>
          </section>

          <section className="space-y-3">
            <p className="text-sm font-semibold text-ink">Release history</p>
            {versionsQuery.isLoading ? (
              <p className="text-sm text-muted">Loading versions…</p>
            ) : history.length === 0 ? (
              <EmptyState title="No versions yet" />
            ) : (
              history.map((v) => {
                const notes =
                  editingNotes[v.id] ?? v.release_notes ?? v.changelog ?? "";
                return (
                  <div key={v.id} className="rounded-xl border border-line p-3">
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <span className="font-semibold text-ink">v{v.version}</span>
                      {v.is_latest && <Badge tone="brand">latest</Badge>}
                      <span className="text-xs text-muted">{formatDate(v.published_at || v.created_at)}</span>
                    </div>
                    <textarea
                      className="min-h-[64px] w-full rounded-xl border border-line bg-panel px-3 py-2 text-sm"
                      value={notes}
                      onChange={(e) =>
                        setEditingNotes((prev) => ({ ...prev, [v.id]: e.target.value }))
                      }
                    />
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        variant="secondary"
                        disabled={notesMut.isPending}
                        onClick={() => notesMut.mutate({ version: v.version, notes })}
                      >
                        Save notes
                      </Button>
                      {!v.is_latest && (
                        <Button
                          size="sm"
                          variant="ghost"
                          disabled={promoteMut.isPending}
                          onClick={() => promoteMut.mutate(v.version)}
                        >
                          Promote to latest
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </section>
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
                <Button size="sm" variant="ghost" onClick={() => moderateMut.mutate({ id: l.id, action: "suspend" })}>
                  Suspend
                </Button>
                <Button size="sm" variant="ghost" onClick={() => moderateMut.mutate({ id: l.id, action: "feature" })}>
                  Feature
                </Button>
                <Button size="sm" variant="ghost" onClick={() => moderateMut.mutate({ id: l.id, action: "unfeature" })}>
                  Unfeature
                </Button>
                <Button size="sm" variant="ghost" onClick={() => moderateMut.mutate({ id: l.id, action: "verify" })}>
                  Verify publisher
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

function CatalogAnalyticsPanel() {
  const analytics = useQuery({
    queryKey: ["admin-marketplace-analytics"],
    queryFn: () => marketplaceApi.adminAnalytics(30)
  });
  const catalog = analytics.data?.catalog;
  const company = analytics.data?.company;

  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Catalog templates" value={String(catalog?.templates_total ?? "—")} />
        <Stat label="Published" value={String(catalog?.published ?? "—")} />
        <Stat label="Active installs" value={String(catalog?.active_installs ?? "—")} />
        <Stat label="Favorites" value={String(catalog?.favorites_total ?? "—")} />
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label="Draft" value={String(catalog?.draft ?? "—")} />
        <Stat label="Archived" value={String(catalog?.archived ?? "—")} />
        <Stat label="Your installs" value={String(company?.installed_count ?? "—")} />
      </div>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">Top templates</h3>
        {(catalog?.top_templates || []).length === 0 ? (
          <EmptyState title="No catalog data" />
        ) : (
          (catalog?.top_templates || []).map((t) => (
            <Card key={t.template_id} className="flex items-center justify-between gap-3 p-4">
              <div className="min-w-0">
                <p className="font-semibold text-ink">{t.name}</p>
                <p className="truncate text-xs text-muted">
                  {t.slug} · {t.kind} · {t.category}
                </p>
              </div>
              <Badge tone="brand">{t.install_count} installs</Badge>
            </Card>
          ))
        )}
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">By kind</h3>
        <div className="flex flex-wrap gap-2">
          {(catalog?.by_kind || []).map((item) => (
            <Badge key={item.key} tone="neutral">
              {item.label}: {item.count}
            </Badge>
          ))}
          {!(catalog?.by_kind || []).length && <p className="text-sm text-muted">No data</p>}
        </div>
      </section>
    </div>
  );
}

function BillingAdminPanel() {
  const analytics = useQuery({
    queryKey: ["admin-billing-analytics"],
    queryFn: billingApi.adminAnalytics
  });
  const data = analytics.data as BillingAdminAnalytics | undefined;

  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="MRR" value={data ? `$${data.mrr.toFixed(2)}` : "—"} />
        <Stat label="ARR" value={data ? `$${data.arr.toFixed(2)}` : "—"} />
        <Stat label="Revenue" value={data ? `$${data.revenue.toFixed(2)}` : "—"} />
        <Stat label="Gross margin" value={data ? `$${data.gross_margin.toFixed(2)}` : "—"} />
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Refunds" value={data ? `$${data.refunds.toFixed(2)}` : "—"} />
        <Stat label="Failed payments" value={String(data?.failed_payments ?? "—")} />
        <Stat label="Active subs" value={String(data?.active_subscriptions ?? "—")} />
        <Stat label="Token usage" value={String(data?.token_usage ?? "—")} />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Stat label="AI costs" value={data ? `$${data.ai_costs.toFixed(4)}` : "—"} />
        <Stat
          label="Providers"
          value={
            data?.providers
              ? `S:${data.providers.stripe?.available ? "on" : "off"} R:${data.providers.razorpay?.available ? "on" : "off"}`
              : "—"
          }
        />
      </div>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">Top plans</h3>
        {(data?.top_plans || []).length === 0 ? (
          <EmptyState title="No subscription mix yet" />
        ) : (
          (data?.top_plans || []).map((p) => (
            <Card key={p.plan} className="flex items-center justify-between p-4">
              <p className="font-semibold text-ink">{p.plan}</p>
              <Badge tone="brand">{p.active_subscriptions} active</Badge>
            </Card>
          ))
        )}
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">Top customers</h3>
        {(data?.top_customers || []).length === 0 ? (
          <EmptyState title="No paid customers yet" />
        ) : (
          (data?.top_customers || []).map((c) => (
            <Card key={c.company_id} className="flex items-center justify-between p-4">
              <p className="font-mono text-xs text-muted">{c.company_id}</p>
              <p className="font-semibold text-ink">${c.revenue.toFixed(2)}</p>
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
    if (tab === "analytics" && !manage) setTab(platform ? "store" : "registry");
    if (tab === "billing" && !platform) setTab(manage ? "registry" : "store");
  }, [tab, manage, platform]);

  const tabs = useMemo(() => {
    const items: { key: AdminTab; label: string }[] = [];
    if (manage) items.push({ key: "registry", label: "Registry" });
    if (manage) items.push({ key: "analytics", label: "Analytics" });
    if (platform) items.push({ key: "store", label: "Agent Store" });
    if (platform) items.push({ key: "billing", label: "Billing" });
    return items;
  }, [manage, platform]);

  if (loading || !allowed) {
    return <div className="text-sm text-muted">Checking access…</div>;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Admin"
        description="Marketplace registry curation, analytics, and agent-store moderation."
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
      {tab === "analytics" && manage ? <CatalogAnalyticsPanel /> : null}
      {tab === "store" && platform ? <StorePanel /> : null}
      {tab === "billing" && platform ? <BillingAdminPanel /> : null}
    </div>
  );
}
