"use client";

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
import { Card, CardHeader } from "@/components/ui/card";

type Point = { period: string; revenue?: number; requests?: number; tokens?: number };

export function AdminCharts({
  revenueChart,
  aiChart
}: {
  revenueChart: Point[];
  aiChart: Point[];
}) {
  return (
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
  );
}
