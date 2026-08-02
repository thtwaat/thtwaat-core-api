"""SendGrid backend placeholder — pluggable without auth changes."""
from __future__ import annotations

from typing import Optional

from app.notifications.config import notifications_settings
from app.notifications.email.base import EmailBackend
from app.notifications.email.errors import EmailConfigurationError
from app.notifications.providers.base import NotificationResult


class SendGridEmailProvider(EmailBackend):
    @property
    def provider_name(self) -> str:
        return "sendgrid"

    def send(
        self,
        recipient: str,
        subject: Optional[str],
        body: str,
        *,
        html: Optional[str] = None,
        text: Optional[str] = None,
    ) -> NotificationResult:
        if not (notifications_settings.SENDGRID_API_KEY or "").strip():
            raise EmailConfigurationError("SENDGRID_API_KEY is not configured")
        raise EmailConfigurationError(
            "SendGrid provider is registered but not implemented yet; use EMAIL_PROVIDER=smtp"
        )
