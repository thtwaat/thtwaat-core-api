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

export type ModuleKind = "existing_module" | "marketplace_template" | "custom_module";

export type ComposedModule = {
  key: string;
  label: string;
  kind: ModuleKind;
  platform_ref?: string | null;
  marketplace_template?: string | null;
  depends_on: string[];
  reason: string;
  custom_effort: string;
  category: string;
};

export type DependencyEdge = {
  key: string;
  label: string;
  depends_on: string[];
};

export type BuildPlanStep = {
  order: number;
  key: string;
  label: string;
  phase: string;
  kind: ModuleKind;
  depends_on: string[];
  platform_ref?: string | null;
  marketplace_template?: string | null;
  note?: string | null;
};

export type BuildPlanSummary = {
  reuse_percent: number;
  existing_count: number;
  marketplace_count: number;
  custom_count: number;
  module_count: number;
  estimated_custom_work: string;
  warnings: BlueprintWarning[];
};

export type StudioBuildPlan = {
  id: string;
  project_id: string;
  workspace_id: string;
  blueprint_version: number;
  version: number;
  is_current: boolean;
  modules: ComposedModule[];
  dependency_graph: DependencyEdge[];
  dependency_tree: Array<{
    key: string;
    label: string;
    kind: string;
    children?: unknown[];
  }>;
  build_plan: BuildPlanStep[];
  summary: BuildPlanSummary;
  created_at: string;
  updated_at: string;
};

export type StudioComposeResult = {
  project: StudioProject;
  build_plan: StudioBuildPlan;
};

export type FrontendFormField = {
  name: string;
  type: string;
  required: boolean;
  label: string;
  list_column?: boolean;
};

export type FrontendNavItem = {
  id: string;
  label: string;
  route: string;
  icon: string;
  page_id: string;
  reuse: boolean;
};

export type FrontendRoute = {
  path: string;
  page_id: string;
  layout: string;
  auth: string;
  reuse: boolean;
};

export type FrontendPageSpec = {
  id: string;
  title: string;
  kind: "reuse" | "generated_spec" | string;
  route: string;
  layout: string;
  auth: string;
  module_key?: string | null;
  reuse?: {
    kind: string;
    path: string;
    route?: string | null;
    module_key?: string | null;
  } | null;
  reason: string;
  responsive: boolean;
  cards: Array<Record<string, unknown>>;
  crud?: {
    entity: string;
    table: string;
    operations: string[];
    fields: FrontendFormField[];
    table_columns: string[];
  } | null;
  layout_slots?: string[];
  preview: Record<string, unknown>;
};

export type FrontendManifest = {
  schema_version: number;
  product_name: string;
  industry: string;
  product_type: string;
  theme: Record<string, unknown>;
  layouts: Array<Record<string, unknown>>;
  design_system: Record<string, string>;
  nav: FrontendNavItem[];
  routes: FrontendRoute[];
  pages: FrontendPageSpec[];
  forms: Array<Record<string, unknown>>;
  dashboard_cards: Array<Record<string, unknown>>;
  responsive: Record<string, unknown>;
  summary: {
    page_count: number;
    reuse_page_count: number;
    generated_page_count: number;
    nav_item_count: number;
    route_count: number;
    form_count: number;
    reuse_percent: number;
    estimated_custom_work: string;
    warnings: BlueprintWarning[];
  };
  traceability: Record<string, unknown>;
  warnings: BlueprintWarning[];
};

export type StudioFrontend = {
  id: string;
  project_id: string;
  workspace_id: string;
  blueprint_version: number;
  build_plan_version: number;
  version: number;
  is_current: boolean;
  status: string;
  manifest: FrontendManifest;
  created_at: string;
  updated_at: string;
};

export type StudioFrontendGenerateResult = {
  project: StudioProject;
  frontend: StudioFrontend;
};

export type BackendApiEndpoint = {
  id: string;
  method: string;
  path: string;
  resource: string;
  operation: string;
  summary: string;
  permissions: string[];
  validation: Record<string, unknown>;
  filters: string[];
  pagination: boolean;
  search: boolean;
  upload: boolean;
  reuse: boolean;
  module_key?: string | null;
  platform_ref?: string | null;
  tags: string[];
};

export type BackendManifest = {
  schema_version: number;
  product_name: string;
  industry: string;
  product_type: string;
  api: {
    endpoints: BackendApiEndpoint[];
    resource_count: number;
    reuse_endpoint_count: number;
    custom_endpoint_count: number;
  };
  database: {
    tables: Array<{
      name: string;
      reuse: boolean;
      module_key?: string | null;
      columns: Array<{ name: string; type: string; primary_key?: boolean }>;
      migration: string;
    }>;
    relationships: Array<{
      from_table: string;
      to_table: string;
      type: string;
      foreign_key: string;
    }>;
    enums: Array<Record<string, unknown>>;
    migrations: string[];
    reuse_table_count: number;
    custom_table_count: number;
  };
  services: Array<{
    id: string;
    name: string;
    kind: string;
    reuse: boolean;
    capabilities: string[];
  }>;
  rbac: {
    roles: string[];
    permissions: string[];
    policies: Array<Record<string, unknown>>;
    reuse: boolean;
    platform_ref: string;
    note: string;
  };
  storage: Array<{ id: string; kind: string; path: string; reuse: boolean }>;
  queues: Array<{ id: string; name: string; kind: string; reuse: boolean; workers: string[] }>;
  openapi: {
    openapi: string;
    info: Record<string, unknown>;
    paths: Record<string, unknown>;
    components: Record<string, unknown>;
  };
  summary: {
    endpoint_count: number;
    table_count: number;
    service_count: number;
    role_count: number;
    storage_item_count: number;
    queue_count: number;
    reuse_percent: number;
    estimated_custom_work: string;
    warnings: BlueprintWarning[];
  };
  traceability: Record<string, unknown>;
  warnings: BlueprintWarning[];
  note: string;
};

export type StudioBackend = {
  id: string;
  project_id: string;
  workspace_id: string;
  blueprint_version: number;
  build_plan_version: number;
  frontend_version: number;
  version: number;
  is_current: boolean;
  status: string;
  manifest: BackendManifest;
  created_at: string;
  updated_at: string;
};

export type StudioBackendGenerateResult = {
  project: StudioProject;
  backend: StudioBackend;
};

export function moduleKindLabel(kind: ModuleKind | string): string {
  if (kind === "existing_module") return "Existing";
  if (kind === "marketplace_template") return "Marketplace";
  if (kind === "custom_module") return "Custom";
  return String(kind);
}

export function moduleKindTone(
  kind: ModuleKind | string
): "neutral" | "success" | "warn" | "danger" {
  if (kind === "existing_module") return "success";
  if (kind === "marketplace_template") return "neutral";
  if (kind === "custom_module") return "warn";
  return "neutral";
}

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
  "Generate Blueprint uses the AI Gateway first; heuristic only if AI fails.",
  "Compose Modules maps the blueprint to Auth, Billing, AI, Marketplace — no codegen yet.",
  "Generate Frontend builds a preview manifest that reuses Dashboard, Auth, Billing, Agents, and Admin UI.",
  "Generate Backend builds API/DB/RBAC/queue manifests — reuses platform modules, no source yet.",
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
