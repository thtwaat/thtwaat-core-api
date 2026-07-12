"""
app/payments/providers/base.py

Abstract base class for payment gateway providers.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class PaymentResult:
    def __init__(
        self, 
        success: bool, 
        transaction_id: Optional[str] = None, 
        error_message: Optional[str] = None,
        provider_data: Optional[Dict[str, Any]] = None
    ):
        self.success = success
        self.transaction_id = transaction_id
        self.error_message = error_message
        self.provider_data = provider_data

class PaymentProviderBase(ABC):
    @abstractmethod
    def process_payment(self, amount: float, currency: str, method: str, metadata: Optional[Dict] = None) -> PaymentResult:
        """
        Process a payment through the gateway.
        """
        pass

    @abstractmethod
    def refund_payment(self, transaction_id: str, amount: Optional[float] = None) -> PaymentResult:
        """
        Refund a previous payment.
        """
        pass
