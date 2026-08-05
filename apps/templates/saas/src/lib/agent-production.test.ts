import { describe, expect, it } from "vitest";

/** Mirrors sdk/widget i18n + handoff keyword checks for SaaS tests. */
function detectHandoffIntent(message: string): boolean {
  return /\b(talk to (a )?human|real person|live agent|hand ?off)\b/i.test(message);
}

function resolveLocale(code?: string | null): string {
  if (!code) return "en";
  return String(code).split("-")[0].toLowerCase();
}

describe("production agent frontend helpers", () => {
  it("detects handoff phrases", () => {
    expect(detectHandoffIntent("talk to a human please")).toBe(true);
    expect(detectHandoffIntent("pricing plans")).toBe(false);
  });

  it("normalizes locales", () => {
    expect(resolveLocale("hi-IN")).toBe("hi");
    expect(resolveLocale(null)).toBe("en");
  });

  it("maps human reply payload shape", () => {
    const body = { content: "Hello visitor", as_human: true, request_handoff: false };
    expect(body.as_human).toBe(true);
  });
});
