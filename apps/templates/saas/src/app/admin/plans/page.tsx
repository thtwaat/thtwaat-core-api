"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { billingApi } from "@/lib/services";
import type { Plan } from "@/lib/types";
import { PageHeader, EmptyState } from "@/components/ui/misc";
import { Badge, Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";

const LIMIT_KEYS = [
  "max_users",
  "max_apps",
  "max_agents",
  "max_messages",
  "max_tokens",
  "max_storage",
  "max_domains",
  "max_team_members",
  "max_api_keys",
  "max_templates"
] as const;

export default function AdminPlansPage() {
  const [editing, setEditing] = useState<Plan | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const plansQ = useQuery({
    queryKey: ["admin-plans"],
    queryFn: () => billingApi.plansAdmin()
  });

  const plans = plansQ.data || [];

  function startEdit(plan: Plan) {
    setEditing(plan);
    const next: Record<string, string> = {};
    for (const key of LIMIT_KEYS) {
      const val = plan[key as keyof Plan];
      next[key] = val == null ? "" : String(val);
    }
    setDraft(next);
  }

  async function save() {
    if (!editing) return;
    setBusy(true);
    try {
      const body: Record<string, number> = {};
      for (const key of LIMIT_KEYS) {
        if (draft[key] === "" || draft[key] == null) continue;
        const n = Number(draft[key]);
        if (!Number.isFinite(n) || n < 0) {
          toast.error(`Invalid ${key}`);
          setBusy(false);
          return;
        }
        body[key] = n;
      }
      await billingApi.updatePlan(editing.id, body);
      toast.success(`${editing.name} limits updated`);
      setEditing(null);
      await plansQ.refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Update failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Plans"
        description="Editable Free / Starter / Pro / Enterprise limits via existing payments plans API."
      />

      {plansQ.isError && (
        <EmptyState title="Failed to load plans" description={(plansQ.error as Error).message} />
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {plans.map((plan) => (
          <Card key={plan.id} className="space-y-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <h2 className="font-semibold text-ink">{plan.name}</h2>
                <p className="text-sm text-muted">{plan.description || "No description"}</p>
              </div>
              <Badge tone={plan.is_active === false ? "danger" : "success"}>
                {plan.is_active === false ? "inactive" : "active"}
              </Badge>
            </div>
            <dl className="grid grid-cols-2 gap-2 text-xs text-muted">
              <div>Agents: {plan.max_agents ?? "—"}</div>
              <div>Messages: {plan.max_messages ?? "—"}</div>
              <div>Tokens: {plan.max_tokens ?? "—"}</div>
              <div>Users: {plan.max_users ?? "—"}</div>
            </dl>
            <Button size="sm" variant="secondary" onClick={() => startEdit(plan)}>
              Edit limits
            </Button>
          </Card>
        ))}
      </div>

      {!plans.length && !plansQ.isLoading && (
        <EmptyState
          title="No plans found"
          description="Seed Free, Starter, Pro, and Enterprise via payments plans."
        />
      )}

      {editing && (
        <Card className="space-y-4">
          <h2 className="font-semibold text-ink">Edit limits — {editing.name}</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {LIMIT_KEYS.map((key) => (
              <div key={key}>
                <Label htmlFor={key}>{key}</Label>
                <Input
                  id={key}
                  inputMode="numeric"
                  value={draft[key] || ""}
                  onChange={(e) => setDraft((prev) => ({ ...prev, [key]: e.target.value }))}
                />
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            <Button onClick={() => void save()} disabled={busy}>
              Save
            </Button>
            <Button variant="ghost" onClick={() => setEditing(null)}>
              Cancel
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
