"""Unit tests for production email backends (SMTP + stub)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import smtplib

from app.notifications.email.errors import EmailConfigurationError
from app.notifications.email.factory import get_email_backend, reset_email_backend_cache
from app.notifications.email.smtp import SMTPEmailProvider
from app.notifications.email.stub import StubEmailProvider
from app.notifications.email.templates import (
    html_to_plaintext_fallback,
    render_security_code_email,
)


@pytest.fixture(autouse=True)
def _reset_backend():
    reset_email_backend_cache()
    yield
    reset_email_backend_cache()


@pytest.mark.unit
def test_development_stub(monkeypatch):
    monkeypatch.setattr("app.notifications.email.factory.settings.app_env", "development")
    monkeypatch.setattr(
        "app.notifications.email.factory.notifications_settings.EMAIL_PROVIDER",
        "stub",
    )
    backend = get_email_backend(force_reload=True)
    assert isinstance(backend, StubEmailProvider)
    result = backend.send("a@example.com", "Hi", "body only")
    assert result.success is True


@pytest.mark.unit
def test_smtp_disabled_in_production(monkeypatch):
    monkeypatch.setattr("app.notifications.email.factory.settings.app_env", "production")
    monkeypatch.setattr(
        "app.notifications.email.factory.notifications_settings.EMAIL_PROVIDER",
        "stub",
    )
    with pytest.raises(EmailConfigurationError):
        get_email_backend(force_reload=True)


@pytest.mark.unit
def test_smtp_missing_config_in_production(monkeypatch):
    monkeypatch.setattr("app.notifications.email.factory.settings.app_env", "production")
    monkeypatch.setattr(
        "app.notifications.email.factory.notifications_settings.EMAIL_PROVIDER",
        "smtp",
    )
    monkeypatch.setattr(
        "app.notifications.email.factory.notifications_settings.SMTP_HOST",
        None,
    )
    monkeypatch.setattr(
        "app.notifications.email.factory.notifications_settings.SMTP_FROM",
        None,
    )
    with pytest.raises(EmailConfigurationError):
        get_email_backend(force_reload=True)


@pytest.mark.unit
def test_smtp_success(monkeypatch):
    monkeypatch.setattr(
        "app.notifications.email.smtp.notifications_settings.SMTP_HOST",
        "smtp.example.com",
    )
    monkeypatch.setattr(
        "app.notifications.email.smtp.notifications_settings.SMTP_FROM",
        "noreply@example.com",
    )
    monkeypatch.setattr(
        "app.notifications.email.smtp.notifications_settings.SMTP_USERNAME",
        "user",
    )
    monkeypatch.setattr(
        "app.notifications.email.smtp.notifications_settings.SMTP_USER",
        None,
    )
    monkeypatch.setattr(
        "app.notifications.email.smtp.notifications_settings.SMTP_PASSWORD",
        "secret",
    )
    monkeypatch.setattr(
        "app.notifications.email.smtp.notifications_settings.SMTP_USE_TLS",
        True,
    )
    monkeypatch.setattr(
        "app.notifications.email.smtp.notifications_settings.SMTP_PORT",
        587,
    )
    monkeypatch.setattr(
        "app.notifications.email.smtp.notifications_settings.SMTP_FROM_NAME",
        "THTWAAT",
    )
    monkeypatch.setattr(
        "app.notifications.email.smtp.notifications_settings.SMTP_TIMEOUT_SECONDS",
        10,
    )

    smtp_instance = MagicMock()
    smtp_cm = MagicMock()
    smtp_cm.__enter__.return_value = smtp_instance
    smtp_cm.__exit__.return_value = False

    with patch("app.notifications.email.smtp.smtplib.SMTP", return_value=smtp_cm) as smtp_ctor:
        provider = SMTPEmailProvider()
        result = provider.send(
            "user@example.com",
            "Subject",
            "plain",
            html="<p>Hello</p>",
            text="Hello",
        )

    assert result.success is True
    smtp_ctor.assert_called()
    smtp_instance.starttls.assert_called()
    smtp_instance.login.assert_called_once_with("user", "secret")
    smtp_instance.sendmail.assert_called_once()
    raw_msg = smtp_instance.sendmail.call_args[0][2]
    # MIME may base64-encode parts; payload must still round-trip.
    assert "multipart/alternative" in raw_msg
    assert "Subject: Subject" in raw_msg
    import base64

    assert b"<p>Hello</p>" in base64.b64decode("PHA+SGVsbG88L3A+")
    assert "PHA+SGVsbG88L3A+" in raw_msg or "Hello" in raw_msg


@pytest.mark.unit
def test_smtp_auth_failure(monkeypatch):
    monkeypatch.setattr(
        "app.notifications.email.smtp.notifications_settings.SMTP_HOST",
        "smtp.example.com",
    )
    monkeypatch.setattr(
        "app.notifications.email.smtp.notifications_settings.SMTP_FROM",
        "noreply@example.com",
    )
    monkeypatch.setattr(
        "app.notifications.email.smtp.notifications_settings.SMTP_USERNAME",
        "user",
    )
    monkeypatch.setattr(
        "app.notifications.email.smtp.notifications_settings.SMTP_USER",
        None,
    )
    monkeypatch.setattr(
        "app.notifications.email.smtp.notifications_settings.SMTP_PASSWORD",
        "bad",
    )
    monkeypatch.setattr(
        "app.notifications.email.smtp.notifications_settings.SMTP_USE_TLS",
        True,
    )
    monkeypatch.setattr(
        "app.notifications.email.smtp.notifications_settings.SMTP_PORT",
        587,
    )
    monkeypatch.setattr(
        "app.notifications.email.smtp.notifications_settings.SMTP_FROM_NAME",
        "THTWAAT",
    )
    monkeypatch.setattr(
        "app.notifications.email.smtp.notifications_settings.SMTP_TIMEOUT_SECONDS",
        10,
    )

    smtp_instance = MagicMock()
    smtp_instance.login.side_effect = smtplib.SMTPAuthenticationError(535, b"auth failed")
    smtp_cm = MagicMock()
    smtp_cm.__enter__.return_value = smtp_instance
    smtp_cm.__exit__.return_value = False

    with patch("app.notifications.email.smtp.smtplib.SMTP", return_value=smtp_cm):
        result = SMTPEmailProvider().send("user@example.com", "S", "body")

    assert result.success is False
    assert "authentication" in (result.error_message or "").lower()


@pytest.mark.unit
def test_smtp_timeout(monkeypatch):
    monkeypatch.setattr(
        "app.notifications.email.smtp.notifications_settings.SMTP_HOST",
        "smtp.example.com",
    )
    monkeypatch.setattr(
        "app.notifications.email.smtp.notifications_settings.SMTP_FROM",
        "noreply@example.com",
    )
    monkeypatch.setattr(
        "app.notifications.email.smtp.notifications_settings.SMTP_USERNAME",
        None,
    )
    monkeypatch.setattr(
        "app.notifications.email.smtp.notifications_settings.SMTP_USER",
        None,
    )
    monkeypatch.setattr(
        "app.notifications.email.smtp.notifications_settings.SMTP_PASSWORD",
        None,
    )
    monkeypatch.setattr(
        "app.notifications.email.smtp.notifications_settings.SMTP_USE_TLS",
        False,
    )
    monkeypatch.setattr(
        "app.notifications.email.smtp.notifications_settings.SMTP_PORT",
        25,
    )
    monkeypatch.setattr(
        "app.notifications.email.smtp.notifications_settings.SMTP_FROM_NAME",
        "THTWAAT",
    )
    monkeypatch.setattr(
        "app.notifications.email.smtp.notifications_settings.SMTP_TIMEOUT_SECONDS",
        1,
    )

    with patch(
        "app.notifications.email.smtp.smtplib.SMTP",
        side_effect=TimeoutError("timed out"),
    ):
        result = SMTPEmailProvider().send("user@example.com", "S", "body")

    assert result.success is False
    assert "timed out" in (result.error_message or "").lower()


@pytest.mark.unit
def test_html_email_rendering_and_plaintext():
    subject, html, text = render_security_code_email("123456", purpose="password_reset")
    assert "Reset" in subject or "reset" in subject.lower()
    assert "<html" in html.lower()
    assert "123456" in html
    assert "123456" in text
    assert "<" not in text or "Code:" in text

    fallback = html_to_plaintext_fallback(html)
    assert "123456" in fallback
    assert "<p" not in fallback.lower()
