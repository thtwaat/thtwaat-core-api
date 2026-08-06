"""Studio deployment progress events (SSE)."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List
from uuid import UUID

logger = logging.getLogger(__name__)


def _events_key(deployment_id: UUID) -> str:
    return f"thtwaat:studio:deploy:{deployment_id}:events"


def publish_deploy_event(deployment_id: UUID, event: str, payload: Dict[str, Any]) -> None:
    try:
        from app.monitoring.queue import _client

        r = _client()
        body = {"event": event, **payload}
        r.rpush(_events_key(deployment_id), json.dumps(body))
        r.ltrim(_events_key(deployment_id), -200, -1)
        r.expire(_events_key(deployment_id), 86400)
        r.publish(f"thtwaat:studio:deploy:{deployment_id}", json.dumps(body))
    except Exception as exc:  # noqa: BLE001
        logger.debug("publish_deploy_event failed: %s", exc)


def list_deploy_events(deployment_id: UUID, after: int = 0) -> List[Dict[str, Any]]:
    try:
        from app.monitoring.queue import _client

        r = _client()
        raw = r.lrange(_events_key(deployment_id), max(after, 0), -1)
        out: List[Dict[str, Any]] = []
        for item in raw:
            try:
                out.append(json.loads(item))
            except Exception:
                out.append({"raw": item})
        return out
    except Exception:
        return []
