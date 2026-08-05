/** THTWAAT Studio helpers (Phase 1 — prompts only). */

export type StudioProjectStatus =
  | "draft"
  | "analyzing"
  | "blueprint_ready"
  | "approved"
  | "building"
  | "completed"
  | "failed";

export type StudioProject = {
  id: string;
  workspace_id: string;
  user_id?: string | null;
  title: string;
  prompt: string;
  status: StudioProjectStatus;
  created_at: string;
  updated_at: string;
};

export type StudioProjectList = {
  items: StudioProject[];
  total: number;
};

const STATUS_LABELS: Record<StudioProjectStatus, string> = {
  draft: "Draft",
  analyzing: "Analyzing",
  blueprint_ready: "Blueprint ready",
  approved: "Approved",
  building: "Building",
  completed: "Completed",
  failed: "Failed"
};

export function studioStatusLabel(status: StudioProjectStatus | string): string {
  return STATUS_LABELS[status as StudioProjectStatus] || String(status);
}

export function studioStatusTone(
  status: StudioProjectStatus | string
): "neutral" | "success" | "warn" | "danger" {
  if (status === "completed" || status === "blueprint_ready" || status === "approved") {
    return "success";
  }
  if (status === "failed") return "danger";
  if (status === "building" || status === "analyzing") return "warn";
  return "neutral";
}

export function deriveStudioTitle(prompt: string): string {
  const line = prompt.trim().split(/\r?\n/)[0]?.trim() || "Untitled product";
  return line.length > 80 ? `${line.slice(0, 77)}...` : line;
}

export const STUDIO_PROMPT_PLACEHOLDER =
  "Create a Hospital Management SaaS with AI appointment booking, billing, admin dashboard and website.";

export const STUDIO_TIPS = [
  "Describe industry, users, and must-have modules in one paragraph.",
  "Mention AI features (chat, RAG, booking) if you need an agent.",
  "Phase 1 saves your prompt — blueprint generation comes next.",
  "Reuse Marketplace templates later instead of reinventing CRUD screens."
];
