import { describe, expect, it } from "vitest";
import {
  AGENT_STARTERS,
  ONBOARDING_UI_STEPS,
  buildGeneratePrompt,
  checklistFromSession,
  defaultOnboardingDraft,
  nextUiStep,
  onboardingProgressPercent,
  prevUiStep,
  sessionStepDone,
  slugifyCompanyName,
  starterPrompt,
  uiStepFromBackendCurrent,
  validateOnboardingUiStep
} from "./onboarding";

describe("onboarding wizard helpers", () => {
  it("defines seven UI steps", () => {
    expect(ONBOARDING_UI_STEPS).toHaveLength(7);
    expect(ONBOARDING_UI_STEPS[0].key).toBe("welcome");
    expect(ONBOARDING_UI_STEPS[6].key).toBe("finish");
  });

  it("navigates forward and back", () => {
    expect(nextUiStep(1)).toBe(2);
    expect(nextUiStep(7)).toBeNull();
    expect(prevUiStep(1)).toBeNull();
    expect(prevUiStep(3)).toBe(2);
  });

  it("computes progress percent", () => {
    expect(onboardingProgressPercent(1)).toBe(14);
    expect(onboardingProgressPercent(7)).toBe(100);
  });

  it("validates workspace and agent steps", () => {
    const draft = defaultOnboardingDraft();
    expect(validateOnboardingUiStep(2, draft).ok).toBe(false);
    draft.displayName = "Acme";
    expect(validateOnboardingUiStep(2, draft).ok).toBe(true);
    draft.agentStarterId = "";
    expect(validateOnboardingUiStep(4, draft).ok).toBe(false);
    draft.agentStarterId = "faq-bot";
    expect(validateOnboardingUiStep(4, draft).ok).toBe(true);
  });

  it("maps backend current_step to UI steps", () => {
    expect(uiStepFromBackendCurrent("verify_email")).toBe(1);
    expect(uiStepFromBackendCurrent("create_company")).toBe(2);
    expect(uiStepFromBackendCurrent("choose_plan")).toBe(3);
    expect(uiStepFromBackendCurrent("create_ai_agent")).toBe(4);
    expect(uiStepFromBackendCurrent("upload_knowledge")).toBe(5);
    expect(uiStepFromBackendCurrent("publish")).toBe(6);
    expect(uiStepFromBackendCurrent("go_live")).toBe(7);
  });

  it("detects completed or skipped backend steps", () => {
    expect(
      sessionStepDone(
        { completed_steps: ["create_company"], skipped_steps: ["upload_knowledge"] },
        "upload_knowledge"
      )
    ).toBe(true);
    expect(sessionStepDone({ completed_steps: [], skipped_steps: [] }, "publish")).toBe(false);
  });

  it("builds checklist from session resources", () => {
    const checklist = checklistFromSession({
      completed_steps: ["create_company", "choose_plan", "create_ai_agent"],
      skipped_steps: ["upload_knowledge"],
      resource_ids: { publish_status: "PUBLISHED" }
    });
    expect(checklist.workspace).toBe(true);
    expect(checklist.provider).toBe(true);
    expect(checklist.agent).toBe(true);
    expect(checklist.knowledge).toBe(true);
    expect(checklist.widget).toBe(true);
  });

  it("exposes starter templates and prompts", () => {
    expect(AGENT_STARTERS.map((s) => s.id)).toContain("customer-support");
    expect(starterPrompt("blank")).toMatch(/helpful AI assistant/i);
    const draft = defaultOnboardingDraft();
    draft.displayName = "Acme";
    draft.agentStarterId = "sales-assistant";
    expect(buildGeneratePrompt(draft)).toContain("Sales Assistant");
    expect(buildGeneratePrompt(draft)).toContain("Acme");
  });

  it("slugifies company names", () => {
    expect(slugifyCompanyName("Acme AI!")).toBe("acme-ai");
    expect(slugifyCompanyName("   ")).toBe("workspace");
  });
});
