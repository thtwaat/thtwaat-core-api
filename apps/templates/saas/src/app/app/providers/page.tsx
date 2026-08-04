"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Cpu, RefreshCw } from "lucide-react";
import { aiProvidersApi } from "@/lib/services";
import { useAuth } from "@/lib/auth";
import { canViewProviders } from "@/lib/permissions";
import {
  mergeProviderRows,
  modelDisplayName,
  providerHealthLabel,
  providerHealthTone
} from "@/lib/provider-status";
import { PageHeader, EmptyState, Stat } from "@/components/ui/misc";
import { Badge, Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function ProvidersPage() {
  const { user } = useAuth();
  const canView = canViewProviders(user?.role);
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
    refetchInterval: 60_000
  });
  const modelsQ = useQuery({
    queryKey: ["ai-provider-models", expanded],
    queryFn: () => aiProvidersApi.models(expanded!),
    enabled: canView && Boolean(expanded)
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

  async function refreshAll() {
    await Promise.all([listQ.refetch(), healthQ.refetch()]);
    if (expanded) await modelsQ.refetch();
  }

  if (!canView) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="AI Providers"
          description="Gateway provider configuration and health."
        />
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
        title="AI Providers"
        description="Read-only status of platform AI gateway providers. API keys and routing are configured via deployment environment (OPENAI_API_KEY, OLLAMA_URL, INFERENCE_*)."
        action={
          <Button
            variant="secondary"
            onClick={() => void refreshAll()}
            disabled={listQ.isFetching || healthQ.isFetching}
          >
            <RefreshCw size={16} className={listQ.isFetching || healthQ.isFetching ? "animate-spin" : ""} />
            Refresh
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Providers" value={String(rows.length || "—")} />
        <Stat label="Configured" value={String(configured)} />
        <Stat label="Errors" value={String(errors)} />
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
          title="Gateway providers"
          description={
            listQ.data?.default
              ? `Default: ${listQ.data.default}`
              : "Status from /api/v1/ai/health"
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
                    <Cpu size={16} className="text-brand" />
                    <span className="flex-1 font-medium text-ink">
                      {row.name}
                      {row.isDefault && (
                        <span className="ml-2 text-xs font-normal text-muted">(default)</span>
                      )}
                    </span>
                    <Badge tone={tone}>{providerHealthLabel(row.status)}</Badge>
                  </button>

                  {open && (
                    <div className="mt-3 ml-9 rounded-xl border border-line bg-canvas p-3">
                      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">
                        Models
                      </p>
                      {modelsQ.isLoading && (
                        <p className="text-sm text-muted">Loading models…</p>
                      )}
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
        <CardHeader title="Configuration notes" />
        <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
          <li>
            Platform keys live in deployment env (<code className="text-ink">OPENAI_API_KEY</code>,{" "}
            <code className="text-ink">ANTHROPIC_API_KEY</code>,{" "}
            <code className="text-ink">GEMINI_API_KEY</code>,{" "}
            <code className="text-ink">OPENROUTER_API_KEY</code>,{" "}
            <code className="text-ink">OLLAMA_URL</code>).
          </li>
          <li>
            Inference routing uses <code className="text-ink">INFERENCE_ROUTING_POLICY</code> and
            related <code className="text-ink">INFERENCE_*</code> settings — not editable in this UI.
          </li>
          <li>
            Tenant API keys under Settings are for calling THTWAAT APIs, not BYOK provider credentials.
          </li>
        </ul>
      </Card>
    </div>
  );
}
