"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { agentsApi, type AgentDeleteImpact } from "@/lib/services";
import { formatDate } from "@/lib/utils";
import { PageHeader, EmptyState } from "@/components/ui/misc";
import { Badge, Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { canDeleteAgents } from "@/lib/permissions";
import { ApiError } from "@/lib/api";
import type { Agent } from "@/lib/types";

type DeleteStep = "closed" | "unpublish" | "confirm";

export default function AgentsPage() {
  const { user } = useAuth();
  const canDelete = canDeleteAgents(user?.role);
  const qc = useQueryClient();
  const agents = useQuery({ queryKey: ["agents"], queryFn: agentsApi.list });

  const [deleteTarget, setDeleteTarget] = useState<Agent | null>(null);
  const [deleteStep, setDeleteStep] = useState<DeleteStep>("closed");
  const [mustUnpublish, setMustUnpublish] = useState(false);
  const [keepConversations, setKeepConversations] = useState(true);
  const [keepKnowledge, setKeepKnowledge] = useState(true);
  const [impact, setImpact] = useState<AgentDeleteImpact | null>(null);
  const [impactLoading, setImpactLoading] = useState(false);

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

  const clone = useMutation({
    mutationFn: (id: string) => agentsApi.clone(id),
    onSuccess: () => {
      toast.success("Agent duplicated");
      qc.invalidateQueries({ queryKey: ["agents"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const remove = useMutation({
    mutationFn: (payload: {
      id: string;
      keep_conversations: boolean;
      keep_knowledge: boolean;
      confirm_unpublish: boolean;
    }) =>
      agentsApi.delete(payload.id, {
        keep_conversations: payload.keep_conversations,
        keep_knowledge: payload.keep_knowledge,
        confirm_unpublish: payload.confirm_unpublish
      }),
    onSuccess: (data) => {
      toast.success(data.message || "Agent deleted");
      closeDeleteDialog();
      qc.invalidateQueries({ queryKey: ["agents"] });
    },
    onError: (e: Error) => {
      if (e instanceof ApiError && e.status === 409) {
        setDeleteStep("unpublish");
        return;
      }
      toast.error(e.message);
    }
  });

  function closeDeleteDialog() {
    setDeleteTarget(null);
    setDeleteStep("closed");
    setMustUnpublish(false);
    setImpact(null);
    setKeepConversations(true);
    setKeepKnowledge(true);
  }

  async function openDelete(agent: Agent) {
    if (!canDelete) return;
    setDeleteTarget(agent);
    setKeepConversations(true);
    setKeepKnowledge(true);
    setImpactLoading(true);
    try {
      const data = await agentsApi.deleteImpact(agent.id);
      setImpact(data);
      const published = data.published || agent.status === "PUBLISHED";
      setMustUnpublish(published);
      if (published) {
        setDeleteStep("unpublish");
      } else {
        setDeleteStep("confirm");
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to load delete impact");
      setDeleteTarget(null);
    } finally {
      setImpactLoading(false);
    }
  }

  function submitDelete() {
    if (!deleteTarget) return;
    remove.mutate({
      id: deleteTarget.id,
      keep_conversations: keepConversations,
      keep_knowledge: keepKnowledge,
      confirm_unpublish: mustUnpublish
    });
  }

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
              <Link href={`/app/agents/${agent.id}`}>
                <Button variant="secondary" size="sm">Edit</Button>
              </Link>
              <Button size="sm" variant="secondary" onClick={() => clone.mutate(agent.id)} disabled={clone.isPending}>
                Duplicate
              </Button>
              {agent.status === "PUBLISHED" ? (
                <Button size="sm" variant="secondary" onClick={() => unpublish.mutate(agent.id)}>
                  Unpublish
                </Button>
              ) : (
                <Button size="sm" onClick={() => publish.mutate(agent.id)}>
                  Publish
                </Button>
              )}
              <Link href={`/app/analytics?agent=${agent.id}`}>
                <Button variant="secondary" size="sm">Analytics</Button>
              </Link>
              {canDelete && (
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => openDelete(agent)}
                  disabled={impactLoading && deleteTarget?.id === agent.id}
                >
                  Delete
                </Button>
              )}
            </div>
          </Card>
        ))}
      </div>

      {deleteStep === "unpublish" && deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-xl border border-border bg-background p-5 shadow-lg">
            <h2 className="text-lg font-semibold">Delete Agent?</h2>
            <p className="mt-2 text-sm text-muted">
              This agent is currently published.
              <br />
              It will be unpublished before deletion.
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <Button variant="secondary" onClick={closeDeleteDialog}>
                Cancel
              </Button>
              <Button onClick={() => setDeleteStep("confirm")}>Unpublish &amp; Delete</Button>
            </div>
          </div>
        </div>
      )}

      {deleteStep === "confirm" && deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg rounded-xl border border-border bg-background p-5 shadow-lg">
            <h2 className="text-lg font-semibold">Delete Agent?</h2>
            <p className="mt-2 text-sm text-muted">
              This action cannot be immediately undone after the retention period.
            </p>

            <div className="mt-4 space-y-2 text-sm">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={keepConversations}
                  onChange={(e) => setKeepConversations(e.target.checked)}
                />
                Keep conversations
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={keepKnowledge}
                  onChange={(e) => setKeepKnowledge(e.target.checked)}
                />
                Keep knowledge base
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={!keepConversations}
                  onChange={(e) => setKeepConversations(!e.target.checked)}
                />
                Delete conversations
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={!keepKnowledge}
                  onChange={(e) => setKeepKnowledge(!e.target.checked)}
                />
                Delete linked knowledge
              </label>
            </div>

            {impact && (
              <div className="mt-4 rounded-lg border border-border bg-muted/30 p-3 text-sm">
                <p className="font-medium">Impact</p>
                <ul className="mt-2 grid grid-cols-2 gap-1 text-muted">
                  <li>Widget: {impact.widget ? "yes" : "no"}</li>
                  <li>API Keys: {impact.api_keys}</li>
                  <li>Playground: {impact.playground ? "yes" : "no"}</li>
                  <li>Draft prompts: {impact.draft_prompts}</li>
                  <li>Scheduled jobs: {impact.scheduled_jobs}</li>
                  <li>Conversations: {impact.conversations}</li>
                  <li>Knowledge links: {impact.knowledge_attachments}</li>
                  <li>Retention: {impact.retention_days} days</li>
                </ul>
              </div>
            )}

            <div className="mt-5 flex justify-end gap-2">
              <Button variant="secondary" onClick={closeDeleteDialog} disabled={remove.isPending}>
                Cancel
              </Button>
              <Button
                onClick={submitDelete}
                disabled={remove.isPending}
              >
                {remove.isPending ? "Deleting…" : "Delete"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
