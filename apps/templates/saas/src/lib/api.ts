"use client";

import { apiPaths } from "@/lib/config";
import type { TokenPair } from "@/lib/types";

const ACCESS_KEY = "tht_access_token";
const REFRESH_KEY = "tht_refresh_token";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

function readToken(key: string) {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(key);
}

export function getAccessToken() {
  return readToken(ACCESS_KEY);
}

export function getRefreshToken() {
  return readToken(REFRESH_KEY);
}

export function setTokens(tokens: TokenPair) {
  window.localStorage.setItem(ACCESS_KEY, tokens.access_token);
  window.localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
  document.cookie = `tht_session=1; path=/; max-age=${60 * 60 * 24 * 14}; SameSite=Lax`;
}

export function clearTokens() {
  window.localStorage.removeItem(ACCESS_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
  document.cookie = "tht_session=; path=/; max-age=0; SameSite=Lax";
}

async function refreshAccessToken(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;
  const response = await fetch(`${apiPaths.v1}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh })
  });
  if (!response.ok) {
    clearTokens();
    return null;
  }
  const data = (await response.json()) as TokenPair;
  setTokens(data);
  return data.access_token;
}

type RequestOptions = {
  method?: string;
  body?: unknown;
  auth?: boolean;
  headers?: Record<string, string>;
  formData?: FormData;
};

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = true, headers = {}, formData } = options;
  const finalHeaders: Record<string, string> = { ...headers };

  if (!formData) finalHeaders["Content-Type"] = "application/json";

  let token = getAccessToken();
  if (auth && token) finalHeaders.Authorization = `Bearer ${token}`;

  let response = await fetch(path, {
    method,
    headers: finalHeaders,
    body: formData ? formData : body !== undefined ? JSON.stringify(body) : undefined
  });

  if (response.status === 401 && auth) {
    token = await refreshAccessToken();
    if (token) {
      finalHeaders.Authorization = `Bearer ${token}`;
      response = await fetch(path, {
        method,
        headers: finalHeaders,
        body: formData ? formData : body !== undefined ? JSON.stringify(body) : undefined
      });
    }
  }

  if (!response.ok) {
    let detail: unknown = null;
    try {
      detail = await response.json();
    } catch {
      detail = await response.text();
    }
    const message =
      typeof detail === "object" && detail && "detail" in detail
        ? String((detail as { detail: unknown }).detail)
        : `Request failed (${response.status})`;
    throw new ApiError(message, response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  v1: <T>(path: string, options?: RequestOptions) => apiRequest<T>(`${apiPaths.v1}${path}`, options),
  v2: <T>(path: string, options?: RequestOptions) => apiRequest<T>(`${apiPaths.v2}${path}`, options),
  public: <T>(path: string, options?: RequestOptions) =>
    apiRequest<T>(`${apiPaths.public}${path}`, { ...options, auth: false })
};
