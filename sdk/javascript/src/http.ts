import { parseApiError, THTWAATError } from "./errors";
import { Logger } from "./utils/logger";
import { withRetry } from "./utils/retry";

export interface HttpClientOptions {
  baseURL: string;
  timeoutMs: number;
  maxRetries: number;
  defaultHeaders: Record<string, string>;
  fetchImpl: typeof fetch;
  logger: Logger;
  getAuthHeaders: () => Record<string, string>;
}

export class HttpClient {
  constructor(private readonly opts: HttpClientOptions) {}

  async request<T = unknown>(
    path: string,
    init: RequestInit & { signal?: AbortSignal; skipRetry?: boolean } = {}
  ): Promise<T> {
    const url = `${this.opts.baseURL.replace(/\/$/, "")}${path}`;
    const headers: Record<string, string> = {
      Accept: "application/json",
      ...this.opts.defaultHeaders,
      ...this.opts.getAuthHeaders(),
      ...(init.headers as Record<string, string> | undefined),
    };

    const run = async () => {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), this.opts.timeoutMs);
      const onOuterAbort = () => controller.abort(init.signal?.reason);
      if (init.signal) {
        if (init.signal.aborted) controller.abort(init.signal.reason);
        else init.signal.addEventListener("abort", onOuterAbort, { once: true });
      }

      try {
        this.opts.logger.debug(init.method || "GET", url);
        const res = await this.opts.fetchImpl(url, {
          ...init,
          headers,
          signal: controller.signal,
        });

        const text = await res.text();
        let body: unknown = null;
        if (text) {
          try {
            body = JSON.parse(text);
          } catch {
            body = text;
          }
        }

        if (!res.ok) {
          throw parseApiError(res.status, body);
        }
        return body as T;
      } catch (err) {
        if (err instanceof THTWAATError) throw err;
        if ((err as Error)?.name === "AbortError") {
          throw new THTWAATError("Request aborted or timed out", {
            code: "aborted",
            retryable: false,
            cause: err,
          });
        }
        throw new THTWAATError((err as Error)?.message || "Network error", {
          code: "network_error",
          retryable: true,
          cause: err,
        });
      } finally {
        clearTimeout(timeout);
        init.signal?.removeEventListener("abort", onOuterAbort);
      }
    };

    if (init.skipRetry || this.opts.maxRetries <= 0) {
      return run();
    }

    return withRetry(run, {
      maxRetries: this.opts.maxRetries,
      signal: init.signal,
      shouldRetry: (err) => err instanceof THTWAATError && err.retryable,
    });
  }

  async stream(
    path: string,
    init: RequestInit & { signal?: AbortSignal } = {}
  ): Promise<Response> {
    const url = `${this.opts.baseURL.replace(/\/$/, "")}${path}`;
    const headers: Record<string, string> = {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
      ...this.opts.defaultHeaders,
      ...this.opts.getAuthHeaders(),
      ...(init.headers as Record<string, string> | undefined),
    };

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.opts.timeoutMs);
    const onOuterAbort = () => controller.abort(init.signal?.reason);
    if (init.signal) {
      if (init.signal.aborted) controller.abort(init.signal.reason);
      else init.signal.addEventListener("abort", onOuterAbort, { once: true });
    }

    try {
      const res = await this.opts.fetchImpl(url, {
        ...init,
        headers,
        signal: controller.signal,
      });
      if (!res.ok) {
        const text = await res.text();
        let body: unknown = text;
        try {
          body = JSON.parse(text);
        } catch {
          /* keep text */
        }
        throw parseApiError(res.status, body);
      }
      return res;
    } finally {
      clearTimeout(timeout);
      init.signal?.removeEventListener("abort", onOuterAbort);
    }
  }
}
