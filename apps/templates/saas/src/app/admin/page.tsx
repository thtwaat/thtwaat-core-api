"use client";

import { useQuery } from "@tanstack/react-query";
import { platformAdminApi } from "@/lib/services";
import { formatRevenue, healthComponentStatus, healthTone } from "@/lib/super-admin";
import { PageHeader, Stat, EmptyState } from "@/components/ui/misc";
import { Badge, Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

function toneClass(tone: string) {
  if (tone === "success") return "success" as const;
  if (tone === "warn") return "warn" as const;
  if (tone === "danger") return "danger" as const;
  return "neutral" as const;
}

export default function AdminDashboardPage() {
  const overviewQ = useQuery({ queryKey: ["admin-overview"], queryFn: platformAdminApi.overview });
  const healthQ = useQuery({ queryKey: ["admin-health"], queryFn: platformAdminApi.health });
  const obsQ = useQuery({
    queryKey: ["admin-observability"],
    queryFn: platformAdminApi.observability
  });

  const o = overviewQ.data;
  const volume = (obsQ.data?.request_volume || {}) as Record<string, unknown>;
  const apiRequests = Number(volume.total ?? volume.count ?? volume.api_requests ?? 0) || 0;
  const aiRequests = Number(volume.ai_requests ?? volume.messages ?? o?.product_generations ?? 0) || 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Super Admin Dashboard"
        description="Platform overview from existing /admin/overview and /monitoring APIs."
        action={
          <Button
            variant="secondary"
            onClick={() => {
              void overviewQ.refetch();
              void healthQ.refetch();
              void obsQ.refetch();
            }}
          >
            Refresh
          </Button>
        }
      />

      {(overviewQ.isError || healthQ.isError) && (
        <EmptyState
          title="Could not load dashboard"
          description={(overviewQ.error as Error)?.message || (healthQ.error as Error)?.message}
        />
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Companies" value={String(o?.companies ?? "—")} />
        <Stat label="Users" value={String(o?.active_users ?? "—")} />
        <Stat label="Revenue" value={formatRevenue(o?.billing_summary?.revenue_paid)} />
        <Stat label="Active agents" value={String(o?.published_agents ?? o?.agents ?? "—")} />
        <Stat label="AI requests" value={String(aiRequests || "—")} hint="From observability / generations" />
        <Stat label="API requests" value={String(apiRequests || "—")} hint="From observability snapshot" />
        <Stat
          label="System health"
          value={(healthQ.data?.status || "—").toString()}
          hint={healthQ.isFetching ? "Checking…" : undefined}
        />
        <Stat
          label="Subscriptions"
          value={String(o?.billing_summary?.active_subscriptions ?? "—")}
        />
      </div>

      <Card className="space-y-3">
        <h2 className="text-sm font-semibold text-ink">Health snapshot</h2>
        <div className="flex flex-wrap gap-2">
          {(
            [
              ["PostgreSQL", healthQ.data?.database],
              ["Redis", healthQ.data?.redis],
              ["Workers", healthQ.data?.workers],
              ["AI Providers", healthQ.data?.ai_providers]
            ] as const
          ).map(([label, component]) => {
            const status = healthComponentStatus(component as Record<string, unknown>);
            return (
              <Badge key={label} tone={toneClass(healthTone(status))}>
                {label}: {status}
              </Badge>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
