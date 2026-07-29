export class THTWAATError extends Error {
  readonly status?: number;
  readonly code?: string;
  readonly details?: unknown;
  readonly retryable: boolean;

  constructor(
    message: string,
    opts: {
      status?: number;
      code?: string;
      details?: unknown;
      retryable?: boolean;
      cause?: unknown;
    } = {}
  ) {
    super(message);
    this.name = "THTWAATError";
    this.status = opts.status;
    this.code = opts.code;
    this.details = opts.details;
    this.retryable = Boolean(opts.retryable);
    if (opts.cause !== undefined) {
      (this as Error & { cause?: unknown }).cause = opts.cause;
    }
  }
}

export function parseApiError(status: number, body: unknown): THTWAATError {
  let message = `Request failed (${status})`;
  let details: unknown = body;

  if (typeof body === "string" && body.trim()) {
    message = body;
  } else if (body && typeof body === "object") {
    const obj = body as Record<string, unknown>;
    if (typeof obj.detail === "string") message = obj.detail;
    else if (obj.detail && typeof obj.detail === "object") {
      const d = obj.detail as Record<string, unknown>;
      message = String(d.message || d.msg || message);
      details = obj.detail;
    } else if (typeof obj.message === "string") {
      message = obj.message;
    }
  }

  const retryable = status === 429 || status >= 500;
  const code =
    status === 401
      ? "unauthorized"
      : status === 403
        ? "forbidden"
        : status === 404
          ? "not_found"
          : status === 429
            ? "rate_limited"
            : status >= 500
              ? "server_error"
              : "request_failed";

  return new THTWAATError(message, { status, code, details, retryable });
}

export function isRateLimited(err: unknown): boolean {
  return err instanceof THTWAATError && (err.status === 429 || err.code === "rate_limited");
}
