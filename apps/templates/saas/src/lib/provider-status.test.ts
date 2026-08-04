import { describe, expect, it } from "vitest";
import {
  mergeProviderRows,
  modelDisplayName,
  normalizeProviderHealth,
  providerHealthLabel,
  providerHealthTone
} from "./provider-status";

describe("provider-status helpers", () => {
  it("normalizes blank health to unknown", () => {
    expect(normalizeProviderHealth(undefined)).toBe("unknown");
    expect(normalizeProviderHealth("  Configured ")).toBe("configured");
  });

  it("maps health tones for badges", () => {
    expect(providerHealthTone("configured")).toBe("success");
    expect(providerHealthTone("unconfigured")).toBe("warn");
    expect(providerHealthTone("error")).toBe("danger");
    expect(providerHealthTone("weird")).toBe("neutral");
  });

  it("labels health for display", () => {
    expect(providerHealthLabel("configured")).toBe("Configured");
    expect(providerHealthLabel("unconfigured")).toBe("Not configured");
    expect(providerHealthLabel("error")).toBe("Error");
  });

  it("merges provider list with health and default flag", () => {
    const rows = mergeProviderRows(
      ["openai", "ollama"],
      { openai: "configured", ollama: "unconfigured" },
      "openai"
    );
    expect(rows).toEqual([
      { name: "openai", status: "configured", isDefault: true },
      { name: "ollama", status: "unconfigured", isDefault: false }
    ]);
  });

  it("falls back to health keys when provider list empty", () => {
    const rows = mergeProviderRows([], { gemini: "error" }, "gemini");
    expect(rows[0]?.name).toBe("gemini");
    expect(rows[0]?.isDefault).toBe(true);
  });

  it("formats model display names", () => {
    expect(modelDisplayName("gpt-4o")).toBe("gpt-4o");
    expect(modelDisplayName({ id: "m1", name: "Model One" })).toBe("Model One");
    expect(modelDisplayName({ id: "m2" })).toBe("m2");
  });
});
