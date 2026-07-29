"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { agentsApi } from "@/lib/services";
import { formatDate } from "@/lib/utils";
import { PageHeader, EmptyState } from "@/components/ui/misc";
import { Badge, Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function AgentsPage() {
  const qc = useQueryClient();
  const agents = useQuery({ queryKey: ["agents"], queryFn: agentsApi.list });

  const publish = useMutation({
    mutationFn: (id: string) => agentsApi.publish(id),
    onSuccess: (data) => {
      toast.success("Agent published");
      if (data.api_key) toast.message(`API key (copy now): ${data.api_key}`);
      qc.invalidateQueries({ queryKey: ["agents"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const unpublish = useMutation({
    mutationFn: (id: string) => agentsApi.unpublish(id),
    onSuccess: () => {
      toast.success("Agent unpublished");
      qc.invalidateQueries({ queryKey: ["agents"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  return (
    <div>
      <PageHeader
        title="Agents"
        description="Create, publish, embed, and manage API keys."
        action={
          <Link href="/app/agents/new">
            <Button>New agent</Button>
          </Link>
        }
      />

      {!agents.data?.length && !agents.isLoading && (
        <EmptyState title="No agents yet" description="Create your first agent to start publishing." />
      )}

      <div className="grid gap-4">
        {(agents.data || []).map((agent) => (
          <Card key={agent.id} className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="font-semibold">{agent.name}</h3>
                <Badge tone={agent.status === "PUBLISHED" ? "success" : "neutral"}>{agent.status}</Badge>
              </div>
              <p className="mt-1 text-sm text-muted">{agent.description || "No description"}</p>
              <p className="mt-2 text-xs text-muted">
                Updated {formatDate(agent.updated_at)}
                {agent.widget_id ? ` · widget ${agent.widget_id}` : ""}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link href={`/app/agents/${agent.id}`}>
                <Button variant="secondary" size="sm">Open</Button>
              </Link>
              {agent.status === "PUBLISHED" ? (
                <Button size="sm" variant="secondary" onClick={() => unpublish.mutate(agent.id)}>
                  Unpublish
                </Button>
              ) : (
                <Button size="sm" onClick={() => publish.mutate(agent.id)}>
                  Publish
                </Button>
              )}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
