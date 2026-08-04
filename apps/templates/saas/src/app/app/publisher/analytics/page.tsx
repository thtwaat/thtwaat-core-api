"use client";

import { useQuery } from "@tanstack/react-query";
import { agentStoreApi } from "@/lib/services";
import { PageHeader, EmptyState, Stat } from "@/components/ui/misc";
import { Card } from "@/components/ui/card";
import { PublisherNav } from "@/components/publisher/nav";

export default function PublisherAnalyticsPage() {
  const analytics = useQuery({
    queryKey: ["publisher-analytics"],
    queryFn: () => agentStoreApi.analytics()
  });
  const a = analytics.data;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Publisher Analytics"
        description="Installs, retention, revenue, and conversion signals."
      />
      <PublisherNav />

      {analytics.isError ? (
        <EmptyState title="Analytics unavailable" description={(analytics.error as Error).message} />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Revenue" value={a ? `${a.currency} ${a.publisher_revenue.toFixed(2)}` : "—"} />
            <Stat label="Downloads" value={String(a?.total_downloads ?? "—")} />
            <Stat
              label="Conversion"
              value={a?.conversion_rate != null ? `${a.conversion_rate}%` : "—"}
            />
            <Stat
              label="Retention"
              value={a?.retention_rate != null ? `${a.retention_rate}%` : "—"}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card className="space-y-3 p-5">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">
                Daily installs
              </h3>
              {(a?.daily_installs ?? []).length === 0 ? (
                <p className="text-sm text-muted">No install events yet.</p>
              ) : (
                <ul className="max-h-64 space-y-1 overflow-auto text-sm">
                  {(a?.daily_installs ?? []).map((row) => (
                    <li key={row.date} className="flex justify-between border-b border-line py-1">
                      <span className="text-muted">{row.date}</span>
                      <span className="font-medium text-ink">{row.count}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
            <Card className="space-y-3 p-5">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">
                Monthly installs
              </h3>
              {(a?.monthly_installs ?? []).length === 0 ? (
                <p className="text-sm text-muted">No monthly data yet.</p>
              ) : (
                <ul className="max-h-64 space-y-1 overflow-auto text-sm">
                  {(a?.monthly_installs ?? []).map((row) => (
                    <li key={row.month} className="flex justify-between border-b border-line py-1">
                      <span className="text-muted">{row.month}</span>
                      <span className="font-medium text-ink">{row.count}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
            <Card className="space-y-3 p-5">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">Countries</h3>
              {(a?.countries ?? []).length === 0 ? (
                <p className="text-sm text-muted">Geo breakdown not available yet.</p>
              ) : (
                <ul className="space-y-1 text-sm">
                  {(a?.countries ?? []).map((row) => (
                    <li key={row.country} className="flex justify-between">
                      <span>{row.country}</span>
                      <span>{row.count}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
            <Card className="space-y-3 p-5">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">Devices</h3>
              {(a?.devices ?? []).length === 0 ? (
                <p className="text-sm text-muted">Device breakdown not available yet.</p>
              ) : (
                <ul className="space-y-1 text-sm">
                  {(a?.devices ?? []).map((row) => (
                    <li key={row.device} className="flex justify-between">
                      <span className="capitalize">{row.device}</span>
                      <span>{row.count}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
