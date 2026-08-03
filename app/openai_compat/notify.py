"""Enqueue completion webhooks onto Redis worker (Week 3 Day 1).

Fail-open: Redis / DB lookup errors are logged and never raise to the client.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.openai_compat.events import COMPLETION_EVENTS
from app.webhooks.repository import WebhookRepository

logger = logging.getLogger(__name__)

JOB_TYPE_WEBHOOK_DISPATCH = "webhook.dispatch"


def _matching_hooks(db: Session, company_id: UUID, event: str) -> List[Any]:
    hooks = WebhookRepository(db).get_active_by_company(str(company_id))
    out = []
    for wh in hooks:
        types = wh.event_types or []
        if "*" in types or event in types:
            out.append(wh)
    return out


def enqueue_webhook_dispatch(
    *,
    company_id: UUID,
    webhook_id: UUID | str,
    url: str,
    secret: str,
    event: str,
    data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Push one `webhook.dispatch` job. Returns enqueue result or None on soft-fail."""
    if event not in COMPLETION_EVENTS and event != "ping":
        # Allow future events; still enqueue if caller is explicit
        pass
    try:
        from app.monitoring.queue import enqueue
        from app.webhooks.delivery import new_delivery_id

        return enqueue(
            {
                "type": JOB_TYPE_WEBHOOK_DISPATCH,
                "company_id": str(company_id),
                "webhook_id": str(webhook_id),
                "url": url,
                "secret": secret,
                "event": event,
                "data": data,
                # Stable across retries so receivers can dedupe (Week 3 Day 5).
                "delivery_id": new_delivery_id(),
            }
        )
    except Exception as exc:  # noqa: BLE001 — soft-fail
        logger.warning("webhook enqueue failed event=%s err=%s", event, exc)
        return None


def enqueue_completion_webhooks(
    db: Session,
    company_id: UUID,
    event: str,
    data: Dict[str, Any],
) -> int:
    """Fan-out: one Redis job per subscribed webhook. Returns jobs enqueued."""
    if event not in COMPLETION_EVENTS:
        logger.debug("skip non-completion event=%s", event)
        return 0
    try:
        hooks = _matching_hooks(db, company_id, event)
    except Exception as exc:  # noqa: BLE001
        logger.warning("webhook lookup failed company=%s err=%s", company_id, exc)
        return 0

    n = 0
    for wh in hooks:
        result = enqueue_webhook_dispatch(
            company_id=company_id,
            webhook_id=wh.id,
            url=wh.url,
            secret=wh.secret,
            event=event,
            data=data,
        )
        if result and result.get("enqueued"):
            n += 1
    return n
