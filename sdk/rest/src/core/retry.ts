export async function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  if (ms <= 0) return;
  await new Promise<void>((resolve, reject) => {
    const t = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(t);
      reject(signal?.reason ?? new Error("Aborted"));
    };
    if (signal) {
      if (signal.aborted) onAbort();
      else signal.addEventListener("abort", onAbort, { once: true });
    }
  });
}

export interface RetryPolicy {
  maxRetries: number;
  baseDelayMs?: number;
  maxDelayMs?: number;
  signal?: AbortSignal;
  shouldRetry?: (error: unknown, attempt: number) => boolean;
}

export async function withRetry<T>(fn: (attempt: number) => Promise<T>, policy: RetryPolicy): Promise<T> {
  const base = policy.baseDelayMs ?? 300;
  const maxDelay = policy.maxDelayMs ?? 8000;
  let last: unknown;

  for (let attempt = 0; attempt <= policy.maxRetries; attempt++) {
    try {
      return await fn(attempt);
    } catch (err) {
      last = err;
      const ok =
        attempt < policy.maxRetries &&
        (policy.shouldRetry ? policy.shouldRetry(err, attempt) : true);
      if (!ok) break;
      const delay = Math.min(maxDelay, base * 2 ** attempt);
      await sleep(delay, policy.signal);
    }
  }
  throw last;
}
