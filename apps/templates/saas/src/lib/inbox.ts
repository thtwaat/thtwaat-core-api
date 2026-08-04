/** Pure helpers for Unified Inbox (widget + agent conversations). */

export type InboxChannel = "widget" | "dashboard" | "api";
export type InboxStatus = "open" | "pending_human" | "human" | "closed";

export function channelLabel(channel?: string | null): string {
  const c = (channel || "dashboard").toLowerCase();
  if (c === "widget") return "Website widget";
  if (c === "api") return "API";
  if (c === "dashboard") return "Agent / dashboard";
  return c;
}

export function statusLabel(status?: string | null): string {
  const s = (status || "open").toLowerCase();
  if (s === "pending_human") return "Pending handoff";
  if (s === "human") return "Human";
  if (s === "closed") return "Closed";
  return "Open";
}

export function statusTone(status?: string | null): "success" | "warn" | "danger" | "neutral" | "brand" {
  const s = (status || "open").toLowerCase();
  if (s === "open") return "brand";
  if (s === "pending_human") return "warn";
  if (s === "human") return "success";
  if (s === "closed") return "neutral";
  return "neutral";
}

export function buildInboxQuery(params: {
  q?: string;
  channel?: string;
  status?: string;
  unread_only?: boolean;
}): string {
  const sp = new URLSearchParams();
  if (params.q?.trim()) sp.set("q", params.q.trim());
  if (params.channel && params.channel !== "all") sp.set("channel", params.channel);
  if (params.status && params.status !== "all") sp.set("status", params.status);
  if (params.unread_only) sp.set("unread_only", "true");
  const qs = sp.toString();
  return qs ? `?${qs}` : "";
}
