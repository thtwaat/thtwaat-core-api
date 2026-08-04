"use client";

import { useQuery } from "@tanstack/react-query";
import { platformAdminApi } from "@/lib/services";
import { healthComponentStatus, healthTone } from "@/lib/super-admin";
import { PageHeader, EmptyState, Stat } from "@/components/ui/misc";
import { Badge, Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

function tone(status: string) {
  const t = healthTone(status);
  if (t === "success") return "success" as const;
  if (t === "warn") return "warn" as const;
  if (t === "danger") return "danger" as const;
  return "neutral" as const;
}

export default function AdminHealthPage() {
  const healthQ = useQuery({
    queryKey: ["admin-system-health"],
    queryFn: platformAdminApi.health,
    refetchInterval: 30_000
  });

  const data = healthQ.data;
  const components = [
    ["API", data?.api],
    ["PostgreSQL", data?.database],
    ["Redis", data?.redis],
    ["Workers", data?.workers],
    ["Queue / webhooks", data?.queue],
    ["Email queue", data?.email_queue],
    ["Background jobs", data?.background_jobs],
    ["Storage", data?.storage],
    ["AI Providers", data?.ai_providers]
  ] as const;

  return (
    <div className="space-y-6">
      <PageHeader
        title="System Health"
        description="Live signals from GET /monitoring/health (platform admin)."
        action={
          <Button variant="secondary" onClick={() => void healthQ.refetch()} disabled={healthQ.isFetching}>
            Refresh
          </Button>
        }
      />

      {healthQ.isError && (
        <EmptyState title="Health check failed" description={(healthQ.error as Error).message} />
      )}

      <Stat label="Overall" value={(data?.status || "—").toString()} />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {components.map(([label, component]) => {
          const status = healthComponentStatus(component as Record<string, unknown>);
          return (
            <Card key={label} className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <h2 className="font-semibold text-ink">{label}</h2>
                <Badge tone={tone(status)}>{status}</Badge>
              </div>
              <pre className="max-h-40 overflow-auto rounded-xl bg-canvas p-3 text-xs text-muted">
                {JSON.stringify(component || {}, null, 2)}
              </pre>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
