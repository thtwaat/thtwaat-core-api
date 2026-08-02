"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  type Installation,
  type TemplateItem,
  type UpdateNotification,
  marketplaceApi
} from "@/lib/services";
import { formatDate } from "@/lib/utils";
import { PageHeader, EmptyState } from "@/components/ui/misc";
import { Badge, Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type TabKey = "browse" | "featured" | "favorites" | "installed" | "updates";

const CATEGORY_LABEL: Record<string, string> = {
  website: "Website",
  landing: "Landing",
  saas: "SaaS",
  crm: "CRM",
  helpdesk: "Helpdesk",
  ecommerce: "Ecommerce",
  education: "Education",
  healthcare: "Healthcare",
  real_estate: "Real Estate",
  restaurant: "Restaurant",
  finance: "Finance",
  legal: "Legal",
  writing: "Writing",
  coding: "Coding",
  marketing: "Marketing",
  hr: "HR",
  research: "Research",
  ai_agents: "AI Agents",
  business: "Business",
  analytics: "Analytics"
};

function statusTone(status: string): "success" | "warn" | "neutral" | "brand" {
  switch (status) {
    case "ready":
      return "success";
    case "published":
      return "brand";
    case "update_available":
      return "warn";
    default:
      return "neutral";
  }
}

function priceLabel(price: string | number | undefined, tier?: string) {
  const n = Number(price ?? 0);
  if (!(n > 0)) return tier && tier !== "free" ? tier : "Free";
  return `$${n}`;
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
      <button
        type="button"
        aria-label="Close dialog"
        className="absolute inset-0 bg-ink/40 backdrop-blur-[1px]"
        onClick={onClose}
      />
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

function TemplateCard({
  template,
  onOpen,
  onInstall,
  onToggleFavorite,
  installing,
  favoriting
}: {
  template: TemplateItem;
  onOpen: (t: TemplateItem) => void;
  onInstall: (t: TemplateItem) => void;
  onToggleFavorite: (t: TemplateItem) => void;
  installing: boolean;
  favoriting: boolean;
}) {
  return (
    <Card className="flex flex-col">
      <button type="button" className="text-left" onClick={() => onOpen(template)}>
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-line bg-canvas text-sm font-semibold uppercase text-brand">
            {(template.category || "t").slice(0, 2)}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-semibold text-ink">{template.name}</h3>
              {template.is_featured && <Badge tone="brand">Featured</Badge>}
              {template.installed && <Badge tone="success">Installed</Badge>}
              {template.update_available && <Badge tone="warn">Update</Badge>}
            </div>
            <p className="mt-1 text-xs capitalize text-muted">
              {CATEGORY_LABEL[template.category] || template.category}
              {template.kind ? ` · ${template.kind}` : ""} · v{template.version}
            </p>
          </div>
        </div>
        <p className="mt-3 line-clamp-2 text-sm text-muted">{template.description}</p>
      </button>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {(template.tags || []).slice(0, 4).map((tag) => (
          <span
            key={tag}
            className="rounded-full border border-line bg-canvas px-2 py-0.5 text-xs text-muted"
          >
            {tag}
          </span>
        ))}
      </div>
      <div className="mt-4 flex items-center justify-between gap-2">
        <span className="text-sm font-semibold">{priceLabel(template.price, template.pricing_tier)}</span>
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="secondary"
            disabled={favoriting}
            onClick={() => onToggleFavorite(template)}
          >
            {template.is_favorited ? "Unfavorite" : "Favorite"}
          </Button>
          {template.installed ? (
            <Badge tone="success">Installed</Badge>
          ) : (
            <Button size="sm" disabled={installing} onClick={() => onInstall(template)}>
              Install
            </Button>
          )}
        </div>
      </div>
      <p className="mt-2 text-xs text-muted">
        {template.install_count} install{template.install_count !== 1 ? "s" : ""}
      </p>
    </Card>
  );
}

function InstallCard({
  install,
  onUpdate,
  onRollback,
  onUninstall
}: {
  install: Installation;
  onUpdate: (install: Installation) => void;
  onRollback: (id: string) => void;
  onUninstall: (id: string) => void;
}) {
  return (
    <Card>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-semibold">{install.template_name || install.template_slug}</h3>
            <Badge tone={statusTone(install.status)}>{install.status}</Badge>
            {install.update_available && (
              <Badge tone="warn">→ {install.latest_available_version}</Badge>
            )}
          </div>
          <p className="mt-1 text-xs text-muted">
            v{install.installed_version} · Installed {formatDate(install.created_at)}
          </p>
          {install.failure_reason && (
            <p className="mt-1 text-sm text-red-600 dark:text-red-400">{install.failure_reason}</p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {install.update_available && (
            <Button size="sm" onClick={() => onUpdate(install)}>
              Update
            </Button>
          )}
          {install.previous_version && (
            <Button size="sm" variant="secondary" onClick={() => onRollback(install.id)}>
              Rollback to v{install.previous_version}
            </Button>
          )}
          <Button size="sm" variant="danger" onClick={() => onUninstall(install.id)}>
            Uninstall
          </Button>
        </div>
      </div>
    </Card>
  );
}

export default function MarketplacePage() {
  const qc = useQueryClient();
  const [activeTab, setActiveTab] = useState<TabKey>("browse");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [kindFilter, setKindFilter] = useState("");
  const [detail, setDetail] = useState<TemplateItem | null>(null);
  const [installTarget, setInstallTarget] = useState<TemplateItem | null>(null);
  const [updateTarget, setUpdateTarget] = useState<Installation | UpdateNotification | null>(null);

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedSearch(search.trim()), 250);
    return () => window.clearTimeout(t);
  }, [search]);

  const dash = useQuery({ queryKey: ["mkt-dashboard"], queryFn: marketplaceApi.dashboard });
  const templates = useQuery({
    queryKey: ["mkt-templates", debouncedSearch, selectedCategory, kindFilter, activeTab],
    enabled: activeTab === "browse" || activeTab === "featured",
    queryFn: () =>
      marketplaceApi.listPage({
        q: debouncedSearch || undefined,
        category: selectedCategory || undefined,
        kind: kindFilter || undefined,
        featured: activeTab === "featured" ? true : undefined,
        sort: activeTab === "featured" ? "featured" : "newest",
        limit: 48
      })
  });
  const favorites = useQuery({
    queryKey: ["mkt-favorites"],
    queryFn: marketplaceApi.favorites
  });
  const installed = useQuery({ queryKey: ["mkt-installed"], queryFn: marketplaceApi.installed });
  const updates = useQuery({ queryKey: ["mkt-updates"], queryFn: marketplaceApi.updates });
  const detailQuery = useQuery({
    queryKey: ["mkt-template", detail?.slug],
    enabled: Boolean(detail?.slug),
    queryFn: () => marketplaceApi.get(detail!.slug)
  });
  const versionsQuery = useQuery({
    queryKey: ["mkt-versions", detail?.slug],
    enabled: Boolean(detail?.slug),
    queryFn: () => marketplaceApi.versions(detail!.slug)
  });

  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ["mkt-templates"] });
    qc.invalidateQueries({ queryKey: ["mkt-installed"] });
    qc.invalidateQueries({ queryKey: ["mkt-dashboard"] });
    qc.invalidateQueries({ queryKey: ["mkt-updates"] });
    qc.invalidateQueries({ queryKey: ["mkt-favorites"] });
    if (detail?.slug) qc.invalidateQueries({ queryKey: ["mkt-template", detail.slug] });
  };

  const install = useMutation({
    mutationFn: (slug: string) => marketplaceApi.install(slug, { create_api_key: false }),
    onSuccess: (data) => {
      toast.success(`${data.template_name || data.template_slug} installed`);
      if (data.api_key) toast.message(`API key (copy now): ${data.api_key}`);
      setInstallTarget(null);
      setDetail(null);
      invalidateAll();
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const update = useMutation({
    mutationFn: (id: string) => marketplaceApi.update(id),
    onSuccess: () => {
      toast.success("Updated to latest version");
      setUpdateTarget(null);
      invalidateAll();
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const rollback = useMutation({
    mutationFn: (id: string) => marketplaceApi.rollback(id),
    onSuccess: () => {
      toast.success("Rolled back to previous version");
      invalidateAll();
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const uninstall = useMutation({
    mutationFn: (id: string) => marketplaceApi.uninstall(id),
    onSuccess: () => {
      toast.success("Uninstalled");
      invalidateAll();
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const favorite = useMutation({
    mutationFn: async (template: TemplateItem) => {
      if (template.is_favorited) {
        await marketplaceApi.unfavorite(template.slug);
        return { ...template, is_favorited: false };
      }
      return marketplaceApi.favorite(template.slug);
    },
    onSuccess: (t) => {
      toast.message(t.is_favorited ? "Added to favorites" : "Removed from favorites");
      invalidateAll();
      if (detail && (detail.slug === t.slug || detail.id === t.id)) {
        setDetail({ ...detail, is_favorited: Boolean(t.is_favorited) });
      }
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const categories = dash.data?.categories || [];
  const browseItems = useMemo(() => {
    if (activeTab === "featured" && !debouncedSearch && !selectedCategory && !kindFilter) {
      return dash.data?.featured || templates.data?.items || [];
    }
    return templates.data?.items || [];
  }, [activeTab, debouncedSearch, selectedCategory, kindFilter, dash.data?.featured, templates.data?.items]);

  const activeDetail = detailQuery.data || detail;

  const tabs: Array<{ key: TabKey; label: string }> = [
    { key: "browse", label: "Browse" },
    { key: "featured", label: "Featured" },
    { key: "favorites", label: `Favorites (${favorites.data?.length || 0})` },
    { key: "installed", label: `Installed (${installed.data?.length || 0})` },
    { key: "updates", label: `Updates (${updates.data?.length || 0})` }
  ];

  return (
    <div className="space-y-5">
      <PageHeader
        title="Marketplace"
        description="Browse, install, update, and favorite AI templates."
        action={
          <div className="flex items-center gap-2 text-sm text-muted">
            <span>{dash.data?.installed_count || 0} installed</span>
            {(dash.data?.updates_count || 0) > 0 && (
              <Badge tone="warn">{dash.data?.updates_count} updates</Badge>
            )}
          </div>
        }
      />

      <div className="flex gap-2 overflow-x-auto border-b border-line">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            className={`-mb-px shrink-0 border-b-2 px-1 pb-3 text-sm font-medium transition ${
              activeTab === tab.key
                ? "border-brand text-brand"
                : "border-transparent text-muted hover:text-ink"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {(activeTab === "browse" || activeTab === "featured") && (
        <div className="space-y-5">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
            <Input
              placeholder="Search templates…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="lg:max-w-xs"
            />
            <div className="flex flex-wrap gap-2">
              {["", "package", "prompt", "agent"].map((kind) => (
                <Button
                  key={kind || "all-kinds"}
                  size="sm"
                  variant={kindFilter === kind ? "default" : "secondary"}
                  onClick={() => setKindFilter(kind)}
                >
                  {kind ? kind : "All kinds"}
                </Button>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant={!selectedCategory ? "default" : "secondary"}
              onClick={() => setSelectedCategory("")}
            >
              All categories
            </Button>
            {categories
              .filter((c) => c.count > 0 || selectedCategory === c.slug)
              .map((cat) => (
                <Button
                  key={cat.slug}
                  size="sm"
                  variant={selectedCategory === cat.slug ? "default" : "secondary"}
                  onClick={() =>
                    setSelectedCategory(cat.slug === selectedCategory ? "" : cat.slug)
                  }
                >
                  {cat.name}
                  {cat.count > 0 ? ` (${cat.count})` : ""}
                </Button>
              ))}
          </div>

          {browseItems.length === 0 && !templates.isLoading && (
            <EmptyState
              title="No templates found"
              description="Try a different search, kind, or category. Seed marketplace templates if the catalog is empty."
            />
          )}
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {browseItems.map((template) => (
              <TemplateCard
                key={template.id}
                template={template}
                installing={install.isPending}
                favoriting={favorite.isPending}
                onOpen={setDetail}
                onInstall={setInstallTarget}
                onToggleFavorite={(t) => favorite.mutate(t)}
              />
            ))}
          </div>
          {typeof templates.data?.total === "number" && templates.data.total > browseItems.length && (
            <p className="text-sm text-muted">
              Showing {browseItems.length} of {templates.data.total}
            </p>
          )}
        </div>
      )}

      {activeTab === "favorites" && (
        <div className="space-y-4">
          {!favorites.data?.length && !favorites.isLoading && (
            <EmptyState
              title="No favorites yet"
              description="Favorite templates from Browse to find them quickly here."
            />
          )}
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {(favorites.data || []).map((template) => (
              <TemplateCard
                key={template.id}
                template={{ ...template, is_favorited: true }}
                installing={install.isPending}
                favoriting={favorite.isPending}
                onOpen={setDetail}
                onInstall={setInstallTarget}
                onToggleFavorite={(t) => favorite.mutate(t)}
              />
            ))}
          </div>
        </div>
      )}

      {activeTab === "installed" && (
        <div className="space-y-4">
          {!installed.data?.length && (
            <EmptyState
              title="Nothing installed yet"
              description="Browse templates to install your first one."
            />
          )}
          {(installed.data || []).map((item) => (
            <InstallCard
              key={item.id}
              install={item}
              onUpdate={setUpdateTarget}
              onRollback={(id) => rollback.mutate(id)}
              onUninstall={(id) => uninstall.mutate(id)}
            />
          ))}
        </div>
      )}

      {activeTab === "updates" && (
        <div className="space-y-4">
          {!updates.data?.length && <EmptyState title="All up to date" />}
          {(updates.data || []).map((notif) => (
            <Card key={notif.installation_id}>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h3 className="font-semibold">{notif.template_name}</h3>
                  <p className="text-sm text-muted">
                    v{notif.installed_version} → v{notif.latest_version}
                  </p>
                  {notif.changelog && <p className="mt-1 text-sm text-muted">{notif.changelog}</p>}
                </div>
                <Button size="sm" onClick={() => setUpdateTarget(notif)}>
                  Update
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      <DialogShell
        open={Boolean(activeDetail)}
        title={activeDetail?.name || "Template"}
        onClose={() => setDetail(null)}
      >
        {activeDetail && (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Badge>{CATEGORY_LABEL[activeDetail.category] || activeDetail.category}</Badge>
              {activeDetail.kind && <Badge tone="neutral">{activeDetail.kind}</Badge>}
              {activeDetail.is_featured && <Badge tone="brand">Featured</Badge>}
              {activeDetail.installed && <Badge tone="success">Installed</Badge>}
            </div>
            <p className="text-sm text-muted">{activeDetail.description}</p>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-muted">Version</dt>
                <dd className="font-medium">v{activeDetail.version}</dd>
              </div>
              <div>
                <dt className="text-muted">Price</dt>
                <dd className="font-medium">
                  {priceLabel(activeDetail.price, activeDetail.pricing_tier)}
                </dd>
              </div>
              <div>
                <dt className="text-muted">Author</dt>
                <dd className="font-medium">{activeDetail.author}</dd>
              </div>
              <div>
                <dt className="text-muted">Installs</dt>
                <dd className="font-medium">{activeDetail.install_count}</dd>
              </div>
            </dl>
            {(activeDetail.tags || []).length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {activeDetail.tags.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full border border-line bg-canvas px-2 py-0.5 text-xs text-muted"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}
            <div className="space-y-2">
              <p className="text-sm font-semibold text-ink">Release notes</p>
              {versionsQuery.isLoading ? (
                <p className="text-sm text-muted">Loading history…</p>
              ) : (versionsQuery.data || []).length === 0 ? (
                <p className="text-sm text-muted">No version history yet.</p>
              ) : (
                <ul className="max-h-48 space-y-2 overflow-y-auto">
                  {(versionsQuery.data || []).map((v) => (
                    <li key={v.id} className="rounded-xl border border-line bg-canvas px-3 py-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold text-ink">v{v.version}</span>
                        {v.is_latest && <Badge tone="brand">latest</Badge>}
                        <span className="text-xs text-muted">
                          {formatDate(v.published_at || v.created_at)}
                        </span>
                      </div>
                      <p className="mt-1 whitespace-pre-wrap text-sm text-muted">
                        {v.release_notes || v.changelog || "No release notes."}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="flex flex-wrap gap-2 pt-2">
              <Button
                variant="secondary"
                disabled={favorite.isPending}
                onClick={() => favorite.mutate(activeDetail)}
              >
                {activeDetail.is_favorited ? "Unfavorite" : "Favorite"}
              </Button>
              {!activeDetail.installed && (
                <Button onClick={() => setInstallTarget(activeDetail)}>Install</Button>
              )}
            </div>
          </div>
        )}
      </DialogShell>

      <DialogShell
        open={Boolean(installTarget)}
        title="Install template"
        onClose={() => setInstallTarget(null)}
      >
        {installTarget && (
          <div className="space-y-4">
            <p className="text-sm text-muted">
              Install <span className="font-medium text-ink">{installTarget.name}</span> into your
              company workspace? You can update or uninstall later.
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setInstallTarget(null)}>
                Cancel
              </Button>
              <Button
                disabled={install.isPending}
                onClick={() => install.mutate(installTarget.slug)}
              >
                {install.isPending ? "Installing…" : "Confirm install"}
              </Button>
            </div>
          </div>
        )}
      </DialogShell>

      <DialogShell
        open={Boolean(updateTarget)}
        title="Update template"
        onClose={() => setUpdateTarget(null)}
      >
        {updateTarget && (
          <div className="space-y-4">
            <p className="text-sm text-muted">
              {"template_name" in updateTarget
                ? `Update ${updateTarget.template_name} from v${updateTarget.installed_version} to v${"latest_version" in updateTarget ? updateTarget.latest_version : updateTarget.latest_available_version}.`
                : "Update this installation to the latest available version."}
            </p>
            {"changelog" in updateTarget && updateTarget.changelog ? (
              <div className="rounded-xl border border-line bg-canvas px-3 py-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted">Release notes</p>
                <p className="mt-1 whitespace-pre-wrap text-sm text-ink">{updateTarget.changelog}</p>
              </div>
            ) : null}
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setUpdateTarget(null)}>
                Cancel
              </Button>
              <Button
                disabled={update.isPending}
                onClick={() =>
                  update.mutate(
                    "installation_id" in updateTarget
                      ? updateTarget.installation_id
                      : updateTarget.id
                  )
                }
              >
                {update.isPending ? "Updating…" : "Confirm update"}
              </Button>
            </div>
          </div>
        )}
      </DialogShell>
    </div>
  );
}
