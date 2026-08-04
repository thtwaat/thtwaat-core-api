"use client";

import { useQuery } from "@tanstack/react-query";
import { platformAdminApi } from "@/lib/services";
import { PageHeader, EmptyState, Stat } from "@/components/ui/misc";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function AdminOperationsPage() {
  const jobsQ = useQuery({ queryKey: ["admin-jobs"], queryFn: () => platformAdminApi.jobs(50) });
  const healthQ = useQuery({ queryKey: ["admin-health"], queryFn: platformAdminApi.health });

  const active = ((jobsQ.data?.active as Array<Record<string, unknown>>) || []);
  const dead = ((jobsQ.data?.dead_letter as Array<Record<string, unknown>>) || []);
  const stats = (jobsQ.data?.stats as Record<string, unknown>) || {};
  const queue = healthQ.data?.queue || {};
  const email = healthQ.data?.email_queue || {};

  return (
    <div className="space-y-6">
      <PageHeader
        title="Operations"
        description="Background jobs, webhook/email queue depth, and worker health."
        action={
          <Button
            variant="secondary"
            onClick={() => {
              void jobsQ.refetch();
              void healthQ.refetch();
            }}
          >
            Refresh
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Queued" value={String(stats.queued ?? queue.queued ?? "—")} />
        <Stat label="Active jobs" value={String(active.length)} />
        <Stat label="Dead letter" value={String(dead.length)} />
        <Stat label="Email queue" value={String(email.depth ?? "—")} hint={String(email.status || "")} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="space-y-3">
          <h2 className="text-sm font-semibold text-ink">Active / queued jobs</h2>
          <ul className="max-h-80 space-y-2 overflow-auto text-sm">
            {active.map((job, idx) => (
              <li key={idx} className="border-b border-line/50 py-1 font-mono text-xs">
                {JSON.stringify(job)}
              </li>
            ))}
            {!active.length && <li className="text-muted">No active jobs.</li>}
          </ul>
        </Card>
        <Card className="space-y-3">
          <h2 className="text-sm font-semibold text-ink">Dead letter</h2>
          <ul className="max-h-80 space-y-2 overflow-auto text-sm">
            {dead.map((job, idx) => (
              <li key={idx} className="border-b border-line/50 py-1 font-mono text-xs text-danger">
                {JSON.stringify(job)}
              </li>
            ))}
            {!dead.length && <li className="text-muted">Dead letter empty.</li>}
          </ul>
        </Card>
      </div>

      {jobsQ.isError && (
        <EmptyState title="Could not load jobs" description={(jobsQ.error as Error).message} />
      )}
    </div>
  );
}
