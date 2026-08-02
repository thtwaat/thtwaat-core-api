"""Select email backend from EMAIL_PROVIDER + APP_ENV."""
from __future__ import annotations

import logging

from app.config.settings import HARDENED_ENVS, settings
from app.notifications.config import notifications_settings
from app.notifications.email.base import EmailBackend
from app.notifications.email.errors import EmailConfigurationError
from app.notifications.email.resend import ResendEmailProvider
from app.notifications.email.sendgrid import SendGridEmailProvider
from app.notifications.email.ses import SESEmailProvider
from app.notifications.email.smtp import SMTPEmailProvider, smtp_is_configured
from app.notifications.email.stub import StubEmailProvider

logger = logging.getLogger(__name__)

_CACHED: EmailBackend | None = None


def reset_email_backend_cache() -> None:
    """Test helper to clear the cached backend instance."""
    global _CACHED
    _CACHED = None


def _env_name() -> str:
    return (settings.app_env or "development").strip().lower()


def _provider_name() -> str:
    return (notifications_settings.EMAIL_PROVIDER or "stub").strip().lower()


def get_email_backend(*, force_reload: bool = False) -> EmailBackend:
    global _CACHED
    if _CACHED is not None and not force_reload:
        return _CACHED

    env = _env_name()
    name = _provider_name()
    hardened = env in HARDENED_ENVS

    if name in ("stub", "none", "log"):
        if hardened:
            # Fail closed — never pretend mail was sent in production.
            raise EmailConfigurationError(
                "EMAIL_PROVIDER=stub is not allowed when APP_ENV is production/staging"
            )
        backend: EmailBackend = StubEmailProvider()
        _CACHED = backend
        logger.info("Email backend selected provider=stub env=%s", env)
        return backend

    if name == "smtp":
        if hardened and not smtp_is_configured():
            raise EmailConfigurationError(
                "SMTP is required in production but SMTP_HOST/SMTP_FROM are not configured"
            )
        backend = SMTPEmailProvider()
        _CACHED = backend
        logger.info("Email backend selected provider=smtp env=%s", env)
        return backend

    if name == "sendgrid":
        backend = SendGridEmailProvider()
        _CACHED = backend
        return backend
    if name in ("ses", "aws_ses", "aws-ses"):
        backend = SESEmailProvider()
        _CACHED = backend
        return backend
    if name == "resend":
        backend = ResendEmailProvider()
        _CACHED = backend
        return backend

    raise EmailConfigurationError(f"Unknown EMAIL_PROVIDER={name!r}")
