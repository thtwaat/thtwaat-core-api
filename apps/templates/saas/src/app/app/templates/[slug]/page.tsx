"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  marketplaceApi,
  type TemplateItem,
  type TemplateVersion
} from "@/lib/services";
import { cn, formatDate } from "@/lib/utils";
import { EmptyState } from "@/components/ui/misc";
import { Badge, Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  priceLabel,
  renderSimpleMarkdown,
  starsLabel,
  youtubeEmbedUrl
} from "./detail-helpers";

type DetailTab =
  | "overview"
  | "features"
  | "screenshots"
  | "demo"
  | "docs"
  | "reviews"
  | "versions"
  | "release_notes"
  | "related"
  | "permissions"
  | "requirements";

const TABS: Array<{ key: DetailTab; label: string }> = [
  { key: "overview", label: "Overview" },
  { key: "features", label: "Features" },
  { key: "screenshots", label: "Screenshots" },
  { key: "demo", label: "Demo Video" },
  { key: "docs", label: "Documentation" },
  { key: "reviews", label: "Reviews" },
  { key: "versions", label: "Versions" },
  { key: "release_notes", label: "Release Notes" },
  { key: "related", label: "Related" },
  { key: "permissions", label: "Permissions" },
  { key: "requirements", label: "Requirements" }
];

function SkeletonBlock({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-xl bg-line/60 dark:bg-line/30", className)} />;
}

function StarRow({ value }: { value: number }) {
  const full = Math.round(Math.max(0, Math.min(5, value)));
  return (
    <span className="inline-flex gap-0.5" aria-label={`${value} out of 5 stars`}>
      {Array.from({ length: 5 }).map((_, i) => (
        <span key={i} className={i < full ? "text-brand" : "text-line"}>
          ★
        </span>
      ))}
    </span>
  );
}

function MarkdownBlock({ source }: { source: string }) {
  return (
    <div
      className="prose-marketplace max-w-none"
      dangerouslySetInnerHTML={{ __html: renderSimpleMarkdown(source) }}
    />
  );
}

function InstallPanel({
  t,
  onInstall,
  onFavorite,
  onShare,
  onReport,
  onPreview,
  installing,
  favoriting
}: {
  t: TemplateItem;
  onInstall: () => void;
  onFavorite: () => void;
  onShare: () => void;
  onReport: () => void;
  onPreview: () => void;
  installing: boolean;
  favoriting: boolean;
}) {
  return (
    <aside className="lg:sticky lg:top-20">
      <Card className="space-y-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">Pricing</p>
          <p className="mt-1 text-2xl font-semibold text-ink">
            {priceLabel(t.price, t.pricing_tier, t.pricing_badge)}
          </p>
          {t.discount_percent ? (
            <p className="text-sm text-brand">{t.discount_percent}% off</p>
          ) : null}
        </div>
        <dl className="space-y-2 text-sm">
          <div className="flex justify-between gap-3">
            <dt className="text-muted">License</dt>
            <dd className="text-right font-medium text-ink">{t.license || "Marketplace"}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-muted">Publisher</dt>
            <dd className="text-right font-medium text-ink">{t.company_name || t.author}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-muted">Version</dt>
            <dd className="text-right font-medium text-ink">v{t.version}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-muted">Downloads</dt>
            <dd className="text-right font-medium text-ink">
              {t.download_count ?? t.install_count}
            </dd>
          </div>
        </dl>
        <div className="flex flex-col gap-2">
          {t.installed ? (
            <Badge tone="success">Installed</Badge>
          ) : (
            <Button onClick={onInstall} disabled={installing}>
              {installing ? "Installing…" : "Install"}
            </Button>
          )}
          <Button variant="secondary" onClick={onPreview}>
            Preview
          </Button>
          <Button variant="secondary" disabled={favoriting} onClick={onFavorite}>
            {t.is_favorited ? "Unfavorite" : "Favorite"}
          </Button>
          <Button variant="ghost" onClick={onShare}>
            Share / Copy link
          </Button>
          <Button variant="ghost" onClick={onReport}>
            Report
          </Button>
        </div>
        <div className="space-y-2 border-t border-line pt-3 text-sm">
          {t.publisher_website || t.website_url ? (
            <a
              className="block text-brand hover:underline"
              href={t.publisher_website || t.website_url || "#"}
              target="_blank"
              rel="noreferrer"
            >
              Website
            </a>
          ) : null}
          {t.support_url ? (
            <a className="block text-brand hover:underline" href={t.support_url} target="_blank" rel="noreferrer">
              Support
            </a>
          ) : null}
          {t.docs_url ? (
            <a className="block text-brand hover:underline" href={t.docs_url} target="_blank" rel="noreferrer">
              Documentation
            </a>
          ) : (
            <button type="button" className="block text-left text-brand hover:underline" onClick={onPreview}>
              Documentation
            </button>
          )}
        </div>
      </Card>
    </aside>
  );
}

export default function TemplateDetailPage() {
  const params = useParams<{ slug: string }>();
  const slug = decodeURIComponent(params.slug || "");
  const qc = useQueryClient();
  const [tab, setTab] = useState<DetailTab>("overview");
  const [confirmInstall, setConfirmInstall] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [lightbox, setLightbox] = useState<number | null>(null);

  const detail = useQuery({
    queryKey: ["mkt-template", slug],
    enabled: Boolean(slug),
    queryFn: () => marketplaceApi.get(slug)
  });
  const versions = useQuery({
    queryKey: ["mkt-versions", slug],
    enabled: Boolean(slug),
    queryFn: () => marketplaceApi.versions(slug)
  });
  const reviews = useQuery({
    queryKey: ["mkt-reviews", slug],
    enabled: Boolean(slug) && tab === "reviews",
    queryFn: () => marketplaceApi.reviews(slug)
  });
  const related = useQuery({
    queryKey: ["mkt-related", detail.data?.category],
    enabled: Boolean(detail.data?.category),
    queryFn: () =>
      marketplaceApi.listPage({
        category: detail.data!.category,
        sort: "installs",
        limit: 12
      })
  });

  const install = useMutation({
    mutationFn: () => marketplaceApi.install(slug, { create_api_key: false }),
    onSuccess: (data) => {
      toast.success(`${data.template_name || data.template_slug} installed`);
      if (data.api_key) toast.message(`API key (copy now): ${data.api_key}`);
      setConfirmInstall(false);
      qc.invalidateQueries({ queryKey: ["mkt-template", slug] });
      qc.invalidateQueries({ queryKey: ["mkt-home"] });
      qc.invalidateQueries({ queryKey: ["mkt-installed"] });
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
    onSuccess: () => {
      toast.message("Favorites updated");
      qc.invalidateQueries({ queryKey: ["mkt-template", slug] });
      qc.invalidateQueries({ queryKey: ["mkt-favorites"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const t = detail.data;
  const screenshots = t?.screenshots?.length ? t.screenshots : t?.thumbnail ? [t.thumbnail] : [];
  const embed = youtubeEmbedUrl(t?.video_url || undefined);
  const relatedItems = (related.data?.items || []).filter((item) => item.slug !== slug).slice(0, 8);

  const latestNotes = useMemo(() => {
    const list = versions.data || [];
    const latest = list.find((v) => v.is_latest) || list[0];
    return latest?.release_notes || latest?.changelog || null;
  }, [versions.data]);

  const docsCombined = useMemo(() => {
    if (!t) return "";
    const parts: string[] = [];
    if (t.quick_start) parts.push(`## Quick Start\n\n${t.quick_start}`);
    if (t.installation_docs) parts.push(`## Installation\n\n${t.installation_docs}`);
    if (t.configuration_docs) parts.push(`## Configuration\n\n${t.configuration_docs}`);
    if (t.examples_docs) parts.push(`## Examples\n\n${t.examples_docs}`);
    if (t.docs_markdown) parts.push(t.docs_markdown);
    if (!parts.length) parts.push(t.description || "No documentation published yet.");
    return parts.join("\n\n");
  }, [t]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setLightbox(null);
        setShareOpen(false);
        setConfirmInstall(false);
      }
      if (lightbox == null) return;
      if (e.key === "ArrowRight") setLightbox((i) => (i == null ? i : (i + 1) % screenshots.length));
      if (e.key === "ArrowLeft") {
        setLightbox((i) =>
          i == null ? i : (i - 1 + screenshots.length) % screenshots.length
        );
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [lightbox, screenshots.length]);

  const copyLink = async () => {
    const url = window.location.href;
    try {
      await navigator.clipboard.writeText(url);
      toast.success("Link copied");
    } catch {
      toast.message(url);
    }
  };

  const share = async () => {
    const url = window.location.href;
    if (navigator.share && t) {
      try {
        await navigator.share({ title: t.name, text: t.description, url });
        return;
      } catch {
        /* fall through */
      }
    }
    setShareOpen(true);
  };

  const report = () => {
    const subject = encodeURIComponent(`Report template: ${t?.name || slug}`);
    const body = encodeURIComponent(
      `Template: ${t?.name || slug}\nURL: ${typeof window !== "undefined" ? window.location.href : ""}\n\nDescribe the issue:`
    );
    window.open(`mailto:support@thtwaat.com?subject=${subject}&body=${body}`, "_blank");
    toast.message("Opened report email");
  };

  if (detail.isError) {
    return (
      <div className="space-y-4">
        <EmptyState title="Template not found" description="Check the slug or return to the store." />
        <Link
          href="/app/templates"
          className="inline-flex h-10 items-center rounded-xl bg-brand px-4 text-sm font-semibold text-brand-foreground"
        >
          Back to Marketplace
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-7xl space-y-5 pb-10">
      <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-2 text-sm text-muted">
        <Link href="/app/templates" className="hover:text-ink">
          Marketplace
        </Link>
        <span aria-hidden>/</span>
        <span className="text-ink">{t?.name || slug}</span>
      </nav>

      {detail.isLoading || !t ? (
        <div className="space-y-4" aria-busy="true" aria-label="Loading template">
          <SkeletonBlock className="h-48 w-full sm:h-64" />
          <div className="grid gap-4 lg:grid-cols-[1fr_300px]">
            <SkeletonBlock className="h-64" />
            <SkeletonBlock className="h-80" />
          </div>
        </div>
      ) : (
        <>
          {/* Hero */}
          <section className="overflow-hidden rounded-2xl border border-line bg-panel">
            <div className="relative h-44 w-full bg-gradient-to-br from-brand/20 via-canvas to-panel sm:h-56 md:h-64">
              {t.banner_url || t.thumbnail ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={t.banner_url || t.thumbnail || ""}
                  alt=""
                  className="h-full w-full object-cover"
                />
              ) : null}
              <div className="absolute bottom-4 left-4 flex items-end gap-3 sm:left-6">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-line bg-panel text-sm font-bold uppercase text-brand shadow-soft sm:h-16 sm:w-16">
                  {t.icon ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={t.icon} alt="" className="h-10 w-10 object-contain" />
                  ) : (
                    (t.category || "tp").slice(0, 2)
                  )}
                </div>
              </div>
            </div>

            <div className="space-y-4 p-4 sm:p-6">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0 space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                    {t.category.replace(/_/g, " ")}
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    <h1 className="text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
                      {t.name}
                    </h1>
                    <Badge>{priceLabel(t.price, t.pricing_tier, t.pricing_badge)}</Badge>
                    <Badge tone="neutral">{t.category.replace(/_/g, " ")}</Badge>
                    {t.verified_publisher && <Badge tone="success">Verified</Badge>}
                    {t.is_featured && <Badge tone="brand">Featured</Badge>}
                    {t.installed && <Badge tone="success">Installed</Badge>}
                  </div>
                  <p className="max-w-3xl text-sm text-muted sm:text-base">
                    {t.what_it_does || t.description}
                  </p>
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted sm:text-sm">
                    <span>by {t.company_name || t.author}</span>
                    <span>v{t.version}</span>
                    <span className="inline-flex items-center gap-1">
                      <StarRow value={t.rating_avg ?? 0} />
                      <span>{starsLabel(t.rating_avg)}</span>
                      {t.review_count ? <span>({t.review_count})</span> : null}
                    </span>
                    <span>
                      {t.install_count} install{t.install_count !== 1 ? "s" : ""}
                    </span>
                    <span>Updated {formatDate(t.updated_at || t.created_at)}</span>
                    {t.compatibility ? <span>AI: {t.compatibility}</span> : null}
                    {t.supported_providers?.length ? (
                      <span>Providers: {t.supported_providers.join(", ")}</span>
                    ) : null}
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 lg:hidden">
                  {!t.installed && (
                    <Button onClick={() => setConfirmInstall(true)} disabled={install.isPending}>
                      Install
                    </Button>
                  )}
                  <Button variant="secondary" onClick={() => setTab("overview")}>
                    Preview
                  </Button>
                  <Button
                    variant="secondary"
                    disabled={favorite.isPending}
                    onClick={() => favorite.mutate(t)}
                  >
                    {t.is_favorited ? "Unfavorite" : "Favorite"}
                  </Button>
                  <Button variant="ghost" onClick={share}>
                    Share
                  </Button>
                  <Button variant="ghost" onClick={report}>
                    Report
                  </Button>
                </div>
              </div>
            </div>
          </section>

          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
            <div className="min-w-0 space-y-5">
              <div
                role="tablist"
                aria-label="Template sections"
                className="-mx-1 flex gap-1 overflow-x-auto border-b border-line px-1 [scrollbar-width:thin]"
              >
                {TABS.map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    role="tab"
                    aria-selected={tab === item.key}
                    onClick={() => setTab(item.key)}
                    className={cn(
                      "-mb-px shrink-0 border-b-2 px-3 pb-3 text-sm font-medium transition",
                      tab === item.key
                        ? "border-brand text-brand"
                        : "border-transparent text-muted hover:text-ink"
                    )}
                  >
                    {item.label}
                  </button>
                ))}
              </div>

              {tab === "overview" && (
                <Card className="space-y-5">
                  <div>
                    <h2 className="text-lg font-semibold text-ink">Overview</h2>
                    <p className="mt-2 whitespace-pre-wrap text-sm text-muted">{t.description}</p>
                  </div>
                  {t.what_it_does && (
                    <div>
                      <h3 className="text-sm font-semibold text-ink">What it does</h3>
                      <p className="mt-1 text-sm text-muted">{t.what_it_does}</p>
                    </div>
                  )}
                  {(t.best_for || []).length > 0 && (
                    <div>
                      <h3 className="text-sm font-semibold text-ink">Best for</h3>
                      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted">
                        {t.best_for!.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {(t.use_cases || []).length > 0 && (
                    <div>
                      <h3 className="text-sm font-semibold text-ink">Use cases</h3>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {t.use_cases!.map((item) => (
                          <Badge key={item}>{item}</Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {(t.industries || []).length > 0 && (
                    <div>
                      <h3 className="text-sm font-semibold text-ink">Industries</h3>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {t.industries!.map((item) => (
                          <Badge key={item} tone="neutral">
                            {item}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 text-sm">
                    <div>
                      <dt className="text-muted">Estimated setup</dt>
                      <dd className="font-medium text-ink">
                        {t.estimated_install_minutes != null
                          ? `~${t.estimated_install_minutes} minutes`
                          : "A few minutes"}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted">Compatibility</dt>
                      <dd className="font-medium text-ink">{t.compatibility || "THTWAAT Cloud"}</dd>
                    </div>
                    <div>
                      <dt className="text-muted">Languages</dt>
                      <dd className="font-medium text-ink">
                        {(t.languages || []).length ? t.languages!.join(", ") : "English"}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted">License</dt>
                      <dd className="font-medium text-ink">{t.license || "Marketplace"}</dd>
                    </div>
                    <div>
                      <dt className="text-muted">Kind</dt>
                      <dd className="font-medium capitalize text-ink">{t.kind || "package"}</dd>
                    </div>
                    <div>
                      <dt className="text-muted">Publisher</dt>
                      <dd className="font-medium text-ink">{t.company_name || t.author}</dd>
                    </div>
                  </dl>
                </Card>
              )}

              {tab === "features" && (
                <div className="grid gap-3 sm:grid-cols-2">
                  {(t.feature_cards || []).map((f) => (
                    <Card key={f.key} className="space-y-1">
                      <h3 className="font-semibold text-ink">{f.title}</h3>
                      <p className="text-sm text-muted">{f.description}</p>
                    </Card>
                  ))}
                </div>
              )}

              {tab === "screenshots" && (
                <Card>
                  <h2 className="mb-3 text-lg font-semibold text-ink">Screenshots</h2>
                  {!screenshots.length ? (
                    <EmptyState title="No screenshots yet" description="Publisher has not uploaded gallery images." />
                  ) : (
                    <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
                      {screenshots.map((src, idx) => (
                        <button
                          key={`${src}-${idx}`}
                          type="button"
                          className="overflow-hidden rounded-xl border border-line focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
                          onClick={() => setLightbox(idx)}
                        >
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img src={src} alt={`Screenshot ${idx + 1}`} className="aspect-video w-full object-cover" />
                        </button>
                      ))}
                    </div>
                  )}
                </Card>
              )}

              {tab === "demo" && (
                <Card className="space-y-3">
                  <h2 className="text-lg font-semibold text-ink">Demo Video</h2>
                  {embed ? (
                    <div className="aspect-video overflow-hidden rounded-xl border border-line">
                      <iframe
                        title="Demo video"
                        src={embed}
                        className="h-full w-full"
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                        allowFullScreen
                      />
                    </div>
                  ) : t.video_url ? (
                    <a
                      href={t.video_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex text-sm font-medium text-brand hover:underline"
                    >
                      Open demo video
                    </a>
                  ) : t.live_demo_url ? (
                    <a
                      href={t.live_demo_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex h-10 items-center rounded-xl border border-line px-4 text-sm font-semibold"
                    >
                      Open live demo
                    </a>
                  ) : (
                    <EmptyState title="No demo video" description="A walkthrough video has not been published yet." />
                  )}
                </Card>
              )}

              {tab === "docs" && (
                <Card>
                  <h2 className="mb-3 text-lg font-semibold text-ink">Documentation</h2>
                  <MarkdownBlock source={docsCombined} />
                </Card>
              )}

              {tab === "reviews" && (
                <Card className="space-y-4">
                  <h2 className="text-lg font-semibold text-ink">Reviews</h2>
                  {reviews.isLoading && <p className="text-sm text-muted">Loading reviews…</p>}
                  <div className="flex flex-wrap items-center gap-4">
                    <div>
                      <p className="text-3xl font-semibold text-ink">
                        {(reviews.data?.rating_avg ?? t.rating_avg)?.toFixed(1) || "—"}
                      </p>
                      <StarRow value={reviews.data?.rating_avg ?? t.rating_avg ?? 0} />
                      <p className="mt-1 text-xs text-muted">
                        {reviews.data?.review_count ?? t.review_count ?? 0} reviews
                      </p>
                    </div>
                    <div className="min-w-[180px] flex-1 space-y-1">
                      {[5, 4, 3, 2, 1].map((star) => {
                        const total = reviews.data?.review_count || t.review_count || 0;
                        const count = reviews.data?.distribution?.[String(star)] || 0;
                        const pct = total ? Math.round((count / total) * 100) : 0;
                        return (
                          <div key={star} className="flex items-center gap-2 text-xs text-muted">
                            <span className="w-3">{star}</span>
                            <div className="h-2 flex-1 overflow-hidden rounded-full bg-canvas">
                              <div className="h-full bg-brand" style={{ width: `${pct}%` }} />
                            </div>
                            <span className="w-8 text-right">{count}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                  {(reviews.data?.items || []).length === 0 && !reviews.isLoading && (
                    <EmptyState
                      title="No reviews yet"
                      description="Reviews appear when this template has a published agent-store listing."
                    />
                  )}
                  <ul className="space-y-3">
                    {(reviews.data?.items || []).map((r) => (
                      <li key={r.id} className="rounded-xl border border-line bg-canvas p-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <StarRow value={r.rating} />
                          {r.verified_install && <Badge tone="success">Verified install</Badge>}
                          <span className="text-xs text-muted">{formatDate(r.created_at)}</span>
                        </div>
                        {r.title && <p className="mt-1 text-sm font-semibold text-ink">{r.title}</p>}
                        {r.body && <p className="mt-1 text-sm text-muted">{r.body}</p>}
                        <div className="mt-2 flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => toast.message("Thanks — helpful votes ship with full review moderation.")}
                          >
                            Helpful ({r.helpful_count || 0})
                          </Button>
                          <Button size="sm" variant="ghost" onClick={report}>
                            Report abuse
                          </Button>
                        </div>
                      </li>
                    ))}
                  </ul>
                </Card>
              )}

              {tab === "versions" && (
                <Card className="space-y-4">
                  <h2 className="text-lg font-semibold text-ink">Version history</h2>
                  {versions.isLoading && <p className="text-sm text-muted">Loading…</p>}
                  {!versions.isLoading && !(versions.data || []).length && (
                    <p className="text-sm text-muted">No version history yet.</p>
                  )}
                  <ol className="relative space-y-4 border-l border-line pl-4">
                    {(versions.data || []).map((v: TemplateVersion) => (
                      <li key={v.id} className="relative">
                        <span className="absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full bg-brand" />
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-semibold text-ink">v{v.version}</span>
                          {v.is_latest && <Badge tone="brand">latest</Badge>}
                          <span className="text-xs text-muted">
                            {formatDate(v.published_at || v.created_at)}
                          </span>
                        </div>
                        <p className="mt-1 whitespace-pre-wrap text-sm text-muted">
                          {v.release_notes || v.changelog || "No changelog."}
                        </p>
                        {/breaking/i.test(v.release_notes || v.changelog || "") && (
                          <Badge tone="warn">Breaking changes noted</Badge>
                        )}
                      </li>
                    ))}
                  </ol>
                </Card>
              )}

              {tab === "release_notes" && (
                <Card>
                  <h2 className="mb-3 text-lg font-semibold text-ink">Release notes</h2>
                  {latestNotes ? (
                    <MarkdownBlock source={latestNotes} />
                  ) : (
                    <EmptyState title="No release notes" description="Latest version has no notes yet." />
                  )}
                </Card>
              )}

              {tab === "related" && (
                <div className="space-y-3">
                  <h2 className="text-lg font-semibold text-ink">Related templates</h2>
                  <p className="text-sm text-muted">Similar category · often installed together</p>
                  {!relatedItems.length && (
                    <EmptyState title="No related templates" description="Try browsing the catalog." />
                  )}
                  <div className="-mx-1 flex gap-3 overflow-x-auto px-1 pb-2 snap-x">
                    {relatedItems.map((item) => (
                      <Card key={item.id} className="min-w-[240px] max-w-[280px] shrink-0 snap-start">
                        <Link
                          href={`/app/templates/${item.slug}`}
                          className="font-semibold text-ink hover:underline"
                        >
                          {item.name}
                        </Link>
                        <p className="mt-1 line-clamp-2 text-sm text-muted">{item.description}</p>
                        <p className="mt-2 text-xs text-muted">
                          {priceLabel(item.price, item.pricing_tier, item.pricing_badge)} ·{" "}
                          {item.install_count} installs
                        </p>
                      </Card>
                    ))}
                  </div>
                </div>
              )}

              {tab === "permissions" && (
                <Card>
                  <h2 className="mb-3 text-lg font-semibold text-ink">Permissions</h2>
                  <p className="mb-3 text-sm text-muted">
                    Installing this template may use the following platform capabilities.
                  </p>
                  <ul className="space-y-2">
                    {(t.permissions || []).map((p) => (
                      <li
                        key={p}
                        className="flex items-center justify-between rounded-xl border border-line bg-canvas px-3 py-2 text-sm"
                      >
                        <span className="font-medium text-ink">{p}</span>
                        <Badge tone="neutral">Required</Badge>
                      </li>
                    ))}
                  </ul>
                </Card>
              )}

              {tab === "requirements" && (
                <Card className="space-y-4">
                  <h2 className="text-lg font-semibold text-ink">Requirements</h2>
                  <dl className="grid gap-3 sm:grid-cols-2 text-sm">
                    <div>
                      <dt className="text-muted">Minimum platform version</dt>
                      <dd className="font-medium text-ink">{t.min_platform_version || "Latest THTWAAT Cloud"}</dd>
                    </div>
                    <div>
                      <dt className="text-muted">Supported AI providers</dt>
                      <dd className="font-medium text-ink">
                        {(t.supported_providers || []).length
                          ? t.supported_providers!.join(", ")
                          : t.compatibility || "Platform default"}
                      </dd>
                    </div>
                  </dl>
                  <div>
                    <h3 className="text-sm font-semibold text-ink">Dependencies</h3>
                    {(t.dependencies || []).length ? (
                      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted">
                        {t.dependencies!.map((d) => (
                          <li key={d}>{d}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-1 text-sm text-muted">No extra dependencies beyond a THTWAAT workspace.</p>
                    )}
                  </div>
                </Card>
              )}
            </div>

            <div className="hidden lg:block">
              <InstallPanel
                t={t}
                installing={install.isPending}
                favoriting={favorite.isPending}
                onInstall={() => setConfirmInstall(true)}
                onFavorite={() => favorite.mutate(t)}
                onShare={share}
                onReport={report}
                onPreview={() => setTab("docs")}
              />
            </div>
          </div>
        </>
      )}

      {/* Lightbox */}
      {lightbox != null && screenshots[lightbox] && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/70 p-4" role="dialog" aria-modal="true">
          <button type="button" className="absolute inset-0" aria-label="Close gallery" onClick={() => setLightbox(null)} />
          <div className="relative z-10 w-full max-w-4xl">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={screenshots[lightbox]}
              alt={`Screenshot ${lightbox + 1}`}
              className="max-h-[80vh] w-full rounded-2xl object-contain"
            />
            <div className="mt-3 flex justify-between gap-2">
              <Button
                variant="secondary"
                onClick={() =>
                  setLightbox((i) => (i == null ? i : (i - 1 + screenshots.length) % screenshots.length))
                }
              >
                Previous
              </Button>
              <Button variant="secondary" onClick={() => setLightbox(null)}>
                Close
              </Button>
              <Button
                variant="secondary"
                onClick={() => setLightbox((i) => (i == null ? i : (i + 1) % screenshots.length))}
              >
                Next
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Share dialog */}
      {shareOpen && t && (
        <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center">
          <button type="button" aria-label="Close" className="absolute inset-0 bg-ink/40" onClick={() => setShareOpen(false)} />
          <div className="relative z-10 w-full max-w-md rounded-t-2xl border border-line bg-panel p-5 sm:rounded-2xl">
            <h2 className="text-lg font-semibold text-ink">Share {t.name}</h2>
            <p className="mt-2 break-all text-sm text-muted">{typeof window !== "undefined" ? window.location.href : ""}</p>
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setShareOpen(false)}>
                Close
              </Button>
              <Button onClick={copyLink}>Copy link</Button>
            </div>
          </div>
        </div>
      )}

      {confirmInstall && t && (
        <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center">
          <button
            type="button"
            aria-label="Close"
            className="absolute inset-0 bg-ink/40"
            onClick={() => setConfirmInstall(false)}
          />
          <div className="relative z-10 w-full max-w-md rounded-t-2xl border border-line bg-panel p-5 sm:rounded-2xl">
            <h2 className="text-lg font-semibold">Install {t.name}?</h2>
            <p className="mt-2 text-sm text-muted">
              Uses the existing marketplace install engine for your company workspace.
            </p>
            <div className="mt-4 flex flex-col-reverse justify-end gap-2 sm:flex-row">
              <Button variant="secondary" onClick={() => setConfirmInstall(false)}>
                Cancel
              </Button>
              <Button disabled={install.isPending} onClick={() => install.mutate()}>
                {install.isPending ? "Installing…" : "Confirm install"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
