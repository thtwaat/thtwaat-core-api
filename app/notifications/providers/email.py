"""
app/notifications/providers/email.py
"""
import logging
from typing import Optional
from app.notifications.providers.base import NotificationProviderBase, NotificationResult
from app.notifications.config import notifications_settings

logger = logging.getLogger(__name__)

class EmailProvider(NotificationProviderBase):
    @property
    def provider_name(self) -> str:
        return notifications_settings.EMAIL_PROVIDER

    def send(self, recipient: str, subject: Optional[str], body: str) -> NotificationResult:
        logger.info(f"STUB [Email - {self.provider_name}]: Sending to {recipient} | Subject: {subject}")
        # Placeholder for real integration (e.g. SendGrid, AWS SES)
        return NotificationResult(success=True)
