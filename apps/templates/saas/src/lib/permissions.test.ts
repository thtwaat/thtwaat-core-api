import { describe, expect, it } from "vitest";
import { canViewProviders, canManageWebhooks } from "./permissions";

describe("canViewProviders", () => {
  it("allows operator roles", () => {
    expect(canViewProviders("company_owner")).toBe(true);
    expect(canViewProviders("admin")).toBe(true);
    expect(canViewProviders("developer")).toBe(true);
    expect(canViewProviders("super_admin")).toBe(true);
  });

  it("denies members and empty", () => {
    expect(canViewProviders("member")).toBe(false);
    expect(canViewProviders(null)).toBe(false);
    expect(canViewProviders(undefined)).toBe(false);
  });

  it("aligns with webhook manage roles", () => {
    for (const role of ["company_owner", "admin", "developer", "member", null]) {
      expect(canViewProviders(role)).toBe(canManageWebhooks(role));
    }
  });
});
