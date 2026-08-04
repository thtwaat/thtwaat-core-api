"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ApiError } from "@/lib/api";
import { agentStoreApi } from "@/lib/services";
import { PageHeader, EmptyState, Stat } from "@/components/ui/misc";
import { buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PublisherNav } from "@/components/publisher/nav";
import { cn } from "@/lib/utils";

export default function PublisherDashboardPage() {
  const me = useQuery({
    queryKey: ["publisher-me"],
    queryFn: () => agentStoreApi.getMe(),
    retry: false
  });
  const analytics = useQuery({
    queryKey: ["publisher-analytics"],
    queryFn: () => agentStoreApi.analytics(),
    enabled: me.isSuccess,
    retry: false
  });

  const needsOnboarding =
    me.isError && me.error instanceof ApiError && me.error.status === 404;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Publisher Portal"
        description="Manage listings, revenue, and marketplace presence."
        action={
          <Link href="/app/publisher/listings/new" className={cn(buttonVariants())}>
            New template
          </Link>
        }
      />
      <PublisherNav />

      {needsOnboarding ? (
        <Card className="space-y-4 p-6">
          <EmptyState
            title="Become a publisher"
            description="Create your publisher profile to list templates on the THTWAAT Marketplace."
          />
          <Link href="/app/publisher/profile" className={cn(buttonVariants())}>
            Set up profile
          </Link>
        </Card>
      ) : me.isError ? (
        <EmptyState title="Unable to load publisher" description={(me.error as Error).message} />
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-sm text-muted">
              Signed in as{" "}
              <span className="font-semibold text-ink">{me.data?.display_name ?? "…"}</span>
              {me.data?.is_verified ? (
                <span className="ml-2 rounded-full bg-teal-50 px-2 py-0.5 text-xs font-medium text-teal-800">
                  Verified
                </span>
              ) : null}
            </p>
            {me.data?.slug ? (
              <Link
                href={`/app/publishers/${me.data.slug}`}
                className="text-sm font-medium text-teal-700 hover:underline"
              >
                View public profile
              </Link>
            ) : null}
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            <Stat label="Total Templates" value={String(analytics.data?.listings ?? "—")} />
            <Stat label="Published" value={String(analytics.data?.published_listings ?? "—")} />
            <Stat label="Draft" value={String(analytics.data?.draft_listings ?? "—")} />
            <Stat
              label="Pending Review"
              value={String(analytics.data?.pending_review_listings ?? "—")}
            />
            <Stat
              label="Revenue"
              value={
                analytics.data
                  ? `${analytics.data.currency} ${analytics.data.publisher_revenue.toFixed(2)}`
                  : "—"
              }
            />
            <Stat label="Total Installs" value={String(analytics.data?.total_installs ?? "—")} />
            <Stat label="Active Installs" value={String(analytics.data?.active_installs ?? "—")} />
            <Stat
              label="Monthly Growth"
              value={
                analytics.data?.monthly_growth_pct != null
                  ? `${analytics.data.monthly_growth_pct}%`
                  : "—"
              }
            />
            <Stat
              label="Average Rating"
              value={
                analytics.data?.average_rating != null
                  ? String(analytics.data.average_rating)
                  : "—"
              }
            />
          </div>
        </>
      )}
    </div>
  );
}
