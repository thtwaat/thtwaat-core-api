"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { toast } from "sonner";
import { billingApi, platformAdminApi } from "@/lib/services";
import {
  downloadAdminExport,
  formatPct,
  formatRevenue,
  healthComponentStatus,
  healthTone
} from "@/lib/super-admin";
import { formatNumber } from "@/lib/utils";
import { PageHeader, Stat, EmptyState } from "@/components/ui/misc";
import { Badge, Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const REALTIME_MS = 15_000;

function toneClass(tone: string) {
  if (tone === "success") return "success" as const;
  if (tone === "warn") return "warn" as const;
  if (tone === "danger") return "danger" as const;
  return "neutral" as const;
}

export default function AdminDashboardPage() {
  const execQ = useQuery({
    queryKey: ["admin-executive"],
    queryFn: platformAdminApi.executive,
    refetchInterval: REALTIME_MS
  });
  const healthQ = useQuery({
    queryKey: ["admin-health"],
    queryFn: platformAdminApi.health,
    refetchInterval: REALTIME_MS
  });
  const billingQ = useQuery({
    queryKey: ["admin-billing-analytics"],
    queryFn: billingApi.adminAnalytics,
    refetchInterval: REALTIME_MS
  });

  const e = execQ.data;
  const health = healthQ.data;
  const billing = billingQ.data;

  const revenueChart = useMemo(
    () =>
      (e?.revenue_series || []).map((row) => ({
        period: row.period,
        revenue: Number(row.revenue || 0)
      })),
    [e?.revenue_series]
  );
  const aiChart = useMemo(
    () =>
      (e?.ai_series || []).map((row) => ({
        period: String(row.period || "").slice(5),
        requests: Number(row.requests || 0),
        tokens: Number(row.tokens || 0)
      })),
    [e?.ai_series]
  );

  async function exportKind(kind: string, format: "csv" | "xlsx" | "pdf" = "csv") {
    try {
      const payload = await platformAdminApi.export(kind, format);
      downloadAdminExport(payload);
      toast.success(`Exported ${payload.filename}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Export failed");
    }
  }

  const healthRows = [
    ["System", health?.status],
    ["API", healthComponentStatus(health?.api as Record<string, unknown>)],
    ["DB", healthComponentStatus(health?.database as Record<string, unknown>)],
    ["Redis", healthComponentStatus(health?.redis as Record<string, unknown>)],
    [
      "Queue",
      healthComponentStatus(
        (health?.queue || health?.background_jobs || health?.email_queue) as Record<string, unknown>
      )
    ],
    ["Workers", healthComponentStatus(health?.workers as Record<string, unknown>)]
  ] as const;

  const lastUpdated = e?.generated_at
    ? new Date(e.generated_at).toLocaleTimeString()
    : healthQ.dataUpdatedAt
      ? new Date(healthQ.dataUpdatedAt).toLocaleTimeString()
      : "—";

  return (
    <div className="space-y-6">
      <PageHeader
        title="Enterprise Super Admin"
        description="Global revenue, AI usage, billing failures, and live system health. Auto-refreshes every 15s."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="neutral">Live · {lastUpdated}</Badge>
            <Button
              variant="secondary"
              onClick={() => {
                void execQ.refetch();
                void healthQ.refetch();
                void billingQ.refetch();
              }}
            >
              Refresh
            </Button>
            <Button variant="secondary" onClick={() => void exportKind("executive", "csv")}>
              Export KPIs CSV
            </Button>
            <Button variant="secondary" onClick={() => void exportKind("billing", "csv")}>
              Export revenue CSV
            </Button>
            <Button variant="secondary" onClick={() => void exportKind("ai", "csv")}>
              Export AI CSV
            </Button>
          </div>
        }
      />

      {execQ.isError && (
        <EmptyState title="Could not load dashboard" description={(execQ.error as Error)?.message} />
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Global Revenue" value={formatRevenue(e?.global_revenue ?? e?.revenue)} />
        <Stat label="Monthly Revenue" value={formatRevenue(e?.monthly_revenue)} />
        <Stat label="MRR" value={formatRevenue(e?.mrr ?? billing?.mrr)} />
        <Stat label="Failed Payments" value={String(e?.failed_payments ?? billing?.failed_payments ?? "—")} />
        <Stat label="Active Companies" value={String(e?.active_companies ?? e?.workspaces ?? "—")} />
        <Stat label="Active Users" value={String(e?.active_users ?? "—")} />
        <Stat label="Active Subscriptions" value={String(e?.active_subscriptions ?? "—")} />
        <Stat label="ARR" value={formatRevenue(e?.arr ?? billing?.arr)} />
        <Stat label="AI Usage" value={formatNumber(e?.ai_usage ?? e?.ai_requests)} />
        <Stat label="Token Usage" value={formatNumber(e?.token_usage)} />
        <Stat label="Provider Cost" value={formatRevenue(e?.provider_cost ?? e?.ai_cost)} hint="Estimated" />
        <Stat label="Churn" value={formatPct(e?.churn)} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Monthly Revenue" description="Paid invoice totals by month" />
          <div className="h-64 w-full">
            {revenueChart.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={revenueChart}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="period" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Area
                    type="monotone"
                    dataKey="revenue"
                    stroke="#0f766e"
                    fill="#99f6e4"
                    fillOpacity={0.55}
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted">No revenue series yet.</p>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader title="AI Usage (14d)" description="Completion requests and tokens" />
          <div className="h-64 w-full">
            {aiChart.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={aiChart}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="period" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="requests" fill="#0f766e" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted">No AI series yet.</p>
            )}
          </div>
        </Card>
      </div>

      <Card className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-ink">System Health</h2>
          <Badge tone={toneClass(healthTone(String(health?.status || "unknown")))}>
            Overall: {String(health?.status || "—")}
          </Badge>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {healthRows.map(([label, status]) => (
            <div
              key={label}
              className="flex items-center justify-between rounded-xl border border-line px-3 py-2.5 text-sm"
            >
              <span className="font-medium">{label} Health</span>
              <Badge tone={toneClass(healthTone(String(status || "unknown")))}>
                {String(status || "unknown")}
              </Badge>
            </div>
          ))}
        </div>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="New signups (7d)" value={String(e?.new_signups ?? "—")} />
        <Stat label="Active agents" value={String(e?.active_agents ?? "—")} />
        <Stat label="Knowledge bases" value={String(e?.knowledge_bases ?? "—")} />
        <Stat label="Conversion" value={formatPct(e?.conversion_rate)} />
      </div>
    </div>
  );
}
