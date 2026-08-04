"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { marketplaceApi, type TemplateItem } from "@/lib/services";
import { formatDate } from "@/lib/utils";
import { PageHeader, EmptyState } from "@/components/ui/misc";
import { Badge, Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

type DetailTab = "overview" | "features" | "docs" | "versions" | "reviews" | "related";

function priceLabel(price: string | number | undefined, tier?: string, badge?: string | null) {
  if (badge) return badge;
  const n = Number(price ?? 0);
  if (!(n > 0)) return tier && tier !== "free" ? tier : "Free";
  return `$${n}`;
}

export default function TemplateDetailPage() {
  const params = useParams<{ slug: string }>();
  const slug = decodeURIComponent(params.slug || "");
  const qc = useQueryClient();
  const [tab, setTab] = useState<DetailTab>("overview");
  const [confirmInstall, setConfirmInstall] = useState(false);

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
  const related = useQuery({
    queryKey: ["mkt-related", detail.data?.category],
    enabled: Boolean(detail.data?.category),
    queryFn: () =>
      marketplaceApi.listPage({
        category: detail.data!.category,
        sort: "installs",
        limit: 8
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
  const features = useMemo(() => {
    const cfg = (t?.default_config || {}) as Record<string, unknown>;
    const raw = cfg.features;
    if (Array.isArray(raw)) return raw.map(String);
    const tags = t?.tags || [];
    return tags.length ? tags : ["Agents", "Domains", "Marketplace install"];
  }, [t]);

  const docsBody = useMemo(() => {
    const cfg = (t?.default_config || {}) as Record<string, unknown>;
    return (
      (typeof cfg.docs === "string" && cfg.docs) ||
      (typeof cfg.readme === "string" && cfg.readme) ||
      t?.description ||
      "No additional documentation yet."
    );
  }, [t]);

  const relatedItems = (related.data?.items || []).filter((item) => item.slug !== slug).slice(0, 6);

  const tabs: Array<{ key: DetailTab; label: string }> = [
    { key: "overview", label: "Overview" },
    { key: "features", label: "Features" },
    { key: "docs", label: "Docs" },
    { key: "versions", label: "Versions" },
    { key: "reviews", label: "Reviews" },
    { key: "related", label: "Related" }
  ];

  const share = async () => {
    if (!t) return;
    const url = window.location.href;
    try {
      await navigator.clipboard.writeText(url);
      toast.success("Link copied");
    } catch {
      toast.message(url);
    }
  };

  if (detail.isError) {
    return (
      <div className="space-y-4">
        <PageHeader title="Template" description="Could not load this template." />
        <EmptyState title="Not found" description="Check the slug or return to the store." />
        <Link
          href="/app/templates"
          className="inline-flex h-10 items-center rounded-lg bg-brand px-4 text-sm font-medium text-white"
        >
          Back to Marketplace
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
        <Link href="/app/templates" className="hover:text-ink">
          Marketplace
        </Link>
        <span>/</span>
        <span className="text-ink">{t?.name || slug}</span>
      </div>

      {detail.isLoading || !t ? (
        <p className="text-sm text-muted">Loading template…</p>
      ) : (
        <>
          <div className="overflow-hidden rounded-2xl border border-line bg-panel">
            {t.banner_url || t.thumbnail ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={t.banner_url || t.thumbnail || ""}
                alt=""
                className="h-40 w-full object-cover sm:h-56"
              />
            ) : (
              <div className="flex h-32 items-end bg-gradient-to-br from-brand/15 via-canvas to-panel p-5 sm:h-40">
                <p className="text-sm uppercase tracking-wide text-muted">{t.category}</p>
              </div>
            )}
            <div className="space-y-4 p-5 sm:p-6">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <h1 className="text-2xl font-semibold text-ink">{t.name}</h1>
                    <Badge>{priceLabel(t.price, t.pricing_tier, t.pricing_badge)}</Badge>
                    {t.is_featured && <Badge tone="brand">Featured</Badge>}
                    {t.is_editors_choice && <Badge tone="brand">Editor’s choice</Badge>}
                    {t.verified_publisher && <Badge tone="success">Verified publisher</Badge>}
                    {t.installed && <Badge tone="success">Installed</Badge>}
                  </div>
                  <p className="max-w-3xl text-sm text-muted">{t.description}</p>
                  <div className="flex flex-wrap gap-3 text-xs text-muted">
                    <span>by {t.company_name || t.author}</span>
                    <span>v{t.version}</span>
                    <span>
                      {t.install_count} install{t.install_count !== 1 ? "s" : ""}
                    </span>
                    {t.rating_avg != null && t.review_count ? (
                      <span>
                        ★ {t.rating_avg.toFixed(1)} · {t.review_count} reviews
                      </span>
                    ) : null}
                    {t.estimated_install_minutes != null ? (
                      <span>~{t.estimated_install_minutes} min install</span>
                    ) : null}
                    {t.compatibility ? <span>{t.compatibility}</span> : null}
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button variant="secondary" onClick={share}>
                    Share
                  </Button>
                  <Button
                    variant="secondary"
                    disabled={favorite.isPending}
                    onClick={() => favorite.mutate(t)}
                  >
                    {t.is_favorited ? "Unfavorite" : "Favorite"}
                  </Button>
                  {t.live_demo_url && (
                    <a
                      href={t.live_demo_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex h-10 items-center rounded-lg border border-line bg-panel px-4 text-sm font-medium"
                    >
                      Live demo
                    </a>
                  )}
                  {!t.installed && (
                    <Button onClick={() => setConfirmInstall(true)} disabled={install.isPending}>
                      Install
                    </Button>
                  )}
                </div>
              </div>

              {(t.screenshots || []).length > 0 && (
                <div className="flex gap-3 overflow-x-auto pb-1">
                  {(t.screenshots || []).map((src) => (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      key={src}
                      src={src}
                      alt=""
                      className="h-28 w-48 shrink-0 rounded-xl border border-line object-cover"
                    />
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="flex gap-2 overflow-x-auto border-b border-line">
            {tabs.map((item) => (
              <button
                key={item.key}
                type="button"
                onClick={() => setTab(item.key)}
                className={`-mb-px shrink-0 border-b-2 px-1 pb-3 text-sm font-medium transition ${
                  tab === item.key
                    ? "border-brand text-brand"
                    : "border-transparent text-muted hover:text-ink"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>

          {tab === "overview" && (
            <Card className="space-y-3">
              <h2 className="font-semibold text-ink">Overview</h2>
              <p className="whitespace-pre-wrap text-sm text-muted">{t.description}</p>
              <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 text-sm">
                <div>
                  <dt className="text-muted">Kind</dt>
                  <dd className="font-medium capitalize">{t.kind || "package"}</dd>
                </div>
                <div>
                  <dt className="text-muted">Category</dt>
                  <dd className="font-medium capitalize">{t.category.replace(/_/g, " ")}</dd>
                </div>
                <div>
                  <dt className="text-muted">Publisher</dt>
                  <dd className="font-medium">{t.publisher_slug || t.author}</dd>
                </div>
                <div>
                  <dt className="text-muted">Updated</dt>
                  <dd className="font-medium">{formatDate(t.updated_at || t.created_at)}</dd>
                </div>
              </dl>
            </Card>
          )}

          {tab === "features" && (
            <Card>
              <h2 className="mb-3 font-semibold text-ink">Features</h2>
              <ul className="space-y-2 text-sm text-muted">
                {features.map((f) => (
                  <li key={f} className="flex gap-2">
                    <span className="text-brand">•</span>
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-4 flex flex-wrap gap-2 text-xs">
                {t.supports_agents && <Badge>Agents</Badge>}
                {t.supports_domains && <Badge>Domains</Badge>}
                {t.supports_billing && <Badge>Billing</Badge>}
                {t.supports_mobile && <Badge>Mobile</Badge>}
              </div>
            </Card>
          )}

          {tab === "docs" && (
            <Card>
              <h2 className="mb-3 font-semibold text-ink">Docs</h2>
              <p className="whitespace-pre-wrap text-sm text-muted">{docsBody}</p>
              {t.video_url && (
                <a
                  href={t.video_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-3 inline-block text-sm text-brand hover:underline"
                >
                  Watch video walkthrough
                </a>
              )}
            </Card>
          )}

          {tab === "versions" && (
            <Card className="space-y-3">
              <h2 className="font-semibold text-ink">Versions</h2>
              {versions.isLoading ? (
                <p className="text-sm text-muted">Loading…</p>
              ) : (versions.data || []).length === 0 ? (
                <p className="text-sm text-muted">No version history yet.</p>
              ) : (
                <ul className="space-y-2">
                  {(versions.data || []).map((v) => (
                    <li key={v.id} className="rounded-xl border border-line bg-canvas px-3 py-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold">v{v.version}</span>
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
            </Card>
          )}

          {tab === "reviews" && (
            <Card className="space-y-2">
              <h2 className="font-semibold text-ink">Reviews</h2>
              {t.rating_avg != null && t.review_count ? (
                <p className="text-sm text-muted">
                  Average ★ {t.rating_avg.toFixed(1)} from {t.review_count} agent-store reviews.
                  Full review threads ship in the next marketplace phase.
                </p>
              ) : (
                <p className="text-sm text-muted">
                  No linked agent-store ratings yet. Ratings appear when this template has a published
                  listing.
                </p>
              )}
            </Card>
          )}

          {tab === "related" && (
            <div className="space-y-3">
              <h2 className="font-semibold text-ink">Related templates</h2>
              {!relatedItems.length && (
                <EmptyState title="No related templates" description="Try browsing the same category." />
              )}
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {relatedItems.map((item) => (
                  <Card key={item.id}>
                    <Link href={`/app/templates/${item.slug}`} className="font-semibold text-ink hover:underline">
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
        </>
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
              This uses the existing marketplace install engine for your company workspace.
            </p>
            <div className="mt-4 flex justify-end gap-2">
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
