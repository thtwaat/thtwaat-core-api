"""
app/notifications/providers/sms.py
"""
import logging
from typing import Optional
from app.notifications.providers.base import NotificationProviderBase, NotificationResult
from app.notifications.config import notifications_settings

logger = logging.getLogger(__name__)

class SMSProvider(NotificationProviderBase):
    @property
    def provider_name(self) -> str:
        return notifications_settings.SMS_PROVIDER

    def send(
        self,
        recipient: str,
        subject: Optional[str],
        body: str,
        *,
        html: Optional[str] = None,
        text: Optional[str] = None,
    ) -> NotificationResult:
        logger.info(f"STUB [SMS - {self.provider_name}]: Sending to {recipient} | Body length: {len(body)}")
        # Placeholder for real integration (e.g. Twilio, AWS SNS)
        return NotificationResult(success=True)
