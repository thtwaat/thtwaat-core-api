"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Copy, Pencil, RefreshCw, Webhook as WebhookIcon } from "lucide-react";
import { webhooksApi } from "@/lib/services";
import { webhookSchema } from "@/lib/validators";
import { formatDate } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { canManageWebhooks } from "@/lib/permissions";
import { PageHeader, EmptyState } from "@/components/ui/misc";
import { Badge, Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Label, Select } from "@/components/ui/input";
import type { Webhook } from "@/lib/types";
import type { z } from "zod";

type FormValues = z.infer<typeof webhookSchema>;

const EVENT_OPTIONS = [
  { value: "*", label: "All events (*)" },
  { value: "ping", label: "ping" },
  { value: "completion.succeeded", label: "completion.succeeded" },
  { value: "completion.failed", label: "completion.failed" },
  { value: "domain.created", label: "domain.created" },
  { value: "domain.verified", label: "domain.verified" },
  { value: "domain.ssl_active", label: "domain.ssl_active" },
  { value: "domain.live", label: "domain.live" },
  { value: "domain.deleted", label: "domain.deleted" },
  { value: "quota.exceeded", label: "quota.exceeded" },
  { value: "usage.updated", label: "usage.updated" },
  { value: "subscription.upgraded", label: "subscription.upgraded" },
  { value: "subscription.expired", label: "subscription.expired" }
];

const PAGE_SIZE = 10;

function statusTone(status: string): "success" | "warn" | "danger" | "neutral" {
  if (status === "delivered") return "success";
  if (status === "queued" || status === "pending") return "warn";
  if (status === "failed" || status === "dead") return "danger";
  return "neutral";
}

async function copyText(value: string, label: string) {
  try {
    await navigator.clipboard.writeText(value);
    toast.success(`${label} copied`);
  } catch {
    toast.error("Could not copy to clipboard");
  }
}

export default function WebhooksPage() {
  const { user } = useAuth();
  const canManage = canManageWebhooks(user?.role);
  const qc = useQueryClient();
  const [editing, setEditing] = useState<Webhook | null>(null);
  const [search, setSearch] = useState("");
  const [eventFilter, setEventFilter] = useState("");
  const [hookPage, setHookPage] = useState(0);
  const [deliveryWebhookId, setDeliveryWebhookId] = useState("");
  const [deliveryStatus, setDeliveryStatus] = useState("");
  const [deliveryEvent, setDeliveryEvent] = useState("");
  const [deliveryQ, setDeliveryQ] = useState("");
  const [deliveryPage, setDeliveryPage] = useState(0);
  const [createdSecret, setCreatedSecret] = useState<string | null>(null);

  const form = useForm<FormValues>({
    resolver: zodResolver(webhookSchema),
    defaultValues: { url: "", event_types: ["*"] }
  });

  const hooks = useQuery({
    queryKey: ["webhooks"],
    queryFn: webhooksApi.list,
    enabled: canManage
  });

  const deliveries = useQuery({
    queryKey: [
      "webhook-deliveries",
      deliveryWebhookId,
      deliveryStatus,
      deliveryEvent,
      deliveryQ,
      deliveryPage
    ],
    queryFn: () =>
      webhooksApi.deliveries({
        webhook_id: deliveryWebhookId || undefined,
        status: deliveryStatus || undefined,
        event: deliveryEvent || undefined,
        q: deliveryQ || undefined,
        limit: PAGE_SIZE,
        offset: deliveryPage * PAGE_SIZE
      }),
    enabled: canManage
  });

  const create = useMutation({
    mutationFn: (values: FormValues) => webhooksApi.create(values),
    onSuccess: (data) => {
      toast.success("Webhook created");
      if (data.secret) setCreatedSecret(data.secret);
      form.reset({ url: "", event_types: ["*"] });
      setEditing(null);
      qc.invalidateQueries({ queryKey: ["webhooks"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const update = useMutation({
    mutationFn: (values: FormValues) => {
      if (!editing) throw new Error("No webhook selected");
      return webhooksApi.update(editing.id, values);
    },
    onSuccess: () => {
      toast.success("Webhook updated");
      form.reset({ url: "", event_types: ["*"] });
      setEditing(null);
      qc.invalidateQueries({ queryKey: ["webhooks"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const toggle = useMutation({
    mutationFn: (hook: Webhook) => (hook.is_active ? webhooksApi.disable(hook.id) : webhooksApi.enable(hook.id)),
    onSuccess: (data) => {
      toast.success(data.is_active ? "Webhook enabled" : "Webhook disabled");
      qc.invalidateQueries({ queryKey: ["webhooks"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const remove = useMutation({
    mutationFn: (id: string) => webhooksApi.remove(id),
    onSuccess: () => {
      toast.success("Webhook deleted");
      qc.invalidateQueries({ queryKey: ["webhooks"] });
      qc.invalidateQueries({ queryKey: ["webhook-deliveries"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const test = useMutation({
    mutationFn: (id: string) => webhooksApi.test(id),
    onSuccess: (data) => {
      toast.success(data.message || "Test dispatched");
      qc.invalidateQueries({ queryKey: ["webhook-deliveries"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const copySecret = useMutation({
    mutationFn: (id: string) => webhooksApi.secret(id),
    onSuccess: async (data) => {
      await copyText(data.secret, "Webhook secret");
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const retry = useMutation({
    mutationFn: (deliveryId: string) => webhooksApi.retryDelivery(deliveryId),
    onSuccess: (data) => {
      toast.success(data.message || "Retry queued");
      qc.invalidateQueries({ queryKey: ["webhook-deliveries"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const list = Array.isArray(hooks.data) ? hooks.data : [];

  const filteredHooks = useMemo(() => {
    const q = search.trim().toLowerCase();
    return list.filter((hook) => {
      const events = hook.event_types || [];
      if (eventFilter && !(events.includes(eventFilter) || events.includes("*"))) return false;
      if (!q) return true;
      return (
        hook.url.toLowerCase().includes(q) ||
        events.some((e) => e.toLowerCase().includes(q)) ||
        hook.id.toLowerCase().includes(q)
      );
    });
  }, [list, search, eventFilter]);

  const hookTotalPages = Math.max(1, Math.ceil(filteredHooks.length / PAGE_SIZE));
  const pagedHooks = filteredHooks.slice(hookPage * PAGE_SIZE, hookPage * PAGE_SIZE + PAGE_SIZE);
  const deliveryTotal = deliveries.data?.total ?? 0;
  const deliveryTotalPages = Math.max(1, Math.ceil(deliveryTotal / PAGE_SIZE));
  const deliveryRows = deliveries.data?.results ?? [];

  function startEdit(hook: Webhook) {
    setEditing(hook);
    setCreatedSecret(null);
    form.reset({
      url: hook.url,
      event_types: hook.event_types?.length ? hook.event_types : ["*"]
    });
  }

  function cancelEdit() {
    setEditing(null);
    form.reset({ url: "", event_types: ["*"] });
  }

  function toggleEvent(value: string) {
    const current = form.getValues("event_types") || [];
    if (value === "*") {
      form.setValue("event_types", ["*"], { shouldValidate: true });
      return;
    }
    const withoutStar = current.filter((e) => e !== "*");
    const next = withoutStar.includes(value)
      ? withoutStar.filter((e) => e !== value)
      : [...withoutStar, value];
    form.setValue("event_types", next.length ? next : ["*"], { shouldValidate: true });
  }

  if (!canManage) {
    return (
      <div className="space-y-6">
        <PageHeader title="Webhooks" description="Manage outbound event deliveries for your company." />
        <EmptyState
          title="Access restricted"
          description="Webhook management is available to company owners, admins, and developers."
        />
      </div>
    );
  }

  const selectedEvents = form.watch("event_types") || [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Webhooks"
        description="Register HTTPS endpoints, filter by event, inspect delivery history, and retry failures."
      />

      {createdSecret && (
        <Card className="border-brand/30 bg-brand-soft/40">
          <CardHeader title="Save your webhook secret" description="Shown once after create — copy it now." />
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <code className="flex-1 break-all rounded-xl border border-line bg-white px-3 py-2 text-xs">{createdSecret}</code>
            <Button type="button" variant="secondary" onClick={() => copyText(createdSecret, "Webhook secret")}>
              <Copy size={14} /> Copy
            </Button>
            <Button type="button" variant="ghost" onClick={() => setCreatedSecret(null)}>
              Dismiss
            </Button>
          </div>
        </Card>
      )}

      <Card>
        <CardHeader
          title={editing ? "Edit webhook" : "Create webhook"}
          description="Events are signed with your webhook secret (HMAC)."
          action={
            editing ? (
              <Button type="button" variant="ghost" size="sm" onClick={cancelEdit}>
                Cancel edit
              </Button>
            ) : undefined
          }
        />
        <form
          className="space-y-4"
          onSubmit={form.handleSubmit((values) => {
            if (editing) update.mutate(values);
            else create.mutate(values);
          })}
        >
          <div>
            <Label>Endpoint URL</Label>
            <Input placeholder="https://example.com/hooks/thtwaat" {...form.register("url")} />
            {form.formState.errors.url && (
              <p className="mt-1 text-xs text-red-600">{form.formState.errors.url.message}</p>
            )}
          </div>
          <div>
            <Label>Event types</Label>
            <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {EVENT_OPTIONS.map((opt) => {
                const checked = selectedEvents.includes(opt.value) || (opt.value !== "*" && selectedEvents.includes("*"));
                return (
                  <label
                    key={opt.value}
                    className="flex cursor-pointer items-center gap-2 rounded-xl border border-line bg-white px-3 py-2 text-sm"
                  >
                    <input
                      type="checkbox"
                      className="accent-[var(--brand)]"
                      checked={selectedEvents.includes(opt.value)}
                      onChange={() => toggleEvent(opt.value)}
                    />
                    <span className={checked ? "text-ink" : "text-muted"}>{opt.label}</span>
                  </label>
                );
              })}
            </div>
            {form.formState.errors.event_types && (
              <p className="mt-1 text-xs text-red-600">{form.formState.errors.event_types.message}</p>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button disabled={create.isPending || update.isPending}>
              {editing ? (update.isPending ? "Saving…" : "Save changes") : create.isPending ? "Creating…" : "Create webhook"}
            </Button>
          </div>
        </form>
      </Card>

      <Card>
        <CardHeader title="Endpoints" description={`${filteredHooks.length} webhook${filteredHooks.length === 1 ? "" : "s"}`} />
        <div className="mb-4 grid gap-3 md:grid-cols-3">
          <Input
            placeholder="Search URL, event, or id…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setHookPage(0);
            }}
          />
          <Select
            value={eventFilter}
            onChange={(e) => {
              setEventFilter(e.target.value);
              setHookPage(0);
            }}
          >
            <option value="">All event types</option>
            {EVENT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </Select>
        </div>

        {!pagedHooks.length && !hooks.isLoading && (
          <EmptyState title="No webhooks yet" description="Create an HTTPS endpoint to receive THTWAAT events." />
        )}

        <div className="grid gap-4">
          {pagedHooks.map((hook) => (
            <div key={hook.id} className="rounded-2xl border border-line bg-white p-4">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0 space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <WebhookIcon size={16} className="text-brand" />
                    <h3 className="truncate font-semibold text-ink">{hook.url}</h3>
                    <Badge tone={hook.is_active ? "success" : "neutral"}>
                      {hook.is_active ? "Active" : "Disabled"}
                    </Badge>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {(hook.event_types || []).map((ev) => (
                      <Badge key={ev} tone="brand">
                        {ev}
                      </Badge>
                    ))}
                  </div>
                  <p className="text-xs text-muted">Created {formatDate(hook.created_at)}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button type="button" size="sm" variant="secondary" onClick={() => startEdit(hook)}>
                    <Pencil size={14} /> Edit
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    disabled={toggle.isPending}
                    onClick={() => toggle.mutate(hook)}
                  >
                    {hook.is_active ? "Disable" : "Enable"}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    disabled={!hook.is_active || test.isPending}
                    onClick={() => test.mutate(hook.id)}
                  >
                    Test
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    disabled={copySecret.isPending}
                    onClick={() => copySecret.mutate(hook.id)}
                  >
                    <Copy size={14} /> Secret
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="danger"
                    disabled={remove.isPending}
                    onClick={() => {
                      if (window.confirm("Delete this webhook?")) remove.mutate(hook.id);
                    }}
                  >
                    Delete
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>

        {filteredHooks.length > PAGE_SIZE && (
          <div className="mt-4 flex items-center justify-between gap-3">
            <p className="text-xs text-muted">
              Page {hookPage + 1} of {hookTotalPages}
            </p>
            <div className="flex gap-2">
              <Button
                type="button"
                size="sm"
                variant="secondary"
                disabled={hookPage <= 0}
                onClick={() => setHookPage((p) => Math.max(0, p - 1))}
              >
                Previous
              </Button>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                disabled={hookPage + 1 >= hookTotalPages}
                onClick={() => setHookPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader
          title="Delivery history"
          description="Outbox deliveries for this company. Retry failed or dead rows."
          action={
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => qc.invalidateQueries({ queryKey: ["webhook-deliveries"] })}
            >
              <RefreshCw size={14} /> Refresh
            </Button>
          }
        />
        <div className="mb-4 grid gap-3 md:grid-cols-4">
          <Select
            value={deliveryWebhookId}
            onChange={(e) => {
              setDeliveryWebhookId(e.target.value);
              setDeliveryPage(0);
            }}
          >
            <option value="">All webhooks</option>
            {list.map((h) => (
              <option key={h.id} value={h.id}>
                {h.url}
              </option>
            ))}
          </Select>
          <Select
            value={deliveryStatus}
            onChange={(e) => {
              setDeliveryStatus(e.target.value);
              setDeliveryPage(0);
            }}
          >
            <option value="">All statuses</option>
            <option value="pending">pending</option>
            <option value="queued">queued</option>
            <option value="delivered">delivered</option>
            <option value="failed">failed</option>
            <option value="dead">dead</option>
          </Select>
          <Select
            value={deliveryEvent}
            onChange={(e) => {
              setDeliveryEvent(e.target.value);
              setDeliveryPage(0);
            }}
          >
            <option value="">All events</option>
            {EVENT_OPTIONS.filter((e) => e.value !== "*").map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </Select>
          <Input
            placeholder="Search delivery id / URL / error…"
            value={deliveryQ}
            onChange={(e) => {
              setDeliveryQ(e.target.value);
              setDeliveryPage(0);
            }}
          />
        </div>

        {!deliveryRows.length && !deliveries.isLoading && (
          <EmptyState title="No deliveries yet" description="Send a test event or wait for production traffic." />
        )}

        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-line text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-2 py-2 font-semibold">Delivery</th>
                <th className="px-2 py-2 font-semibold">Event</th>
                <th className="px-2 py-2 font-semibold">Status</th>
                <th className="px-2 py-2 font-semibold">Attempts</th>
                <th className="px-2 py-2 font-semibold">When</th>
                <th className="px-2 py-2 font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody>
              {deliveryRows.map((row) => {
                const canRetry = row.status === "failed" || row.status === "dead" || row.status === "pending";
                return (
                  <tr key={row.id} className="border-b border-line/70 align-top">
                    <td className="px-2 py-3">
                      <p className="font-mono text-xs text-ink">{row.delivery_id}</p>
                      <p className="mt-1 max-w-[220px] truncate text-xs text-muted">{row.url}</p>
                      {row.last_error && <p className="mt-1 max-w-xs text-xs text-red-600">{row.last_error}</p>}
                    </td>
                    <td className="px-2 py-3">
                      <Badge tone="brand">{row.event}</Badge>
                    </td>
                    <td className="px-2 py-3">
                      <Badge tone={statusTone(row.status)}>{row.status}</Badge>
                    </td>
                    <td className="px-2 py-3 text-muted">{row.attempts}</td>
                    <td className="px-2 py-3 text-xs text-muted">{formatDate(row.created_at || row.updated_at)}</td>
                    <td className="px-2 py-3">
                      <Button
                        type="button"
                        size="sm"
                        variant="secondary"
                        disabled={!canRetry || retry.isPending}
                        onClick={() => retry.mutate(row.delivery_id)}
                      >
                        Retry
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {deliveryTotal > PAGE_SIZE && (
          <div className="mt-4 flex items-center justify-between gap-3">
            <p className="text-xs text-muted">
              {deliveryTotal} total · page {deliveryPage + 1} of {deliveryTotalPages}
            </p>
            <div className="flex gap-2">
              <Button
                type="button"
                size="sm"
                variant="secondary"
                disabled={deliveryPage <= 0}
                onClick={() => setDeliveryPage((p) => Math.max(0, p - 1))}
              >
                Previous
              </Button>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                disabled={deliveryPage + 1 >= deliveryTotalPages}
                onClick={() => setDeliveryPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
