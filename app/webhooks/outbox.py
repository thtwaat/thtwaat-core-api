"""Webhook delivery outbox helpers (Week 4 Day 1–2).

Day 1: record pending + mark queued after Redis RPUSH.
Day 2: worker ACK (delivered / failed / dead) + redrive stuck rows.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.webhooks.model import (
    WEBHOOK_DELIVERY_DEAD,
    WEBHOOK_DELIVERY_DELIVERED,
    WEBHOOK_DELIVERY_FAILED,
    WEBHOOK_DELIVERY_PENDING,
    WEBHOOK_DELIVERY_QUEUED,
    Webhook,
    WebhookDelivery,
)

logger = logging.getLogger(__name__)

JOB_TYPE_WEBHOOK_DISPATCH = "webhook.dispatch"


def _ensure_orm_models() -> None:
    """Webhook.company relationship needs Company registered (worker has no main.py)."""
    import app.companies.model  # noqa: F401


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_by_delivery_id(db: Session, delivery_id: str) -> Optional[WebhookDelivery]:
    if not delivery_id:
        return None
    return (
        db.query(WebhookDelivery)
        .filter(WebhookDelivery.delivery_id == delivery_id)
        .first()
    )


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
    row = _get_by_delivery_id(db, delivery_id)
    if row is None:
        return None
    if row.status in (WEBHOOK_DELIVERY_PENDING, WEBHOOK_DELIVERY_FAILED):
        row.status = WEBHOOK_DELIVERY_QUEUED
        row.next_attempt_at = None
        db.commit()
        db.refresh(row)
    return row


def mark_delivery_attempt(
    db: Session,
    delivery_id: str,
    *,
    attempt: int,
) -> Optional[WebhookDelivery]:
    """Record that the worker is processing this delivery_id."""
    row = _get_by_delivery_id(db, delivery_id)
    if row is None:
        return None
    row.attempts = max(int(attempt), int(row.attempts or 0))
    if row.status in (WEBHOOK_DELIVERY_PENDING, WEBHOOK_DELIVERY_FAILED):
        row.status = WEBHOOK_DELIVERY_QUEUED
    db.commit()
    db.refresh(row)
    return row


def mark_delivery_delivered(
    db: Session,
    delivery_id: str,
    *,
    attempt: Optional[int] = None,
) -> Optional[WebhookDelivery]:
    row = _get_by_delivery_id(db, delivery_id)
    if row is None:
        return None
    row.status = WEBHOOK_DELIVERY_DELIVERED
    row.delivered_at = _utcnow()
    row.last_error = None
    row.next_attempt_at = None
    if attempt is not None:
        row.attempts = max(int(attempt), int(row.attempts or 0))
    db.commit()
    db.refresh(row)
    return row


def mark_delivery_failed(
    db: Session,
    delivery_id: str,
    *,
    reason: str,
    attempt: int,
    next_attempt_at: Optional[datetime] = None,
) -> Optional[WebhookDelivery]:
    """Soft failure — will retry (Redis delayed and/or outbox redrive)."""
    row = _get_by_delivery_id(db, delivery_id)
    if row is None:
        return None
    row.status = WEBHOOK_DELIVERY_FAILED
    row.last_error = (reason or "")[:2000]
    row.attempts = max(int(attempt), int(row.attempts or 0))
    row.next_attempt_at = next_attempt_at
    db.commit()
    db.refresh(row)
    return row


def mark_delivery_dead(
    db: Session,
    delivery_id: str,
    *,
    reason: str,
    attempt: int,
) -> Optional[WebhookDelivery]:
    row = _get_by_delivery_id(db, delivery_id)
    if row is None:
        return None
    row.status = WEBHOOK_DELIVERY_DEAD
    row.last_error = (reason or "")[:2000]
    row.attempts = max(int(attempt), int(row.attempts or 0))
    row.next_attempt_at = None
    db.commit()
    db.refresh(row)
    return row


def _outbox_enabled() -> bool:
    return bool(getattr(settings, "WEBHOOK_OUTBOX_ENABLED", True))


def ack_from_job_payload(
    db: Session,
    payload: Dict[str, Any],
    *,
    outcome: str,
    reason: str = "",
    next_attempt_at: Optional[datetime] = None,
) -> None:
    """Soft-fail wrapper used by the worker."""
    if not _outbox_enabled():
        return
    delivery_id = payload.get("delivery_id")
    if not delivery_id:
        return
    _ensure_orm_models()
    attempt = int(payload.get("attempt") or 1)
    try:
        if outcome == "delivered":
            mark_delivery_delivered(db, str(delivery_id), attempt=attempt)
        elif outcome == "failed":
            mark_delivery_failed(
                db,
                str(delivery_id),
                reason=reason,
                attempt=attempt,
                next_attempt_at=next_attempt_at,
            )
        elif outcome == "dead":
            mark_delivery_dead(
                db, str(delivery_id), reason=reason, attempt=attempt
            )
        elif outcome == "attempt":
            mark_delivery_attempt(db, str(delivery_id), attempt=attempt)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "outbox ack failed delivery_id=%s outcome=%s err=%s",
            delivery_id,
            outcome,
            exc,
        )


def list_redrive_candidates(
    db: Session,
    *,
    limit: int = 50,
    stale_seconds: Optional[int] = None,
) -> List[WebhookDelivery]:
    """Rows that likely lost their Redis job or are due for retry."""
    stale = int(
        stale_seconds
        if stale_seconds is not None
        else getattr(settings, "WEBHOOK_OUTBOX_STALE_SECONDS", 120) or 120
    )
    now = _utcnow()
    stale_before = now - timedelta(seconds=max(stale, 1))

    q = (
        db.query(WebhookDelivery)
        .filter(
            or_(
                # Never made it onto Redis / mark_queued failed
                and_(
                    WebhookDelivery.status == WEBHOOK_DELIVERY_PENDING,
                    WebhookDelivery.created_at <= stale_before,
                ),
                # Job likely lost after BLPOP / worker crash
                and_(
                    WebhookDelivery.status == WEBHOOK_DELIVERY_QUEUED,
                    WebhookDelivery.updated_at <= stale_before,
                ),
                # Retry due (mirrors delayed queue; safety net)
                and_(
                    WebhookDelivery.status == WEBHOOK_DELIVERY_FAILED,
                    or_(
                        WebhookDelivery.next_attempt_at.is_(None),
                        WebhookDelivery.next_attempt_at <= now,
                    ),
                    WebhookDelivery.updated_at <= stale_before,
                ),
            )
        )
        .order_by(WebhookDelivery.created_at.asc())
        .limit(max(1, int(limit)))
    )
    return list(q.all())


def build_redis_job_from_outbox(
    db: Session,
    row: WebhookDelivery,
) -> Optional[Dict[str, Any]]:
    """Rebuild webhook.dispatch job; secret loaded from webhooks table."""
    _ensure_orm_models()
    secret = ""
    if row.webhook_id is not None:
        wh = db.query(Webhook).filter(Webhook.id == row.webhook_id).first()
        if wh is None or not wh.is_active:
            logger.warning(
                "outbox redrive skip delivery_id=%s — webhook missing/inactive",
                row.delivery_id,
            )
            return None
        secret = wh.secret or ""
        url = wh.url or row.url
    else:
        url = row.url

    data = {}
    if isinstance(row.payload, dict):
        data = row.payload.get("data") or {}

    prior = int(row.attempts or 0)
    if row.status == WEBHOOK_DELIVERY_QUEUED:
        # Replay the in-flight attempt that was likely lost from Redis
        attempt = max(prior, 1)
    else:
        attempt = prior + 1
    max_attempts = int(getattr(settings, "WEBHOOK_MAX_ATTEMPTS", 5) or 5)
    if attempt > max_attempts:
        mark_delivery_dead(
            db,
            row.delivery_id,
            reason=f"redrive_exhausted attempt={attempt}/{max_attempts}",
            attempt=attempt,
        )
        return None

    return {
        "type": JOB_TYPE_WEBHOOK_DISPATCH,
        "company_id": str(row.company_id),
        "webhook_id": str(row.webhook_id) if row.webhook_id else None,
        "url": url,
        "secret": secret,
        "event": row.event,
        "data": data,
        "delivery_id": row.delivery_id,
        "attempt": attempt,
        "redriven_from_outbox": True,
    }


def redrive_stuck_deliveries(
    db: Session,
    *,
    limit: Optional[int] = None,
    stale_seconds: Optional[int] = None,
) -> int:
    """Re-enqueue stuck outbox rows onto Redis. Returns count enqueued."""
    if not _outbox_enabled():
        return 0
    _ensure_orm_models()
    batch = int(
        limit
        if limit is not None
        else getattr(settings, "WEBHOOK_OUTBOX_REDRIVE_BATCH", 50) or 50
    )
    try:
        from app.monitoring.queue import enqueue
    except Exception as exc:  # noqa: BLE001
        logger.warning("outbox redrive enqueue import failed: %s", exc)
        return 0

    n = 0
    try:
        rows = list_redrive_candidates(
            db, limit=batch, stale_seconds=stale_seconds
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("outbox redrive query failed: %s", exc)
        return 0

    for row in rows:
        try:
            job = build_redis_job_from_outbox(db, row)
            if not job:
                continue
            result = enqueue(job)
            if result and result.get("enqueued"):
                mark_delivery_queued(db, row.delivery_id)
                n += 1
                logger.info(
                    "outbox_redrive delivery_id=%s attempt=%s",
                    row.delivery_id,
                    job["attempt"],
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "outbox redrive failed delivery_id=%s err=%s",
                getattr(row, "delivery_id", "?"),
                exc,
            )
    return n
