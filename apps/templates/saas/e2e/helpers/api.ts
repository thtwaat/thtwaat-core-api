import { APIRequestContext, expect } from "@playwright/test";
import { apiBaseUrl } from "./env";

export type AuthSession = {
  accessToken: string;
  refreshToken?: string;
  email: string;
  password: string;
  companyId?: string;
  headers: Record<string, string>;
};

function uid(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export async function apiGet(request: APIRequestContext, path: string, headers?: Record<string, string>) {
  const res = await request.get(`${apiBaseUrl()}${path}`, { headers });
  return res;
}

export async function apiPost(
  request: APIRequestContext,
  path: string,
  body?: unknown,
  headers?: Record<string, string>
) {
  const res = await request.post(`${apiBaseUrl()}${path}`, {
    data: body,
    headers: { "Content-Type": "application/json", ...(headers || {}) }
  });
  return res;
}

/** Create company + user + login (mirrors tests/agent_platform/_auth). */
export async function seedWorkspace(request: APIRequestContext): Promise<AuthSession> {
  const slug = uid("e2e");
  const email = `${slug}@example.com`;
  const password = "SecurePass123!";

  const companyRes = await apiPost(request, "/api/v1/companies/", {
    name: `E2E Co ${slug}`,
    slug
  });
  expect(companyRes.ok(), await companyRes.text()).toBeTruthy();
  const company = await companyRes.json();

  const userRes = await apiPost(request, "/api/v1/users/", {
    email,
    password,
    company_id: company.id,
    first_name: "E2E",
    last_name: "Owner",
    role: "company_owner"
  });
  expect(userRes.ok(), await userRes.text()).toBeTruthy();

  const loginRes = await apiPost(request, "/api/v1/auth/login", { email, password });
  expect(loginRes.ok(), await loginRes.text()).toBeTruthy();
  const tokens = await loginRes.json();

  return {
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    email,
    password,
    companyId: company.id,
    headers: { Authorization: `Bearer ${tokens.access_token}` }
  };
}

export async function loginWithEnv(request: APIRequestContext): Promise<AuthSession | null> {
  const email = process.env.E2E_EMAIL;
  const password = process.env.E2E_PASSWORD;
  if (!email || !password) return null;
  const loginRes = await apiPost(request, "/api/v1/auth/login", { email, password });
  if (!loginRes.ok()) return null;
  const tokens = await loginRes.json();
  return {
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    email,
    password,
    headers: { Authorization: `Bearer ${tokens.access_token}` }
  };
}

export async function injectBrowserAuth(
  page: import("@playwright/test").Page,
  session: AuthSession
): Promise<void> {
  await page.addInitScript(
    ({ access, refresh }) => {
      window.localStorage.setItem("tht_access_token", access);
      if (refresh) window.localStorage.setItem("tht_refresh_token", refresh);
      document.cookie = `tht_session=1; path=/; max-age=${60 * 60 * 24 * 14}; SameSite=Lax`;
    },
    { access: session.accessToken, refresh: session.refreshToken || "" }
  );
}
