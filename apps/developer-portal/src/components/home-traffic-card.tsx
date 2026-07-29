"use client";

import dynamic from "next/dynamic";
import { Card } from "@/components/ui/card";

const TrafficChart = dynamic(
  () => import("@/components/traffic-chart").then((m) => m.TrafficChart),
  {
    ssr: false,
    loading: () => <div className="mt-3 h-48 animate-pulse rounded-xl bg-canvas" />
  }
);

export function HomeTrafficCard() {
  return (
    <Card className="relative z-10">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">Sample API traffic</p>
      <TrafficChart />
    </Card>
  );
}
