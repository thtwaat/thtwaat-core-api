"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { platformAdminApi } from "@/lib/services";
import { downloadAdminExport, formatRevenue } from "@/lib/super-admin";
import { PageHeader, EmptyState, Stat } from "@/components/ui/misc";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/input";

export default function AdminAiAnalyticsPage() {
  const [days, setDays] = useState(30);
  const q = useQuery({
    queryKey: ["admin-ai-analytics", days],
    queryFn: () => platformAdminApi.aiAnalytics(days)
  });

  const data = q.data || {};
  const providers = (data.provider_usage as Array<Record<string, unknown>>) || [];
  const byDay = (data.requests_day as Array<{ t: string; count: number }>) || [];
  const byHour = (data.requests_hour as Array<{ t: string; count: number }>) || [];
  const topPrompts = (data.top_prompts as Array<{ prompt: string; count: number }>) || [];
  const topAgents = (data.top_agents as Array<{ agent_id: string; count: number }>) || [];
  const tokens = (data.token_usage as Record<string, number>) || {};
  const latency = (data.latency as Record<string, number>) || {};

  async function doExport(format: "csv" | "xlsx" | "pdf") {
    try {
      const payload = await platformAdminApi.export("ai", format);
      downloadAdminExport(payload);
      toast.success(`Exported ${payload.filename}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Export failed");
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI Analytics"
        description="Requests, providers, tokens, cost, latency, and top prompts/agents."
        action={
          <div className="flex flex-wrap gap-2">
            <Select
              value={String(days)}
              onChange={(e) => setDays(Number(e.target.value))}
              aria-label="Range days"
            >
              <option value="7">7 days</option>
              <option value="30">30 days</option>
              <option value="90">90 days</option>
            </Select>
            <Button variant="secondary" onClick={() => void q.refetch()}>
              Refresh
            </Button>
            <Button variant="secondary" onClick={() => void doExport("csv")}>
              CSV
            </Button>
            <Button variant="secondary" onClick={() => void doExport("xlsx")}>
              Excel
            </Button>
          </div>
        }
      />

      {q.isError && <EmptyState title="Failed to load AI analytics" description={(q.error as Error).message} />}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Total requests" value={String(data.total_requests ?? "—")} />
        <Stat label="Success rate" value={`${Number(data.success_rate ?? 0).toFixed(1)}%`} />
        <Stat label="Error rate" value={`${Number(data.error_rate ?? 0).toFixed(1)}%`} />
        <Stat label="Avg latency" value={`${Number(latency.avg_ms ?? 0).toFixed(0)} ms`} />
        <Stat label="Prompt tokens" value={String(tokens.prompt_tokens ?? "—")} />
        <Stat label="Completion tokens" value={String(tokens.completion_tokens ?? "—")} />
        <Stat label="Total tokens" value={String(tokens.total_tokens ?? "—")} />
        <Stat label="Hour buckets" value={String(byHour.length || "—")} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="space-y-3">
          <h2 className="text-sm font-semibold text-ink">Provider usage</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="text-xs uppercase text-muted">
                <tr>
                  <th className="py-2">Provider</th>
                  <th className="py-2">Requests</th>
                  <th className="py-2">Tokens</th>
                  <th className="py-2">Cost</th>
                  <th className="py-2">Latency</th>
                </tr>
              </thead>
              <tbody>
                {providers.map((p) => (
                  <tr key={String(p.provider)} className="border-t border-line/70">
                    <td className="py-2">{String(p.provider)}</td>
                    <td className="py-2">{String(p.requests)}</td>
                    <td className="py-2">{String(p.tokens)}</td>
                    <td className="py-2">{formatRevenue(Number(p.cost_estimate || 0))}</td>
                    <td className="py-2">{String(p.avg_latency_ms)} ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!providers.length && <p className="text-sm text-muted">No provider traffic in range.</p>}
          </div>
        </Card>

        <Card className="space-y-3">
          <h2 className="text-sm font-semibold text-ink">Requests / day</h2>
          <ul className="max-h-72 space-y-1 overflow-auto text-sm">
            {byDay.map((d) => (
              <li key={d.t} className="flex justify-between gap-4 border-b border-line/50 py-1">
                <span className="text-muted">{d.t}</span>
                <span className="font-medium text-ink">{d.count}</span>
              </li>
            ))}
            {!byDay.length && <li className="text-muted">No daily series yet.</li>}
          </ul>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="space-y-3">
          <h2 className="text-sm font-semibold text-ink">Top prompts</h2>
          <ul className="max-h-72 space-y-2 overflow-auto text-sm">
            {topPrompts.map((p) => (
              <li key={p.prompt} className="border-b border-line/50 pb-2">
                <p className="text-ink">{p.prompt}</p>
                <p className="text-xs text-muted">{p.count} requests</p>
              </li>
            ))}
            {!topPrompts.length && <li className="text-muted">No prompt samples.</li>}
          </ul>
        </Card>
        <Card className="space-y-3">
          <h2 className="text-sm font-semibold text-ink">Top agents</h2>
          <ul className="max-h-72 space-y-2 overflow-auto text-sm">
            {topAgents.map((a) => (
              <li key={a.agent_id} className="flex justify-between gap-4 border-b border-line/50 py-1">
                <span className="truncate font-mono text-xs text-ink">{a.agent_id}</span>
                <span className="text-muted">{a.count}</span>
              </li>
            ))}
            {!topAgents.length && <li className="text-muted">No agent traffic.</li>}
          </ul>
        </Card>
      </div>
    </div>
  );
}
