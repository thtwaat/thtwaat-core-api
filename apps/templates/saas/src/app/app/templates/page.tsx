"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { type Installation, type TemplateItem, marketplaceApi } from "@/lib/services";
import { formatDate } from "@/lib/utils";
import { PageHeader, EmptyState } from "@/components/ui/misc";
import { Badge, Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const CATEGORY_ICONS: Record<string, string> = {
  website: "🌐",
  landing: "✨",
  saas: "📊",
  crm: "👥",
  helpdesk: "🎧",
  ecommerce: "🛒",
  education: "🎓",
  healthcare: "⚕️",
  real_estate: "🏠",
  restaurant: "🍽️",
  finance: "💰",
  legal: "⚖️"
};

function statusTone(status: string): "success" | "warn" | "neutral" | "brand" {
  switch (status) {
    case "ready": return "success";
    case "published": return "brand";
    case "update_available": return "warn";
    case "failed": return "danger" as never;
    default: return "neutral";
  }
}

function TemplateCard({
  template,
  onInstall,
  installing
}: {
  template: TemplateItem;
  onInstall: (slug: string) => void;
  installing: boolean;
}) {
  return (
    <Card className="flex flex-col">
      <div className="flex items-start gap-3">
        <span className="text-2xl">{CATEGORY_ICONS[template.category] || "🗂️"}</span>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-semibold text-ink">{template.name}</h3>
            {template.is_featured && <Badge tone="brand">Featured</Badge>}
            {template.installed && <Badge tone="success">Installed</Badge>}
            {template.update_available && <Badge tone="warn">Update</Badge>}
          </div>
          <p className="mt-1 text-xs text-muted capitalize">{template.category} · v{template.version}</p>
        </div>
      </div>
      <p className="mt-3 text-sm text-muted line-clamp-2 flex-1">{template.description}</p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {template.tags.slice(0, 4).map((tag) => (
          <span key={tag} className="rounded-full bg-canvas px-2 py-0.5 text-xs text-muted border border-line">
            {tag}
          </span>
        ))}
      </div>
      <div className="mt-4 flex items-center justify-between">
        <span className="text-sm font-semibold">
          {parseFloat(template.price) === 0 ? "Free" : `$${template.price}`}
        </span>
        <div className="flex gap-2">
          {template.installed ? (
            <Badge tone="success">Installed</Badge>
          ) : (
            <Button size="sm" disabled={installing} onClick={() => onInstall(template.slug)}>
              Install
            </Button>
          )}
        </div>
      </div>
      <p className="mt-2 text-xs text-muted">{template.install_count} install{template.install_count !== 1 ? "s" : ""}</p>
    </Card>
  );
}

function InstallCard({ install, onUpdate, onRollback, onUninstall }: {
  install: Installation;
  onUpdate: (id: string) => void;
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
          {install.failure_reason && <p className="mt-1 text-sm text-red-600">{install.failure_reason}</p>}
        </div>
        <div className="flex flex-wrap gap-2">
          {install.update_available && (
            <Button size="sm" onClick={() => onUpdate(install.id)}>Update</Button>
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
  const [activeTab, setActiveTab] = useState<"browse" | "installed" | "updates">("browse");
  const [search, setSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("");

  const dash = useQuery({ queryKey: ["mkt-dashboard"], queryFn: marketplaceApi.dashboard });
  const templates = useQuery({
    queryKey: ["mkt-templates", search, selectedCategory],
    queryFn: () => marketplaceApi.list({
      q: search || undefined,
      category: selectedCategory || undefined,
      limit: 50
    })
  });
  const installed = useQuery({ queryKey: ["mkt-installed"], queryFn: marketplaceApi.installed });
  const updates = useQuery({ queryKey: ["mkt-updates"], queryFn: marketplaceApi.updates });

  const install = useMutation({
    mutationFn: (slug: string) => marketplaceApi.install(slug, { create_api_key: false }),
    onSuccess: (data) => {
      toast.success(`${data.template_name || data.template_slug} installed!`);
      if (data.api_key) toast.message(`API key (copy now): ${data.api_key}`);
      qc.invalidateQueries({ queryKey: ["mkt-templates"] });
      qc.invalidateQueries({ queryKey: ["mkt-installed"] });
      qc.invalidateQueries({ queryKey: ["mkt-dashboard"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const update = useMutation({
    mutationFn: (id: string) => marketplaceApi.update(id),
    onSuccess: () => {
      toast.success("Updated to latest version");
      qc.invalidateQueries({ queryKey: ["mkt-installed"] });
      qc.invalidateQueries({ queryKey: ["mkt-updates"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const rollback = useMutation({
    mutationFn: (id: string) => marketplaceApi.rollback(id),
    onSuccess: () => {
      toast.success("Rolled back to previous version");
      qc.invalidateQueries({ queryKey: ["mkt-installed"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const uninstall = useMutation({
    mutationFn: (id: string) => marketplaceApi.uninstall(id),
    onSuccess: () => {
      toast.success("Uninstalled");
      qc.invalidateQueries({ queryKey: ["mkt-installed"] });
      qc.invalidateQueries({ queryKey: ["mkt-templates"] });
      qc.invalidateQueries({ queryKey: ["mkt-dashboard"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const categories = dash.data?.categories || [];
  const items = templates.data || (activeTab === "browse" ? (dash.data?.featured || []) : []);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Marketplace"
        description="Browse, install, update, and publish AI templates."
        action={
          <div className="flex items-center gap-2 text-sm text-muted">
            <span>{dash.data?.installed_count || 0} installed</span>
            {(dash.data?.updates_count || 0) > 0 && (
              <Badge tone="warn">{dash.data?.updates_count} updates</Badge>
            )}
          </div>
        }
      />

      {/* Tabs */}
      <div className="flex gap-2 border-b border-line">
        {[
          { key: "browse", label: "Browse" },
          { key: "installed", label: `Installed (${installed.data?.length || 0})` },
          { key: "updates", label: `Updates (${updates.data?.length || 0})` }
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as typeof activeTab)}
            className={`pb-3 px-1 text-sm font-medium border-b-2 -mb-px transition ${
              activeTab === tab.key
                ? "border-brand text-brand"
                : "border-transparent text-muted hover:text-ink"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "browse" && (
        <div className="space-y-5">
          {/* Search + filter */}
          <div className="flex flex-col gap-3 sm:flex-row">
            <Input
              placeholder="Search templates…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="sm:max-w-xs"
            />
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                variant={!selectedCategory ? "default" : "secondary"}
                onClick={() => setSelectedCategory("")}
              >
                All
              </Button>
              {categories.filter(c => c.count > 0).map((cat) => (
                <Button
                  key={cat.slug}
                  size="sm"
                  variant={selectedCategory === cat.slug ? "default" : "secondary"}
                  onClick={() => setSelectedCategory(cat.slug === selectedCategory ? "" : cat.slug)}
                >
                  {CATEGORY_ICONS[cat.slug]} {cat.name}
                </Button>
              ))}
            </div>
          </div>

          {items.length === 0 && !templates.isLoading && (
            <EmptyState title="No templates found" description="Try a different search or category." />
          )}
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {items.map((template) => (
              <TemplateCard
                key={template.id}
                template={template}
                installing={install.isPending}
                onInstall={(slug) => install.mutate(slug)}
              />
            ))}
          </div>
        </div>
      )}

      {activeTab === "installed" && (
        <div className="space-y-4">
          {!installed.data?.length && (
            <EmptyState title="Nothing installed yet" description="Browse templates to install your first one." />
          )}
          {(installed.data || []).map((item) => (
            <InstallCard
              key={item.id}
              install={item}
              onUpdate={(id) => update.mutate(id)}
              onRollback={(id) => rollback.mutate(id)}
              onUninstall={(id) => uninstall.mutate(id)}
            />
          ))}
        </div>
      )}

      {activeTab === "updates" && (
        <div className="space-y-4">
          {!updates.data?.length && (
            <EmptyState title="All up to date" />
          )}
          {(updates.data || []).map((notif) => (
            <Card key={notif.installation_id}>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h3 className="font-semibold">{notif.template_name}</h3>
                  <p className="text-sm text-muted">
                    v{notif.installed_version} → v{notif.latest_version}
                  </p>
                  {notif.changelog && <p className="mt-1 text-sm text-muted">{notif.changelog}</p>}
                </div>
                <Button size="sm" onClick={() => update.mutate(notif.installation_id)}>Update</Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
