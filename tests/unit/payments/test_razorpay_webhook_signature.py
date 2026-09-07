"""P0: Razorpay webhook must verify with RAZORPAY_WEBHOOK_SECRET, never
RAZORPAY_KEY_SECRET (the checkout/order secret), and must fail closed when
the webhook secret is not configured.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.database.orm_bootstrap import register_orm_models

register_orm_models()

from app.payments.webhooks.router import razorpay_webhook

WEBHOOK_SECRET = "whsec_test_razorpay_webhook_secret"
KEY_SECRET = "test_razorpay_checkout_key_secret"


def _sign(payload_bytes: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()


def _payload_bytes(event: str = "payment.failed") -> bytes:
    body = {
        "event": event,
        "payload": {
            "payment": {
                "entity": {
                    "id": f"pay_{uuid.uuid4().hex[:14]}",
                    "amount": 9900,
                    "currency": "INR",
                    "notes": {"company_id": str(uuid.uuid4())},
                }
            }
        },
    }
    return json.dumps(body).encode()


class _FakeRequest:
    def __init__(self, body: bytes):
        self._body = body

    async def body(self) -> bytes:
        return self._body


def _db_returning_existing(processed: bool) -> MagicMock:
    """A mock DB whose claim_webhook_event lookup finds an existing row."""
    db = MagicMock()
    existing = MagicMock()
    existing.processed = processed
    db.query.return_value.filter.return_value.first.return_value = existing
    return db


def _fresh_db() -> MagicMock:
    """A mock DB whose claim_webhook_event lookup finds nothing (first delivery)."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    return db


@pytest.fixture(autouse=True)
def _razorpay_secrets(monkeypatch):
    monkeypatch.setattr(
        "app.payments.webhooks.router.settings.RAZORPAY_WEBHOOK_SECRET", WEBHOOK_SECRET
    )
    monkeypatch.setattr(
        "app.payments.webhooks.router.settings.RAZORPAY_KEY_SECRET", KEY_SECRET
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_valid_webhook_secret_signature_is_accepted():
    payload = _payload_bytes()
    sig = _sign(payload, WEBHOOK_SECRET)
    db = _fresh_db()

    result = await razorpay_webhook(
        request=_FakeRequest(payload), x_razorpay_signature=sig, db=db
    )

    assert result["received"] is True
    db.commit.assert_called()  # claim_webhook_event + mark_webhook_processed


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invalid_signature_is_rejected():
    payload = _payload_bytes()
    db = _fresh_db()

    with pytest.raises(HTTPException) as exc:
        await razorpay_webhook(
            request=_FakeRequest(payload), x_razorpay_signature="0" * 64, db=db
        )

    assert exc.value.status_code == 400
    db.add.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_missing_webhook_secret_fails_closed(monkeypatch):
    monkeypatch.setattr(
        "app.payments.webhooks.router.settings.RAZORPAY_WEBHOOK_SECRET", None
    )
    payload = _payload_bytes()
    sig = _sign(payload, WEBHOOK_SECRET)
    db = MagicMock()

    with pytest.raises(HTTPException) as exc:
        await razorpay_webhook(
            request=_FakeRequest(payload), x_razorpay_signature=sig, db=db
        )

    assert exc.value.status_code == 503
    db.query.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_key_secret_does_not_validate_webhook():
    """A signature computed with RAZORPAY_KEY_SECRET (the checkout secret)
    must never be accepted for webhook verification."""
    payload = _payload_bytes()
    sig = _sign(payload, KEY_SECRET)
    db = _fresh_db()

    with pytest.raises(HTTPException) as exc:
        await razorpay_webhook(
            request=_FakeRequest(payload), x_razorpay_signature=sig, db=db
        )

    assert exc.value.status_code == 400
    db.add.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_duplicate_event_is_reported_and_not_reprocessed():
    """Existing idempotency: a webhook event already marked processed must
    short-circuit as a duplicate rather than being handled again."""
    payload = _payload_bytes()
    sig = _sign(payload, WEBHOOK_SECRET)
    db = _db_returning_existing(processed=True)

    result = await razorpay_webhook(
        request=_FakeRequest(payload), x_razorpay_signature=sig, db=db
    )

    assert result["duplicate"] is True
    db.add.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unprocessed_claim_is_reclaimed_not_duplicated():
    """A prior delivery that failed (processed=False) must be retried, not
    treated as a duplicate — preserves retry behavior."""
    payload = _payload_bytes()
    sig = _sign(payload, WEBHOOK_SECRET)
    db = _db_returning_existing(processed=False)

    result = await razorpay_webhook(
        request=_FakeRequest(payload), x_razorpay_signature=sig, db=db
    )

    assert result.get("duplicate") is not True
    assert result["received"] is True
    # No new BillingWebhookEvent row inserted — claim_webhook_event reuses
    # the existing unprocessed row rather than creating a second one.
    from app.payments.billing_extras import BillingWebhookEvent

    assert not any(
        call.args and isinstance(call.args[0], BillingWebhookEvent)
        for call in db.add.call_args_list
    )
