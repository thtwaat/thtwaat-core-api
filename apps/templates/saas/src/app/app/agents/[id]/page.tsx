"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { agentsApi } from "@/lib/services";
import { site } from "@/lib/config";
import { PageHeader } from "@/components/ui/misc";
import { Badge, Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Label, Textarea } from "@/components/ui/input";

export default function AgentDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const qc = useQueryClient();
  const agent = useQuery({ queryKey: ["agent", id], queryFn: () => agentsApi.get(id) });
  const embed = useQuery({
    queryKey: ["embed", id],
    queryFn: () => agentsApi.embed(id),
    enabled: Boolean(agent.data?.status === "PUBLISHED")
  });
  const [apiKeyName, setApiKeyName] = useState("Production");
  const [createdKey, setCreatedKey] = useState<string | null>(null);

  const publish = useMutation({
    mutationFn: () => agentsApi.publish(id),
    onSuccess: (data) => {
      toast.success("Published");
      if (data.api_key) setCreatedKey(data.api_key);
      qc.invalidateQueries({ queryKey: ["agent", id] });
      qc.invalidateQueries({ queryKey: ["agents"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const unpublish = useMutation({
    mutationFn: () => agentsApi.unpublish(id),
    onSuccess: () => {
      toast.success("Unpublished");
      qc.invalidateQueries({ queryKey: ["agent", id] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const createKey = useMutation({
    mutationFn: () => agentsApi.createApiKey(id, apiKeyName),
    onSuccess: (data) => {
      const key = data.api_key || data.key;
      if (key) setCreatedKey(key);
      toast.success("API key created — copy it now");
    },
    onError: (e: Error) => toast.error(e.message)
  });

  if (agent.isLoading) return <p className="text-sm text-muted">Loading agent…</p>;
  if (!agent.data) return <p className="text-sm text-muted">Agent not found.</p>;

  const a = agent.data;
  const embedScript =
    embed.data?.script ||
    embed.data?.embed_script ||
    `<script src="${site.apiUrl}/widget.js" data-api-key="YOUR_KEY" async></script>`;

  return (
    <div className="space-y-6">
      <PageHeader
        title={a.name}
        description={a.description || "Agent details, publish, widget, and API keys"}
        action={<Badge tone={a.status === "PUBLISHED" ? "success" : "neutral"}>{a.status}</Badge>}
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Configuration" />
          <div className="space-y-3 text-sm">
            <div>
              <Label>System prompt</Label>
              <Textarea readOnly value={a.system_prompt_template} />
            </div>
            <p className="text-muted">Temperature: {a.temperature}</p>
            <p className="text-muted">Widget ID: {a.widget_id || "—"}</p>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Link
              href={`/app/agents/${id}/playground`}
              className="inline-flex items-center justify-center rounded-xl border border-line bg-white px-3 py-2 text-sm font-medium hover:bg-slate-50"
            >
              Open playground
            </Link>
            {a.status === "PUBLISHED" ? (
              <Button variant="secondary" onClick={() => unpublish.mutate()}>Unpublish</Button>
            ) : (
              <Button onClick={() => publish.mutate()}>Publish</Button>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader title="API keys" description="Create agent keys for public chat / widget" />
          <div className="flex gap-2">
            <Input value={apiKeyName} onChange={(e) => setApiKeyName(e.target.value)} />
            <Button onClick={() => createKey.mutate()}>Create</Button>
          </div>
          {createdKey && (
            <div className="mt-4 rounded-xl bg-brand-soft p-3 text-sm">
              <p className="font-semibold text-brand-dark">Copy this key now</p>
              <code className="mt-2 block break-all text-xs">{createdKey}</code>
            </div>
          )}
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Widget / Embed" />
          <Label>Embed snippet</Label>
          <Textarea readOnly className="font-mono text-xs" value={embedScript} />
          <p className="mt-3 text-sm text-muted">
            Public chat: <code>{site.apiUrl}/public/v1/chat</code>
          </p>
        </Card>
      </div>
    </div>
  );
}
