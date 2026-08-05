import { describe, expect, it } from "vitest";
import {
  COMPANY_PLAN_OPTIONS,
  LOG_CATEGORIES,
  SUPER_ADMIN_NAV,
  formatPct,
  formatRevenue,
  healthComponentStatus,
  healthTone,
  planLabel
} from "./super-admin";

describe("super-admin helpers", () => {
  it("exposes enterprise ops nav including AI, logs, marketplace", () => {
    expect(SUPER_ADMIN_NAV.length).toBeGreaterThanOrEqual(8);
    expect(SUPER_ADMIN_NAV[0].href).toBe("/admin");
    const hrefs = SUPER_ADMIN_NAV.map((n) => n.href);
    expect(hrefs).toContain("/admin/companies");
    expect(hrefs).toContain("/admin/ai");
    expect(hrefs).toContain("/admin/audit");
    expect(hrefs).toContain("/admin/marketplace");
    expect(hrefs).toContain("/admin/operations");
    expect(hrefs).toContain("/admin/health");
  });

  it("supports dashboard KPI aliases for enterprise labels", () => {
    const kpi = {
      active_companies: 12,
      global_revenue: 5000,
      monthly_revenue: 800,
      failed_payments: 3,
      provider_cost: 42,
      ai_usage: 900
    };
    expect(kpi.active_companies).toBe(12);
    expect(kpi.failed_payments).toBe(3);
    expect(formatRevenue(kpi.global_revenue)).toMatch(/5,000/);
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
    expect(healthTone("backlog")).toBe("warn");
  });

  it("formats revenue and percent", () => {
    expect(formatRevenue(1200)).toMatch(/1,200/);
    expect(formatRevenue(null)).toBe("—");
    expect(formatPct(12.34)).toBe("12.3%");
  });

  it("lists log categories", () => {
    expect(LOG_CATEGORIES.map((c) => c.value)).toContain("webhook");
    expect(LOG_CATEGORIES.map((c) => c.value)).toContain("ai");
  });
});
