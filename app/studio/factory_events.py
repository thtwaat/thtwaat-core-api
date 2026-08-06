"""Studio factory progress events via Redis (SSE + worker coordination)."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


def _events_key(build_id: UUID) -> str:
    return f"thtwaat:studio:build:{build_id}:events"


def _cancel_key(build_id: UUID) -> str:
    return f"thtwaat:studio:build:{build_id}:cancel"


def publish_build_event(build_id: UUID, event: str, payload: Dict[str, Any]) -> None:
    try:
        from app.monitoring.queue import _client

        r = _client()
        body = {"event": event, **payload}
        r.rpush(_events_key(build_id), json.dumps(body))
        r.ltrim(_events_key(build_id), -200, -1)
        r.expire(_events_key(build_id), 86400)
        r.publish(f"thtwaat:studio:build:{build_id}", json.dumps(body))
    except Exception as exc:  # noqa: BLE001
        logger.debug("publish_build_event failed: %s", exc)


def list_build_events(build_id: UUID, after: int = 0) -> List[Dict[str, Any]]:
    try:
        from app.monitoring.queue import _client

        r = _client()
        raw = r.lrange(_events_key(build_id), max(after, 0), -1)
        out: List[Dict[str, Any]] = []
        for item in raw:
            try:
                out.append(json.loads(item))
            except Exception:
                out.append({"raw": item})
        return out
    except Exception:
        return []


def request_cancel(build_id: UUID) -> None:
    try:
        from app.monitoring.queue import _client

        r = _client()
        r.setex(_cancel_key(build_id), 3600, "1")
    except Exception as exc:  # noqa: BLE001
        logger.debug("request_cancel failed: %s", exc)


def is_cancelled(build_id: UUID) -> bool:
    try:
        from app.monitoring.queue import _client

        r = _client()
        return bool(r.get(_cancel_key(build_id)))
    except Exception:
        return False
