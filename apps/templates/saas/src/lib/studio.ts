/** THTWAAT Studio helpers — prompts + Product Blueprint architect. */

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

export type ProductBlueprint = {
  industry: string;
  product_type: string;
  target_users: string[];
  pages: string[];
  dashboard_modules: string[];
  backend_modules: string[];
  database_tables: string[];
  roles: string[];
  permissions: string[];
  authentication: Record<string, unknown>;
  billing: Record<string, unknown>;
  payments: Record<string, unknown>;
  ai_features: string[];
  knowledge: Record<string, unknown>;
  workflows: string[];
  integrations: string[];
  deployment: Record<string, unknown>;
  marketplace_category: string;
  estimated_complexity: string;
  estimated_build_time: string;
};

export type BlueprintWarning = {
  code: string;
  severity: "info" | "warn" | "error" | string;
  message: string;
  field?: string | null;
};

export type BlueprintRecommendations = {
  templates: string[];
  marketplace_assets: string[];
  agents: string[];
  knowledge_packs: string[];
  integrations: string[];
};

export type StudioBlueprint = {
  id: string;
  project_id: string;
  workspace_id: string;
  version: number;
  is_current: boolean;
  source: string;
  blueprint: ProductBlueprint;
  warnings: BlueprintWarning[];
  recommendations: BlueprintRecommendations;
  created_at: string;
  updated_at: string;
};

export type StudioBlueprintVersionSummary = {
  id: string;
  version: number;
  is_current: boolean;
  source: string;
  created_at: string;
  warning_count: number;
};

export type StudioBlueprintVersionList = {
  items: StudioBlueprintVersionSummary[];
  current_version?: number | null;
};

export type StudioAnalyzeResult = {
  project: StudioProject;
  blueprint: StudioBlueprint;
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

export function warningTone(severity: string): "neutral" | "success" | "warn" | "danger" {
  if (severity === "error") return "danger";
  if (severity === "warn") return "warn";
  return "neutral";
}

export function deriveStudioTitle(prompt: string): string {
  const line = prompt.trim().split(/\r?\n/)[0]?.trim() || "Untitled product";
  return line.length > 80 ? `${line.slice(0, 77)}...` : line;
}

export function parseListField(raw: string): string[] {
  return raw
    .split(/[\n,]/)
    .map((s) => s.trim())
    .filter(Boolean);
}

export function listFieldToText(items: string[] | undefined): string {
  return (items || []).join("\n");
}

export const STUDIO_PROMPT_PLACEHOLDER =
  "Create a Hospital Management SaaS with AI appointment booking, billing, admin dashboard and website.";

export const STUDIO_TIPS = [
  "Describe industry, users, and must-have modules in one paragraph.",
  "Mention AI features (chat, RAG, booking) if you need an agent.",
  "Generate Blueprint analyzes via AI Gateway (with heuristic fallback).",
  "Edit pages/tables/roles, then save — each save creates a new version."
];

export const EMPTY_BLUEPRINT: ProductBlueprint = {
  industry: "general",
  product_type: "saas",
  target_users: [],
  pages: [],
  dashboard_modules: [],
  backend_modules: [],
  database_tables: [],
  roles: [],
  permissions: [],
  authentication: {},
  billing: {},
  payments: {},
  ai_features: [],
  knowledge: {},
  workflows: [],
  integrations: [],
  deployment: {},
  marketplace_category: "saas",
  estimated_complexity: "medium",
  estimated_build_time: "2-4 weeks"
};
