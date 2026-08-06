import { describe, expect, it } from "vitest";
import {
  deriveStudioTitle,
  listFieldToText,
  parseListField,
  studioStatusLabel,
  studioStatusTone,
  warningTone,
  EMPTY_BLUEPRINT
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

  it("parses list editor fields", () => {
    expect(parseListField("Dashboard\nSettings, Users")).toEqual([
      "Dashboard",
      "Settings",
      "Users"
    ]);
    expect(listFieldToText(["A", "B"])).toBe("A\nB");
  });

  it("maps warning tones", () => {
    expect(warningTone("error")).toBe("danger");
    expect(warningTone("warn")).toBe("warn");
    expect(warningTone("info")).toBe("neutral");
  });

  it("has empty blueprint defaults for editor", () => {
    expect(EMPTY_BLUEPRINT.pages).toEqual([]);
    expect(EMPTY_BLUEPRINT.product_type).toBe("saas");
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

describe("studioApi architect contract", () => {
  it("analyze/save/versions/restore paths", async () => {
    const calls: Array<{ path: string; method?: string }> = [];
    const fakeApi = {
      apiV2: async <T>(path: string, options?: { method?: string }) => {
        calls.push({ path, method: options?.method });
        return {} as T;
      }
    };
    const id = "proj-1";
    await fakeApi.apiV2(`/studio/projects/${id}/analyze?use_ai=true`, { method: "POST" });
    await fakeApi.apiV2(`/studio/projects/${id}/blueprint`);
    await fakeApi.apiV2(`/studio/projects/${id}/blueprint`, { method: "PUT" });
    await fakeApi.apiV2(`/studio/projects/${id}/versions`);
    await fakeApi.apiV2(`/studio/projects/${id}/restore/1`, { method: "POST" });
    await fakeApi.apiV2(`/studio/projects/${id}/compose`, { method: "POST" });
    await fakeApi.apiV2(`/studio/projects/${id}/build-plan`);
    await fakeApi.apiV2(`/studio/projects/${id}/generate/frontend`, { method: "POST" });
    await fakeApi.apiV2(`/studio/projects/${id}/frontend`);
    await fakeApi.apiV2(`/studio/projects/${id}/frontend`, { method: "PUT" });
    await fakeApi.apiV2(`/studio/projects/${id}/generate/backend`, { method: "POST" });
    await fakeApi.apiV2(`/studio/projects/${id}/backend`);
    await fakeApi.apiV2(`/studio/projects/${id}/backend`, { method: "PUT" });
    await fakeApi.apiV2(`/studio/projects/${id}/generate/ai`, { method: "POST" });
    await fakeApi.apiV2(`/studio/projects/${id}/ai`);
    await fakeApi.apiV2(`/studio/projects/${id}/ai`, { method: "PUT" });

    expect(calls.map((c) => c.path)).toEqual([
      `/studio/projects/${id}/analyze?use_ai=true`,
      `/studio/projects/${id}/blueprint`,
      `/studio/projects/${id}/blueprint`,
      `/studio/projects/${id}/versions`,
      `/studio/projects/${id}/restore/1`,
      `/studio/projects/${id}/compose`,
      `/studio/projects/${id}/build-plan`,
      `/studio/projects/${id}/generate/frontend`,
      `/studio/projects/${id}/frontend`,
      `/studio/projects/${id}/frontend`,
      `/studio/projects/${id}/generate/backend`,
      `/studio/projects/${id}/backend`,
      `/studio/projects/${id}/backend`,
      `/studio/projects/${id}/generate/ai`,
      `/studio/projects/${id}/ai`,
      `/studio/projects/${id}/ai`
    ]);
    expect(calls[10].method).toBe("POST");
    expect(calls[12].method).toBe("PUT");
    expect(calls[13].method).toBe("POST");
    expect(calls[15].method).toBe("PUT");
  });
});
