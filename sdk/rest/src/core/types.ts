export type AuthMode = "apiKey" | "bearer" | "session";

export interface RestClientConfig {
  baseURL?: string;
  apiUrl?: string;
  apiKey?: string;
  bearerToken?: string;
  sessionToken?: string;
  timeoutMs?: number;
  maxRetries?: number;
  retryStatuses?: number[];
  headers?: Record<string, string>;
  fetch?: typeof fetch;
  debug?: boolean;
}

export interface RequestOptions {
  query?: Record<string, string | number | boolean | null | undefined>;
  headers?: Record<string, string>;
  signal?: AbortSignal;
  skipRetry?: boolean;
  /** Raw body for multipart FormData — do not JSON.stringify */
  formData?: FormData;
  body?: unknown;
}

export interface PageParams {
  limit?: number;
  offset?: number;
  cursor?: string | null;
  [key: string]: unknown;
}

export interface PageResult<T> {
  items: T[];
  total?: number;
  limit?: number;
  offset?: number;
  cursor?: string | null;
  nextCursor?: string | null;
  hasMore?: boolean;
  raw: unknown;
}

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
