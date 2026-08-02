"""Development stub — never claims delivery in production (factory blocks it)."""
from __future__ import annotations

import logging
from typing import Optional

from app.notifications.email.base import EmailBackend
from app.notifications.providers.base import NotificationResult

logger = logging.getLogger(__name__)


class StubEmailProvider(EmailBackend):
    @property
    def provider_name(self) -> str:
        return "stub"

    def send(
        self,
        recipient: str,
        subject: Optional[str],
        body: str,
        *,
        html: Optional[str] = None,
        text: Optional[str] = None,
    ) -> NotificationResult:
        # Never log body/html — may contain OTPs or reset tokens.
        logger.info(
            "STUB [Email]: queued message recipient=%s subject=%s has_html=%s",
            recipient,
            bool(subject),
            bool(html),
        )
        return NotificationResult(success=True)
