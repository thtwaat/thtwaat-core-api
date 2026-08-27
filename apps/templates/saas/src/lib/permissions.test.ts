import { describe, expect, it } from "vitest";
import {
  canViewProviders,
  canManageWebhooks,
  canManageGithubConnection,
  canDeleteStudioProjects,
  canUseCodingAgent
} from "./permissions";

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

describe("canManageGithubConnection", () => {
  it("allows owners/admins only — same role set as can_manage_company_users on the backend", () => {
    expect(canManageGithubConnection("super_admin")).toBe(true);
    expect(canManageGithubConnection("company_owner")).toBe(true);
    expect(canManageGithubConnection("admin")).toBe(true);
  });

  it("denies developer/member/viewer and empty roles", () => {
    expect(canManageGithubConnection("developer")).toBe(false);
    expect(canManageGithubConnection("member")).toBe(false);
    expect(canManageGithubConnection("viewer")).toBe(false);
    expect(canManageGithubConnection(null)).toBe(false);
    expect(canManageGithubConnection(undefined)).toBe(false);
  });

  it("matches canDeleteStudioProjects's role set exactly", () => {
    for (const role of ["super_admin", "company_owner", "admin", "developer", "member", null]) {
      expect(canManageGithubConnection(role)).toBe(canDeleteStudioProjects(role));
    }
  });
});

describe("canUseCodingAgent", () => {
  it("allows every granted role — matches Permission.CODING_AGENT_ACCESS in app/rbac/policy.py", () => {
    for (const role of ["super_admin", "company_owner", "admin", "manager", "developer", "employee"]) {
      expect(canUseCodingAgent(role)).toBe(true);
    }
  });

  it("denies viewer and empty roles", () => {
    expect(canUseCodingAgent("viewer")).toBe(false);
    expect(canUseCodingAgent(null)).toBe(false);
    expect(canUseCodingAgent(undefined)).toBe(false);
  });

  it("is a strict superset of canDeleteStudioProjects", () => {
    expect(canUseCodingAgent("employee")).toBe(true);
    expect(canDeleteStudioProjects("employee")).toBe(false);
    expect(canUseCodingAgent("developer")).toBe(true);
    expect(canDeleteStudioProjects("developer")).toBe(false);
  });
});
