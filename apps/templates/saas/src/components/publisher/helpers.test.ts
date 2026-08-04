import { describe, expect, it } from "vitest";
import { slugify, statusBadgeClass } from "./helpers";

describe("publisher portal helpers", () => {
  it("slugifies titles", () => {
    expect(slugify("Hello World Agent!")).toBe("hello-world-agent");
    expect(slugify("  AI---Copilot  ")).toBe("ai-copilot");
  });

  it("maps status badge classes", () => {
    expect(statusBadgeClass("published")).toContain("emerald");
    expect(statusBadgeClass("pending_review")).toContain("amber");
    expect(statusBadgeClass("rejected")).toContain("rose");
    expect(statusBadgeClass("draft")).toContain("slate");
  });
});
