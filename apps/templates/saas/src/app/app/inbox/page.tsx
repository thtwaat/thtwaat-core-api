"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { Inbox, RefreshCw, Search } from "lucide-react";
import { agentsApi, conversationsApi } from "@/lib/services";
import { channelLabel, statusLabel, statusTone } from "@/lib/inbox";
import { cn, formatDate } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { PageHeader, EmptyState } from "@/components/ui/misc";
import { Badge, Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Label, Select } from "@/components/ui/input";

function InboxContent() {
  const { user } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const qc = useQueryClient();

  const selectedId = searchParams.get("id");
  const [q, setQ] = useState("");
  const [qDebounced, setQDebounced] = useState("");
  const [channel, setChannel] = useState("all");
  const [status, setStatus] = useState("all");
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [reply, setReply] = useState("");
  const [mobileShowDetail, setMobileShowDetail] = useState(Boolean(selectedId));

  useEffect(() => {
    const t = setTimeout(() => setQDebounced(q), 300);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    setMobileShowDetail(Boolean(selectedId));
  }, [selectedId]);

  const listQ = useQuery({
    queryKey: ["inbox", qDebounced, channel, status, unreadOnly],
    queryFn: () =>
      conversationsApi.list({
        q: qDebounced || undefined,
        channel: channel === "all" ? undefined : channel,
        status: status === "all" ? undefined : status,
        unread_only: unreadOnly || undefined,
        limit: 100
      })
  });

  const detailQ = useQuery({
    queryKey: ["inbox-detail", selectedId],
    queryFn: () => conversationsApi.get(selectedId!, true),
    enabled: Boolean(selectedId)
  });

  const agentsQ = useQuery({ queryKey: ["agents"], queryFn: agentsApi.list });

  const agentName = useMemo(() => {
    const map = new Map((agentsQ.data || []).map((a) => [a.id, a.name]));
    return (id?: string) => (id && map.get(id)) || id?.slice(0, 8) || "—";
  }, [agentsQ.data]);

  const patchM = useMutation({
    mutationFn: (body: {
      status?: string;
      mark_read?: boolean;
      assigned_to_user_id?: string;
      clear_assignee?: boolean;
    }) => conversationsApi.update(selectedId!, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["inbox"] });
      void qc.invalidateQueries({ queryKey: ["inbox-detail", selectedId] });
      void qc.invalidateQueries({ queryKey: ["conversations"] });
      toast.success("Conversation updated");
    },
    onError: (e: Error) => toast.error(e.message || "Update failed")
  });

  const sendM = useMutation({
    mutationFn: (content: string) => conversationsApi.sendMessage(selectedId!, content),
    onSuccess: () => {
      setReply("");
      void qc.invalidateQueries({ queryKey: ["inbox"] });
      void qc.invalidateQueries({ queryKey: ["inbox-detail", selectedId] });
      toast.success("Message sent");
    },
    onError: (e: Error) => toast.error(e.message || "Send failed")
  });

  function selectConversation(id: string) {
    router.replace(`/app/inbox?id=${encodeURIComponent(id)}`);
    setMobileShowDetail(true);
  }

  function clearSelection() {
    router.replace("/app/inbox");
    setMobileShowDetail(false);
  }

  const rows = listQ.data || [];
  const detail = detailQ.data;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Inbox"
        description="Unified conversations from the website widget and AI agents. Handoff-ready (assign + status)."
        action={
          <Button
            variant="secondary"
            onClick={() => void listQ.refetch()}
            disabled={listQ.isFetching}
          >
            <RefreshCw size={16} className={listQ.isFetching ? "animate-spin" : ""} />
            Refresh
          </Button>
        }
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
        <div className="min-w-[200px] flex-1">
          <Label>Search</Label>
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <Input
              className="pl-8"
              placeholder="Title or message…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
        </div>
        <div className="w-full sm:w-40">
          <Label>Channel</Label>
          <Select value={channel} onChange={(e) => setChannel(e.target.value)}>
            <option value="all">All</option>
            <option value="widget">Website widget</option>
            <option value="dashboard">Agent / dashboard</option>
            <option value="api">API</option>
          </Select>
        </div>
        <div className="w-full sm:w-40">
          <Label>Status</Label>
          <Select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="all">All</option>
            <option value="open">Open</option>
            <option value="pending_human">Pending handoff</option>
            <option value="human">Human</option>
            <option value="closed">Closed</option>
          </Select>
        </div>
        <label className="flex items-center gap-2 pb-2 text-sm text-muted">
          <input
            type="checkbox"
            checked={unreadOnly}
            onChange={(e) => setUnreadOnly(e.target.checked)}
          />
          Unread only
        </label>
      </div>

      {listQ.isError && (
        <p className="text-sm text-red-600">
          Could not load inbox: {(listQ.error as Error)?.message || "Unknown error"}
        </p>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(280px,360px)_1fr]">
        <Card
          className={cn(
            "max-h-[70vh] overflow-hidden p-0",
            mobileShowDetail ? "hidden lg:block" : "block"
          )}
        >
          <div className="border-b border-line px-4 py-3 text-sm font-medium text-ink">
            Conversations ({rows.length})
          </div>
          <div className="max-h-[calc(70vh-48px)] overflow-y-auto">
            {listQ.isLoading && <p className="p-4 text-sm text-muted">Loading…</p>}
            {!listQ.isLoading && !rows.length && (
              <div className="p-4">
                <EmptyState
                  title="No conversations"
                  description="Widget chats and agent threads will appear here."
                />
              </div>
            )}
            <ul className="divide-y divide-line">
              {rows.map((c) => {
                const active = c.id === selectedId;
                return (
                  <li key={c.id}>
                    <button
                      type="button"
                      onClick={() => selectConversation(c.id)}
                      className={cn(
                        "w-full px-4 py-3 text-left transition hover:bg-canvas",
                        active && "bg-brand-soft/40"
                      )}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p
                          className={cn(
                            "text-sm",
                            c.unread ? "font-semibold text-ink" : "font-medium text-ink"
                          )}
                        >
                          {c.title || c.id.slice(0, 8)}
                        </p>
                        {c.unread && <Badge tone="brand">Unread</Badge>}
                      </div>
                      <p className="mt-0.5 line-clamp-1 text-xs text-muted">
                        {c.last_message_preview || "No messages yet"}
                      </p>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        <Badge tone="neutral">{channelLabel(c.channel)}</Badge>
                        <Badge tone={statusTone(c.status)}>{statusLabel(c.status)}</Badge>
                        <span className="text-[11px] text-muted">
                          {formatDate(c.last_message_at || c.updated_at || c.created_at)}
                        </span>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        </Card>

        <Card
          className={cn(
            "flex max-h-[70vh] flex-col overflow-hidden p-0",
            !mobileShowDetail ? "hidden lg:flex" : "flex"
          )}
        >
          {!selectedId && (
            <div className="grid flex-1 place-items-center p-8">
              <EmptyState
                title="Select a conversation"
                description="Choose a thread from the list to view messages."
              />
            </div>
          )}
          {selectedId && detailQ.isLoading && (
            <p className="p-4 text-sm text-muted">Loading conversation…</p>
          )}
          {selectedId && detailQ.isError && (
            <p className="p-4 text-sm text-red-600">
              {(detailQ.error as Error)?.message || "Failed to load conversation"}
            </p>
          )}
          {detail && (
            <>
              <div className="border-b border-line px-4 py-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <button
                      type="button"
                      className="mb-1 text-xs text-muted lg:hidden"
                      onClick={clearSelection}
                    >
                      ← Back to list
                    </button>
                    <h2 className="text-base font-semibold text-ink">
                      {detail.title || detail.id.slice(0, 8)}
                    </h2>
                    <p className="text-xs text-muted">
                      Agent: {agentName(detail.agent_id)} · {channelLabel(detail.channel)}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Select
                      value={detail.status || "open"}
                      onChange={(e) => patchM.mutate({ status: e.target.value })}
                      className="w-40"
                    >
                      <option value="open">Open</option>
                      <option value="pending_human">Pending handoff</option>
                      <option value="human">Human</option>
                      <option value="closed">Closed</option>
                    </Select>
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={!user?.id || patchM.isPending}
                      onClick={() =>
                        patchM.mutate(
                          detail.assigned_to_user_id === user?.id
                            ? { clear_assignee: true }
                            : { assigned_to_user_id: user!.id, status: "pending_human" }
                        )
                      }
                    >
                      {detail.assigned_to_user_id === user?.id ? "Unassign" : "Assign to me"}
                    </Button>
                  </div>
                </div>
              </div>

              <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
                {(detail.messages || []).map((m) => (
                  <div
                    key={m.id}
                    className={cn(
                      "max-w-[90%] rounded-2xl px-3 py-2 text-sm",
                      m.role === "user"
                        ? "ml-auto bg-brand text-white"
                        : m.role === "assistant"
                          ? "bg-canvas text-ink"
                          : "bg-panel text-muted"
                    )}
                  >
                    <p className="mb-1 text-[10px] uppercase opacity-70">{m.role}</p>
                    <p className="whitespace-pre-wrap">{m.content}</p>
                    <p className="mt-1 text-[10px] opacity-60">{formatDate(m.created_at)}</p>
                  </div>
                ))}
                {!detail.messages?.length && (
                  <EmptyState title="No messages yet" description="Send a reply below." />
                )}
              </div>

              <div className="border-t border-line p-3">
                <form
                  className="flex gap-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (!reply.trim()) return;
                    sendM.mutate(reply.trim());
                  }}
                >
                  <Input
                    placeholder="Reply as AI agent…"
                    value={reply}
                    onChange={(e) => setReply(e.target.value)}
                    disabled={sendM.isPending || detail.status === "closed"}
                  />
                  <Button
                    type="submit"
                    disabled={sendM.isPending || !reply.trim() || detail.status === "closed"}
                  >
                    Send
                  </Button>
                </form>
              </div>
            </>
          )}
        </Card>
      </div>

      {!rows.length && !listQ.isLoading && (
        <p className="flex items-center gap-2 text-xs text-muted">
          <Inbox size={14} /> Widget and dashboard chats share one store (`/v2/conversations`).
        </p>
      )}
    </div>
  );
}

export default function InboxPage() {
  return (
    <Suspense fallback={<div className="text-sm text-muted">Loading inbox…</div>}>
      <InboxContent />
    </Suspense>
  );
}
