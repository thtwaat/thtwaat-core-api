"""Week 4 Day 2 — outbox ACK + redrive."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.webhooks.model import (
    WEBHOOK_DELIVERY_DEAD,
    WEBHOOK_DELIVERY_DELIVERED,
    WEBHOOK_DELIVERY_FAILED,
    WEBHOOK_DELIVERY_PENDING,
    WEBHOOK_DELIVERY_QUEUED,
)
from app.webhooks.outbox import (
    ack_from_job_payload,
    build_redis_job_from_outbox,
    mark_delivery_dead,
    mark_delivery_delivered,
    mark_delivery_failed,
    redrive_stuck_deliveries,
)


def _row(**kwargs):
    row = MagicMock()
    row.delivery_id = kwargs.get("delivery_id", "whdel_x")
    row.company_id = kwargs.get("company_id", uuid.uuid4())
    row.webhook_id = kwargs.get("webhook_id", uuid.uuid4())
    row.event = kwargs.get("event", "completion.succeeded")
    row.url = kwargs.get("url", "https://example.com/hook")
    row.payload = kwargs.get("payload", {"data": {"completion_id": "c1"}})
    row.status = kwargs.get("status", WEBHOOK_DELIVERY_QUEUED)
    row.attempts = kwargs.get("attempts", 1)
    row.last_error = None
    row.next_attempt_at = kwargs.get("next_attempt_at")
    row.delivered_at = None
    return row


@pytest.mark.unit
def test_mark_delivery_delivered():
    db = MagicMock()
    row = _row(status=WEBHOOK_DELIVERY_QUEUED, attempts=1)
    db.query.return_value.filter.return_value.first.return_value = row
    out = mark_delivery_delivered(db, "whdel_x", attempt=1)
    assert out is row
    assert row.status == WEBHOOK_DELIVERY_DELIVERED
    assert row.delivered_at is not None
    db.commit.assert_called()


@pytest.mark.unit
def test_mark_delivery_failed_sets_next_attempt():
    db = MagicMock()
    row = _row()
    db.query.return_value.filter.return_value.first.return_value = row
    nxt = datetime.now(timezone.utc) + timedelta(seconds=4)
    mark_delivery_failed(db, "whdel_x", reason="timeout", attempt=1, next_attempt_at=nxt)
    assert row.status == WEBHOOK_DELIVERY_FAILED
    assert row.last_error == "timeout"
    assert row.next_attempt_at == nxt


@pytest.mark.unit
def test_mark_delivery_dead():
    db = MagicMock()
    row = _row(attempts=5)
    db.query.return_value.filter.return_value.first.return_value = row
    mark_delivery_dead(db, "whdel_x", reason="exhausted", attempt=5)
    assert row.status == WEBHOOK_DELIVERY_DEAD


@pytest.mark.unit
def test_ack_from_job_payload_delivered(monkeypatch):
    monkeypatch.setattr(
        "app.webhooks.outbox.settings.WEBHOOK_OUTBOX_ENABLED", True, raising=False
    )
    db = MagicMock()
    with patch("app.webhooks.outbox.mark_delivery_delivered") as m:
        ack_from_job_payload(
            db,
            {"delivery_id": "whdel_1", "attempt": 2},
            outcome="delivered",
        )
    m.assert_called_once_with(db, "whdel_1", attempt=2)


@pytest.mark.unit
def test_build_job_loads_secret_and_replays_queued_attempt():
    db = MagicMock()
    wh_id = uuid.uuid4()
    row = _row(status=WEBHOOK_DELIVERY_QUEUED, attempts=2, webhook_id=wh_id)
    wh = MagicMock()
    wh.is_active = True
    wh.secret = "whsec_live"
    wh.url = "https://customer.example/hook"
    db.query.return_value.filter.return_value.first.return_value = wh

    job = build_redis_job_from_outbox(db, row)
    assert job is not None
    assert job["secret"] == "whsec_live"
    assert job["attempt"] == 2  # replay same attempt
    assert job["delivery_id"] == row.delivery_id
    assert job["redriven_from_outbox"] is True


@pytest.mark.unit
def test_build_job_increments_attempt_for_failed():
    db = MagicMock()
    wh_id = uuid.uuid4()
    row = _row(status=WEBHOOK_DELIVERY_FAILED, attempts=2, webhook_id=wh_id)
    wh = MagicMock()
    wh.is_active = True
    wh.secret = "whsec_x"
    wh.url = row.url
    db.query.return_value.filter.return_value.first.return_value = wh

    job = build_redis_job_from_outbox(db, row)
    assert job["attempt"] == 3


@pytest.mark.unit
def test_redrive_stuck_enqueues_and_marks_queued(monkeypatch):
    monkeypatch.setattr(
        "app.webhooks.outbox.settings.WEBHOOK_OUTBOX_ENABLED", True, raising=False
    )
    db = MagicMock()
    row = _row(status=WEBHOOK_DELIVERY_PENDING, attempts=0)
    with patch(
        "app.webhooks.outbox.list_redrive_candidates", return_value=[row]
    ), patch(
        "app.webhooks.outbox.build_redis_job_from_outbox",
        return_value={
            "type": "webhook.dispatch",
            "delivery_id": row.delivery_id,
            "attempt": 1,
            "url": row.url,
            "secret": "s",
            "event": row.event,
            "data": {},
            "company_id": str(row.company_id),
            "webhook_id": str(row.webhook_id),
        },
    ), patch(
        "app.monitoring.queue.enqueue", return_value={"enqueued": True}
    ), patch(
        "app.webhooks.outbox.mark_delivery_queued"
    ) as mark_q:
        n = redrive_stuck_deliveries(db, limit=10, stale_seconds=1)
    assert n == 1
    mark_q.assert_called_once_with(db, row.delivery_id)


@pytest.mark.unit
def test_worker_failure_acks_dead():
    from scripts.worker import _handle_webhook_failure
    from app.webhooks.delivery import WebhookDeliveryError

    payload = {
        "type": "webhook.dispatch",
        "delivery_id": "whdel_dead",
        "attempt": 5,
        "event": "completion.succeeded",
    }
    with patch("app.database.database.SessionLocal") as sl, patch(
        "app.monitoring.queue.dead_letter"
    ) as dl, patch(
        "app.webhooks.outbox.ack_from_job_payload"
    ) as ack:
        db = MagicMock()
        sl.return_value = db
        _handle_webhook_failure(
            payload, WebhookDeliveryError("gone", status_code=410, retryable=False)
        )
    dl.assert_called_once()
    ack.assert_called_once()
    assert ack.call_args.kwargs["outcome"] == "dead"
