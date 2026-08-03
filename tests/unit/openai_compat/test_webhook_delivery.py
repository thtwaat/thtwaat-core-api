"""Week 3 Day 2 — webhook delivery retry / backoff tests."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.webhooks.delivery import (
    WebhookDeliveryError,
    backoff_seconds,
    deliver_webhook,
    sign_payload,
)


def _load_worker():
    path = Path(__file__).resolve().parents[3] / "scripts" / "worker.py"
    spec = importlib.util.spec_from_file_location("thtwaat_worker", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_sign_payload_stable():
    sig = sign_payload('{"a":1}', "whsec_test")
    assert sig.startswith("sha256=")
    assert len(sig) == len("sha256=") + 64


def test_backoff_grows_and_caps():
    assert backoff_seconds(1, base=2.0, cap=300.0) == 2.0
    assert backoff_seconds(2, base=2.0, cap=300.0) == 4.0
    assert backoff_seconds(3, base=2.0, cap=300.0) == 8.0
    assert backoff_seconds(20, base=2.0, cap=300.0) == 300.0


def test_deliver_webhook_success(monkeypatch):
    monkeypatch.setattr(
        "app.webhooks.url_safety.settings.WEBHOOK_URL_RESOLVE_DNS",
        False,
        raising=False,
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "ok"
    with patch("app.webhooks.delivery.requests.post", return_value=mock_resp) as post:
        code, body = deliver_webhook(
            "https://example.com/hook",
            {"event": "completion.succeeded", "data": {}},
            "whsec_x",
        )
    assert code == 200
    assert body == "ok"
    kwargs = post.call_args.kwargs
    assert "X-THTWAAT-Signature" in kwargs["headers"]
    assert kwargs["headers"]["X-THTWAAT-Signature"].startswith("v1=")
    assert "X-THTWAAT-Timestamp" in kwargs["headers"]


def test_deliver_webhook_5xx_retryable(monkeypatch):
    monkeypatch.setattr(
        "app.webhooks.url_safety.settings.WEBHOOK_URL_RESOLVE_DNS",
        False,
        raising=False,
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_resp.text = "unavailable"
    with patch("app.webhooks.delivery.requests.post", return_value=mock_resp):
        with pytest.raises(WebhookDeliveryError) as exc:
            deliver_webhook("https://example.com/hook", {"event": "x"}, "sec")
    assert exc.value.retryable is True
    assert exc.value.status_code == 503


def test_deliver_webhook_4xx_not_retryable(monkeypatch):
    monkeypatch.setattr(
        "app.webhooks.url_safety.settings.WEBHOOK_URL_RESOLVE_DNS",
        False,
        raising=False,
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = "bad"
    with patch("app.webhooks.delivery.requests.post", return_value=mock_resp):
        with pytest.raises(WebhookDeliveryError) as exc:
            deliver_webhook("https://example.com/hook", {"event": "x"}, "sec")
    assert exc.value.retryable is False


def test_handle_webhook_failure_schedules_retry():
    worker = _load_worker()
    payload = {
        "type": "webhook.dispatch",
        "event": "completion.succeeded",
        "attempt": 1,
        "url": "https://example.com/h",
    }
    with patch("app.monitoring.queue.enqueue_delayed") as delayed, patch(
        "app.monitoring.queue.dead_letter"
    ) as dead:
        worker._handle_webhook_failure(payload, WebhookDeliveryError("boom", retryable=True))
    assert delayed.called
    assert not dead.called
    retry_job = delayed.call_args.args[0]
    assert retry_job["attempt"] == 2


def test_handle_webhook_failure_dead_letters_after_max():
    worker = _load_worker()
    payload = {
        "type": "webhook.dispatch",
        "event": "completion.failed",
        "attempt": 5,
        "url": "https://example.com/h",
    }
    with patch("app.monitoring.queue.enqueue_delayed") as delayed, patch(
        "app.monitoring.queue.dead_letter"
    ) as dead, patch(
        "app.config.settings.settings.WEBHOOK_MAX_ATTEMPTS", 5
    ):
        worker._handle_webhook_failure(payload, WebhookDeliveryError("gone", retryable=True))
    assert dead.called
    assert not delayed.called


def test_handle_non_retryable_goes_dead():
    worker = _load_worker()
    payload = {
        "type": "webhook.dispatch",
        "event": "completion.succeeded",
        "attempt": 1,
        "url": "https://example.com/h",
    }
    with patch("app.monitoring.queue.enqueue_delayed") as delayed, patch(
        "app.monitoring.queue.dead_letter"
    ) as dead:
        worker._handle_webhook_failure(
            payload, WebhookDeliveryError("bad request", status_code=400, retryable=False)
        )
    assert dead.called
    assert not delayed.called
