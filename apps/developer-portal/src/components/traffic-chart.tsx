"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

const traffic = [
  { day: "Mon", calls: 1200 },
  { day: "Tue", calls: 1800 },
  { day: "Wed", calls: 1600 },
  { day: "Thu", calls: 2400 },
  { day: "Fri", calls: 2800 },
  { day: "Sat", calls: 2100 },
  { day: "Sun", calls: 1900 }
];

export function TrafficChart() {
  return (
    <div className="mt-3 h-48">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={traffic}>
          <defs>
            <linearGradient id="calls" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#0f766e" stopOpacity={0.35} />
              <stop offset="95%" stopColor="#0f766e" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--line))" />
          <XAxis dataKey="day" tick={{ fill: "rgb(var(--muted))", fontSize: 12 }} />
          <YAxis tick={{ fill: "rgb(var(--muted))", fontSize: 12 }} />
          <Tooltip />
          <Area type="monotone" dataKey="calls" stroke="#0f766e" fill="url(#calls)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
