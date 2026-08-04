/** Super Admin console helpers — frontend composition over existing platform APIs */

export const SUPER_ADMIN_NAV = [
  { href: "/admin", label: "Dashboard", exact: true as boolean },
  { href: "/admin/companies", label: "Workspaces", exact: false as boolean },
  { href: "/admin/users", label: "Users", exact: false as boolean },
  { href: "/admin/ai", label: "AI Analytics", exact: false as boolean },
  { href: "/admin/marketplace", label: "Marketplace", exact: false as boolean },
  { href: "/admin/audit", label: "Logs", exact: false as boolean },
  { href: "/admin/operations", label: "Operations", exact: false as boolean },
  { href: "/admin/plans", label: "Plans", exact: false as boolean },
  { href: "/admin/health", label: "System Health", exact: false as boolean }
] as const;

/** Company plan enum values; UI label "Pro" maps to growth */
export const COMPANY_PLAN_OPTIONS = [
  { value: "free", label: "Free" },
  { value: "starter", label: "Starter" },
  { value: "growth", label: "Pro" },
  { value: "enterprise", label: "Enterprise" }
] as const;

export const COMPANY_STATUS_OPTIONS = [
  { value: "trial", label: "Trial" },
  { value: "active", label: "Active" },
  { value: "suspended", label: "Suspended" },
  { value: "cancelled", label: "Cancelled" }
] as const;

export const USER_ROLE_OPTIONS = [
  "super_admin",
  "company_owner",
  "admin",
  "manager",
  "developer",
  "employee",
  "viewer"
] as const;

export const QUOTA_FIELDS = [
  { key: "max_agents", label: "Max agents" },
  { key: "max_messages", label: "Max messages" },
  { key: "max_tokens", label: "Max tokens" },
  { key: "max_storage", label: "Max storage (bytes)" },
  { key: "max_domains", label: "Max domains" },
  { key: "max_team_members", label: "Max team members" },
  { key: "max_api_keys", label: "Max API keys" },
  { key: "max_templates", label: "Max templates" }
] as const;

export const LOG_CATEGORIES = [
  { value: "all", label: "All" },
  { value: "audit", label: "Audit" },
  { value: "payment", label: "Payments" },
  { value: "webhook", label: "Webhooks" },
  { value: "auth", label: "Authentication" },
  { value: "ai", label: "AI" }
] as const;

export function planLabel(plan?: string | null): string {
  const row = COMPANY_PLAN_OPTIONS.find((p) => p.value === plan);
  return row?.label || plan || "—";
}

export function healthComponentStatus(component: Record<string, unknown> | undefined | null): string {
  if (!component) return "unknown";
  const raw = (component.status ?? component.state ?? component.ok) as unknown;
  if (typeof raw === "boolean") return raw ? "ok" : "error";
  if (typeof raw === "string" && raw.trim()) return raw.trim().toLowerCase();
  return "unknown";
}

export function healthTone(status: string): "success" | "warn" | "danger" | "neutral" {
  const s = status.toLowerCase();
  if (["ok", "healthy", "up", "configured", "ready"].includes(s)) return "success";
  if (["degraded", "warn", "warning", "slow", "backlog"].includes(s)) return "warn";
  if (["error", "down", "unhealthy", "fail", "failed"].includes(s)) return "danger";
  return "neutral";
}

export function formatRevenue(amount?: number | null): string {
  if (amount == null || Number.isNaN(Number(amount))) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0
  }).format(Number(amount));
}

export function formatPct(value?: number | null): string {
  if (value == null || Number.isNaN(Number(value))) return "—";
  return `${Number(value).toFixed(1)}%`;
}

export function downloadAdminExport(payload: {
  filename: string;
  content: string;
  encoding: string;
  content_type: string;
}): void {
  if (typeof window === "undefined") return;
  let blob: Blob;
  if (payload.encoding === "base64") {
    const binary = atob(payload.content);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    blob = new Blob([bytes], { type: payload.content_type });
  } else {
    blob = new Blob([payload.content], { type: payload.content_type });
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = payload.filename;
  a.click();
  URL.revokeObjectURL(url);
}

export const ADMIN_BACKUP_KEY = "tht_admin_session_backup_v1";

export function saveAdminSessionBackup(tokens: {
  access_token: string;
  refresh_token: string;
}): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ADMIN_BACKUP_KEY, JSON.stringify(tokens));
}

export function loadAdminSessionBackup(): {
  access_token: string;
  refresh_token: string;
} | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(ADMIN_BACKUP_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function clearAdminSessionBackup(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(ADMIN_BACKUP_KEY);
}
