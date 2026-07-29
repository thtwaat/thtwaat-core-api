export class RestError extends Error {
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
    this.name = "RestError";
    this.status = opts.status;
    this.code = opts.code;
    this.details = opts.details;
    this.retryable = Boolean(opts.retryable);
    if (opts.cause !== undefined) {
      (this as Error & { cause?: unknown }).cause = opts.cause;
    }
  }
}

export function normalizeError(status: number, body: unknown): RestError {
  let message = `HTTP ${status}`;
  let details: unknown = body;

  if (typeof body === "string" && body.trim()) {
    message = body;
  } else if (body && typeof body === "object") {
    const obj = body as Record<string, unknown>;
    if (typeof obj.detail === "string") message = obj.detail;
    else if (Array.isArray(obj.detail)) {
      message = obj.detail
        .map((d) => (typeof d === "object" && d && "msg" in d ? String((d as any).msg) : JSON.stringify(d)))
        .join("; ");
      details = obj.detail;
    } else if (obj.detail && typeof obj.detail === "object") {
      const d = obj.detail as Record<string, unknown>;
      message = String(d.message || d.msg || message);
      details = obj.detail;
    } else if (typeof obj.message === "string") {
      message = obj.message;
    }
  }

  const retryable = status === 429 || status === 502 || status === 503 || status === 504;
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

  return new RestError(message, { status, code, details, retryable });
}

export function isRetryableStatus(status: number, extra: number[] = []): boolean {
  return [429, 502, 503, 504, ...extra].includes(status);
}
