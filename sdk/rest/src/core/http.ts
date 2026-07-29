import { normalizeError, RestError } from "./errors";
import { withRetry } from "./retry";
import type { HttpMethod, RequestOptions, RestClientConfig } from "./types";

function resolveBaseURL(config: RestClientConfig): string {
  return (config.apiUrl || config.baseURL || "http://localhost:8000").replace(/\/$/, "");
}

function buildQuery(query?: RequestOptions["query"]): string {
  if (!query) return "";
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === null) continue;
    sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export class HttpCore {
  readonly baseURL: string;
  private readonly timeoutMs: number;
  private readonly maxRetries: number;
  private readonly retryStatuses: number[];
  private readonly defaultHeaders: Record<string, string>;
  private readonly fetchImpl: typeof fetch;
  private readonly debug: boolean;
  private apiKey?: string;
  private bearerToken?: string;
  private sessionToken?: string;

  constructor(config: RestClientConfig = {}) {
    this.baseURL = resolveBaseURL(config);
    this.timeoutMs = config.timeoutMs ?? 60_000;
    this.maxRetries = config.maxRetries ?? 2;
    this.retryStatuses = config.retryStatuses ?? [429, 502, 503, 504];
    this.defaultHeaders = {
      Accept: "application/json",
      "X-THTWAAT-REST-SDK": "1.0.0",
      ...(config.headers || {}),
    };
    this.debug = Boolean(config.debug);
    this.apiKey = config.apiKey;
    this.bearerToken = config.bearerToken;
    this.sessionToken = config.sessionToken;

    if (config.fetch) this.fetchImpl = config.fetch.bind(config);
    else if (typeof fetch !== "undefined") this.fetchImpl = fetch.bind(globalThis);
    else {
      throw new Error("fetch is unavailable. Pass config.fetch or use Node 18+.");
    }
  }

  setApiKey(key: string): void {
    this.apiKey = key;
  }
  setBearerToken(token: string): void {
    this.bearerToken = token;
  }
  setSessionToken(token: string): void {
    this.sessionToken = token;
  }

  private authHeaders(): Record<string, string> {
    if (this.bearerToken) return { Authorization: `Bearer ${this.bearerToken}` };
    if (this.sessionToken) return { Authorization: `Bearer ${this.sessionToken}` };
    if (this.apiKey) return { Authorization: `Bearer ${this.apiKey}` };
    return {};
  }

  async request<T = unknown>(
    method: HttpMethod,
    path: string,
    opts: RequestOptions = {}
  ): Promise<T> {
    const url = `${this.baseURL}${path}${buildQuery(opts.query)}`;

    const run = async () => {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
      const onAbort = () => controller.abort(opts.signal?.reason);
      if (opts.signal) {
        if (opts.signal.aborted) controller.abort(opts.signal.reason);
        else opts.signal.addEventListener("abort", onAbort, { once: true });
      }

      const headers: Record<string, string> = {
        ...this.defaultHeaders,
        ...this.authHeaders(),
        ...(opts.headers || {}),
      };

      let body: BodyInit | undefined;
      if (opts.formData) {
        body = opts.formData;
        delete headers["Content-Type"];
      } else if (opts.body !== undefined && method !== "GET") {
        headers["Content-Type"] = headers["Content-Type"] || "application/json";
        body = typeof opts.body === "string" ? opts.body : JSON.stringify(opts.body);
      }

      try {
        if (this.debug) console.debug("[thtwaat-rest]", method, url);
        const res = await this.fetchImpl(url, {
          method,
          headers,
          body,
          signal: controller.signal,
        });

        if (res.status === 204) return undefined as T;

        const text = await res.text();
        let parsed: unknown = null;
        if (text) {
          try {
            parsed = JSON.parse(text);
          } catch {
            parsed = text;
          }
        }

        if (!res.ok) throw normalizeError(res.status, parsed);
        return parsed as T;
      } catch (err) {
        if (err instanceof RestError) throw err;
        if ((err as Error)?.name === "AbortError") {
          throw new RestError("Request aborted or timed out", {
            code: "aborted",
            retryable: false,
            cause: err,
          });
        }
        throw new RestError((err as Error)?.message || "Network error", {
          code: "network_error",
          retryable: true,
          cause: err,
        });
      } finally {
        clearTimeout(timeout);
        opts.signal?.removeEventListener("abort", onAbort);
      }
    };

    if (opts.skipRetry || this.maxRetries <= 0) return run();

    return withRetry(run, {
      maxRetries: this.maxRetries,
      signal: opts.signal,
      shouldRetry: (err) => {
        if (!(err instanceof RestError)) return false;
        if (err.status && this.retryStatuses.includes(err.status)) return true;
        return err.retryable;
      },
    });
  }

  get<T = unknown>(path: string, opts?: RequestOptions) {
    return this.request<T>("GET", path, opts);
  }
  post<T = unknown>(path: string, body?: unknown, opts?: RequestOptions) {
    return this.request<T>("POST", path, { ...opts, body });
  }
  put<T = unknown>(path: string, body?: unknown, opts?: RequestOptions) {
    return this.request<T>("PUT", path, { ...opts, body });
  }
  patch<T = unknown>(path: string, body?: unknown, opts?: RequestOptions) {
    return this.request<T>("PATCH", path, { ...opts, body });
  }
  delete<T = unknown>(path: string, opts?: RequestOptions) {
    return this.request<T>("DELETE", path, opts);
  }

  async upload<T = unknown>(
    path: string,
    file: Blob | File | ArrayBuffer | Uint8Array,
    fields: Record<string, string> = {},
    filename = "upload.bin",
    opts: RequestOptions = {}
  ): Promise<T> {
    const form = new FormData();
    let blob: Blob;
    if (typeof Blob !== "undefined" && file instanceof Blob) blob = file;
    else if (file instanceof ArrayBuffer) blob = new Blob([file]);
    else if (file instanceof Uint8Array) blob = new Blob([new Uint8Array(file)]);
    else blob = file as Blob;

    form.append("file", blob, filename);
    for (const [k, v] of Object.entries(fields)) form.append(k, v);

    return this.request<T>("POST", path, { ...opts, formData: form });
  }

  async *streamSSE(
    path: string,
    body?: unknown,
    opts: RequestOptions = {}
  ): AsyncGenerator<{ event: string; data: unknown }, void, void> {
    const url = `${this.baseURL}${path}${buildQuery(opts.query)}`;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
    const onAbort = () => controller.abort(opts.signal?.reason);
    if (opts.signal) {
      if (opts.signal.aborted) controller.abort(opts.signal.reason);
      else opts.signal.addEventListener("abort", onAbort, { once: true });
    }

    try {
      const res = await this.fetchImpl(url, {
        method: "POST",
        headers: {
          ...this.defaultHeaders,
          ...this.authHeaders(),
          Accept: "text/event-stream",
          "Content-Type": "application/json",
          ...(opts.headers || {}),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal,
      });

      if (!res.ok) {
        const text = await res.text();
        let parsed: unknown = text;
        try {
          parsed = JSON.parse(text);
        } catch {
          /* keep */
        }
        throw normalizeError(res.status, parsed);
      }
      if (!res.body) throw new RestError("Missing stream body", { code: "stream_error" });

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        for (const part of parts) {
          const lines = part.split("\n");
          let event = "message";
          let data = "";
          for (const line of lines) {
            if (line.startsWith("event:")) event = line.slice(6).trim();
            if (line.startsWith("data:")) data += line.slice(5).trim();
          }
          if (!data) continue;
          let parsed: unknown = data;
          try {
            parsed = JSON.parse(data);
          } catch {
            /* keep string */
          }
          yield { event, data: parsed };
        }
      }
    } finally {
      clearTimeout(timeout);
      opts.signal?.removeEventListener("abort", onAbort);
    }
  }
}
