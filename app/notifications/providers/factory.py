"""
app/notifications/providers/factory.py
"""
from app.notifications.model import NotificationChannel
from app.notifications.providers.base import NotificationProviderBase
from app.notifications.providers.email import EmailProvider
from app.notifications.providers.sms import SMSProvider
from app.notifications.providers.whatsapp import WhatsAppProvider
from app.notifications.providers.push import PushProvider


def get_notification_provider(channel: NotificationChannel) -> NotificationProviderBase:
    """
    Returns the appropriate provider stub for the given channel.
    """
    if channel == NotificationChannel.EMAIL:
        return EmailProvider()
    elif channel == NotificationChannel.SMS:
        return SMSProvider()
    elif channel == NotificationChannel.WHATSAPP:
        return WhatsAppProvider()
    elif channel == NotificationChannel.PUSH:
        return PushProvider()
    
    raise ValueError(f"Unsupported notification channel: {channel}")
