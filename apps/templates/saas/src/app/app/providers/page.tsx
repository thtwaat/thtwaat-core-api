"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Cpu, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { aiProvidersApi } from "@/lib/services";
import { useAuth } from "@/lib/auth";
import { canManageTemplates, canViewProviders } from "@/lib/permissions";
import {
  mergeProviderRows,
  modelDisplayName,
  providerHealthLabel,
  providerHealthTone
} from "@/lib/provider-status";
import { PageHeader, EmptyState, Stat } from "@/components/ui/misc";
import { Badge, Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function ProvidersPage() {
  const { user } = useAuth();
  const canView = canViewProviders(user?.role);
  const canManage = canManageTemplates(user?.role);
  const qc = useQueryClient();
  const [expanded, setExpanded] = useState<string | null>(null);

  const listQ = useQuery({
    queryKey: ["ai-providers"],
    queryFn: aiProvidersApi.list,
    enabled: canView
  });
  const healthQ = useQuery({
    queryKey: ["ai-providers-health"],
    queryFn: aiProvidersApi.health,
    enabled: canView,
    refetchInterval: 15_000
  });
  const detailQ = useQuery({
    queryKey: ["ai-providers-health-detail"],
    queryFn: aiProvidersApi.healthDetail,
    enabled: canView,
    refetchInterval: 15_000
  });
  const dashQ = useQuery({
    queryKey: ["ai-gateway-dashboard"],
    queryFn: aiProvidersApi.dashboard,
    enabled: canView,
    refetchInterval: 30_000
  });
  const settingsQ = useQuery({
    queryKey: ["ai-workspace-settings"],
    queryFn: aiProvidersApi.workspaceSettings,
    enabled: canView
  });
  const modelsQ = useQuery({
    queryKey: ["ai-provider-models", expanded],
    queryFn: () => aiProvidersApi.models(expanded!),
    enabled: canView && Boolean(expanded)
  });

  const [defaultProvider, setDefaultProvider] = useState("");
  const [tokenLimit, setTokenLimit] = useState("");

  const saveMut = useMutation({
    mutationFn: () =>
      aiProvidersApi.updateWorkspaceSettings({
        default_provider: defaultProvider || settingsQ.data?.default_provider,
        monthly_token_limit: tokenLimit ? Number(tokenLimit) : settingsQ.data?.monthly_token_limit,
        allowed_providers: settingsQ.data?.allowed_providers
      }),
    onSuccess: () => {
      toast.success("Workspace gateway settings saved");
      qc.invalidateQueries({ queryKey: ["ai-workspace-settings"] });
      qc.invalidateQueries({ queryKey: ["ai-providers"] });
      qc.invalidateQueries({ queryKey: ["ai-gateway-dashboard"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const rows = useMemo(
    () =>
      mergeProviderRows(
        listQ.data?.providers || [],
        healthQ.data || {},
        listQ.data?.default
      ),
    [listQ.data, healthQ.data]
  );

  const configured = rows.filter((r) => r.status === "configured").length;
  const errors = rows.filter((r) => r.status === "error").length;
  const dash = dashQ.data;
  const detail = detailQ.data;

  async function refreshAll() {
    await Promise.all([
      listQ.refetch(),
      healthQ.refetch(),
      detailQ.refetch(),
      dashQ.refetch(),
      settingsQ.refetch()
    ]);
    if (expanded) await modelsQ.refetch();
  }

  if (!canView) {
    return (
      <div className="space-y-6">
        <PageHeader title="AI Providers" description="Gateway provider configuration and health." />
        <EmptyState
          title="Access restricted"
          description="Provider status is available to company owners, admins, and developers."
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI Gateway"
        description="Live provider health, latency, cost, and workspace routing for the enterprise AI gateway."
        action={
          <Button
            variant="secondary"
            onClick={() => void refreshAll()}
            disabled={listQ.isFetching || healthQ.isFetching}
          >
            <RefreshCw
              size={16}
              className={listQ.isFetching || healthQ.isFetching ? "animate-spin" : ""}
            />
            Refresh
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
        <Stat label="Providers" value={String(rows.length || "—")} />
        <Stat label="Configured" value={String(configured)} />
        <Stat label="Errors" value={String(errors)} />
        <Stat
          label="Success rate"
          value={dash?.success_rate != null ? `${dash.success_rate}%` : "—"}
        />
        <Stat
          label="Avg latency"
          value={dash?.avg_latency_ms != null ? `${Math.round(dash.avg_latency_ms)} ms` : "—"}
        />
        <Stat
          label="Cost (30d)"
          value={
            dash
              ? `${dash.currency} ${Number(dash.cost || 0).toFixed(4)}`
              : "—"
          }
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Requests (30d)" value={String(dash?.requests ?? "—")} />
        <Stat label="Tokens (30d)" value={String(dash?.tokens ?? "—")} />
        <Stat
          label="Failed"
          value={String(dash?.failed ?? "—")}
        />
      </div>

      {(listQ.isError || healthQ.isError) && (
        <p className="text-sm text-red-600">
          Could not load providers:{" "}
          {(listQ.error as Error)?.message ||
            (healthQ.error as Error)?.message ||
            "Unknown error"}
        </p>
      )}

      <Card>
        <CardHeader
          title="Live provider health"
          description={
            listQ.data?.default
              ? `Default: ${listQ.data.default} · policy: ${listQ.data.routing_policy || "default"}`
              : "Status from /api/v1/ai/health (refreshes every 15s)"
          }
        />

        {listQ.isLoading || healthQ.isLoading ? (
          <p className="text-sm text-muted">Loading providers…</p>
        ) : !rows.length ? (
          <EmptyState
            title="No providers listed"
            description="The AI gateway returned an empty provider list."
          />
        ) : (
          <ul className="divide-y divide-line">
            {rows.map((row) => {
              const open = expanded === row.name;
              const tone = providerHealthTone(row.status);
              const meta = detail?.providers?.[row.name];
              const caps = meta?.capabilities || listQ.data?.capabilities?.[row.name] || [];
              return (
                <li key={row.name} className="py-3">
                  <button
                    type="button"
                    className="flex w-full items-center gap-3 text-left"
                    onClick={() => setExpanded(open ? null : row.name)}
                    aria-expanded={open}
                  >
                    <span className="text-muted">
                      {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                    </span>
                    <span
                      className={`h-2.5 w-2.5 rounded-full ${
                        tone === "success"
                          ? "bg-emerald-500"
                          : tone === "warn"
                            ? "bg-amber-400"
                            : tone === "danger"
                              ? "bg-rose-500"
                              : "bg-slate-300"
                      }`}
                      title={providerHealthLabel(row.status)}
                    />
                    <Cpu size={16} className="text-brand" />
                    <span className="flex-1 font-medium text-ink">
                      {row.name}
                      {row.isDefault && (
                        <span className="ml-2 text-xs font-normal text-muted">(default)</span>
                      )}
                    </span>
                    <span className="hidden text-xs text-muted sm:inline">
                      {meta?.avg_latency_ms != null
                        ? `${Math.round(meta.avg_latency_ms)} ms avg`
                        : "— ms"}
                    </span>
                    <Badge tone={tone}>{providerHealthLabel(row.status)}</Badge>
                  </button>

                  {open && (
                    <div className="mt-3 ml-9 space-y-3 rounded-xl border border-line bg-canvas p-3">
                      <p className="text-xs text-muted">
                        Capabilities: {caps.length ? caps.join(", ") : "chat"}
                      </p>
                      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">
                        Models
                      </p>
                      {modelsQ.isLoading && <p className="text-sm text-muted">Loading models…</p>}
                      {modelsQ.isError && (
                        <p className="text-sm text-red-600">
                          {(modelsQ.error as Error)?.message || "Failed to load models"}
                        </p>
                      )}
                      {modelsQ.data && (
                        <ul className="max-h-48 space-y-1 overflow-y-auto text-sm text-ink">
                          {(modelsQ.data.models || []).length === 0 ? (
                            <li className="text-muted">No models reported for this provider.</li>
                          ) : (
                            (modelsQ.data.models || []).map((m, i) => (
                              <li key={`${row.name}-${i}`} className="font-mono text-xs">
                                {modelDisplayName(m as string | { id?: string; name?: string })}
                              </li>
                            ))
                          )}
                        </ul>
                      )}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      <Card>
        <CardHeader
          title="Cost & latency by provider"
          description="Last 30 days from AI gateway request logs."
        />
        {(dash?.providers || []).length === 0 ? (
          <p className="text-sm text-muted">No usage yet in this window.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th className="pb-2 pr-4">Provider</th>
                  <th className="pb-2 pr-4">Requests</th>
                  <th className="pb-2 pr-4">Tokens</th>
                  <th className="pb-2 pr-4">Cost</th>
                  <th className="pb-2 pr-4">Error %</th>
                  <th className="pb-2">Latency</th>
                </tr>
              </thead>
              <tbody>
                {(dash?.providers || []).map((p) => (
                  <tr key={p.provider} className="border-t border-line">
                    <td className="py-2 pr-4 font-medium text-ink">{p.provider}</td>
                    <td className="py-2 pr-4">{p.requests}</td>
                    <td className="py-2 pr-4">{p.tokens}</td>
                    <td className="py-2 pr-4">{p.cost.toFixed(4)}</td>
                    <td className="py-2 pr-4">{p.error_rate}%</td>
                    <td className="py-2">{Math.round(p.avg_latency_ms)} ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card className="space-y-4">
        <CardHeader
          title="Workspace settings"
          description="Default provider, allowed providers, and monthly usage limits."
        />
        {settingsQ.isLoading ? (
          <p className="text-sm text-muted">Loading settings…</p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="space-y-1.5 text-sm">
              <span className="text-xs font-medium uppercase tracking-wide text-muted">
                Default provider
              </span>
              <select
                className="h-11 w-full rounded-xl border border-line bg-panel px-3 text-sm"
                value={defaultProvider || settingsQ.data?.default_provider || ""}
                onChange={(e) => setDefaultProvider(e.target.value)}
                disabled={!canManage}
              >
                {(settingsQ.data?.allowed_providers || listQ.data?.providers || []).map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1.5 text-sm">
              <span className="text-xs font-medium uppercase tracking-wide text-muted">
                Monthly token limit
              </span>
              <Input
                type="number"
                min={0}
                placeholder={String(settingsQ.data?.monthly_token_limit ?? "unlimited")}
                value={tokenLimit}
                onChange={(e) => setTokenLimit(e.target.value)}
                disabled={!canManage}
              />
            </label>
            <p className="sm:col-span-2 text-xs text-muted">
              Allowed: {(settingsQ.data?.allowed_providers || []).join(", ") || "all"} · Retry{" "}
              {settingsQ.data?.retry_max_attempts ?? 2} · Timeout{" "}
              {settingsQ.data?.timeout_seconds ?? 60}s · Policy{" "}
              {settingsQ.data?.routing_policy || "default"}
            </p>
            {canManage ? (
              <Button
                onClick={() => saveMut.mutate()}
                disabled={saveMut.isPending}
                className="sm:col-span-2 sm:w-fit"
              >
                Save workspace defaults
              </Button>
            ) : null}
          </div>
        )}
      </Card>
    </div>
  );
}
