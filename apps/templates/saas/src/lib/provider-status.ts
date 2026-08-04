/**
 * Pure helpers for AI Provider Management status board.
 * Status values come from GET /api/v1/ai/health.
 */

export type ProviderHealthTone = "success" | "warn" | "danger" | "neutral";

export function normalizeProviderHealth(raw: string | undefined | null): string {
  return (raw || "unknown").trim().toLowerCase() || "unknown";
}

export function providerHealthTone(status: string | undefined | null): ProviderHealthTone {
  const s = normalizeProviderHealth(status);
  if (s === "configured" || s === "ok" || s === "healthy") return "success";
  if (s === "unconfigured") return "warn";
  if (s === "error" || s === "unhealthy") return "danger";
  return "neutral";
}

export function providerHealthLabel(status: string | undefined | null): string {
  const s = normalizeProviderHealth(status);
  if (s === "configured") return "Configured";
  if (s === "unconfigured") return "Not configured";
  if (s === "error") return "Error";
  if (s === "unknown") return "Unknown";
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function mergeProviderRows(
  providers: string[],
  health: Record<string, string>,
  defaultProvider?: string
): Array<{ name: string; status: string; isDefault: boolean }> {
  const names = providers.length
    ? providers
    : Array.from(new Set([...Object.keys(health), ...(defaultProvider ? [defaultProvider] : [])]));
  return names.map((name) => ({
    name,
    status: normalizeProviderHealth(health[name]),
    isDefault: Boolean(defaultProvider && name === defaultProvider)
  }));
}

export function modelDisplayName(model: string | { id?: string; name?: string }): string {
  if (typeof model === "string") return model;
  return model.name || model.id || "unnamed";
}
