"""
app/notifications/providers/factory.py
"""
from app.notifications.model import NotificationChannel
from app.notifications.providers.base import NotificationProviderBase, NotificationResult
from app.notifications.providers.email import EmailProvider
from app.notifications.providers.sms import SMSProvider
from app.notifications.providers.push import PushProvider
from app.notifications.providers.whatsapp import WhatsAppProvider


class InAppProvider(NotificationProviderBase):
    """No-op provider for IN_APP channel. Records are created directly by the service."""

    @property
    def provider_name(self) -> str:
        return "in_app"

    def send(self, recipient: str, subject=None, body: str = "") -> NotificationResult:
        # No external delivery needed — record is persisted by the service layer
        return NotificationResult(success=True)


def get_notification_provider(channel: NotificationChannel) -> NotificationProviderBase:
    """
    Returns the appropriate notification provider for the given channel.
    """
    if channel == NotificationChannel.EMAIL:
        return EmailProvider()
    elif channel == NotificationChannel.SMS:
        return SMSProvider()
    elif channel == NotificationChannel.PUSH:
        return PushProvider()
    elif channel == NotificationChannel.WHATSAPP:
        return WhatsAppProvider()
    elif channel == NotificationChannel.IN_APP:
        return InAppProvider()
    raise ValueError(f"Unsupported notification channel: {channel}")
