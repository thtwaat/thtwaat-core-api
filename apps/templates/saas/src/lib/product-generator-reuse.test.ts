import { describe, expect, it } from "vitest";
import {
  isAlreadyInstalledGeneration,
  productReuseLinks,
  reuseMessageFor,
  REUSE_EXISTING_TOAST,
} from "./product-generator-reuse";

describe("product-generator-reuse", () => {
  it("detects already_installed from top-level or result payload", () => {
    expect(isAlreadyInstalledGeneration({ already_installed: true })).toBe(true);
    expect(
      isAlreadyInstalledGeneration({ result: { already_installed: true } })
    ).toBe(true);
    expect(isAlreadyInstalledGeneration({ already_installed: false, result: {} })).toBe(
      false
    );
  });

  it("prefers server reuse_message", () => {
    expect(
      reuseMessageFor({
        reuse_message: "Template already installed. Opening your existing AI workspace.",
      })
    ).toContain("Opening your existing AI workspace");
    expect(reuseMessageFor({})).toBe(REUSE_EXISTING_TOAST.replace("\n", " "));
  });

  it("builds workspace deep links without inventing resources", () => {
    const links = productReuseLinks({
      id: "gen-1",
      agent_id: "agent-9",
      knowledge_base_id: "kb-3",
      widget_id: "w_abc",
    });
    expect(links.agentHref).toContain("/app/agents/agent-9");
    expect(links.knowledgeHref).toContain("kb=kb-3");
    expect(links.widgetHref).toContain("tab=widget");
    expect(links.continueHref).toContain("generation=gen-1");
  });
});
