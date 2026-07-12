"""
app/notifications/providers/push.py
"""
import logging
from typing import Optional
from app.notifications.providers.base import NotificationProviderBase, NotificationResult
from app.notifications.config import notifications_settings

logger = logging.getLogger(__name__)

class PushProvider(NotificationProviderBase):
    @property
    def provider_name(self) -> str:
        return notifications_settings.PUSH_PROVIDER

    def send(self, recipient: str, subject: Optional[str], body: str) -> NotificationResult:
        logger.info(f"STUB [Push - {self.provider_name}]: Sending to device token {recipient}")
        # Placeholder for real integration (e.g. FCM, APNs)
        return NotificationResult(success=True)
