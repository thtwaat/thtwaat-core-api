"""Webhook delivery outbox helpers (Week 4 Day 1).

Day 1: record pending + mark queued after Redis RPUSH.
Day 2: worker claim / ACK / redrive.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.webhooks.model import (
    WEBHOOK_DELIVERY_PENDING,
    WEBHOOK_DELIVERY_QUEUED,
    WebhookDelivery,
)

logger = logging.getLogger(__name__)


def record_pending_delivery(
    db: Session,
    *,
    delivery_id: str,
    company_id: UUID,
    webhook_id: UUID | str | None,
    event: str,
    url: str,
    payload: Dict[str, Any],
) -> WebhookDelivery:
    """Insert a durable outbox row (status=pending). Commits immediately."""
    wh_uuid: Optional[UUID] = None
    if webhook_id is not None:
        wh_uuid = webhook_id if isinstance(webhook_id, UUID) else UUID(str(webhook_id))

    row = WebhookDelivery(
        delivery_id=delivery_id,
        company_id=company_id,
        webhook_id=wh_uuid,
        event=event,
        url=url,
        payload=payload,
        status=WEBHOOK_DELIVERY_PENDING,
        attempts=0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def mark_delivery_queued(db: Session, delivery_id: str) -> Optional[WebhookDelivery]:
    """Flip pending → queued after Redis accept. Soft no-op if row missing."""
    row = (
        db.query(WebhookDelivery)
        .filter(WebhookDelivery.delivery_id == delivery_id)
        .first()
    )
    if row is None:
        return None
    if row.status == WEBHOOK_DELIVERY_PENDING:
        row.status = WEBHOOK_DELIVERY_QUEUED
        db.commit()
        db.refresh(row)
    return row
