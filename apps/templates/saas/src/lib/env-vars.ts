// THTWAAT Deploy — environment variables (Phase 4A/4B backend, Phase 4C UI).
// Sibling to lib/static-sites.ts — types and pure helpers only; the API
// surface lives in lib/services.ts (envVarsApi) alongside staticSitesApi.
//
// Mirrors the backend contract exactly (app/static_sites/schemas.py):
// GET/list responses never carry `value`/`encrypted_value` — only metadata.
// Every validation/warning rule here is a FRONTEND CONVENIENCE ONLY; the
// backend (app/static_sites/env_vars_service.py) is the source of truth and
// re-validates everything independently.

import { ApiError } from "@/lib/api";

export type EnvVarEnvironment = "production" | "development";

export const ENV_VAR_ENVIRONMENTS: EnvVarEnvironment[] = ["production", "development"];

export type EnvVar = {
  id: string;
  site_id: string;
  key: string;
  environment: EnvVarEnvironment | string;
  is_secret: boolean;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
};

export type EnvVarList = {
  items: EnvVar[];
  total: number;
};

export type EnvVarCreateRequest = {
  key: string;
  value: string;
  environment: EnvVarEnvironment | string;
  is_secret: boolean;
};

// `value` is OMITTED (not sent as "") when the user leaves the field blank
// during an edit — the backend keeps the existing encrypted value in that
// case. Never send an empty-string value meaning "clear it"; that isn't a
// supported operation (see buildUpdatePayload).
export type EnvVarUpdateRequest = {
  value?: string;
  is_secret?: boolean;
};

// Same shape a POSIX/shell env var name requires — mirrors
// app/static_sites/schemas.py's _ENV_VAR_KEY_PATTERN exactly.
export const ENV_KEY_PATTERN = /^[A-Z_][A-Z0-9_]*$/;

export function validateEnvKey(key: string): string | null {
  const trimmed = key.trim();
  if (!trimmed) return "Key is required.";
  if (!ENV_KEY_PATTERN.test(trimmed)) {
    return "Use uppercase letters, digits, and underscores only, starting with a letter or underscore (e.g. OPENAI_API_KEY).";
  }
  return null;
}

export const VITE_PUBLIC_PREFIX = "VITE_";
export const NEXTJS_PUBLIC_PREFIX = "NEXT_PUBLIC_";

export const PUBLIC_PREFIX_BROWSER_WARNING = "This variable may be exposed in the browser.";

/** Non-blocking UX hint shown while typing a key — not a validation error. */
export function publicPrefixWarning(key: string): string | null {
  const trimmed = key.trim();
  if (trimmed.startsWith(VITE_PUBLIC_PREFIX) || trimmed.startsWith(NEXTJS_PUBLIC_PREFIX)) {
    return PUBLIC_PREFIX_BROWSER_WARNING;
  }
  return null;
}

/**
 * Frontend mirror of app/static_sites/schemas.py's check_secret_public_prefix
 * — shown before submission so the user isn't surprised by a 400. The
 * backend re-checks this independently on both create and update; this
 * function existing does not relax that.
 */
export function secretPublicPrefixConflict(key: string, isSecret: boolean): string | null {
  if (!isSecret) return null;
  const trimmed = key.trim();
  if (trimmed.startsWith(VITE_PUBLIC_PREFIX)) {
    return "Secret variables cannot use the VITE_ public prefix.";
  }
  if (trimmed.startsWith(NEXTJS_PUBLIC_PREFIX)) {
    return "Secret variables cannot use the NEXT_PUBLIC_ public prefix.";
  }
  return null;
}

/** Fixed placeholder shown in place of any secret value — never derived
 * from, or hinting at, the real value's length or content. */
export const MASKED_VALUE = "••••••••••";

/** What the list/table should render for a row's value column — the API
 * response never carries a value at all, so this is intentionally static,
 * never a function of `EnvVar` data (there is no plaintext to derive from). */
export function displayValueFor(row: Pick<EnvVar, "is_secret">): string {
  return row.is_secret ? MASKED_VALUE : MASKED_VALUE;
}

export function buildCreatePayload(input: {
  key: string;
  value: string;
  environment: EnvVarEnvironment | string;
  isSecret: boolean;
}): EnvVarCreateRequest {
  return {
    key: input.key.trim(),
    value: input.value,
    environment: input.environment,
    is_secret: input.isSecret
  };
}

/**
 * Blank `value` means "keep the existing secret" — the field is OMITTED
 * from the payload entirely (not sent as an empty string), matching
 * StaticSiteEnvVarUpdateRequest's `value: Optional[str] = None` on the
 * backend. Only include is_secret when it actually changed from the
 * row's current value, so a no-op edit sends `{}`.
 */
export function buildUpdatePayload(input: {
  newValue: string;
  isSecret: boolean;
  currentIsSecret: boolean;
}): EnvVarUpdateRequest {
  const payload: EnvVarUpdateRequest = {};
  if (input.newValue.trim().length > 0) {
    payload.value = input.newValue;
  }
  if (input.isSecret !== input.currentIsSecret) {
    payload.is_secret = input.isSecret;
  }
  return payload;
}

export function hasUpdatePayloadChanges(payload: EnvVarUpdateRequest): boolean {
  return payload.value !== undefined || payload.is_secret !== undefined;
}

/** Deployment framework -> what "redeploy required" actually means for this
 * project. Static HTML/ZIP has no build step at all, so env vars there are
 * inert until Vite/Next.js support is actually used — still worth telling
 * the user plainly rather than implying anything is instantly live. */
export function redeployNoticeFor(framework?: string | null): string {
  const base = "Environment variable changed. Redeploy required for the change to take effect.";
  switch (framework) {
    case "vite":
      return `${base} Vite variables are applied during build, so a new deployment is required.`;
    case "nextjs":
      return `${base} NEXT_PUBLIC_ variables are baked in at build time; server-only variables are picked up the next time this deployment's runtime is (re)started.`;
    default:
      return base;
  }
}

const FRIENDLY_STATUS_MESSAGE: Record<number, string> = {
  401: "Your session has expired. Please sign in again.",
  403: "You don't have permission to manage environment variables.",
  404: "That environment variable or site could not be found.",
  409: "An environment variable with this key already exists for this environment.",
  422: "Please check the values you entered.",
  500: "Something went wrong on our end. Please try again."
};

/**
 * Safe, user-facing message for any env-var API failure. `ApiError.message`
 * (see lib/api.ts's formatApiErrorMessage) already strips raw backend
 * payloads down to a short string — this only overrides it with the exact
 * copy this feature calls for on well-known status codes, and otherwise
 * falls back to that already-sanitized message. Never surfaces
 * `error.detail` directly (which could be a raw object) and never a stack
 * trace, encrypted value, or plaintext secret.
 */
export function envVarApiErrorMessage(error: unknown): string {
  // Only ApiError's `.message` is trusted here — it is always produced by
  // lib/api.ts's formatApiErrorMessage(), which already strips a raw
  // backend payload down to a short, safe string. A plain Error (or any
  // other thrown value) is NOT a response from this API and could contain
  // anything (e.g. a stack trace fragment) — never surfaced verbatim.
  if (!(error instanceof ApiError)) {
    return "Something went wrong. Please try again.";
  }
  const status = error.status;
  if (FRIENDLY_STATUS_MESSAGE[status]) {
    // 422 bodies can legitimately be useful (e.g. "Invalid environment
    // variable name...") — prefer the formatted message when it's a short,
    // plain string; otherwise use the generic copy above.
    if (status === 422 && error.message.trim()) {
      return error.message;
    }
    return FRIENDLY_STATUS_MESSAGE[status];
  }
  if (error.message.trim()) {
    return error.message;
  }
  return "Something went wrong. Please try again.";
}

export function environmentLabel(environment: string): string {
  switch (environment) {
    case "production":
      return "Production";
    case "development":
      return "Development";
    default:
      return environment;
  }
}

export function typeLabel(isSecret: boolean): "Secret" | "Public" {
  return isSecret ? "Secret" : "Public";
}
