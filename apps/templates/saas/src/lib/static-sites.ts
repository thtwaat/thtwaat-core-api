// THTWAAT Deploy — static HTML/ZIP website hosting types.
// Sibling to lib/studio.ts (AI-generated products); a separate, simpler
// entity for uploaded static sites — see app/static_sites on the backend.

export type StaticSite = {
  id: string;
  workspace_id: string;
  name: string;
  slug: string;
  created_at: string;
  updated_at: string;
};

export type StaticSiteList = {
  items: StaticSite[];
  total: number;
};

export type StaticSiteDeploymentStatus =
  | "queued"
  | "validating"
  | "runtime_starting"
  | "provisioning_ssl"
  | "completed"
  | "failed";

export type ProjectFramework = "static_html" | "static_zip" | "vite" | "nextjs";

export type RuntimeType = "static" | "node";

export type StaticSiteDeployment = {
  id: string;
  site_id: string;
  version: number;
  is_current: boolean;
  provider: string;
  status: StaticSiteDeploymentStatus | string;
  stage: string;
  source_type: "html" | "zip" | string;
  // THTWAAT Deploy Phase 5C — "upload" (manual HTML/ZIP, the only value
  // before this phase) or "github" (auto-deployed from a connected
  // repository's pinned commit — see GitHubPanel.tsx's Auto Deploy status).
  source_provider?: "upload" | "github" | string;
  github_repository_owner?: string | null;
  github_repository_name?: string | null;
  github_commit_sha?: string | null;
  github_branch?: string | null;
  framework?: ProjectFramework | string | null;
  upload_filename?: string | null;
  // THTWAAT Phase 3 — Next.js. runtime_type is "static" (nginx serves files
  // directly, the only mode before this phase) or "node" (nginx proxies to
  // an isolated runtime container). runtime_container_id/internal_port are
  // internal/debug fields; health_status tracks the last runtime health probe.
  runtime_type?: RuntimeType | string | null;
  runtime_container_id?: string | null;
  internal_port?: number | null;
  health_status?: "pending" | "healthy" | "unhealthy" | "stopped" | string | null;
  domain?: string | null;
  subdomain?: string | null;
  environment: string;
  live: boolean;
  urls: Record<string, string>;
  health: Record<string, unknown>;
  ssl: Record<string, unknown>;
  instructions: unknown[];
  logs: Array<{ stage?: string; message?: string; event?: string }>;
  file_count: number;
  total_bytes: number;
  duration_ms: number;
  error?: string | null;
  retryable: boolean;
  rollback_of?: string | null;
  created_at: string;
  updated_at: string;
};

export type StaticSiteDeploymentList = {
  items: StaticSiteDeployment[];
  total: number;
};

export function staticDeployStatusLabel(status: string): string {
  switch (status) {
    case "queued":
      return "Queued";
    case "validating":
      return "Validating";
    case "runtime_starting":
      return "Starting runtime";
    case "provisioning_ssl":
      return "Provisioning SSL";
    case "completed":
      return "Live";
    case "failed":
      return "Failed";
    default:
      return status;
  }
}

export function frameworkLabel(framework?: string | null): string | null {
  switch (framework) {
    case "vite":
      return "Vite";
    case "nextjs":
      return "Next.js";
    case "static_html":
    case "static_zip":
      return "Static HTML";
    default:
      return null;
  }
}

export function runtimeLabel(runtimeType?: string | null): string {
  return runtimeType === "node" ? "Node.js" : "Static";
}

export function staticDeployStatusTone(status: string): "success" | "warn" | "danger" | "neutral" {
  if (status === "completed") return "success";
  if (status === "failed") return "danger";
  if (status === "queued" || status === "validating" || status === "runtime_starting" || status === "provisioning_ssl") return "warn";
  return "neutral";
}

// THTWAAT Phase 3 — deployment pipeline steps shown in the UI for a Next.js
// deployment (Build -> Runtime -> Health -> Domain -> SSL -> LIVE). Static
// deployments never show the "Runtime" step (see StaticDeployPanel.tsx).
export const NEXTJS_PIPELINE_STAGES = [
  { key: "building", label: "Build" },
  { key: "runtime_starting", label: "Runtime" },
  { key: "health_check", label: "Health" },
  { key: "domain", label: "Domain" },
  { key: "ssl", label: "SSL" },
  { key: "completed", label: "Live" },
] as const;
