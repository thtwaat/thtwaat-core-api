// THTWAAT Deploy Phase 6A — Preview Deployments types + label/tone mappers.
// Sibling to lib/static-sites.ts, following its exact
// staticDeployStatusLabel/staticDeployStatusTone convention (a small pure
// function per domain mapping a backend status string to a UI label/tone —
// see components/ui/card.tsx's Badge) rather than a new UI primitive.

export type PreviewDeploymentStatus = "queued" | "building" | "ready" | "failed" | "torn_down";

export type PreviewDeployment = {
  id: string;
  site_id: string;
  pr_number: number;
  branch: string;
  base_branch?: string | null;
  github_repository_owner?: string | null;
  github_repository_name?: string | null;
  commit_sha: string;
  generation: number;
  status: PreviewDeploymentStatus | string;
  stage: string;
  hostname?: string | null;
  framework?: string | null;
  runtime_type?: string | null;
  health_status?: string | null;
  urls: Record<string, string>;
  logs: Array<{ stage?: string; message?: string; event?: string }>;
  error?: string | null;
  expires_at?: string | null;
  torn_down_at?: string | null;
  teardown_reason?: string | null;
  created_at: string;
  updated_at: string;
};

export type PreviewDeploymentList = {
  items: PreviewDeployment[];
  page: number;
  per_page: number;
  total: number;
};

export function previewDeployStatusLabel(status: string): string {
  switch (status) {
    case "queued":
      return "Queued";
    case "building":
      return "Building";
    case "ready":
      return "Ready";
    case "failed":
      return "Failed";
    case "torn_down":
      return "Closed";
    default:
      return status;
  }
}

export function previewDeployStatusTone(status: string): "success" | "warn" | "danger" | "neutral" {
  if (status === "ready") return "success";
  if (status === "failed") return "danger";
  if (status === "queued" || status === "building") return "warn";
  return "neutral"; // torn_down
}

export function previewIsActive(preview: PreviewDeployment): boolean {
  return !preview.torn_down_at;
}

export function shortCommit(sha: string): string {
  return (sha || "").slice(0, 12);
}
