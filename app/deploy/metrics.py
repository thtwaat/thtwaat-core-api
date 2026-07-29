"""Deploy / ops monitoring metrics (Prometheus-friendly gauges via in-process counters)."""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)

_START = time.time()
_REQUESTS = 0
_ERRORS = 0
_MESSAGES = 0


def incr_requests() -> None:
    global _REQUESTS
    _REQUESTS += 1


def incr_errors() -> None:
    global _ERRORS
    _ERRORS += 1


def incr_messages(n: int = 1) -> None:
    global _MESSAGES
    _MESSAGES += n


def process_metrics() -> Dict[str, Any]:
    try:
        import psutil

        proc = psutil.Process(os.getpid())
        mem = proc.memory_info().rss / (1024 * 1024)
        cpu = proc.cpu_percent(interval=0.0)
        return {"cpu_percent": cpu, "memory_mb": round(mem, 2)}
    except Exception:
        return {
            "cpu_percent": None,
            "memory_mb": None,
            "note": "psutil optional",
        }


def certificates_expiring(db) -> Dict[str, Any]:
    try:
        from datetime import datetime, timezone, timedelta
        from app.domains.models import CompanyDomain, SslStatus

        now = datetime.now(timezone.utc)
        soon = now + timedelta(days=30)
        expiring = (
            db.query(CompanyDomain)
            .filter(
                CompanyDomain.ssl_expires_at.isnot(None),
                CompanyDomain.ssl_expires_at <= soon,
                CompanyDomain.ssl_status.in_([SslStatus.ACTIVE.value, SslStatus.ISSUED.value]),
            )
            .count()
        )
        expired = (
            db.query(CompanyDomain)
            .filter(CompanyDomain.ssl_status == SslStatus.EXPIRED.value)
            .count()
        )
        return {"expiring_30d": expiring, "expired": expired}
    except Exception as exc:
        return {"error": str(exc)}


def snapshot(db=None) -> Dict[str, Any]:
    uptime = int(time.time() - _START)
    queue = 0
    try:
        import redis

        from app.config.settings import settings

        r = redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}", decode_responses=True)
        queue = int(r.llen("thtwaat:jobs") or 0)
    except Exception:
        pass

    out: Dict[str, Any] = {
        "uptime_seconds": uptime,
        "api_requests": _REQUESTS,
        "errors": _ERRORS,
        "messages_total": _MESSAGES,
        "messages_per_min": round(_MESSAGES / max(uptime / 60, 1), 2),
        "queue_depth": queue,
        "process": process_metrics(),
    }
    if db is not None:
        out["certificates"] = certificates_expiring(db)
    return out
