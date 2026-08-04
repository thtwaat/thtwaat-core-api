"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { agentsApi, conversationsApi, domainsApi, usageApi } from "@/lib/services";
import { formatBytes, formatDate, formatNumber } from "@/lib/utils";
import { PageHeader, Stat } from "@/components/ui/misc";
import { Badge, Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/misc";
import { Progress } from "@/components/ui/misc";

export default function DashboardPage() {
  const usage = useQuery({ queryKey: ["usage-current"], queryFn: usageApi.current });
  const agents = useQuery({ queryKey: ["agents"], queryFn: agentsApi.list });
  const conversations = useQuery({
    queryKey: ["conversations"],
    queryFn: () => conversationsApi.list()
  });
  const domains = useQuery({ queryKey: ["domains"], queryFn: domainsApi.list });

  const u = usage.data?.usage || {};
  const progress = usage.data?.progress || [];

  return (
    <div>
      <PageHeader
        title="Overview"
        description="Usage, agents, conversations, and recent activity in one place."
        action={
          <Link href="/app/agents/new">
            <Button>Create agent</Button>
          </Link>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Plan" value={(usage.data?.plan || "—").toString()} hint="Current subscription tier" />
        <Stat label="Messages" value={formatNumber(u.ai_messages)} hint="This billing period" />
        <Stat label="Tokens" value={formatNumber(u.total_tokens)} />
        <Stat label="Storage" value={formatBytes(u.storage_bytes)} />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader title="Quota" description="Live limits from /usage/current" />
          <div className="space-y-4">
            {progress.length === 0 && <EmptyState title="No quota data yet" description="Usage appears after first AI activity." />}
            {progress.slice(0, 6).map((item) => (
              <div key={item.dimension}>
                <div className="mb-1 flex justify-between text-sm">
                  <span className="font-medium capitalize">{item.dimension.replaceAll("_", " ")}</span>
                  <span className="text-muted">
                    {formatNumber(item.current)} / {formatNumber(item.limit)}
                  </span>
                </div>
                <Progress value={item.percent} />
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader title="Quick actions" />
          <div className="grid gap-2">
            <Link href="/app/inbox"><Button variant="secondary" className="w-full justify-start">Open inbox</Button></Link>
            <Link href="/app/agents"><Button variant="secondary" className="w-full justify-start">Manage agents</Button></Link>
            <Link href="/app/knowledge"><Button variant="secondary" className="w-full justify-start">Upload knowledge</Button></Link>
            <Link href="/app/domains"><Button variant="secondary" className="w-full justify-start">Add domain</Button></Link>
            <Link href="/app/publish"><Button variant="secondary" className="w-full justify-start">Publish checklist</Button></Link>
            <Link href="/app/billing"><Button className="w-full justify-start">Upgrade plan</Button></Link>
          </div>
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="Recent conversations"
            action={
              <Link href="/app/inbox">
                <Badge tone="brand">{conversations.data?.length || 0}</Badge>
              </Link>
            }
          />
          <div className="space-y-3">
            {(conversations.data || []).slice(0, 5).map((c) => (
              <Link
                key={c.id}
                href={`/app/inbox?id=${encodeURIComponent(c.id)}`}
                className="flex items-center justify-between rounded-xl border border-line px-3 py-2.5 transition hover:bg-canvas"
              >
                <div>
                  <p className="text-sm font-medium">{c.title || c.id.slice(0, 8)}</p>
                  <p className="text-xs text-muted">{formatDate(c.created_at)}</p>
                </div>
                <Badge>{c.message_count ?? 0} msgs</Badge>
              </Link>
            ))}
            {!conversations.data?.length && <EmptyState title="No conversations yet" />}
          </div>
        </Card>

        <Card>
          <CardHeader title="Recent activity" description="Agents and domains snapshot" />
          <div className="space-y-3">
            {(agents.data || []).slice(0, 3).map((a) => (
              <div key={a.id} className="flex items-center justify-between rounded-xl border border-line px-3 py-2.5">
                <div>
                  <p className="text-sm font-medium">{a.name}</p>
                  <p className="text-xs text-muted">Updated {formatDate(a.updated_at)}</p>
                </div>
                <Badge tone={a.status === "PUBLISHED" ? "success" : "neutral"}>{a.status}</Badge>
              </div>
            ))}
            {(domains.data || []).slice(0, 2).map((d) => (
              <div key={d.id} className="flex items-center justify-between rounded-xl border border-line px-3 py-2.5">
                <div>
                  <p className="text-sm font-medium">{d.hostname}</p>
                  <p className="text-xs text-muted">SSL {d.ssl_status}</p>
                </div>
                <Badge tone={d.status === "LIVE" || d.status === "VERIFIED" ? "success" : "warn"}>{d.status}</Badge>
              </div>
            ))}
            {!agents.data?.length && !domains.data?.length && <EmptyState title="No activity yet" />}
          </div>
        </Card>
      </div>
    </div>
  );
}
