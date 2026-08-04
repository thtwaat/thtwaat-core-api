import { describe, expect, it } from "vitest";
import {
  COMPANY_PLAN_OPTIONS,
  SUPER_ADMIN_NAV,
  formatRevenue,
  healthComponentStatus,
  healthTone,
  planLabel
} from "./super-admin";

describe("super-admin helpers", () => {
  it("exposes five console nav items including /admin", () => {
    expect(SUPER_ADMIN_NAV).toHaveLength(5);
    expect(SUPER_ADMIN_NAV[0].href).toBe("/admin");
    expect(SUPER_ADMIN_NAV.map((n) => n.href)).toContain("/admin/companies");
  });

  it("maps growth plan to Pro label", () => {
    expect(COMPANY_PLAN_OPTIONS.find((p) => p.value === "growth")?.label).toBe("Pro");
    expect(planLabel("growth")).toBe("Pro");
    expect(planLabel("free")).toBe("Free");
  });

  it("normalizes health component status", () => {
    expect(healthComponentStatus({ status: "OK" })).toBe("ok");
    expect(healthComponentStatus({ ok: true })).toBe("ok");
    expect(healthComponentStatus({ ok: false })).toBe("error");
    expect(healthTone("healthy")).toBe("success");
    expect(healthTone("down")).toBe("danger");
  });

  it("formats revenue", () => {
    expect(formatRevenue(1200)).toMatch(/1,200/);
    expect(formatRevenue(null)).toBe("—");
  });
});
