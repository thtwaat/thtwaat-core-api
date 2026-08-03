"""Enqueue completion webhooks onto Redis worker (Week 3 Day 1 + Week 4 Day 1 outbox).

Fail-open: Redis / DB lookup / outbox errors are logged and never raise to the client.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.config.settings import settings
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
    db: Optional[Session] = None,
) -> Optional[Dict[str, Any]]:
    """Push one `webhook.dispatch` job. Optionally dual-write outbox first (W4 D1)."""
    if event not in COMPLETION_EVENTS and event != "ping":
        # Allow future events; still enqueue if caller is explicit
        pass
    try:
        from app.monitoring.queue import enqueue
        from app.webhooks.delivery import new_delivery_id

        delivery_id = new_delivery_id()
        outbox_payload = {
            "event": event,
            "data": data,
            "company_id": str(company_id),
            "delivery_id": delivery_id,
        }

        if db is not None and getattr(settings, "WEBHOOK_OUTBOX_ENABLED", True):
            try:
                from app.webhooks.outbox import record_pending_delivery

                record_pending_delivery(
                    db,
                    delivery_id=delivery_id,
                    company_id=company_id,
                    webhook_id=webhook_id,
                    event=event,
                    url=url,
                    payload=outbox_payload,
                )
            except Exception as exc:  # noqa: BLE001 — soft-fail outbox
                logger.warning(
                    "webhook outbox write failed delivery_id=%s err=%s",
                    delivery_id,
                    exc,
                )

        result = enqueue(
            {
                "type": JOB_TYPE_WEBHOOK_DISPATCH,
                "company_id": str(company_id),
                "webhook_id": str(webhook_id),
                "url": url,
                "secret": secret,
                "event": event,
                "data": data,
                # Stable across retries so receivers can dedupe (Week 3 Day 5).
                "delivery_id": delivery_id,
            }
        )

        if (
            db is not None
            and getattr(settings, "WEBHOOK_OUTBOX_ENABLED", True)
            and result
            and result.get("enqueued")
        ):
            try:
                from app.webhooks.outbox import mark_delivery_queued

                mark_delivery_queued(db, delivery_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "webhook outbox mark_queued failed delivery_id=%s err=%s",
                    delivery_id,
                    exc,
                )

        return result
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
            db=db,
        )
        if result and result.get("enqueued"):
            n += 1
    return n
