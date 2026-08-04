"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  type Installation,
  type MarketplaceCollection,
  type TemplateItem,
  type UpdateNotification,
  marketplaceApi
} from "@/lib/services";
import { formatDate } from "@/lib/utils";
import { PageHeader, EmptyState } from "@/components/ui/misc";
import { Badge, Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type TabKey = "home" | "browse" | "featured" | "favorites" | "installed" | "updates";

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
  analytics: "Analytics",
  insurance: "Insurance",
  government: "Government",
  travel: "Travel",
  retail: "Retail",
  manufacturing: "Manufacturing",
  sales: "Sales",
  erp: "ERP",
  bi: "BI",
  devops: "DevOps",
  security: "Security",
  news: "News",
  media: "Media",
  startup: "Startup",
  productivity: "Productivity",
  automation: "Automation",
  multilingual: "Multilingual"
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

function priceLabel(price: string | number | undefined, tier?: string, badge?: string | null) {
  if (badge) return badge;
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
  onInstall,
  onToggleFavorite,
  onCompare,
  compareSelected,
  installing,
  favoriting
}: {
  template: TemplateItem;
  onInstall: (t: TemplateItem) => void;
  onToggleFavorite: (t: TemplateItem) => void;
  onCompare?: (t: TemplateItem) => void;
  compareSelected?: boolean;
  installing: boolean;
  favoriting: boolean;
}) {
  return (
    <Card className="flex min-w-[260px] max-w-sm flex-col snap-start">
      <Link href={`/app/templates/${template.slug}`} className="text-left">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-line bg-canvas text-sm font-semibold uppercase text-brand">
            {(template.category || "t").slice(0, 2)}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-semibold text-ink">{template.name}</h3>
              {(template.pricing_badge || template.pricing_tier) && (
                <Badge tone="neutral">
                  {priceLabel(template.price, template.pricing_tier, template.pricing_badge)}
                </Badge>
              )}
              {template.is_featured && <Badge tone="brand">Featured</Badge>}
              {template.is_editors_choice && <Badge tone="brand">Editor</Badge>}
              {template.verified_publisher && <Badge tone="success">Verified</Badge>}
              {template.installed && <Badge tone="success">Installed</Badge>}
            </div>
            <p className="mt-1 text-xs capitalize text-muted">
              {CATEGORY_LABEL[template.category] || template.category}
              {template.kind ? ` · ${template.kind}` : ""} · v{template.version}
            </p>
          </div>
        </div>
        <p className="mt-3 line-clamp-2 text-sm text-muted">{template.description}</p>
      </Link>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted">
        {template.rating_avg != null && template.review_count ? (
          <span>
            ★ {template.rating_avg.toFixed(1)} ({template.review_count})
          </span>
        ) : null}
        <span>
          {template.install_count} install{template.install_count !== 1 ? "s" : ""}
        </span>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Link
          href={`/app/templates/${template.slug}`}
          className="inline-flex h-8 items-center justify-center rounded-lg border border-line bg-panel px-3 text-sm font-medium text-ink hover:bg-canvas"
        >
          Preview
        </Link>
        <Button
          size="sm"
          variant="secondary"
          disabled={favoriting}
          onClick={() => onToggleFavorite(template)}
        >
          {template.is_favorited ? "Unfavorite" : "Favorite"}
        </Button>
        {onCompare && (
          <Button
            size="sm"
            variant={compareSelected ? "default" : "secondary"}
            onClick={() => onCompare(template)}
          >
            {compareSelected ? "Compared" : "Compare"}
          </Button>
        )}
        {template.installed ? (
          <Badge tone="success">Installed</Badge>
        ) : (
          <Button size="sm" disabled={installing} onClick={() => onInstall(template)}>
            Install
          </Button>
        )}
      </div>
    </Card>
  );
}

function Rail({
  title,
  items,
  ...cardProps
}: {
  title: string;
  items: TemplateItem[];
  onInstall: (t: TemplateItem) => void;
  onToggleFavorite: (t: TemplateItem) => void;
  onCompare?: (t: TemplateItem) => void;
  compareIds: Set<string>;
  installing: boolean;
  favoriting: boolean;
}) {
  if (!items.length) return null;
  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold text-ink">{title}</h2>
      <div className="flex gap-3 overflow-x-auto pb-2 snap-x">
        {items.map((template) => (
          <TemplateCard
            key={template.id}
            template={template}
            installing={cardProps.installing}
            favoriting={cardProps.favoriting}
            onInstall={cardProps.onInstall}
            onToggleFavorite={cardProps.onToggleFavorite}
            onCompare={cardProps.onCompare}
            compareSelected={cardProps.compareIds.has(template.id)}
          />
        ))}
      </div>
    </section>
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
            <Link
              href={
                install.template_slug
                  ? `/app/templates/${install.template_slug}`
                  : "/app/templates"
              }
              className="font-semibold text-ink hover:underline"
            >
              {install.template_name || install.template_slug}
            </Link>
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
  const router = useRouter();
  const qc = useQueryClient();
  const [activeTab, setActiveTab] = useState<TabKey>("home");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [kindFilter, setKindFilter] = useState("");
  const [installTarget, setInstallTarget] = useState<TemplateItem | null>(null);
  const [updateTarget, setUpdateTarget] = useState<Installation | UpdateNotification | null>(null);
  const [compareIds, setCompareIds] = useState<Set<string>>(new Set());
  const [collectionFocus, setCollectionFocus] = useState<MarketplaceCollection | null>(null);

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedSearch(search.trim()), 250);
    return () => window.clearTimeout(t);
  }, [search]);

  const home = useQuery({ queryKey: ["mkt-home"], queryFn: marketplaceApi.home });
  const templates = useQuery({
    queryKey: ["mkt-templates", debouncedSearch, selectedCategory, kindFilter, activeTab],
    enabled: activeTab === "browse" || activeTab === "featured" || Boolean(debouncedSearch),
    queryFn: () =>
      marketplaceApi.listPage({
        q: debouncedSearch || undefined,
        category: selectedCategory || undefined,
        kind: kindFilter || undefined,
        featured: activeTab === "featured" ? true : undefined,
        sort: activeTab === "featured" ? "featured" : debouncedSearch ? "relevance" : "newest",
        limit: 48
      })
  });
  const favorites = useQuery({
    queryKey: ["mkt-favorites"],
    queryFn: marketplaceApi.favorites
  });
  const installed = useQuery({ queryKey: ["mkt-installed"], queryFn: marketplaceApi.installed });
  const updates = useQuery({ queryKey: ["mkt-updates"], queryFn: marketplaceApi.updates });
  const collectionDetail = useQuery({
    queryKey: ["mkt-collection", collectionFocus?.slug],
    enabled: Boolean(collectionFocus?.slug),
    queryFn: () => marketplaceApi.collection(collectionFocus!.slug)
  });

  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ["mkt-templates"] });
    qc.invalidateQueries({ queryKey: ["mkt-installed"] });
    qc.invalidateQueries({ queryKey: ["mkt-home"] });
    qc.invalidateQueries({ queryKey: ["mkt-updates"] });
    qc.invalidateQueries({ queryKey: ["mkt-favorites"] });
  };

  const install = useMutation({
    mutationFn: (slug: string) => marketplaceApi.install(slug, { create_api_key: false }),
    onSuccess: (data) => {
      toast.success(`${data.template_name || data.template_slug} installed`);
      if (data.api_key) toast.message(`API key (copy now): ${data.api_key}`);
      setInstallTarget(null);
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
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const categories = home.data?.categories || [];
  const featuredCategories = useMemo(
    () =>
      categories.filter((c) => c.is_featured || (c.count || 0) > 0).slice(0, 16),
    [categories]
  );

  const shareTemplate = async (t: TemplateItem) => {
    const url = `${window.location.origin}/app/templates/${t.slug}`;
    try {
      if (navigator.share) {
        await navigator.share({ title: t.name, text: t.description, url });
      } else {
        await navigator.clipboard.writeText(url);
        toast.success("Link copied");
      }
    } catch {
      try {
        await navigator.clipboard.writeText(url);
        toast.success("Link copied");
      } catch {
        toast.message(url);
      }
    }
  };

  const toggleCompare = (t: TemplateItem) => {
    setCompareIds((prev) => {
      const next = new Set(prev);
      if (next.has(t.id)) next.delete(t.id);
      else if (next.size < 3) next.add(t.id);
      else toast.message("Compare up to 3 templates");
      return next;
    });
  };

  const compareItems = useMemo(() => {
    const pool = [
      ...(home.data?.featured || []),
      ...(home.data?.newest || []),
      ...(home.data?.trending || []),
      ...(templates.data?.items || []),
      ...(favorites.data || [])
    ];
    const byId = new Map(pool.map((t) => [t.id, t]));
    return [...compareIds].map((id) => byId.get(id)).filter(Boolean) as TemplateItem[];
  }, [compareIds, home.data, templates.data, favorites.data]);

  const cardProps = {
    installing: install.isPending,
    favoriting: favorite.isPending,
    onInstall: setInstallTarget,
    onToggleFavorite: (t: TemplateItem) => favorite.mutate(t),
    onCompare: toggleCompare,
    compareIds
  };

  const tabs: Array<{ key: TabKey; label: string }> = [
    { key: "home", label: "Store Home" },
    { key: "browse", label: "Browse" },
    { key: "featured", label: "Featured" },
    { key: "favorites", label: `Favorites (${favorites.data?.length || 0})` },
    { key: "installed", label: `Installed (${installed.data?.length || 0})` },
    { key: "updates", label: `Updates (${updates.data?.length || 0})` }
  ];

  const showSearchResults = Boolean(debouncedSearch) && activeTab === "home";

  return (
    <div className="space-y-5">
      <PageHeader
        title="Marketplace"
        description="Discover, compare, and install AI templates for your workspace."
        action={
          <div className="flex items-center gap-2 text-sm text-muted">
            <span>{home.data?.installed_count || 0} installed</span>
            {(home.data?.updates_count || 0) > 0 && (
              <Badge tone="warn">{home.data?.updates_count} updates</Badge>
            )}
          </div>
        }
      />

      <div className="rounded-2xl border border-line bg-gradient-to-br from-canvas via-panel to-canvas p-5 sm:p-7">
        <h2 className="text-xl font-semibold text-ink sm:text-2xl">Find the right AI template</h2>
        <p className="mt-1 max-w-2xl text-sm text-muted">
          Search the catalog, browse curated collections, and install in minutes.
        </p>
        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
          <Input
            placeholder="Search templates, categories, or use cases…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="sm:max-w-md"
          />
          <Button
            variant="secondary"
            onClick={() => {
              setActiveTab("browse");
            }}
          >
            Browse all
          </Button>
        </div>
      </div>

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

      {compareItems.length > 0 && (
        <Card className="space-y-3">
          <div className="flex items-center justify-between gap-2">
            <h3 className="font-semibold text-ink">Compare ({compareItems.length}/3)</h3>
            <Button size="sm" variant="ghost" onClick={() => setCompareIds(new Set())}>
              Clear
            </Button>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            {compareItems.map((t) => (
              <div key={t.id} className="rounded-xl border border-line bg-canvas p-3 text-sm">
                <p className="font-semibold text-ink">{t.name}</p>
                <p className="mt-1 text-muted">
                  {priceLabel(t.price, t.pricing_tier, t.pricing_badge)} · {t.install_count} installs
                </p>
                <p className="mt-1 text-muted">
                  {t.rating_avg != null ? `★ ${t.rating_avg.toFixed(1)}` : "No ratings"}
                </p>
                <div className="mt-2 flex gap-2">
                  <Button size="sm" variant="secondary" onClick={() => router.push(`/app/templates/${t.slug}`)}>
                    Open
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => shareTemplate(t)}>
                    Share
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {(activeTab === "home" || showSearchResults) && (
        <div className="space-y-8">
          {showSearchResults ? (
            <div className="space-y-4">
              <h2 className="text-base font-semibold text-ink">
                Search results{templates.data ? ` (${templates.data.total})` : ""}
              </h2>
              {!templates.data?.items.length && !templates.isLoading && (
                <EmptyState title="No matches" description="Try a different query or browse categories." />
              )}
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {(templates.data?.items || []).map((template) => (
                  <TemplateCard key={template.id} template={template} {...cardProps} />
                ))}
              </div>
            </div>
          ) : (
            <>
              <section className="space-y-3">
                <h2 className="text-base font-semibold text-ink">Categories</h2>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
                  {featuredCategories.map((cat) => (
                    <button
                      key={cat.slug}
                      type="button"
                      onClick={() => {
                        setSelectedCategory(cat.slug);
                        setActiveTab("browse");
                      }}
                      className="rounded-xl border border-line bg-panel px-3 py-3 text-left transition hover:border-brand/40"
                    >
                      <p className="text-sm font-semibold text-ink">{cat.name}</p>
                      <p className="mt-1 text-xs text-muted">{cat.count || 0} templates</p>
                    </button>
                  ))}
                </div>
              </section>

              {(home.data?.collections || []).length > 0 && (
                <section className="space-y-3">
                  <h2 className="text-base font-semibold text-ink">Collections</h2>
                  <div className="flex gap-3 overflow-x-auto pb-1">
                    {(home.data?.collections || []).map((col) => (
                      <button
                        key={col.id}
                        type="button"
                        onClick={() => setCollectionFocus(col)}
                        className="min-w-[200px] rounded-xl border border-line bg-panel px-4 py-3 text-left transition hover:border-brand/40"
                      >
                        <p className="font-semibold text-ink">{col.name}</p>
                        <p className="mt-1 line-clamp-2 text-xs text-muted">{col.description}</p>
                        <p className="mt-2 text-xs text-muted">{col.item_count} items</p>
                      </button>
                    ))}
                  </div>
                </section>
              )}

              <Rail title="Continue using" items={home.data?.continue_using || []} {...cardProps} />
              <Rail title="Recently viewed" items={home.data?.recently_viewed || []} {...cardProps} />
              <Rail title="Featured" items={home.data?.featured || []} {...cardProps} />
              <Rail title="Editor’s choice" items={home.data?.editors_choice || []} {...cardProps} />
              <Rail title="Trending" items={home.data?.trending || []} {...cardProps} />
              <Rail title="Top rated" items={home.data?.top_rated || []} {...cardProps} />
              <Rail title="Most installed" items={home.data?.most_installed || []} {...cardProps} />
              <Rail title="Newest" items={home.data?.newest || []} {...cardProps} />
            </>
          )}
        </div>
      )}

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
              .filter((c) => c.count > 0 || selectedCategory === c.slug || c.is_featured)
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

          {(templates.data?.items || []).length === 0 && !templates.isLoading && (
            <EmptyState
              title="No templates found"
              description="Try a different search, kind, or category."
            />
          )}
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {(templates.data?.items || []).map((template) => (
              <TemplateCard key={template.id} template={template} {...cardProps} />
            ))}
          </div>
        </div>
      )}

      {activeTab === "favorites" && (
        <div className="space-y-4">
          {!favorites.data?.length && !favorites.isLoading && (
            <EmptyState
              title="No favorites yet"
              description="Favorite templates from Store Home to find them quickly here."
            />
          )}
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {(favorites.data || []).map((template) => (
              <TemplateCard
                key={template.id}
                template={{ ...template, is_favorited: true }}
                {...cardProps}
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
        open={Boolean(collectionFocus)}
        title={collectionFocus?.name || "Collection"}
        onClose={() => setCollectionFocus(null)}
      >
        {collectionFocus && (
          <div className="space-y-4">
            <p className="text-sm text-muted">{collectionFocus.description}</p>
            {collectionDetail.isLoading && <p className="text-sm text-muted">Loading…</p>}
            <div className="grid gap-3">
              {(collectionDetail.data?.items || []).map((template) => (
                <div
                  key={template.id}
                  className="flex items-center justify-between gap-2 rounded-xl border border-line bg-canvas px-3 py-2"
                >
                  <div>
                    <Link
                      href={`/app/templates/${template.slug}`}
                      className="font-medium text-ink hover:underline"
                    >
                      {template.name}
                    </Link>
                    <p className="text-xs text-muted">
                      {priceLabel(template.price, template.pricing_tier, template.pricing_badge)}
                    </p>
                  </div>
                  {!template.installed && (
                    <Button size="sm" onClick={() => setInstallTarget(template)}>
                      Install
                    </Button>
                  )}
                </div>
              ))}
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
