"use client";

import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { platformAdminApi } from "@/lib/services";
import {
  downloadAdminExport,
  formatPct,
  formatRevenue,
  healthComponentStatus,
  healthTone
} from "@/lib/super-admin";
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
  const execQ = useQuery({ queryKey: ["admin-executive"], queryFn: platformAdminApi.executive });
  const healthQ = useQuery({ queryKey: ["admin-health"], queryFn: platformAdminApi.health });

  const e = execQ.data;

  async function exportKind(kind: string, format: "csv" | "xlsx" | "pdf") {
    try {
      const payload = await platformAdminApi.export(kind, format);
      downloadAdminExport(payload);
      toast.success(`Exported ${payload.filename}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Export failed");
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Executive Dashboard"
        description="Platform KPIs from /admin/executive — workspaces, AI usage, revenue, churn."
        action={
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              onClick={() => {
                void execQ.refetch();
                void healthQ.refetch();
              }}
            >
              Refresh
            </Button>
            <Button variant="secondary" onClick={() => void exportKind("executive", "csv")}>
              CSV
            </Button>
            <Button variant="secondary" onClick={() => void exportKind("executive", "xlsx")}>
              Excel
            </Button>
            <Button variant="secondary" onClick={() => void exportKind("executive", "pdf")}>
              PDF
            </Button>
          </div>
        }
      />

      {execQ.isError && (
        <EmptyState title="Could not load dashboard" description={(execQ.error as Error)?.message} />
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Workspaces" value={String(e?.workspaces ?? "—")} />
        <Stat label="Active users" value={String(e?.active_users ?? "—")} />
        <Stat label="New signups (7d)" value={String(e?.new_signups ?? "—")} />
        <Stat label="Active agents" value={String(e?.active_agents ?? "—")} />
        <Stat label="Knowledge bases" value={String(e?.knowledge_bases ?? "—")} />
        <Stat label="Widgets" value={String(e?.widgets ?? "—")} />
        <Stat label="AI requests" value={String(e?.ai_requests ?? "—")} />
        <Stat label="Token usage" value={String(e?.token_usage ?? "—")} />
        <Stat label="Revenue" value={formatRevenue(e?.revenue)} />
        <Stat label="MRR" value={formatRevenue(e?.mrr)} />
        <Stat label="ARR" value={formatRevenue(e?.arr)} />
        <Stat label="Active subscriptions" value={String(e?.active_subscriptions ?? "—")} />
        <Stat label="Churn" value={formatPct(e?.churn)} />
        <Stat label="Conversion" value={formatPct(e?.conversion_rate)} />
        <Stat label="AI cost" value={formatRevenue(e?.ai_cost)} />
        <Stat label="System health" value={(healthQ.data?.status || "—").toString()} />
      </div>

      <Card className="space-y-3">
        <h2 className="text-sm font-semibold text-ink">Health snapshot</h2>
        <div className="flex flex-wrap gap-2">
          {(
            [
              ["API", healthQ.data?.api],
              ["PostgreSQL", healthQ.data?.database],
              ["Redis", healthQ.data?.redis],
              ["Workers", healthQ.data?.workers],
              ["Storage", healthQ.data?.storage],
              ["AI Providers", healthQ.data?.ai_providers],
              ["Email queue", healthQ.data?.email_queue],
              ["Jobs", healthQ.data?.background_jobs]
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
