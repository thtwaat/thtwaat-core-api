"""
app/notifications/providers/base.py

Abstract base class for notification providers.
"""
from abc import ABC, abstractmethod
from typing import Optional

class NotificationResult:
    def __init__(self, success: bool, error_message: Optional[str] = None):
        self.success = success
        self.error_message = error_message

class NotificationProviderBase(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    def send(self, recipient: str, subject: Optional[str], body: str) -> NotificationResult:
        """
        Sends the notification. 
        Returns NotificationResult.
        Synchronous for now to simulate direct sending.
        """
        pass
