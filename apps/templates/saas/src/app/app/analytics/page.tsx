"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Bar,
  BarChart
} from "recharts";
import { marketplaceApi, usageApi } from "@/lib/services";
import { formatBytes, formatNumber } from "@/lib/utils";
import { PageHeader, Stat } from "@/components/ui/misc";
import { Card, CardHeader, Badge } from "@/components/ui/card";

export default function AnalyticsPage() {
  const current = useQuery({ queryKey: ["usage-current"], queryFn: usageApi.current });
  const history = useQuery({ queryKey: ["usage-history"], queryFn: () => usageApi.history(30) });
  const dashboard = useQuery({ queryKey: ["usage-dashboard"], queryFn: usageApi.dashboard });
  const marketplace = useQuery({
    queryKey: ["marketplace-analytics"],
    queryFn: () => marketplaceApi.analytics(30)
  });

  const chartData = useMemo(() => {
    const map = new Map<string, { day: string; messages: number; tokens: number; api: number }>();
    for (const point of history.data?.points || []) {
      const day = point.day.slice(0, 10);
      const row = map.get(day) || { day, messages: 0, tokens: 0, api: 0 };
      if (point.dimension.includes("message") || point.dimension === "ai_messages") row.messages += point.quantity;
      if (point.dimension.includes("token")) row.tokens += point.quantity;
      if (point.dimension.includes("api") || point.dimension === "api_requests") row.api += point.quantity;
      map.set(day, row);
    }
    return Array.from(map.values()).sort((a, b) => a.day.localeCompare(b.day));
  }, [history.data]);

  const usage = current.data?.usage || {};
  const topAgents = (dashboard.data?.top_agents as Array<Record<string, unknown>>) || [];
  const mkt = marketplace.data?.company;
  const mktChart = mkt?.installs_over_time || [];
  const mktCategories = mkt?.by_category || [];

  return (
    <div className="space-y-6">
      <PageHeader title="Analytics" description="Usage, marketplace installs, and agent activity." />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Messages" value={formatNumber(usage.ai_messages)} />
        <Stat label="Tokens" value={formatNumber(usage.total_tokens)} />
        <Stat label="API requests" value={formatNumber(usage.api_requests)} />
        <Stat label="Storage" value={formatBytes(usage.storage_bytes)} />
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Templates installed" value={formatNumber(mkt?.installed_count)} />
        <Stat label="Updates available" value={formatNumber(mkt?.updates_available)} />
        <Stat label="Favorites" value={formatNumber(mkt?.favorites_count)} />
        <Stat
          label="Installs (30d)"
          value={formatNumber(mktChart.reduce((sum, p) => sum + p.installs, 0))}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader title="Messages over time" />
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Area type="monotone" dataKey="messages" stroke="#0f766e" fill="#ccfbf1" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <CardHeader title="Marketplace installs" description="Last 30 days" />
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={mktChart}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Area type="monotone" dataKey="installs" stroke="#0f766e" fill="#ccfbf1" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader title="API usage" />
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="api" fill="#0f766e" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <CardHeader title="Installs by category" />
          <div className="h-64">
            {mktCategories.length === 0 ? (
              <p className="px-1 py-8 text-sm text-muted">No marketplace installs yet.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={mktCategories}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#0f766e" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader title="Recent marketplace installs" />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-muted">
              <tr>
                <th className="pb-2 font-medium">Template</th>
                <th className="pb-2 font-medium">Kind</th>
                <th className="pb-2 font-medium">Category</th>
                <th className="pb-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {(mkt?.recent_installs || []).map((row) => (
                <tr key={row.template_id} className="border-t border-line">
                  <td className="py-2">
                    <p className="font-medium text-ink">{row.name}</p>
                    <p className="text-xs text-muted">{row.slug}</p>
                  </td>
                  <td className="py-2">
                    <Badge tone="neutral">{row.kind}</Badge>
                  </td>
                  <td className="py-2">{row.category}</td>
                  <td className="py-2">{row.status || "—"}</td>
                </tr>
              ))}
              {!(mkt?.recent_installs || []).length && (
                <tr>
                  <td className="py-4 text-muted" colSpan={4}>
                    No marketplace installs yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <Card>
        <CardHeader title="Top agents" description="From /usage/dashboard" />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-muted">
              <tr>
                <th className="pb-2 font-medium">Agent</th>
                <th className="pb-2 font-medium">Messages</th>
                <th className="pb-2 font-medium">Tokens</th>
              </tr>
            </thead>
            <tbody>
              {topAgents.map((row, i) => (
                <tr key={i} className="border-t border-line">
                  <td className="py-2">{String(row.agent_name || row.agent_id || "—")}</td>
                  <td className="py-2">{formatNumber(Number(row.messages || row.ai_messages || 0))}</td>
                  <td className="py-2">{formatNumber(Number(row.tokens || row.total_tokens || 0))}</td>
                </tr>
              ))}
              {!topAgents.length && (
                <tr>
                  <td className="py-4 text-muted" colSpan={3}>
                    No analytics yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
