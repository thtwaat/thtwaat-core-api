import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import {
  AGENT_BUILDER_STEPS,
  buildAgentCreatePayload,
  clearAgentBuilderDraft,
  defaultAgentBuilderDraft,
  loadAgentBuilderDraft,
  prefillFromTemplate,
  saveAgentBuilderDraft,
  stepProgressPercent,
  validateAgentBuilderStep
} from "./agent-builder";

describe("agent-builder", () => {
  it("has seven wizard steps", () => {
    expect(AGENT_BUILDER_STEPS).toHaveLength(7);
    expect(AGENT_BUILDER_STEPS[0].key).toBe("template");
    expect(AGENT_BUILDER_STEPS[6].key).toBe("publish");
  });

  it("validates basic info", () => {
    const draft = defaultAgentBuilderDraft();
    expect(validateAgentBuilderStep(2, draft).ok).toBe(false);
    draft.name = "Support";
    draft.system_prompt_template = "You are a helpful support agent for our product.";
    expect(validateAgentBuilderStep(2, draft).ok).toBe(true);
  });

  it("requires model for explicit providers", () => {
    const draft = defaultAgentBuilderDraft();
    draft.provider = "openai";
    draft.model = "";
    expect(validateAgentBuilderStep(4, draft).ok).toBe(false);
    draft.model = "gpt-4o-mini";
    expect(validateAgentBuilderStep(4, draft).ok).toBe(true);
  });

  it("prefills from marketplace template default_config", () => {
    const draft = prefillFromTemplate(defaultAgentBuilderDraft(), {
      slug: "support-agent",
      name: "Support Agent",
      description: "Helps customers",
      default_config: {
        prompt: "You are a customer support specialist.",
        temperature: 0.3,
        provider: "openai",
        model: "gpt-4o-mini"
      }
    });
    expect(draft.templateSlug).toBe("support-agent");
    expect(draft.system_prompt_template).toContain("customer support");
    expect(draft.temperature).toBe(0.3);
    expect(draft.step).toBe(2);
  });

  it("defaults optional voice/vision/image_generation/calling capabilities to false", () => {
    const draft = defaultAgentBuilderDraft();
    expect(draft.capabilities.voice).toBe(false);
    expect(draft.capabilities.vision).toBe(false);
    expect(draft.capabilities.image_generation).toBe(false);
    expect(draft.capabilities.calling).toBe(false);
    // Existing defaults must stay unchanged.
    expect(draft.capabilities.rag).toBe(true);
    expect(draft.capabilities.tools).toBe(false);
    expect(draft.capabilities.memory).toBe(false);
    expect(draft.capabilities.handoff).toBe(false);
  });

  it("serializes toggled optional capabilities into the create payload", () => {
    const draft = defaultAgentBuilderDraft();
    draft.name = "Voice Bot";
    draft.system_prompt_template = "You are a helpful voice assistant.";
    draft.capabilities = {
      ...draft.capabilities,
      voice: true,
      vision: true,
      image_generation: false,
      calling: false
    };
    const web = buildAgentCreatePayload(draft).web_config as Record<string, unknown>;
    const caps = web.capabilities as Record<string, boolean>;
    expect(caps.voice).toBe(true);
    expect(caps.vision).toBe(true);
    expect(caps.image_generation).toBe(false);
    expect(caps.calling).toBe(false);
  });

  it("builds create payload with web_config provider and widget", () => {
    const draft = defaultAgentBuilderDraft();
    draft.name = "Bot";
    draft.system_prompt_template = "You are a helpful product assistant.";
    draft.provider = "gemini";
    draft.model = "gemini-2.0-flash";
    draft.capabilities.rag = true;
    const payload = buildAgentCreatePayload(draft);
    expect(payload.name).toBe("Bot");
    const web = payload.web_config as Record<string, unknown>;
    expect(web.provider).toBe("gemini");
    expect(web.model).toBe("gemini-2.0-flash");
    expect((web.widget as Record<string, unknown>).primary_color).toBe("#0f766e");
  });

  it("maps auto provider to openai default model in payload", () => {
    const draft = defaultAgentBuilderDraft();
    draft.name = "AutoBot";
    draft.system_prompt_template = "You are a helpful product assistant.";
    draft.provider = "auto";
    const web = buildAgentCreatePayload(draft).web_config as Record<string, unknown>;
    expect(web.routing).toBe("auto");
    expect(web.provider).toBe("openai");
  });

  it("computes progress percent", () => {
    expect(stepProgressPercent(1)).toBe(14);
    expect(stepProgressPercent(7)).toBe(100);
  });

  describe("draft persistence (New agent must never resume another agent's draft)", () => {
    const store = new Map<string, string>();

    beforeEach(() => {
      store.clear();
      const localStorage = {
        getItem: (k: string) => store.get(k) ?? null,
        setItem: (k: string, v: string) => {
          store.set(k, v);
        },
        removeItem: (k: string) => {
          store.delete(k);
        }
      };
      // agent-builder.ts guards on `typeof window === "undefined"` and reads
      // window.localStorage, so both window and localStorage need stubbing here.
      vi.stubGlobal("window", { localStorage });
      vi.stubGlobal("localStorage", localStorage);
    });

    afterEach(() => {
      vi.unstubAllGlobals();
    });

    it("never carries a real agentId in a fresh default draft", () => {
      expect(defaultAgentBuilderDraft().agentId).toBeNull();
    });

    it("clearing a draft that was tied to a previously created agent removes it entirely", () => {
      const published = {
        ...defaultAgentBuilderDraft(),
        name: "Viral Awaaz Assistant",
        agentId: "agent-viral-awaaz-123",
        published: true
      };
      saveAgentBuilderDraft(published);
      expect(loadAgentBuilderDraft()?.agentId).toBe("agent-viral-awaaz-123");

      clearAgentBuilderDraft();

      expect(loadAgentBuilderDraft()).toBeNull();
    });
  });
});
