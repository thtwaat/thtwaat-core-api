import { ApiError } from "@/lib/api";

/**
 * POST /auth/login returns 409 when the same email exists in more than one
 * company and no company_slug was given. The platform's global HTTPException
 * handler (app/api/exceptions.py) re-wraps HTTPException(detail={"code": ...})
 * as {"error": {"code": "company_required", "message": ...}, "code": 409} —
 * not FastAPI's raw {"detail": {...}}. Check both shapes defensively.
 */
export function isCompanyRequiredError(error: unknown): boolean {
  if (!(error instanceof ApiError) || error.status !== 409) return false;
  const root = error.detail;
  if (!root || typeof root !== "object") return false;
  const row = root as Record<string, unknown>;
  const inner = (row.error ?? row.detail) as unknown;
  const code =
    (inner && typeof inner === "object" ? (inner as Record<string, unknown>).code : undefined) ?? row.code;
  return code === "company_required";
}
