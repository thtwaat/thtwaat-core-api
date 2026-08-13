"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  type Installation,
  type TemplateCategory,
  type TemplateItem,
  type UpdateNotification,
  marketplaceApi
} from "@/lib/services";
import { ApiError } from "@/lib/api";
import { cn, formatDate } from "@/lib/utils";
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

const CATEGORY_ICON: Record<string, string> = {
  website: "WB",
  landing: "LP",
  saas: "SA",
  crm: "CR",
  helpdesk: "HD",
  ecommerce: "EC",
  education: "ED",
  healthcare: "HC",
  real_estate: "RE",
  restaurant: "RS",
  finance: "FN",
  legal: "LG",
  writing: "WR",
  coding: "CD",
  marketing: "MK",
  hr: "HR",
  research: "RS",
  ai_agents: "AI",
  business: "BZ",
  analytics: "AN",
  insurance: "IN",
  government: "GV",
  travel: "TV",
  retail: "RT",
  manufacturing: "MF",
  sales: "SL",
  erp: "ER",
  bi: "BI",
  devops: "DV",
  security: "SC",
  news: "NW",
  media: "MD",
  startup: "ST",
  productivity: "PD",
  automation: "AU",
  multilingual: "ML"
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
  if (!(n > 0)) return tier && tier !== "free" ? String(tier) : "Free";
  return `$${n}`;
}

function isFreeTemplate(template: TemplateItem) {
  const tier = (template.pricing_tier || "free").toLowerCase();
  if (tier === "free") return true;
  const n = Number(template.price ?? 0);
  return !(n > 0);
}

function categoryName(slug: string, categories?: TemplateCategory[]) {
  const fromApi = categories?.find((c) => c.slug === slug)?.name;
  return fromApi || CATEGORY_LABEL[slug] || slug.replace(/_/g, " ");
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
    <div className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-4">
      <button
        type="button"
        aria-label="Close dialog"
        className="absolute inset-0 bg-ink/40 backdrop-blur-[1px]"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        className="relative z-10 max-h-[90vh] w-full overflow-y-auto rounded-t-2xl border border-line bg-panel p-4 shadow-xl sm:max-w-lg sm:rounded-2xl sm:p-5"
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
  categories,
  onInstall,
  onToggleFavorite,
  installing,
  favoriting,
  layout = "rail"
}: {
  template: TemplateItem;
  categories?: TemplateCategory[];
  onInstall: (t: TemplateItem) => void;
  onToggleFavorite: (t: TemplateItem) => void;
  installing: boolean;
  favoriting: boolean;
  layout?: "rail" | "grid";
}) {
  const thumb = template.thumbnail || template.banner_url;
  return (
    <Card
      className={cn(
        "flex flex-col overflow-hidden p-0 transition hover:border-brand/35",
        layout === "rail" && "min-w-[260px] max-w-[300px] shrink-0 snap-start sm:min-w-[280px]",
        layout === "grid" && "w-full"
      )}
    >
      <Link href={`/app/templates/${template.slug}`} className="block text-left">
        <div className="relative h-28 w-full border-b border-line bg-gradient-to-br from-brand/10 via-canvas to-panel sm:h-32">
          {thumb ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={thumb} alt="" className="h-full w-full object-cover" />
          ) : (
            <div className="flex h-full items-end justify-between p-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-line bg-panel text-xs font-bold uppercase tracking-wide text-brand">
                {CATEGORY_ICON[template.category] || (template.category || "tp").slice(0, 2)}
              </span>
              <span className="rounded-lg bg-panel/90 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-muted">
                {template.kind || "package"}
              </span>
            </div>
          )}
        </div>
        <div className="space-y-2 p-4">
          <div className="flex flex-wrap items-start gap-2">
            <h3 className="min-w-0 flex-1 text-sm font-semibold leading-snug text-ink sm:text-base">
              {template.name}
            </h3>
            <Badge tone="neutral">
              {priceLabel(template.price, template.pricing_tier, template.pricing_badge)}
            </Badge>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {template.is_featured && <Badge tone="brand">Featured</Badge>}
            {template.installed && <Badge tone="success">Installed</Badge>}
            {template.update_available && <Badge tone="warn">Update</Badge>}
          </div>
          <p className="text-xs capitalize text-muted">
            {categoryName(template.category, categories)}
            {template.kind ? ` · ${template.kind}` : ""} · v{template.version}
          </p>
          <p className="line-clamp-2 text-sm text-muted">{template.description}</p>
          <p className="text-xs text-muted">
            {template.install_count} install{template.install_count !== 1 ? "s" : ""}
            {template.author ? ` · ${template.author}` : ""}
          </p>
        </div>
      </Link>
      <div className="mt-auto flex flex-wrap gap-2 border-t border-line px-4 py-3">
        <Link
          href={`/app/templates/${template.slug}`}
          className="inline-flex h-9 items-center justify-center rounded-xl border border-line bg-panel px-3 text-xs font-semibold text-ink hover:bg-canvas"
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

function TemplateRail({
  title,
  subtitle,
  items,
  categories,
  onSeeAll,
  ...cardProps
}: {
  title: string;
  subtitle?: string;
  items: TemplateItem[];
  categories?: TemplateCategory[];
  onSeeAll?: () => void;
  onInstall: (t: TemplateItem) => void;
  onToggleFavorite: (t: TemplateItem) => void;
  installing: boolean;
  favoriting: boolean;
}) {
  if (!items.length) return null;
  return (
    <section className="space-y-3">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink sm:text-lg">{title}</h2>
          {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
        </div>
        {onSeeAll && (
          <Button size="sm" variant="ghost" onClick={onSeeAll}>
            See all
          </Button>
        )}
      </div>
      <div className="-mx-1 flex gap-3 overflow-x-auto px-1 pb-2 snap-x snap-mandatory [scrollbar-width:thin]">
        {items.map((template) => (
          <TemplateCard
            key={template.id}
            template={template}
            categories={categories}
            layout="rail"
            {...cardProps}
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
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href={
                install.template_slug
                  ? `/app/templates/${install.template_slug}`
                  : "/app/templates"
              }
              className="truncate font-semibold text-ink hover:underline"
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
  const qc = useQueryClient();
  const [activeTab, setActiveTab] = useState<TabKey>("home");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [kindFilter, setKindFilter] = useState("");
  const [installTarget, setInstallTarget] = useState<TemplateItem | null>(null);
  const [updateTarget, setUpdateTarget] = useState<Installation | UpdateNotification | null>(null);

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedSearch(search.trim()), 250);
    return () => window.clearTimeout(t);
  }, [search]);

  // Prefer /home when available; always load categories independently so the
  // homepage catalog still renders if a rail endpoint fails.
  const home = useQuery({
    queryKey: ["mkt-home"],
    queryFn: marketplaceApi.home,
    retry: 1
  });
  const categoriesQuery = useQuery({
    queryKey: ["mkt-categories"],
    queryFn: marketplaceApi.categories
  });
  const dash = useQuery({
    queryKey: ["mkt-dashboard"],
    queryFn: marketplaceApi.dashboard,
    enabled: home.isError || !home.data
  });
  const trendingFallback = useQuery({
    queryKey: ["mkt-trending-fallback"],
    queryFn: () => marketplaceApi.listPage({ sort: "installs", limit: 12 }),
    enabled: home.isError || !(home.data?.trending?.length || home.data?.most_installed?.length)
  });
  const featuredFallback = useQuery({
    queryKey: ["mkt-featured-fallback"],
    queryFn: () => marketplaceApi.listPage({ featured: true, sort: "featured", limit: 12 }),
    enabled: home.isError || !(home.data?.featured?.length)
  });
  const newestFallback = useQuery({
    queryKey: ["mkt-newest-fallback"],
    queryFn: () => marketplaceApi.listPage({ newest: true, sort: "newest", limit: 12 }),
    enabled: home.isError || !(home.data?.newest?.length)
  });

  const searching = Boolean(debouncedSearch);
  const templates = useQuery({
    queryKey: ["mkt-templates", debouncedSearch, selectedCategory, kindFilter, activeTab],
    enabled: activeTab === "browse" || activeTab === "featured" || searching,
    queryFn: () =>
      marketplaceApi.listPage({
        q: debouncedSearch || undefined,
        category: selectedCategory || undefined,
        kind: kindFilter || undefined,
        featured: activeTab === "featured" && !searching ? true : undefined,
        sort:
          activeTab === "featured" && !searching
            ? "featured"
            : searching
              ? "relevance"
              : "newest",
        limit: 48
      })
  });
  const favorites = useQuery({
    queryKey: ["mkt-favorites"],
    queryFn: marketplaceApi.favorites,
    enabled: activeTab === "favorites"
  });
  const installed = useQuery({
    queryKey: ["mkt-installed"],
    queryFn: marketplaceApi.installed,
    enabled: activeTab === "installed" || activeTab === "home"
  });
  const updates = useQuery({
    queryKey: ["mkt-updates"],
    queryFn: marketplaceApi.updates,
    enabled: activeTab === "updates" || activeTab === "home"
  });

  const featured =
    home.data?.featured?.length
      ? home.data.featured
      : dash.data?.featured?.length
        ? dash.data.featured
        : featuredFallback.data?.items || [];
  const newest =
    home.data?.newest?.length
      ? home.data.newest
      : dash.data?.newest?.length
        ? dash.data.newest
        : newestFallback.data?.items || [];
  const trending = home.data?.trending?.length
    ? home.data.trending
    : home.data?.most_installed?.length
      ? home.data.most_installed
      : trendingFallback.data?.items || [];
  const categories =
    (categoriesQuery.data && categoriesQuery.data.length > 0
      ? categoriesQuery.data
      : null) ||
    home.data?.categories ||
    dash.data?.categories ||
    [];
  const installedCount =
    home.data?.installed_count ??
    dash.data?.installed_count ??
    installed.data?.length ??
    0;
  const updatesCount = home.data?.updates_count ?? dash.data?.updates_count ?? updates.data?.length ?? 0;

  const categoryCount = (c: TemplateCategory) => c.count || c.template_count || 0;

  const browseCategories = useMemo(() => {
    const withCount = categories.filter(
      (c) => categoryCount(c) > 0 || c.slug === selectedCategory
    );
    const featuredCats = categories.filter(
      (c) => c.is_featured && !withCount.some((w) => w.slug === c.slug)
    );
    return [...withCount, ...featuredCats].slice(0, 24);
  }, [categories, selectedCategory]);

  const homeCategories = useMemo(() => {
    const ranked = [...categories].sort((a, b) => {
      const af = a.is_featured || categoryCount(a) > 0 ? 0 : 1;
      const bf = b.is_featured || categoryCount(b) > 0 ? 0 : 1;
      if (af !== bf) return af - bf;
      return categoryCount(b) - categoryCount(a);
    });
    const populated = ranked.filter((c) => categoryCount(c) > 0 || c.is_featured);
    // If meta marks nothing featured and counts are present, still show top populated.
    return (populated.length ? populated : ranked.filter((c) => categoryCount(c) > 0)).slice(0, 12);
  }, [categories]);

  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ["mkt-templates"] });
    qc.invalidateQueries({ queryKey: ["mkt-installed"] });
    qc.invalidateQueries({ queryKey: ["mkt-home"] });
    qc.invalidateQueries({ queryKey: ["mkt-categories"] });
    qc.invalidateQueries({ queryKey: ["mkt-dashboard"] });
    qc.invalidateQueries({ queryKey: ["mkt-trending-fallback"] });
    qc.invalidateQueries({ queryKey: ["mkt-featured-fallback"] });
    qc.invalidateQueries({ queryKey: ["mkt-newest-fallback"] });
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
    onError: (e: Error) => {
      if (e instanceof ApiError) {
        toast.error(e.message);
      } else {
        toast.error(e.message || "Unable to install template right now.");
      }
    }
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

  const cardProps = {
    categories,
    installing: install.isPending,
    favoriting: favorite.isPending,
    onInstall: setInstallTarget,
    onToggleFavorite: (t: TemplateItem) => favorite.mutate(t)
  };

  const tabs: Array<{ key: TabKey; label: string }> = [
    { key: "home", label: "Home" },
    { key: "browse", label: "Browse" },
    { key: "featured", label: "Featured" },
    { key: "favorites", label: `Favorites (${favorites.data?.length || 0})` },
    { key: "installed", label: `Installed (${installed.data?.length || 0})` },
    { key: "updates", label: `Updates (${updates.data?.length || 0})` }
  ];

  const clearSearch = () => {
    setSearch("");
    setDebouncedSearch("");
  };

  return (
    <div className="mx-auto w-full max-w-7xl space-y-5 pb-8">
      <PageHeader
        title="Marketplace"
        description="Browse featured, trending, and new AI templates for your workspace."
        action={
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
            <span>{installedCount} installed</span>
            {updatesCount > 0 && <Badge tone="warn">{updatesCount} updates</Badge>}
          </div>
        }
      />

      <section className="rounded-2xl border border-line bg-gradient-to-br from-canvas via-panel to-canvas p-4 sm:p-6 md:p-7">
        <h2 className="text-xl font-semibold tracking-tight text-ink sm:text-2xl">
          Discover templates
        </h2>
        <p className="mt-1 max-w-2xl text-sm text-muted">
          Search the catalog or jump into featured, trending, and newest picks.
        </p>
        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative w-full sm:max-w-lg">
            <Input
              aria-label="Search marketplace templates"
              placeholder="Search templates by name, tag, or use case…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                if (e.target.value.trim()) setActiveTab("home");
              }}
              className="w-full pr-20"
            />
            {search ? (
              <button
                type="button"
                onClick={clearSearch}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg px-2 py-1 text-xs font-medium text-muted hover:bg-canvas hover:text-ink"
              >
                Clear
              </button>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              onClick={() => {
                clearSearch();
                setSelectedCategory("");
                setActiveTab("browse");
              }}
            >
              Browse all
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                clearSearch();
                setActiveTab("featured");
              }}
            >
              Featured
            </Button>
          </div>
        </div>
      </section>

      <div className="-mx-1 flex gap-1 overflow-x-auto border-b border-line px-1 [scrollbar-width:none]">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              "-mb-px shrink-0 border-b-2 px-3 pb-3 text-sm font-medium transition",
              activeTab === tab.key
                ? "border-brand text-brand"
                : "border-transparent text-muted hover:text-ink"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "home" && (
        <div className="space-y-8">
          {searching ? (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-base font-semibold text-ink sm:text-lg">
                  Search results
                  {templates.data ? ` (${templates.data.total})` : ""}
                </h2>
                <Button size="sm" variant="ghost" onClick={clearSearch}>
                  Clear search
                </Button>
              </div>
              {templates.isLoading && <p className="text-sm text-muted">Searching…</p>}
              {!templates.isLoading && !(templates.data?.items || []).length && (
                <EmptyState
                  title="No matches"
                  description="Try another keyword, or browse categories below."
                />
              )}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {(templates.data?.items || []).map((template) => (
                  <TemplateCard
                    key={template.id}
                    template={template}
                    layout="grid"
                    {...cardProps}
                  />
                ))}
              </div>
            </div>
          ) : (
            <>
              <section className="space-y-3">
                <div className="flex items-end justify-between gap-3">
                  <div>
                    <h2 className="text-base font-semibold text-ink sm:text-lg">Categories</h2>
                    <p className="mt-0.5 text-sm text-muted">Filter the catalog by industry or use case</p>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      setSelectedCategory("");
                      setActiveTab("browse");
                    }}
                  >
                    View all
                  </Button>
                </div>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
                  {homeCategories.map((cat) => (
                    <button
                      key={cat.slug}
                      type="button"
                      onClick={() => {
                        setSelectedCategory(cat.slug);
                        clearSearch();
                        setActiveTab("browse");
                      }}
                      className={cn(
                        "rounded-xl border border-line bg-panel px-3 py-3 text-left transition hover:border-brand/40 hover:bg-canvas",
                        selectedCategory === cat.slug && "border-brand/50 bg-brand-soft/30"
                      )}
                    >
                      <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-line bg-canvas text-[10px] font-bold uppercase tracking-wide text-brand">
                        {CATEGORY_ICON[cat.slug] || cat.slug.slice(0, 2)}
                      </span>
                      <p className="mt-2 truncate text-sm font-semibold text-ink">{cat.name}</p>
                      <p className="mt-0.5 text-xs text-muted">
                        {cat.count || cat.template_count || 0} templates
                      </p>
                    </button>
                  ))}
                </div>
                {!homeCategories.length &&
                  !home.isLoading &&
                  !dash.isLoading &&
                  !categoriesQuery.isLoading && (
                  <EmptyState
                    title="No categories yet"
                    description="Seed marketplace templates to populate the catalog."
                  />
                )}
              </section>

              <TemplateRail
                title="Featured"
                subtitle="Hand-picked templates ready to install"
                items={featured}
                onSeeAll={() => setActiveTab("featured")}
                {...cardProps}
              />
              <TemplateRail
                title="Trending"
                subtitle="Popular installs across workspaces"
                items={trending}
                onSeeAll={() => {
                  setKindFilter("");
                  setSelectedCategory("");
                  setActiveTab("browse");
                }}
                {...cardProps}
              />
              <TemplateRail
                title="New"
                subtitle="Recently added to the catalog"
                items={newest}
                onSeeAll={() => setActiveTab("browse")}
                {...cardProps}
              />

              {!featured.length && !trending.length && !newest.length && !home.isLoading && (
                <EmptyState
                  title="Catalog is empty"
                  description="Seed marketplace templates, then refresh this page."
                />
              )}
            </>
          )}
        </div>
      )}

      {(activeTab === "browse" || activeTab === "featured") && (
        <div className="space-y-5">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
            <Input
              aria-label="Filter templates"
              placeholder="Search templates…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full lg:max-w-xs"
            />
            <div className="flex flex-wrap gap-2">
              {["", "package", "prompt", "agent"].map((kind) => (
                <Button
                  key={kind || "all-kinds"}
                  size="sm"
                  variant={kindFilter === kind ? "default" : "secondary"}
                  onClick={() => setKindFilter(kind)}
                >
                  {kind || "All kinds"}
                </Button>
              ))}
            </div>
          </div>

          <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 [scrollbar-width:thin]">
            <Button
              size="sm"
              variant={!selectedCategory ? "default" : "secondary"}
              onClick={() => setSelectedCategory("")}
              className="shrink-0"
            >
              All categories
            </Button>
            {browseCategories.map((cat) => (
              <Button
                key={cat.slug}
                size="sm"
                variant={selectedCategory === cat.slug ? "default" : "secondary"}
                className="shrink-0"
                onClick={() =>
                  setSelectedCategory(cat.slug === selectedCategory ? "" : cat.slug)
                }
              >
                {cat.name}
                {(cat.count || 0) > 0 ? ` (${cat.count})` : ""}
              </Button>
            ))}
          </div>

          {templates.isLoading && <p className="text-sm text-muted">Loading templates…</p>}
          {!templates.isLoading && !(templates.data?.items || []).length && (
            <EmptyState
              title="No templates found"
              description="Try a different search, kind, or category."
            />
          )}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {(templates.data?.items || []).map((template) => (
              <TemplateCard key={template.id} template={template} layout="grid" {...cardProps} />
            ))}
          </div>
          {typeof templates.data?.total === "number" &&
            templates.data.total > (templates.data.items?.length || 0) && (
              <p className="text-sm text-muted">
                Showing {templates.data.items.length} of {templates.data.total}
              </p>
            )}
        </div>
      )}

      {activeTab === "favorites" && (
        <div className="space-y-4">
          {!favorites.data?.length && !favorites.isLoading && (
            <EmptyState
              title="No favorites yet"
              description="Favorite templates from Home or Browse to find them here."
            />
          )}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {(favorites.data || []).map((template) => (
              <TemplateCard
                key={template.id}
                template={{ ...template, is_favorited: true }}
                layout="grid"
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
        open={Boolean(installTarget)}
        title={installTarget && !isFreeTemplate(installTarget) ? "Upgrade required" : "Install template"}
        onClose={() => setInstallTarget(null)}
      >
        {installTarget && (
          <div className="space-y-4">
            {isFreeTemplate(installTarget) ? (
              <>
                <p className="text-sm text-muted">
                  Install <span className="font-medium text-ink">{installTarget.name}</span> into your
                  company workspace? You can update or uninstall later.
                </p>
                <div className="flex flex-col-reverse justify-end gap-2 sm:flex-row">
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
              </>
            ) : (
              <>
                <p className="text-sm text-muted">
                  This template is paid and needs a higher plan. Upgrade your workspace to install it.
                </p>
                <div className="rounded-xl border border-line bg-canvas px-3 py-2 text-sm text-ink">
                  <p className="font-semibold">Upgrade to continue</p>
                  <p className="mt-1 text-muted">Choose a paid plan from billing to unlock this template.</p>
                </div>
                <div className="flex flex-col-reverse justify-end gap-2 sm:flex-row">
                  <Button variant="secondary" onClick={() => setInstallTarget(null)}>
                    Close
                  </Button>
                  <Button onClick={() => window.location.assign("/app/billing")}>Go to billing</Button>
                </div>
              </>
            )}
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
                <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                  Release notes
                </p>
                <p className="mt-1 whitespace-pre-wrap text-sm text-ink">{updateTarget.changelog}</p>
              </div>
            ) : null}
            <div className="flex flex-col-reverse justify-end gap-2 sm:flex-row">
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
