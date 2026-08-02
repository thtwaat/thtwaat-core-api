"""
app/notifications/providers/whatsapp.py
"""
import logging
from typing import Optional
from app.notifications.providers.base import NotificationProviderBase, NotificationResult
from app.notifications.config import notifications_settings

logger = logging.getLogger(__name__)

class WhatsAppProvider(NotificationProviderBase):
    @property
    def provider_name(self) -> str:
        return notifications_settings.WHATSAPP_PROVIDER

    def send(
        self,
        recipient: str,
        subject: Optional[str],
        body: str,
        *,
        html: Optional[str] = None,
        text: Optional[str] = None,
    ) -> NotificationResult:
        logger.info(f"STUB [WhatsApp - {self.provider_name}]: Sending to {recipient}")
        # Placeholder for real integration (e.g. Twilio WhatsApp, Meta API)
        return NotificationResult(success=True)
