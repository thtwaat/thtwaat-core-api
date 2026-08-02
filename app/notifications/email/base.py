"""Shared email backend protocol."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from app.notifications.providers.base import NotificationResult


class EmailBackend(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    def send(
        self,
        recipient: str,
        subject: Optional[str],
        body: str,
        *,
        html: Optional[str] = None,
        text: Optional[str] = None,
    ) -> NotificationResult:
        """Send email. ``body`` is used as plaintext when ``text`` is omitted."""
        pass
