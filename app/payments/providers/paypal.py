"""
app/payments/providers/paypal.py
"""
import uuid
import logging
from typing import Optional, Dict
from app.payments.providers.base import PaymentProviderBase, PaymentResult

logger = logging.getLogger(__name__)

class PayPalProvider(PaymentProviderBase):
    def process_payment(self, amount: float, currency: str, method: str, metadata: Optional[Dict] = None) -> PaymentResult:
        logger.info(f"STUB [PayPal]: Processing {amount} {currency} via {method}")
        return PaymentResult(
            success=True, 
            transaction_id=f"PAYID-STUB{uuid.uuid4().hex[:12].upper()}",
            provider_data={"stubbed": True, "provider": "paypal"}
        )

    def refund_payment(self, transaction_id: str, amount: Optional[float] = None) -> PaymentResult:
        logger.info(f"STUB [PayPal]: Refunding transaction {transaction_id}")
        return PaymentResult(
            success=True,
            transaction_id=f"REFUND-STUB{uuid.uuid4().hex[:12].upper()}",
            provider_data={"stubbed": True, "provider": "paypal", "refunded": True}
        )
