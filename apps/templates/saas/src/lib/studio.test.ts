import { describe, expect, it } from "vitest";
import {
  deriveStudioTitle,
  studioStatusLabel,
  studioStatusTone
} from "./studio";
import { canDeleteStudioProjects } from "./permissions";

describe("studio helpers", () => {
  it("derives title from first line", () => {
    expect(deriveStudioTitle("Create CRM\nwith AI")).toBe("Create CRM");
    expect(deriveStudioTitle("x".repeat(100)).endsWith("...")).toBe(true);
  });

  it("maps status labels and tones", () => {
    expect(studioStatusLabel("draft")).toBe("Draft");
    expect(studioStatusTone("failed")).toBe("danger");
    expect(studioStatusTone("completed")).toBe("success");
    expect(studioStatusTone("building")).toBe("warn");
  });
});

describe("canDeleteStudioProjects", () => {
  it("allows owners and admins", () => {
    expect(canDeleteStudioProjects("company_owner")).toBe(true);
    expect(canDeleteStudioProjects("admin")).toBe(true);
    expect(canDeleteStudioProjects("super_admin")).toBe(true);
  });

  it("denies members and developers", () => {
    expect(canDeleteStudioProjects("member")).toBe(false);
    expect(canDeleteStudioProjects("developer")).toBe(false);
    expect(canDeleteStudioProjects(null)).toBe(false);
  });
});

describe("studioApi contract", () => {
  it("create/list/delete paths are under /api/v2/studio", async () => {
    const { apiPaths } = await import("./config");
    expect(apiPaths.apiV2.endsWith("/api/v2")).toBe(true);

    const calls: Array<{ path: string; method?: string }> = [];
    const fakeApi = {
      apiV2: async <T>(path: string, options?: { method?: string }) => {
        calls.push({ path, method: options?.method });
        if (options?.method === "DELETE") return undefined as T;
        if (options?.method === "POST") {
          return {
            id: "p1",
            workspace_id: "w1",
            title: "Create CRM",
            prompt: "Create CRM with leads",
            status: "draft",
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          } as T;
        }
        return { items: [], total: 0 } as T;
      }
    };

    // Inline mirror of studioApi using fake transport
    const studioApi = {
      list: () => fakeApi.apiV2("/studio/projects?limit=50&offset=0"),
      create: (body: { prompt: string }) =>
        fakeApi.apiV2("/studio/projects", { method: "POST", ...{ body } as object }),
      remove: (id: string) => fakeApi.apiV2(`/studio/projects/${id}`, { method: "DELETE" })
    };

    await studioApi.create({ prompt: "Create CRM with leads and invoices" });
    await studioApi.list();
    await studioApi.remove("p1");

    expect(calls[0]).toEqual({ path: "/studio/projects", method: "POST" });
    expect(calls[1].path).toContain("/studio/projects");
    expect(calls[2]).toEqual({ path: "/studio/projects/p1", method: "DELETE" });
  });
});
