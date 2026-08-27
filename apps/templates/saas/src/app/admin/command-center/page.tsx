"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { commandCenterApi, type CommandCenterDashboard, type CeoAnalysis } from "@/lib/services";
import { formatPct, formatRevenue } from "@/lib/super-admin";
import { formatNumber } from "@/lib/utils";
import { PageHeader, Stat, EmptyState } from "@/components/ui/misc";
import { Badge, Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

function formatCost(amount?: number | null): string {
  if (amount == null || Number.isNaN(Number(amount))) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2
  }).format(Number(amount));
}

function MetricGrid({
  items
}: {
  items: Array<{ label: string; value: string; hint?: string }>;
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((item) => (
        <Stat key={item.label} label={item.label} value={item.value} hint={item.hint} />
      ))}
    </div>
  );
}

function departmentCards(data: CommandCenterDashboard) {
  return [
    {
      title: "Sales",
      description: "Revenue performance and pipeline signals from Core billing + leads.",
      metrics: [
        { label: "Revenue", value: formatRevenue(data.revenue) },
        { label: "MRR", value: formatRevenue(data.mrr) },
        { label: "Leads", value: formatNumber(data.leads) },
        { label: "Conversion", value: formatPct(data.conversion) }
      ]
    },
    {
      title: "Engineering",
      description: "Active product surfaces and tenant footprint.",
      metrics: [
        { label: "Active Projects", value: formatNumber(data.active_projects) },
        { label: "Customers", value: formatNumber(data.customers) }
      ]
    },
    {
      title: "Support",
      description: "Human handoffs and captured lead conversations.",
      metrics: [
        { label: "Human Escalations", value: formatNumber(data.human_escalations) },
        { label: "Leads", value: formatNumber(data.leads) }
      ]
    },
    {
      title: "AI Operations",
      description: "Platform AI volume and estimated provider cost.",
      metrics: [
        { label: "AI Tasks", value: formatNumber(data.ai_tasks) },
        { label: "AI Cost", value: formatCost(data.ai_cost) }
      ]
    }
  ] as const;
}

function AnalysisList({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h4 className="text-sm font-semibold text-ink">{title}</h4>
      {items.length === 0 ? (
        <p className="mt-2 text-sm text-muted">None identified.</p>
      ) : (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink">
          {items.map((item) => (
            <li key={`${title}-${item}`}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function AiCeoPanel({ analysis, loading, error, onGenerate }: {
  analysis?: CeoAnalysis;
  loading: boolean;
  error?: string;
  onGenerate: () => void;
}) {
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-ink">AI CEO Analysis</h2>
          <p className="mt-1 text-sm text-muted">
            Read-only advisory from live dashboard metrics. No actions are executed.
          </p>
        </div>
        <Button onClick={onGenerate} disabled={loading} variant="secondary">
          {loading ? "Analyzing…" : analysis ? "Regenerate analysis" : "Generate analysis"}
        </Button>
      </div>

      {error && (
        <EmptyState title="AI CEO analysis failed" description={error} />
      )}

      {loading && !analysis && (
        <EmptyState
          title="Generating AI CEO analysis…"
          description="Using live Command Center metrics only."
        />
      )}

      {analysis && (
        <Card className="space-y-5">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">Advisory only</Badge>
            {analysis.provider && (
              <Badge tone="neutral">
                {analysis.provider}
                {analysis.model_used ? ` · ${analysis.model_used}` : ""}
              </Badge>
            )}
            <Badge tone="neutral">
              {new Date(analysis.generated_at).toLocaleString()}
            </Badge>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-ink">Business status</h3>
            <p className="mt-2 text-sm text-ink">{analysis.business_status}</p>
          </div>

          <div className="grid gap-5 lg:grid-cols-2">
            <AnalysisList title="Problems" items={analysis.problems} />
            <AnalysisList title="Opportunities" items={analysis.opportunities} />
          </div>

          <div>
            <h3 className="text-sm font-semibold text-ink">You Must Decide (Top 3)</h3>
            <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm text-ink">
              {analysis.you_must_decide.map((item, idx) => (
                <li key={`decide-${idx}`}>{item}</li>
              ))}
            </ol>
          </div>

          <AnalysisList title="Recommendations" items={analysis.recommendations} />
        </Card>
      )}
    </section>
  );
}

export default function CommandCenterPage() {
  const dashQ = useQuery({
    queryKey: ["command-center-dashboard"],
    queryFn: commandCenterApi.dashboard,
    refetchInterval: 30_000
  });

  const ceoM = useMutation({
    mutationFn: commandCenterApi.ceoAnalysis
  });

  const data = dashQ.data;
  const updatedAt = dashQ.dataUpdatedAt
    ? new Date(dashQ.dataUpdatedAt).toLocaleTimeString()
    : "—";

  return (
    <div className="space-y-6">
      <PageHeader
        title="Command Center"
        description="Founder / CEO read-only view of live Core API metrics. Super Admin only."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="neutral">Live · {updatedAt}</Badge>
            <Button
              variant="secondary"
              onClick={() => void dashQ.refetch()}
              disabled={dashQ.isFetching}
            >
              {dashQ.isFetching ? "Refreshing…" : "Refresh"}
            </Button>
          </div>
        }
      />

      {dashQ.isLoading && (
        <EmptyState title="Loading Command Center…" description="Fetching live metrics from Core API." />
      )}

      {dashQ.isError && (
        <EmptyState
          title="Could not load Command Center"
          description={(dashQ.error as Error)?.message || "Request failed"}
        />
      )}

      {data && (
        <>
          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-ink">Platform KPIs</h2>
            <MetricGrid
              items={[
                { label: "Revenue", value: formatRevenue(data.revenue) },
                { label: "MRR", value: formatRevenue(data.mrr) },
                { label: "Customers", value: formatNumber(data.customers) },
                { label: "Active Projects", value: formatNumber(data.active_projects) },
                { label: "Leads", value: formatNumber(data.leads) },
                { label: "Conversion", value: formatPct(data.conversion) },
                { label: "AI Tasks", value: formatNumber(data.ai_tasks) },
                { label: "Human Escalations", value: formatNumber(data.human_escalations) },
                { label: "AI Cost", value: formatCost(data.ai_cost), hint: "Estimated" }
              ]}
            />
          </section>

          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-ink">Departments</h2>
            <div className="grid gap-4 lg:grid-cols-2">
              {departmentCards(data).map((dept) => (
                <Card key={dept.title} className="space-y-4">
                  <div>
                    <h3 className="text-base font-semibold text-ink">{dept.title}</h3>
                    <p className="mt-1 text-sm text-muted">{dept.description}</p>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {dept.metrics.map((m) => (
                      <div
                        key={`${dept.title}-${m.label}`}
                        className="rounded-xl border border-line bg-canvas px-3 py-2.5"
                      >
                        <p className="text-xs font-medium uppercase tracking-wide text-muted">
                          {m.label}
                        </p>
                        <p className="mt-1 text-lg font-semibold text-ink">{m.value}</p>
                      </div>
                    ))}
                  </div>
                </Card>
              ))}
            </div>
          </section>

          <AiCeoPanel
            analysis={ceoM.data}
            loading={ceoM.isPending}
            error={ceoM.isError ? ((ceoM.error as Error)?.message || "Request failed") : undefined}
            onGenerate={() => ceoM.mutate()}
          />
        </>
      )}
    </div>
  );
}
