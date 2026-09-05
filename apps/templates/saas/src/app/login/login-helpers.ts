import { ApiError } from "@/lib/api";

// Matches the backend's exact copy ("This email belongs to multiple
// organizations; provide company_slug.") regardless of surrounding wording,
// so it stays specific to this condition and doesn't fire on unrelated 409s.
const MULTI_ORG_MESSAGE = /belongs to multiple organizations/i;

/**
 * POST /auth/login returns 409 when the same email exists in more than one
 * company and no company_slug was given. The platform's global HTTPException
 * handler (app/api/exceptions.py) normally re-wraps a dict-valued
 * HTTPException.detail as {"error": {"code": "company_required", "message":
 * ...}, "code": 409} — not FastAPI's raw {"detail": {...}}. Production has
 * also been observed collapsing this to a flat string envelope —
 * {"error": "This email belongs to multiple organizations; provide
 * company_slug.", "code": 409} — with no "company_required" code anywhere,
 * so a pure structural (code-field) check misses it and the slug field never
 * renders even though the right message is shown (commit a56a9ea bug).
 * Check every shape: nested code, flat code, and the flat-string message.
 */
export function isCompanyRequiredError(error: unknown): boolean {
  if (!(error instanceof ApiError) || error.status !== 409) return false;
  const root = error.detail;
  if (!root || typeof root !== "object") return false;
  const row = root as Record<string, unknown>;
  const inner = (row.error ?? row.detail) as unknown;

  if (inner && typeof inner === "object" && (inner as Record<string, unknown>).code === "company_required") {
    return true;
  }
  if (row.code === "company_required") return true;

  const message = typeof row.error === "string" ? row.error : typeof row.detail === "string" ? row.detail : null;
  return !!message && MULTI_ORG_MESSAGE.test(message);
}
