"""AWS SES backend placeholder — pluggable without auth changes."""
from __future__ import annotations

from typing import Optional

from app.notifications.config import notifications_settings
from app.notifications.email.base import EmailBackend
from app.notifications.email.errors import EmailConfigurationError
from app.notifications.providers.base import NotificationResult


class SESEmailProvider(EmailBackend):
    @property
    def provider_name(self) -> str:
        return "ses"

    def send(
        self,
        recipient: str,
        subject: Optional[str],
        body: str,
        *,
        html: Optional[str] = None,
        text: Optional[str] = None,
    ) -> NotificationResult:
        region = (notifications_settings.AWS_SES_REGION or "").strip()
        if not region:
            raise EmailConfigurationError("AWS_SES_REGION is not configured")
        raise EmailConfigurationError(
            "AWS SES provider is registered but not implemented yet; use EMAIL_PROVIDER=smtp"
        )
