"""
Lightweight load smoke for enterprise AI gateway retry path.

Usage:
  .venv/Scripts/python.exe -m tests.load.test_gateway_load
"""
from __future__ import annotations

import asyncio
import time

from app.openai_compat.policies.retry import RetryPolicy, with_retry


async def _worker(i: int) -> float:
    started = time.perf_counter()

    async def job():
        await asyncio.sleep(0.002)
        if i % 17 == 0:
            raise RuntimeError("transient")
        return i

    policy = RetryPolicy(max_attempts=3, backoff_ms=1, timeout_seconds=5)
    try:
        await with_retry(job, policy=policy)
    except RuntimeError:
        pass
    return (time.perf_counter() - started) * 1000


async def main() -> None:
    n = 200
    t0 = time.perf_counter()
    latencies = await asyncio.gather(*[_worker(i) for i in range(n)])
    elapsed = time.perf_counter() - t0
    avg = sum(latencies) / len(latencies)
    p95 = sorted(latencies)[int(0.95 * len(latencies)) - 1]
    print(f"gateway_load n={n} wall_s={elapsed:.3f} avg_ms={avg:.2f} p95_ms={p95:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
