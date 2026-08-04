/**
 * First-time onboarding wizard — frontend composition over /api/v1/onboarding/*
 * UI is 7 steps; backend remains the canonical 12-step facade.
 */

export const ONBOARDING_UI_STEPS = [
  { id: 1, key: "welcome", title: "Welcome", short: "Welcome" },
  { id: 2, key: "workspace", title: "Workspace", short: "Workspace" },
  { id: 3, key: "provider", title: "AI Provider", short: "Provider" },
  { id: 4, key: "agent", title: "First Agent", short: "Agent" },
  { id: 5, key: "knowledge", title: "Knowledge", short: "Knowledge" },
  { id: 6, key: "widget", title: "Website Widget", short: "Widget" },
  { id: 7, key: "finish", title: "Finish", short: "Finish" }
] as const;

export type OnboardingUiStepId = (typeof ONBOARDING_UI_STEPS)[number]["id"];

export const AGENT_STARTERS = [
  {
    id: "customer-support",
    name: "Customer Support",
    description: "Answer product questions and escalate politely.",
    system_prompt_template:
      "You are a customer support specialist for this company. Be concise, accurate, and empathetic. If you lack information, say so and offer to connect a human."
  },
  {
    id: "sales-assistant",
    name: "Sales Assistant",
    description: "Qualify leads and explain offerings.",
    system_prompt_template:
      "You are a sales assistant. Help visitors understand offerings, capture interest, and suggest next steps without being pushy."
  },
  {
    id: "faq-bot",
    name: "FAQ Bot",
    description: "Short answers from company knowledge.",
    system_prompt_template:
      "You are an FAQ assistant. Prefer short, factual answers from the knowledge base. If unsure, ask a clarifying question."
  },
  {
    id: "website-assistant",
    name: "Website Assistant",
    description: "Guide visitors around the site.",
    system_prompt_template:
      "You are a website assistant. Help visitors navigate the product, find resources, and start the right workflow."
  },
  {
    id: "blank",
    name: "Blank Agent",
    description: "Start with a minimal prompt.",
    system_prompt_template: "You are a helpful AI assistant for this company."
  }
] as const;

export type OnboardingLocalDraft = {
  version: 1;
  uiStep: OnboardingUiStepId;
  updatedAt: string;
  provider: "auto" | "ollama" | "openai" | "gemini" | "anthropic";
  model: string;
  industry: string;
  teamSize: string;
  logoUrl: string;
  displayName: string;
  agentStarterId: string;
  agentName: string;
  skipped: boolean;
  checklist: {
    workspace: boolean;
    provider: boolean;
    agent: boolean;
    knowledge: boolean;
    widget: boolean;
  };
};

export const ONBOARDING_DRAFT_KEY = "tht_onboarding_ui_draft_v1";

export function defaultOnboardingDraft(): OnboardingLocalDraft {
  return {
    version: 1,
    uiStep: 1,
    updatedAt: new Date().toISOString(),
    provider: "auto",
    model: "",
    industry: "",
    teamSize: "",
    logoUrl: "",
    displayName: "",
    agentStarterId: "customer-support",
    agentName: "",
    skipped: false,
    checklist: {
      workspace: false,
      provider: false,
      agent: false,
      knowledge: false,
      widget: false
    }
  };
}

export function loadOnboardingDraft(): OnboardingLocalDraft | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(ONBOARDING_DRAFT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as OnboardingLocalDraft;
    if (parsed?.version !== 1) return null;
    return { ...defaultOnboardingDraft(), ...parsed, checklist: { ...defaultOnboardingDraft().checklist, ...parsed.checklist } };
  } catch {
    return null;
  }
}

export function saveOnboardingDraft(draft: OnboardingLocalDraft): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(
    ONBOARDING_DRAFT_KEY,
    JSON.stringify({ ...draft, updatedAt: new Date().toISOString() })
  );
}

export function clearOnboardingDraft(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(ONBOARDING_DRAFT_KEY);
}

export function slugifyCompanyName(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60) || "workspace";
}

export function onboardingProgressPercent(step: OnboardingUiStepId): number {
  return Math.round((step / ONBOARDING_UI_STEPS.length) * 100);
}

export function validateOnboardingUiStep(
  step: OnboardingUiStepId,
  draft: OnboardingLocalDraft
): { ok: boolean; errors: string[] } {
  const errors: string[] = [];
  if (step === 2) {
    if (draft.displayName.trim().length < 2) errors.push("Company / workspace name is required");
  }
  if (step === 4) {
    if (!draft.agentStarterId) errors.push("Choose a starter template or blank agent");
    if (draft.agentName.trim().length > 0 && draft.agentName.trim().length < 2) {
      errors.push("Agent name must be at least 2 characters");
    }
  }
  return { ok: errors.length === 0, errors };
}

export function starterPrompt(starterId: string): string {
  const row = AGENT_STARTERS.find((s) => s.id === starterId) || AGENT_STARTERS[4];
  return row.system_prompt_template;
}

export function buildAgentWebConfig(draft: OnboardingLocalDraft): Record<string, unknown> {
  const provider = draft.provider === "auto" ? "openai" : draft.provider;
  const model =
    draft.model.trim() ||
    (provider === "ollama"
      ? "llama3.2"
      : provider === "gemini"
        ? "gemini-2.0-flash"
        : provider === "anthropic"
          ? "claude-3-5-sonnet-latest"
          : "gpt-4o-mini");
  return {
    provider,
    model,
    routing: draft.provider === "auto" ? "auto" : "explicit",
    widget: {
      theme: "light",
      primary_color: "#0f766e",
      welcome_message: "Hi! How can I help you today?",
      position: "bottom-right",
      agent_name: draft.agentName || "Assistant"
    }
  };
}

/** Map backend session current_step → recommended UI step */
export function uiStepFromBackendCurrent(current?: string | null): OnboardingUiStepId {
  switch (current) {
    case "verify_email":
    case "create_account":
      return 1;
    case "create_company":
      return 2;
    case "choose_plan":
      return 3;
    case "create_ai_agent":
      return 4;
    case "upload_knowledge":
      return 5;
    case "choose_template":
    case "generate_product":
    case "preview":
    case "publish":
      return 6;
    case "connect_domain":
    case "go_live":
      return 7;
    default:
      return 1;
  }
}

export const INDUSTRY_OPTIONS = [
  "SaaS / Software",
  "E-commerce",
  "Healthcare",
  "Education",
  "Finance",
  "Professional services",
  "Media",
  "Other"
] as const;

export const TEAM_SIZE_OPTIONS = [
  { value: "1", label: "Just me" },
  { value: "2-10", label: "2–10" },
  { value: "11-50", label: "11–50" },
  { value: "51-200", label: "51–200" },
  { value: "200+", label: "200+" }
] as const;

export const ONBOARDING_PROVIDER_OPTIONS = [
  { value: "auto", label: "Auto (recommended)" },
  { value: "ollama", label: "Ollama" },
  { value: "openai", label: "OpenAI" },
  { value: "gemini", label: "Gemini" },
  { value: "anthropic", label: "Anthropic" }
] as const;

export function sessionStepDone(
  session: { completed_steps?: string[]; skipped_steps?: string[] } | null | undefined,
  step: string
): boolean {
  if (!session) return false;
  const done = new Set([...(session.completed_steps || []), ...(session.skipped_steps || [])]);
  return done.has(step);
}

export function buildGeneratePrompt(draft: OnboardingLocalDraft): string {
  const starter = AGENT_STARTERS.find((s) => s.id === draft.agentStarterId);
  const company = draft.displayName.trim() || "our company";
  const role = starter?.name || "Website Assistant";
  return `Build a ${role} for ${company}${draft.industry ? ` in ${draft.industry}` : ""}. Prefer a website chat widget. Keep responses concise and on-brand.`;
}

export function nextUiStep(step: OnboardingUiStepId): OnboardingUiStepId | null {
  if (step >= ONBOARDING_UI_STEPS.length) return null;
  return (step + 1) as OnboardingUiStepId;
}

export function prevUiStep(step: OnboardingUiStepId): OnboardingUiStepId | null {
  if (step <= 1) return null;
  return (step - 1) as OnboardingUiStepId;
}

export function checklistFromSession(session: {
  resource_ids?: Record<string, unknown>;
  completed_steps?: string[];
  skipped_steps?: string[];
} | null): OnboardingLocalDraft["checklist"] {
  const done = new Set([
    ...(session?.completed_steps || []),
    ...(session?.skipped_steps || [])
  ]);
  const resources = session?.resource_ids || {};
  return {
    workspace: done.has("create_company"),
    provider: done.has("choose_plan"),
    agent: done.has("create_ai_agent") || Boolean(resources.agent_id),
    knowledge: done.has("upload_knowledge") || Boolean(resources.knowledge_base_id),
    widget: done.has("publish") || Boolean(resources.publish_status)
  };
}
