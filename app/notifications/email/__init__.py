"""Pluggable email delivery (SMTP default in production; stub in development)."""
from __future__ import annotations

from app.notifications.email.factory import get_email_backend
from app.notifications.email.errors import EmailConfigurationError, EmailDeliveryError
from app.notifications.providers.base import NotificationProviderBase, NotificationResult

__all__ = [
    "EmailConfigurationError",
    "EmailDeliveryError",
    "EmailProvider",
    "get_email_backend",
]


class EmailProvider(NotificationProviderBase):
    """
    Notification-channel facade over the configured email backend.

    Keeps the historical ``EmailProvider`` name used by the notifications factory.
    """

    @property
    def provider_name(self) -> str:
        return get_email_backend().provider_name

    def send(
        self,
        recipient: str,
        subject: str | None,
        body: str,
        *,
        html: str | None = None,
        text: str | None = None,
    ) -> NotificationResult:
        return get_email_backend().send(
            recipient=recipient,
            subject=subject,
            body=body,
            html=html,
            text=text,
        )
