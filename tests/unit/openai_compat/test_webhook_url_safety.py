"""Week 4 Day 5 — webhook URL SSRF guard."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.webhooks.delivery import WebhookDeliveryError, deliver_webhook
from app.webhooks.url_safety import UnsafeWebhookUrlError, assert_safe_webhook_url


@pytest.mark.unit
def test_rejects_localhost(monkeypatch):
    monkeypatch.setattr(
        "app.webhooks.url_safety.settings.WEBHOOK_URL_SSRF_GUARD_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        "app.webhooks.url_safety.settings.WEBHOOK_URL_RESOLVE_DNS",
        False,
        raising=False,
    )
    with pytest.raises(UnsafeWebhookUrlError):
        assert_safe_webhook_url("https://localhost/hook")


@pytest.mark.unit
def test_rejects_private_literal_ip(monkeypatch):
    monkeypatch.setattr(
        "app.webhooks.url_safety.settings.WEBHOOK_URL_SSRF_GUARD_ENABLED",
        True,
        raising=False,
    )
    with pytest.raises(UnsafeWebhookUrlError):
        assert_safe_webhook_url("https://127.0.0.1/hook")
    with pytest.raises(UnsafeWebhookUrlError):
        assert_safe_webhook_url("https://10.0.0.5/hook")
    with pytest.raises(UnsafeWebhookUrlError):
        assert_safe_webhook_url("https://169.254.169.254/latest/meta-data")


@pytest.mark.unit
def test_rejects_http_by_default(monkeypatch):
    monkeypatch.setattr(
        "app.webhooks.url_safety.settings.WEBHOOK_URL_SSRF_GUARD_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        "app.webhooks.url_safety.settings.WEBHOOK_ALLOW_HTTP_URLS",
        False,
        raising=False,
    )
    monkeypatch.setattr(
        "app.webhooks.url_safety.settings.WEBHOOK_URL_RESOLVE_DNS",
        False,
        raising=False,
    )
    with pytest.raises(UnsafeWebhookUrlError):
        assert_safe_webhook_url("http://hooks.example.com/x")


@pytest.mark.unit
def test_allows_https_public_host_without_dns(monkeypatch):
    monkeypatch.setattr(
        "app.webhooks.url_safety.settings.WEBHOOK_URL_SSRF_GUARD_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        "app.webhooks.url_safety.settings.WEBHOOK_URL_RESOLVE_DNS",
        False,
        raising=False,
    )
    assert (
        assert_safe_webhook_url("https://hooks.example.com/thtwaat")
        == "https://hooks.example.com/thtwaat"
    )


@pytest.mark.unit
def test_deliver_blocks_ssrf_non_retryable(monkeypatch):
    monkeypatch.setattr(
        "app.webhooks.url_safety.settings.WEBHOOK_URL_SSRF_GUARD_ENABLED",
        True,
        raising=False,
    )
    with pytest.raises(WebhookDeliveryError) as exc:
        deliver_webhook("https://127.0.0.1/hook", {"event": "x"}, "sec")
    assert exc.value.retryable is False


@pytest.mark.unit
def test_dns_to_private_blocked(monkeypatch):
    monkeypatch.setattr(
        "app.webhooks.url_safety.settings.WEBHOOK_URL_SSRF_GUARD_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        "app.webhooks.url_safety.settings.WEBHOOK_URL_RESOLVE_DNS",
        True,
        raising=False,
    )
    # (family, type, proto, canonname, sockaddr)
    fake = [(0, 0, 0, "", ("10.1.2.3", 0))]
    with patch("app.webhooks.url_safety.socket.getaddrinfo", return_value=fake):
        with pytest.raises(UnsafeWebhookUrlError, match="blocked address"):
            assert_safe_webhook_url("https://evil.example/hook")
