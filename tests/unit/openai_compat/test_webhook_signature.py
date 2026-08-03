"""Week 3 Day 5 — HMAC signature + replay-window tests."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from app.webhooks.delivery import (
    WebhookSignatureError,
    sign_payload,
    sign_v1,
    verify_webhook_signature,
)


def test_sign_v1_and_verify_roundtrip():
    body = '{"event":"completion.succeeded","data":{}}'
    secret = "whsec_test"
    ts, sig = sign_v1(body, secret, timestamp=1_700_000_000)
    assert sig.startswith("v1=")
    assert verify_webhook_signature(
        body,
        secret,
        signature_header=sig,
        timestamp_header=str(ts),
        now=1_700_000_000,
        tolerance_seconds=60,
    )


def test_verify_combined_t_v1_header():
    body = '{"a":1}'
    secret = "s"
    ts, sig = sign_v1(body, secret, timestamp=100)
    header = f"t={ts},{sig}"
    assert verify_webhook_signature(
        body, secret, signature_header=header, now=100, tolerance_seconds=5
    )


def test_verify_rejects_stale_timestamp():
    body = '{"a":1}'
    secret = "s"
    ts, sig = sign_v1(body, secret, timestamp=100)
    with pytest.raises(WebhookSignatureError) as exc:
        verify_webhook_signature(
            body,
            secret,
            signature_header=sig,
            timestamp_header=str(ts),
            now=100 + 400,
            tolerance_seconds=300,
        )
    assert "tolerance" in str(exc.value).lower() or "replay" in str(exc.value).lower()


def test_verify_rejects_tampered_body():
    body = '{"a":1}'
    secret = "s"
    ts, sig = sign_v1(body, secret, timestamp=50)
    with pytest.raises(WebhookSignatureError):
        verify_webhook_signature(
            '{"a":2}',
            secret,
            signature_header=sig,
            timestamp_header=str(ts),
            now=50,
            tolerance_seconds=60,
        )


def test_legacy_sha256_still_verifies():
    body = '{"event":"ping"}'
    secret = "legacy"
    header = sign_payload(body, secret)
    assert verify_webhook_signature(body, secret, signature_header=header)


def test_deliver_webhook_sets_v1_headers():
    from app.webhooks.delivery import deliver_webhook

    mock_resp = MagicMock()
    mock_resp.status_code = 204
    mock_resp.text = ""
    with patch("app.webhooks.delivery.requests.post", return_value=mock_resp) as post:
        deliver_webhook(
            "https://example.com/hook",
            {"event": "completion.succeeded", "data": {}},
            "whsec_x",
            timestamp=1_700_000_111,
        )
    headers = post.call_args.kwargs["headers"]
    assert headers["X-THTWAAT-Timestamp"] == "1700000111"
    assert headers["X-THTWAAT-Signature"].startswith("v1=")
    body = post.call_args.kwargs["data"]
    assert "delivery_id" in body
