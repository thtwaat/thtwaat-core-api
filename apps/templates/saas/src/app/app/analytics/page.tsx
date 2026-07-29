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
import { usageApi } from "@/lib/services";
import { formatBytes, formatNumber } from "@/lib/utils";
import { PageHeader, Stat } from "@/components/ui/misc";
import { Card, CardHeader } from "@/components/ui/card";

export default function AnalyticsPage() {
  const current = useQuery({ queryKey: ["usage-current"], queryFn: usageApi.current });
  const history = useQuery({ queryKey: ["usage-history"], queryFn: () => usageApi.history(30) });
  const dashboard = useQuery({ queryKey: ["usage-dashboard"], queryFn: usageApi.dashboard });

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

  return (
    <div className="space-y-6">
      <PageHeader title="Analytics" description="Messages, tokens, storage, and API usage charts." />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Messages" value={formatNumber(usage.ai_messages)} />
        <Stat label="Tokens" value={formatNumber(usage.total_tokens)} />
        <Stat label="API requests" value={formatNumber(usage.api_requests)} />
        <Stat label="Storage" value={formatBytes(usage.storage_bytes)} />
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
      </div>

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
