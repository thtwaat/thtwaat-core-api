/**
 * Agent Builder draft state, steps, validation — frontend-only composition of existing APIs.
 */

export const AGENT_BUILDER_STEPS = [
  { id: 1, key: "template", title: "Choose Template", short: "Template" },
  { id: 2, key: "basic", title: "Basic Info", short: "Basic" },
  { id: 3, key: "knowledge", title: "Knowledge", short: "Knowledge" },
  { id: 4, key: "provider", title: "AI Provider", short: "Provider" },
  { id: 5, key: "capabilities", title: "Capabilities", short: "Capabilities" },
  { id: 6, key: "appearance", title: "Appearance", short: "Appearance" },
  { id: 7, key: "publish", title: "Publish", short: "Publish" }
] as const;

export type AgentBuilderStepId = (typeof AGENT_BUILDER_STEPS)[number]["id"];

export type AgentBuilderCapability = {
  rag: boolean;
  tools: boolean;
  memory: boolean;
  handoff: boolean;
};

export type AgentBuilderWidget = {
  theme: "light" | "dark";
  primary_color: string;
  welcome_message: string;
  position: "bottom-right" | "bottom-left";
  agent_name: string;
  suggested_prompts: string[];
};

export type AgentBuilderDraft = {
  version: 1;
  step: AgentBuilderStepId;
  updatedAt: string;
  templateSlug: string | null;
  templateName: string | null;
  name: string;
  description: string;
  system_prompt_template: string;
  temperature: number;
  knowledgeBaseId: string | null;
  knowledgeBaseName: string | null;
  provider: "auto" | "ollama" | "openai" | "gemini" | "anthropic";
  model: string;
  capabilities: AgentBuilderCapability;
  widget: AgentBuilderWidget;
  /** Set after create — no update API, so core fields freeze */
  agentId: string | null;
  published: boolean;
};

export const DRAFT_STORAGE_KEY = "tht_agent_builder_draft_v1";

export function defaultAgentBuilderDraft(): AgentBuilderDraft {
  return {
    version: 1,
    step: 1,
    updatedAt: new Date().toISOString(),
    templateSlug: null,
    templateName: null,
    name: "",
    description: "",
    system_prompt_template:
      "You are a helpful AI assistant for our product. Be concise, accurate, and friendly.",
    temperature: 0.7,
    knowledgeBaseId: null,
    knowledgeBaseName: null,
    provider: "auto",
    model: "",
    capabilities: {
      rag: true,
      tools: false,
      memory: false,
      handoff: false
    },
    widget: {
      theme: "light",
      primary_color: "#0f766e",
      welcome_message: "Hi! How can I help you today?",
      position: "bottom-right",
      agent_name: "",
      suggested_prompts: ["What can you do?", "Talk to a human"]
    },
    agentId: null,
    published: false
  };
}

export function loadAgentBuilderDraft(): AgentBuilderDraft | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(DRAFT_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AgentBuilderDraft;
    if (parsed?.version !== 1) return null;
    return { ...defaultAgentBuilderDraft(), ...parsed, widget: { ...defaultAgentBuilderDraft().widget, ...parsed.widget }, capabilities: { ...defaultAgentBuilderDraft().capabilities, ...parsed.capabilities } };
  } catch {
    return null;
  }
}

export function saveAgentBuilderDraft(draft: AgentBuilderDraft): void {
  if (typeof window === "undefined") return;
  const next = { ...draft, updatedAt: new Date().toISOString() };
  window.localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(next));
}

export function clearAgentBuilderDraft(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(DRAFT_STORAGE_KEY);
}

export function prefillFromTemplate(
  draft: AgentBuilderDraft,
  template: {
    slug: string;
    name: string;
    description?: string;
    default_config?: Record<string, unknown> | null;
  }
): AgentBuilderDraft {
  const cfg = template.default_config || {};
  const prompt =
    (typeof cfg.prompt === "string" && cfg.prompt) ||
    (typeof cfg.system_prompt_template === "string" && cfg.system_prompt_template) ||
    draft.system_prompt_template;
  const temperature =
    typeof cfg.temperature === "number" ? cfg.temperature : draft.temperature;
  const provider =
    typeof cfg.provider === "string"
      ? (cfg.provider as AgentBuilderDraft["provider"])
      : draft.provider;
  const model = typeof cfg.model === "string" ? cfg.model : draft.model;

  return {
    ...draft,
    templateSlug: template.slug,
    templateName: template.name,
    name: draft.name || template.name,
    description: draft.description || template.description || "",
    system_prompt_template: prompt,
    temperature,
    provider: ["auto", "ollama", "openai", "gemini", "anthropic"].includes(provider)
      ? provider
      : "auto",
    model,
    widget: {
      ...draft.widget,
      agent_name: draft.widget.agent_name || template.name,
      welcome_message:
        (typeof cfg.welcome_message === "string" && cfg.welcome_message) ||
        draft.widget.welcome_message
    },
    step: 2
  };
}

export type StepValidation = { ok: boolean; errors: string[] };

export function validateAgentBuilderStep(
  step: AgentBuilderStepId,
  draft: AgentBuilderDraft
): StepValidation {
  const errors: string[] = [];
  if (step === 1) {
    // Template optional — blank start allowed
  }
  if (step === 2) {
    if (draft.name.trim().length < 2) errors.push("Name must be at least 2 characters");
    if (draft.system_prompt_template.trim().length < 10) {
      errors.push("System prompt must be at least 10 characters");
    }
    if (draft.temperature < 0 || draft.temperature > 2) {
      errors.push("Temperature must be between 0 and 2");
    }
  }
  if (step === 4) {
    if (!["auto", "ollama", "openai", "gemini", "anthropic"].includes(draft.provider)) {
      errors.push("Choose a valid AI provider");
    }
    if (draft.provider !== "auto" && !draft.model.trim()) {
      errors.push("Select a model for the chosen provider");
    }
  }
  if (step === 6) {
    if (!draft.widget.welcome_message.trim()) errors.push("Welcome message is required");
    if (!/^#[0-9A-Fa-f]{6}$/.test(draft.widget.primary_color)) {
      errors.push("Primary color must be a hex value like #0f766e");
    }
  }
  if (step === 7) {
    const basic = validateAgentBuilderStep(2, draft);
    const provider = validateAgentBuilderStep(4, draft);
    errors.push(...basic.errors, ...provider.errors);
  }
  return { ok: errors.length === 0, errors };
}

export function buildAgentCreatePayload(draft: AgentBuilderDraft): Record<string, unknown> {
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
    name: draft.name.trim(),
    description: draft.description.trim() || undefined,
    system_prompt_template: draft.system_prompt_template.trim(),
    temperature: draft.temperature,
    web_config: {
      provider,
      model,
      routing: draft.provider === "auto" ? "auto" : "explicit",
      capabilities: draft.capabilities,
      widget: {
        theme: draft.widget.theme,
        primary_color: draft.widget.primary_color,
        welcome_message: draft.widget.welcome_message,
        position: draft.widget.position,
        agent_name: draft.widget.agent_name || draft.name.trim(),
        suggested_prompts: draft.widget.suggested_prompts.filter(Boolean),
        border_radius: "16px"
      }
    }
  };
}

export function stepProgressPercent(step: AgentBuilderStepId): number {
  return Math.round((step / AGENT_BUILDER_STEPS.length) * 100);
}

export function docStatusTone(status?: string | null): "success" | "warn" | "danger" | "neutral" | "brand" {
  const s = (status || "ready").toLowerCase();
  if (s === "ready" || s === "indexed" || s === "completed") return "success";
  if (s === "processing" || s === "indexing" || s === "pending" || s === "queued") return "warn";
  if (s === "failed" || s === "error") return "danger";
  return "neutral";
}
