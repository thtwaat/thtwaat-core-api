import { describe, expect, it } from "vitest";
import { ApiError } from "./api";
import {
  MASKED_VALUE,
  buildCreatePayload,
  buildUpdatePayload,
  displayValueFor,
  environmentLabel,
  envVarApiErrorMessage,
  hasUpdatePayloadChanges,
  publicPrefixWarning,
  redeployNoticeFor,
  secretPublicPrefixConflict,
  typeLabel,
  validateEnvKey
} from "./env-vars";

describe("env-vars: key validation (item 9 — invalid key validation)", () => {
  it("accepts valid keys", () => {
    for (const key of ["OPENAI_API_KEY", "DATABASE_URL", "NEXT_PUBLIC_API_URL", "VITE_API_URL", "_X", "A"]) {
      expect(validateEnvKey(key)).toBeNull();
    }
  });

  it("rejects invalid keys", () => {
    for (const key of ["my key", "FOO-BAR", "FOO BAR", "FOO;rm", "$(command)", "foo_bar", "1FOO", ""]) {
      expect(validateEnvKey(key)).not.toBeNull();
    }
  });
});

describe("env-vars: public-prefix browser warning (items 8, 10, 11)", () => {
  it("warns for VITE_ prefixed keys", () => {
    expect(publicPrefixWarning("VITE_API_URL")).toBe("This variable may be exposed in the browser.");
  });

  it("warns for NEXT_PUBLIC_ prefixed keys", () => {
    expect(publicPrefixWarning("NEXT_PUBLIC_API_URL")).toBe("This variable may be exposed in the browser.");
  });

  it("does not warn for server-only keys", () => {
    expect(publicPrefixWarning("DATABASE_URL")).toBeNull();
    expect(publicPrefixWarning("OPENAI_API_KEY")).toBeNull();
  });
});

describe("env-vars: secret + public prefix conflict (item 12)", () => {
  it("flags a secret VITE_ key before submission", () => {
    expect(secretPublicPrefixConflict("VITE_SECRET", true)).toMatch(/VITE_ public prefix/);
  });

  it("flags a secret NEXT_PUBLIC_ key before submission", () => {
    expect(secretPublicPrefixConflict("NEXT_PUBLIC_SECRET", true)).toMatch(/NEXT_PUBLIC_ public prefix/);
  });

  it("does not flag a non-secret public-prefixed key", () => {
    expect(secretPublicPrefixConflict("VITE_API_URL", false)).toBeNull();
  });

  it("does not flag a secret server-only key", () => {
    expect(secretPublicPrefixConflict("DATABASE_URL", true)).toBeNull();
  });
});

describe("env-vars: secret masking (item 6 — secret value masked)", () => {
  it("never renders a real value — only the fixed mask, for both secret and public rows", () => {
    expect(displayValueFor({ is_secret: true })).toBe(MASKED_VALUE);
    expect(displayValueFor({ is_secret: false })).toBe(MASKED_VALUE);
  });

  it("the mask contains no alphanumeric characters that could be mistaken for a real value", () => {
    expect(/[a-zA-Z0-9]/.test(MASKED_VALUE)).toBe(false);
  });
});

describe("env-vars: create payload shaping", () => {
  it("trims the key and passes value/environment/is_secret through", () => {
    const payload = buildCreatePayload({
      key: "  OPENAI_API_KEY  ",
      value: "sk-real-secret-value",
      environment: "production",
      isSecret: true
    });
    expect(payload).toEqual({
      key: "OPENAI_API_KEY",
      value: "sk-real-secret-value",
      environment: "production",
      is_secret: true
    });
  });
});

describe("env-vars: update payload shaping (item 7 — secret not prefilled during edit)", () => {
  it("omits `value` entirely when the user leaves it blank — never sends an empty string", () => {
    const payload = buildUpdatePayload({ newValue: "", isSecret: true, currentIsSecret: true });
    expect(payload).not.toHaveProperty("value");
    expect("value" in payload).toBe(false);
  });

  it("omits `value` for whitespace-only input too", () => {
    const payload = buildUpdatePayload({ newValue: "   ", isSecret: true, currentIsSecret: true });
    expect("value" in payload).toBe(false);
  });

  it("includes `value` only when the user actually typed a replacement", () => {
    const payload = buildUpdatePayload({ newValue: "new-secret-value", isSecret: true, currentIsSecret: true });
    expect(payload.value).toBe("new-secret-value");
  });

  it("omits is_secret when unchanged, includes it when flipped", () => {
    const unchanged = buildUpdatePayload({ newValue: "", isSecret: true, currentIsSecret: true });
    expect("is_secret" in unchanged).toBe(false);

    const flipped = buildUpdatePayload({ newValue: "", isSecret: false, currentIsSecret: true });
    expect(flipped.is_secret).toBe(false);
  });

  it("a fully blank, unchanged edit produces an empty payload (no-op)", () => {
    const payload = buildUpdatePayload({ newValue: "", isSecret: true, currentIsSecret: true });
    expect(hasUpdatePayloadChanges(payload)).toBe(false);
    expect(payload).toEqual({});
  });

  it("a real edit produces a non-empty payload", () => {
    const payload = buildUpdatePayload({ newValue: "x", isSecret: true, currentIsSecret: true });
    expect(hasUpdatePayloadChanges(payload)).toBe(true);
  });
});

describe("env-vars: error message mapping (items 13-17 — 401/403/404/409/422/500)", () => {
  it("401 -> session expired", () => {
    expect(envVarApiErrorMessage(new ApiError("x", 401))).toMatch(/session has expired/i);
  });

  it("403 -> permission message (item 16 — RBAC copy)", () => {
    expect(envVarApiErrorMessage(new ApiError("x", 403))).toBe(
      "You don't have permission to manage environment variables."
    );
  });

  it("404 -> not found message, never echoes backend detail", () => {
    expect(envVarApiErrorMessage(new ApiError("x", 404))).toMatch(/could not be found/i);
  });

  it("409 -> duplicate key message", () => {
    expect(envVarApiErrorMessage(new ApiError("x", 409))).toMatch(/already exists/i);
  });

  it("422 -> prefers the formatted validation message when present", () => {
    const err = new ApiError("Invalid environment variable name.", 422);
    expect(envVarApiErrorMessage(err)).toBe("Invalid environment variable name.");
  });

  it("422 -> falls back to generic copy when no message was formatted", () => {
    const err = new ApiError("", 422);
    expect(envVarApiErrorMessage(err)).toMatch(/check the values/i);
  });

  it("500 -> generic safe message, never a stack trace", () => {
    const err = new ApiError("TypeError: cannot read property 'x' of undefined\n  at foo.js:42", 500);
    const msg = envVarApiErrorMessage(err);
    expect(msg).toBe("Something went wrong on our end. Please try again.");
    expect(msg).not.toMatch(/at foo\.js/);
  });

  it("never surfaces a raw object as the message", () => {
    const err = new ApiError("x", 422, { detail: [{ msg: "bad" }] });
    const msg = envVarApiErrorMessage(err);
    expect(typeof msg).toBe("string");
  });

  it("unknown/non-ApiError errors get a generic safe fallback", () => {
    expect(envVarApiErrorMessage(new Error("boom"))).toBe("Something went wrong. Please try again.");
    expect(envVarApiErrorMessage("not an error at all")).toBe("Something went wrong. Please try again.");
  });
});

describe("env-vars: redeploy notice (item 22)", () => {
  it("gives the Vite-specific build-time explanation", () => {
    expect(redeployNoticeFor("vite")).toMatch(/applied during build/i);
    expect(redeployNoticeFor("vite")).toMatch(/redeploy required/i);
  });

  it("gives the Next.js-specific build-vs-runtime explanation", () => {
    expect(redeployNoticeFor("nextjs")).toMatch(/NEXT_PUBLIC_/);
    expect(redeployNoticeFor("nextjs")).toMatch(/runtime/i);
  });

  it("gives a generic notice for static/unknown frameworks — never claims instant effect", () => {
    const notice = redeployNoticeFor("static_html");
    expect(notice).toMatch(/redeploy required/i);
    expect(notice.toLowerCase()).not.toMatch(/instantly|immediately live/);
  });

  it("handles a missing framework (no deployment yet) without throwing", () => {
    expect(() => redeployNoticeFor(undefined)).not.toThrow();
    expect(() => redeployNoticeFor(null)).not.toThrow();
  });
});

describe("env-vars: labels", () => {
  it("maps environment values to display labels", () => {
    expect(environmentLabel("production")).toBe("Production");
    expect(environmentLabel("development")).toBe("Development");
  });

  it("maps is_secret to Secret/Public type labels — never implies a public var is secret", () => {
    expect(typeLabel(true)).toBe("Secret");
    expect(typeLabel(false)).toBe("Public");
  });
});
