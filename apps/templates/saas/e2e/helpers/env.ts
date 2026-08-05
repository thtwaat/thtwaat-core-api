/** Shared env for Playwright launch readiness. */

export function apiBaseUrl(): string {
  return (
    process.env.E2E_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://127.0.0.1:8000"
  ).replace(/\/$/, "");
}

export function siteBaseUrl(): string {
  return (
    process.env.PLAYWRIGHT_BASE_URL ||
    process.env.E2E_SITE_URL ||
    process.env.NEXT_PUBLIC_SITE_URL ||
    "http://127.0.0.1:3300"
  ).replace(/\/$/, "");
}

export function hasCredentials(): boolean {
  return Boolean(process.env.E2E_EMAIL && process.env.E2E_PASSWORD);
}

export function hasSuperAdminCredentials(): boolean {
  return Boolean(process.env.E2E_SUPER_ADMIN_EMAIL && process.env.E2E_SUPER_ADMIN_PASSWORD);
}

export function skipMessage(reason: string): string {
  return `SKIPPED: ${reason}. Set env vars to run against staging/prod.`;
}
