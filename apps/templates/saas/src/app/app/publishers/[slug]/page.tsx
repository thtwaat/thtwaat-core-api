"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { agentStoreApi } from "@/lib/services";
import { PageHeader, EmptyState, Stat } from "@/components/ui/misc";
import { Badge, Card } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function PublicPublisherPage() {
  const params = useParams<{ slug: string }>();
  const slug = params.slug;

  const profile = useQuery({
    queryKey: ["publisher-public", slug],
    queryFn: () => agentStoreApi.publicPublisher(slug),
    enabled: Boolean(slug)
  });

  if (profile.isLoading) {
    return <p className="text-sm text-muted">Loading publisher…</p>;
  }
  if (profile.isError || !profile.data) {
    return (
      <EmptyState
        title="Publisher not found"
        description={(profile.error as Error | undefined)?.message}
      />
    );
  }

  const p = profile.data;

  return (
    <div className="space-y-6">
      <div
        className="relative overflow-hidden rounded-2xl border border-line bg-panel"
        style={
          p.banner_url
            ? {
                backgroundImage: `linear-gradient(to bottom, rgba(15,23,42,0.35), rgba(15,23,42,0.7)), url(${p.banner_url})`,
                backgroundSize: "cover",
                backgroundPosition: "center"
              }
            : undefined
        }
      >
        <div className={cn("flex flex-col gap-4 p-6 sm:flex-row sm:items-end", p.banner_url && "text-white")}>
          <div
            className="grid h-20 w-20 place-items-center overflow-hidden rounded-2xl border border-line bg-canvas text-2xl font-semibold text-ink"
            style={
              p.logo_url
                ? { backgroundImage: `url(${p.logo_url})`, backgroundSize: "cover" }
                : undefined
            }
          >
            {!p.logo_url ? p.display_name.slice(0, 1).toUpperCase() : null}
          </div>
          <div className="flex-1 space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-semibold tracking-tight">{p.display_name}</h1>
              {p.is_verified ? (
                <Badge className="bg-teal-50 text-teal-800">Verified</Badge>
              ) : null}
            </div>
            <p className={cn("max-w-2xl text-sm", p.banner_url ? "text-white/85" : "text-muted")}>
              {p.bio || "Marketplace publisher on THTWAAT."}
            </p>
            <div className="flex flex-wrap gap-3 text-sm">
              {p.website ? (
                <a href={p.website} target="_blank" rel="noreferrer" className="underline">
                  Website
                </a>
              ) : null}
              {p.github_url ? (
                <a href={p.github_url} target="_blank" rel="noreferrer" className="underline">
                  GitHub
                </a>
              ) : null}
              {p.linkedin_url ? (
                <a href={p.linkedin_url} target="_blank" rel="noreferrer" className="underline">
                  LinkedIn
                </a>
              ) : null}
              {p.twitter_url ? (
                <a href={p.twitter_url} target="_blank" rel="noreferrer" className="underline">
                  Twitter
                </a>
              ) : null}
            </div>
          </div>
        </div>
      </div>

      <PageHeader title="Publisher stats" description={`@${p.slug}`} />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Stat label="Followers" value={String(p.followers_count)} />
        <Stat label="Following" value={String(p.following_count)} />
        <Stat label="Templates" value={String(p.published_count)} />
        <Stat label="Rating" value={String(p.average_rating)} />
        <Stat label="Installs" value={String(p.total_installs)} />
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-ink">Templates</h2>
        {p.listings.length === 0 ? (
          <EmptyState title="No published templates" />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {p.listings.map((l) => (
              <Card key={l.id} className="space-y-2 p-4">
                <p className="font-semibold text-ink">{l.title}</p>
                <p className="line-clamp-2 text-sm text-muted">{l.short_description}</p>
                <p className="text-xs text-muted">
                  ★ {l.rating_avg ?? 0} · {l.install_count} installs · v{l.current_version}
                </p>
                <Link
                  href={`/app/templates/${l.slug}`}
                  className={cn(buttonVariants({ variant: "secondary", size: "sm" }))}
                >
                  View in store
                </Link>
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
