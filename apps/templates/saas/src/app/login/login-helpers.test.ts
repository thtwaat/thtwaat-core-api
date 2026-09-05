import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api";
import { isCompanyRequiredError } from "./login-helpers";

describe("isCompanyRequiredError", () => {
  it("detects the platform's global-exception-handler shape: { error: { code }, code: status }", () => {
    const error = new ApiError("This email belongs to multiple organizations; provide company_slug.", 409, {
      error: {
        code: "company_required",
        message: "This email belongs to multiple organizations; provide company_slug."
      },
      code: 409
    });
    expect(isCompanyRequiredError(error)).toBe(true);
  });

  it("also detects raw FastAPI { detail: { code } } payloads", () => {
    const error = new ApiError("multiple orgs", 409, {
      detail: { code: "company_required", message: "multiple orgs" }
    });
    expect(isCompanyRequiredError(error)).toBe(true);
  });

  it("also detects a flat { code } payload", () => {
    const error = new ApiError("multiple orgs", 409, { code: "company_required" });
    expect(isCompanyRequiredError(error)).toBe(true);
  });

  it("ignores other 409s", () => {
    const error = new ApiError("conflict", 409, { error: { code: "slug_taken" }, code: 409 });
    expect(isCompanyRequiredError(error)).toBe(false);
  });

  it("ignores non-409 errors, including invalid credentials", () => {
    const error = new ApiError("Invalid email or password", 401, "Invalid email or password");
    expect(isCompanyRequiredError(error)).toBe(false);
  });

  it("ignores non-ApiError values", () => {
    expect(isCompanyRequiredError(new Error("boom"))).toBe(false);
    expect(isCompanyRequiredError(null)).toBe(false);
  });
});
