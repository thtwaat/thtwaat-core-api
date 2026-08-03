"""Week 4 Day 1 — webhook_deliveries outbox dual-write."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.openai_compat.events import EVENT_COMPLETION_SUCCEEDED
from app.openai_compat.notify import enqueue_webhook_dispatch
from app.webhooks.model import WEBHOOK_DELIVERY_PENDING, WEBHOOK_DELIVERY_QUEUED
from app.webhooks.outbox import mark_delivery_queued, record_pending_delivery


@pytest.mark.unit
def test_record_pending_delivery_commits_row():
    db = MagicMock()
    company_id = uuid.uuid4()
    webhook_id = uuid.uuid4()
    instance = MagicMock()

    with patch("app.webhooks.outbox.WebhookDelivery", return_value=instance) as cls:
        row = record_pending_delivery(
            db,
            delivery_id="whdel_test1",
            company_id=company_id,
            webhook_id=webhook_id,
            event=EVENT_COMPLETION_SUCCEEDED,
            url="https://example.com/hook",
            payload={"event": EVENT_COMPLETION_SUCCEEDED, "delivery_id": "whdel_test1"},
        )

    assert row is instance
    cls.assert_called_once()
    kwargs = cls.call_args.kwargs
    assert kwargs["delivery_id"] == "whdel_test1"
    assert kwargs["status"] == WEBHOOK_DELIVERY_PENDING
    db.add.assert_called_once_with(instance)
    db.commit.assert_called()


@pytest.mark.unit
def test_mark_delivery_queued_flips_pending():
    db = MagicMock()
    row = MagicMock()
    row.status = WEBHOOK_DELIVERY_PENDING
    db.query.return_value.filter.return_value.first.return_value = row
    out = mark_delivery_queued(db, "whdel_q")
    assert out is row
    assert row.status == WEBHOOK_DELIVERY_QUEUED
    db.commit.assert_called()


@pytest.mark.unit
def test_enqueue_dual_writes_outbox_then_redis(monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.notify.settings.WEBHOOK_OUTBOX_ENABLED",
        True,
        raising=False,
    )
    company_id = uuid.uuid4()
    webhook_id = uuid.uuid4()
    db = MagicMock()
    recorded = {}

    def _record(session, **kwargs):
        recorded.update(kwargs)
        return MagicMock()

    with patch(
        "app.monitoring.queue.enqueue", return_value={"enqueued": True}
    ) as enq, patch(
        "app.webhooks.delivery.new_delivery_id", return_value="whdel_fixed"
    ), patch(
        "app.webhooks.outbox.record_pending_delivery", _record
    ), patch(
        "app.webhooks.outbox.mark_delivery_queued"
    ) as mark_queued:
        result = enqueue_webhook_dispatch(
            company_id=company_id,
            webhook_id=webhook_id,
            url="https://example.com/a",
            secret="whsec_x",
            event=EVENT_COMPLETION_SUCCEEDED,
            data={"completion_id": "chatcmpl_1"},
            db=db,
        )

    assert result == {"enqueued": True}
    assert recorded["delivery_id"] == "whdel_fixed"
    assert recorded["event"] == EVENT_COMPLETION_SUCCEEDED
    assert recorded["payload"]["delivery_id"] == "whdel_fixed"
    enq.assert_called_once()
    job = enq.call_args[0][0]
    assert job["delivery_id"] == "whdel_fixed"
    assert job["type"] == "webhook.dispatch"
    mark_queued.assert_called_once_with(db, "whdel_fixed")


@pytest.mark.unit
def test_enqueue_skips_outbox_when_disabled(monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.notify.settings.WEBHOOK_OUTBOX_ENABLED",
        False,
        raising=False,
    )
    with patch(
        "app.monitoring.queue.enqueue", return_value={"enqueued": True}
    ), patch(
        "app.webhooks.delivery.new_delivery_id", return_value="whdel_x"
    ), patch(
        "app.webhooks.outbox.record_pending_delivery"
    ) as record:
        result = enqueue_webhook_dispatch(
            company_id=uuid.uuid4(),
            webhook_id=uuid.uuid4(),
            url="https://example.com/a",
            secret="whsec_x",
            event=EVENT_COMPLETION_SUCCEEDED,
            data={},
            db=MagicMock(),
        )
    assert result == {"enqueued": True}
    record.assert_not_called()
