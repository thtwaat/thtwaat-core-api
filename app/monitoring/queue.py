"""Redis job-queue introspection for the existing worker (thtwaat:jobs)."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from app.config.settings import settings

logger = logging.getLogger(__name__)

JOBS_KEY = "thtwaat:jobs"
DEAD_KEY = "thtwaat:jobs:dead"
DELAYED_KEY = "thtwaat:jobs:delayed"
HEARTBEAT_KEY = "thtwaat:worker:heartbeat"
CANCELLED_SET = "thtwaat:jobs:cancelled"


def _client():
    import redis

    return redis.from_url(
        f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}",
        decode_responses=True,
    )


def cache_hit_ratio() -> Dict[str, Any]:
    """Derive Redis keyspace hit ratio from INFO stats (not a Prom duplicate)."""
    try:
        r = _client()
        info = r.info("stats")
        hits = int(info.get("keyspace_hits") or 0)
        misses = int(info.get("keyspace_misses") or 0)
        total = hits + misses
        ratio = round(hits / total, 4) if total else None
        return {
            "ok": True,
            "keyspace_hits": hits,
            "keyspace_misses": misses,
            "hit_ratio": ratio,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "hit_ratio": None}


def list_jobs(limit: int = 50, dead: bool = False) -> List[Dict[str, Any]]:
    try:
        r = _client()
        key = DEAD_KEY if dead else JOBS_KEY
        raw_items = r.lrange(key, 0, max(limit - 1, 0))
        out: List[Dict[str, Any]] = []
        for idx, raw in enumerate(raw_items):
            try:
                payload = json.loads(raw)
            except Exception:
                payload = {"raw": raw}
            out.append(
                {
                    "index": idx,
                    "queue": "dead" if dead else "active",
                    "payload": payload,
                    "raw": raw,
                }
            )
        return out
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Queue unavailable: {exc}") from exc


def enqueue(job: Dict[str, Any]) -> Dict[str, Any]:
    try:
        r = _client()
        payload = dict(job)
        payload.setdefault("enqueued_at", datetime.now(timezone.utc).isoformat())
        payload.setdefault("attempt", 1)
        raw = json.dumps(payload)
        r.rpush(JOBS_KEY, raw)
        return {"enqueued": True, "payload": payload}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Enqueue failed: {exc}") from exc


def enqueue_delayed(job: Dict[str, Any], *, ready_at: float) -> Dict[str, Any]:
    """Schedule a job onto the delayed ZSET until ready_at (unix epoch seconds)."""
    try:
        r = _client()
        payload = dict(job)
        payload["ready_at"] = ready_at
        payload["delayed_at"] = datetime.now(timezone.utc).isoformat()
        raw = json.dumps(payload)
        r.zadd(DELAYED_KEY, {raw: float(ready_at)})
        return {"delayed": True, "ready_at": ready_at, "payload": payload}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Delayed enqueue failed: {exc}") from exc


def promote_due_jobs(*, now: Optional[float] = None, limit: int = 100) -> int:
    """Move due delayed jobs onto the active list. Returns count promoted."""
    import time as _time

    try:
        r = _client()
        ts = float(now if now is not None else _time.time())
        due = r.zrangebyscore(DELAYED_KEY, min="-inf", max=ts, start=0, num=max(limit, 1))
        moved = 0
        for raw in due:
            # Atomic-ish: remove from ZSET then push; if remove fails, skip
            removed = r.zrem(DELAYED_KEY, raw)
            if not removed:
                continue
            r.rpush(JOBS_KEY, raw)
            moved += 1
        return moved
    except Exception as exc:
        logger.warning("promote_due_jobs failed: %s", exc)
        return 0


def dead_letter(job: Dict[str, Any], *, reason: str) -> Dict[str, Any]:
    try:
        r = _client()
        payload = dict(job)
        payload["dead_at"] = datetime.now(timezone.utc).isoformat()
        payload["dead_reason"] = reason
        r.rpush(DEAD_KEY, json.dumps(payload))
        return {"dead": True, "payload": payload}
    except Exception as exc:
        logger.warning("dead_letter failed: %s", exc)
        return {"dead": False, "error": str(exc)}


def queue_stats() -> Dict[str, Any]:
    try:
        r = _client()
        depth = int(r.llen(JOBS_KEY) or 0)
        dead = int(r.llen(DEAD_KEY) or 0)
        delayed = int(r.zcard(DELAYED_KEY) or 0)
        beat = r.get(HEARTBEAT_KEY)
        cancelled = int(r.scard(CANCELLED_SET) or 0)
        return {
            "ok": True,
            "queue_depth": depth,
            "dead_letter_depth": dead,
            "delayed_depth": delayed,
            "cancelled_markers": cancelled,
            "worker_heartbeat": beat,
            "worker_alive": beat is not None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "queue_depth": 0,
            "dead_letter_depth": 0,
            "delayed_depth": 0,
        }


def retry_dead(index: int = 0) -> Dict[str, Any]:
    """Move one dead-letter job back onto the active queue."""
    try:
        r = _client()
        raw = r.lindex(DEAD_KEY, index)
        if raw is None:
            raise HTTPException(status_code=404, detail="Dead-letter job not found at index")
        # LREM one occurrence then RPUSH to active
        removed = r.lrem(DEAD_KEY, 1, raw)
        if not removed:
            raise HTTPException(status_code=409, detail="Failed to remove dead-letter job")
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"raw": raw}
        payload["retried_at"] = datetime.now(timezone.utc).isoformat()
        payload["retry_from"] = "dead_letter"
        new_raw = json.dumps(payload) if isinstance(payload, dict) and "raw" not in payload else raw
        if isinstance(payload, dict) and "raw" not in payload:
            r.rpush(JOBS_KEY, new_raw)
        else:
            r.rpush(JOBS_KEY, raw)
        return {"retried": True, "payload": payload}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Retry failed: {exc}") from exc


def cancel_job(index: int = 0, dead: bool = False, job_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Cancel a queued job by removing it from the list.
    Optionally record a cancel marker by job_id for in-flight awareness.
    """
    try:
        r = _client()
        key = DEAD_KEY if dead else JOBS_KEY
        if job_id:
            r.sadd(CANCELLED_SET, job_id)
            r.expire(CANCELLED_SET, 86400)
        raw = r.lindex(key, index)
        if raw is None:
            raise HTTPException(status_code=404, detail="Job not found at index")
        removed = r.lrem(key, 1, raw)
        if not removed:
            raise HTTPException(status_code=409, detail="Failed to cancel job")
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"raw": raw}
        return {"cancelled": True, "payload": payload, "queue": "dead" if dead else "active"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Cancel failed: {exc}") from exc
