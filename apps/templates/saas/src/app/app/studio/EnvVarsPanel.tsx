"use client";

// THTWAAT Deploy — Environment Variables (Phase 4C UI over the Phase 4A/4B
// backend). Scoped to one static site (the same `siteId` StaticDeployPanel
// already tracks) — this is that site's "settings" surface; there is no
// separate project/settings route for static sites to nest under, so this
// renders as its own section within the existing Studio deploy panel
// rather than inventing a new page.

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, Trash2, Pencil, X, Loader2, ShieldAlert } from "lucide-react";
import { envVarsApi } from "@/lib/services";
import {
  ENV_VAR_ENVIRONMENTS,
  MASKED_VALUE,
  buildCreatePayload,
  buildUpdatePayload,
  displayValueFor,
  environmentLabel,
  envVarApiErrorMessage,
  hasUpdatePayloadChanges,
  publicPrefixWarning,
  redeployNoticeFor,
  secretPublicPrefixConflict,
  typeLabel,
  validateEnvKey,
  type EnvVar,
  type EnvVarEnvironment
} from "@/lib/env-vars";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { EmptyState } from "@/components/ui/misc";
import { cn, formatDate } from "@/lib/utils";

function AddVariableForm({
  siteId,
  environment,
  onDone
}: {
  siteId: string;
  environment: EnvVarEnvironment | string;
  onDone: () => void;
}) {
  const qc = useQueryClient();
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const [isSecret, setIsSecret] = useState(true);

  const keyError = key.length > 0 ? validateEnvKey(key) : null;
  const publicWarning = publicPrefixWarning(key);
  const conflict = secretPublicPrefixConflict(key, isSecret);
  const canSubmit = key.trim().length > 0 && !validateEnvKey(key) && value.length > 0 && !conflict;

  const createM = useMutation({
    mutationFn: () => envVarsApi.create(siteId, buildCreatePayload({ key, value, environment, isSecret })),
    onSuccess: () => {
      toast.success(`${key.trim()} added`);
      toast.message(redeployNoticeFor(undefined));
      // Clear the plaintext value out of component state immediately after
      // a successful save — never left sitting in React state longer than
      // needed for the request itself.
      setValue("");
      setKey("");
      setIsSecret(true);
      void qc.invalidateQueries({ queryKey: ["env-vars", siteId] });
      onDone();
    },
    onError: (err) => toast.error(envVarApiErrorMessage(err))
  });

  return (
    <form
      className="mt-4 space-y-3 rounded-2xl border border-line bg-canvas p-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (!canSubmit || createM.isPending) return;
        createM.mutate();
      }}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <Label htmlFor="env-var-key">Key</Label>
          <Input
            id="env-var-key"
            placeholder="OPENAI_API_KEY"
            value={key}
            onChange={(e) => setKey(e.target.value.toUpperCase())}
            autoComplete="off"
            spellCheck={false}
          />
          {keyError && <p className="mt-1 text-xs text-red-600">{keyError}</p>}
          {!keyError && publicWarning && (
            <p className="mt-1 flex items-center gap-1 text-xs text-amber-600">
              <ShieldAlert className="h-3.5 w-3.5" /> {publicWarning}
            </p>
          )}
        </div>
        <div>
          <Label htmlFor="env-var-value">Value</Label>
          <Input
            id="env-var-value"
            type="password"
            placeholder="Enter value"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            autoComplete="new-password"
          />
        </div>
        <div>
          <Label htmlFor="env-var-secret">Type</Label>
          <Select
            id="env-var-secret"
            value={isSecret ? "secret" : "public"}
            onChange={(e) => setIsSecret(e.target.value === "secret")}
          >
            <option value="secret">Secret (encrypted at rest)</option>
            <option value="public">Public (may be exposed to browser code)</option>
          </Select>
        </div>
        <div className="flex items-end text-xs text-muted">
          {isSecret
            ? "Secret values are encrypted at rest and never shown again after saving."
            : "Public values are not secrets — do not store credentials here."}
        </div>
      </div>

      {conflict && (
        <p className="flex items-center gap-1.5 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">
          <ShieldAlert className="h-3.5 w-3.5 shrink-0" /> {conflict}
        </p>
      )}

      <div className="flex justify-end gap-2">
        <Button type="button" variant="secondary" size="sm" onClick={onDone} disabled={createM.isPending}>
          Cancel
        </Button>
        <Button type="submit" size="sm" disabled={!canSubmit || createM.isPending}>
          {createM.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Add Variable
        </Button>
      </div>
    </form>
  );
}

function EditVariableRow({
  siteId,
  row,
  onDone
}: {
  siteId: string;
  row: EnvVar;
  onDone: () => void;
}) {
  const qc = useQueryClient();
  // Deliberately starts EMPTY — the current plaintext value is never
  // fetched or prefilled (the GET/list API never returns it in the first
  // place; see lib/env-vars.ts's EnvVar type).
  const [newValue, setNewValue] = useState("");
  const [isSecret, setIsSecret] = useState(row.is_secret);

  const conflict = secretPublicPrefixConflict(row.key, isSecret);
  const payload = buildUpdatePayload({ newValue, isSecret, currentIsSecret: row.is_secret });
  const canSubmit = hasUpdatePayloadChanges(payload) && !conflict;

  const updateM = useMutation({
    mutationFn: () => envVarsApi.update(siteId, row.id, payload),
    onSuccess: () => {
      toast.success(`${row.key} updated`);
      toast.message(redeployNoticeFor(undefined));
      setNewValue("");
      void qc.invalidateQueries({ queryKey: ["env-vars", siteId] });
      onDone();
    },
    onError: (err) => toast.error(envVarApiErrorMessage(err))
  });

  return (
    <tr className="border-t border-line bg-canvas/60">
      <td colSpan={5} className="p-3">
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (!canSubmit || updateM.isPending) return;
            updateM.mutate();
          }}
        >
          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <Label htmlFor={`edit-value-${row.id}`}>Value</Label>
              <Input
                id={`edit-value-${row.id}`}
                type="password"
                placeholder="Enter new value (leave blank to keep existing)"
                value={newValue}
                onChange={(e) => setNewValue(e.target.value)}
                autoComplete="new-password"
              />
            </div>
            <div>
              <Label htmlFor={`edit-secret-${row.id}`}>Type</Label>
              <Select
                id={`edit-secret-${row.id}`}
                value={isSecret ? "secret" : "public"}
                onChange={(e) => setIsSecret(e.target.value === "secret")}
              >
                <option value="secret">Secret</option>
                <option value="public">Public</option>
              </Select>
            </div>
          </div>
          {conflict && (
            <p className="flex items-center gap-1.5 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">
              <ShieldAlert className="h-3.5 w-3.5 shrink-0" /> {conflict}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" size="sm" onClick={onDone} disabled={updateM.isPending}>
              <X className="mr-1 h-3.5 w-3.5" /> Cancel
            </Button>
            <Button type="submit" size="sm" disabled={!canSubmit || updateM.isPending}>
              {updateM.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Save
            </Button>
          </div>
        </form>
      </td>
    </tr>
  );
}

export function EnvVarsPanel({
  siteId,
  framework,
  canManage
}: {
  siteId: string;
  framework?: string | null;
  canManage: boolean;
}) {
  const qc = useQueryClient();
  const [environment, setEnvironment] = useState<EnvVarEnvironment>("production");
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const listQ = useQuery({
    queryKey: ["env-vars", siteId, environment],
    queryFn: () => envVarsApi.list(siteId, environment),
    enabled: Boolean(siteId)
  });

  const deleteM = useMutation({
    mutationFn: (envId: string) => envVarsApi.remove(siteId, envId),
    onMutate: (envId) => setDeletingId(envId),
    onSuccess: (_data, envId) => {
      const deleted = listQ.data?.items.find((r) => r.id === envId);
      toast.success(deleted ? `${deleted.key} deleted` : "Environment variable deleted");
      toast.message(redeployNoticeFor(undefined));
      void qc.invalidateQueries({ queryKey: ["env-vars", siteId] });
    },
    onError: (err) => toast.error(envVarApiErrorMessage(err)),
    onSettled: () => setDeletingId(null)
  });

  if (!siteId) {
    return (
      <div className="mt-6">
        <h4 className="mb-2 text-sm font-semibold text-ink">Environment Variables</h4>
        <EmptyState
          title="Create a site first"
          description="Upload a site above, then come back here to manage its environment variables."
        />
      </div>
    );
  }

  if (!canManage) {
    return (
      <div className="mt-6">
        <h4 className="mb-2 text-sm font-semibold text-ink">Environment Variables</h4>
        <EmptyState
          title="You don't have permission to manage environment variables."
          description="Ask a company owner or admin for access."
        />
      </div>
    );
  }

  const rows = listQ.data?.items || [];

  return (
    <div className="mt-6">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h4 className="text-sm font-semibold text-ink">Environment Variables</h4>
          <p className="text-xs text-muted">{redeployNoticeFor(framework)}</p>
        </div>
        <div className="flex items-center gap-2">
          <Label htmlFor="env-var-environment-select">Environment</Label>
          <Select
            id="env-var-environment-select"
            className="w-40"
            value={environment}
            onChange={(e) => {
              setEnvironment(e.target.value as EnvVarEnvironment);
              setShowAddForm(false);
              setEditingId(null);
            }}
          >
            {ENV_VAR_ENVIRONMENTS.map((env) => (
              <option key={env} value={env}>
                {environmentLabel(env)}
              </option>
            ))}
          </Select>
          <Button
            size="sm"
            onClick={() => {
              setShowAddForm((v) => !v);
              setEditingId(null);
            }}
            disabled={listQ.isLoading}
          >
            <Plus className="mr-1 h-3.5 w-3.5" /> Add Variable
          </Button>
        </div>
      </div>

      {showAddForm && (
        <AddVariableForm siteId={siteId} environment={environment} onDone={() => setShowAddForm(false)} />
      )}

      {listQ.isLoading ? (
        <p className="mt-4 flex items-center gap-2 text-sm text-muted">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading environment variables…
        </p>
      ) : listQ.isError ? (
        <div className="mt-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {envVarApiErrorMessage(listQ.error)}
        </div>
      ) : rows.length === 0 ? (
        <div className="mt-4">
          <EmptyState
            title="No environment variables yet"
            description={`No variables set for ${environmentLabel(environment)}. Add one above.`}
          />
        </div>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[560px] border-collapse text-sm">
            <thead>
              <tr className="text-left text-xs font-semibold uppercase tracking-wide text-muted">
                <th className="pb-2 pr-3">Key</th>
                <th className="pb-2 pr-3">Value</th>
                <th className="pb-2 pr-3">Environment</th>
                <th className="pb-2 pr-3">Type</th>
                <th className="pb-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) =>
                editingId === row.id ? (
                  <EditVariableRow key={row.id} siteId={siteId} row={row} onDone={() => setEditingId(null)} />
                ) : (
                  <tr key={row.id} className="border-t border-line">
                    <td className="py-2.5 pr-3 font-mono text-xs text-ink">{row.key}</td>
                    <td className="py-2.5 pr-3 font-mono text-xs text-muted">{displayValueFor(row)}</td>
                    <td className="py-2.5 pr-3">
                      <Badge tone="neutral">{environmentLabel(row.environment)}</Badge>
                    </td>
                    <td className="py-2.5 pr-3">
                      <Badge tone={row.is_secret ? "brand" : "neutral"}>{typeLabel(row.is_secret)}</Badge>
                    </td>
                    <td className="py-2.5">
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          className={cn("text-muted hover:text-ink")}
                          aria-label={`Edit ${row.key}`}
                          onClick={() => {
                            setEditingId(row.id);
                            setShowAddForm(false);
                          }}
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          className="text-red-500 hover:text-red-600 disabled:opacity-50"
                          aria-label={`Delete ${row.key}`}
                          disabled={deleteM.isPending && deletingId === row.id}
                          onClick={() => {
                            if (
                              window.confirm(
                                `Delete ${row.key} from ${environmentLabel(row.environment)}?`
                              )
                            ) {
                              deleteM.mutate(row.id);
                            }
                          }}
                        >
                          {deleteM.isPending && deletingId === row.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Trash2 className="h-4 w-4" />
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              )}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-muted">
            Secret values are never shown again after saving — {MASKED_VALUE} always means the value is
            stored, not that it is empty.
          </p>
        </div>
      )}
    </div>
  );
}
