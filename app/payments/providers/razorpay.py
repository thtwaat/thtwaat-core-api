"""
app/payments/providers/razorpay.py
"""
import uuid
import logging
from typing import Optional, Dict
from app.payments.providers.base import PaymentProviderBase, PaymentResult

logger = logging.getLogger(__name__)

class RazorpayProvider(PaymentProviderBase):
    def process_payment(self, amount: float, currency: str, method: str, metadata: Optional[Dict] = None) -> PaymentResult:
        logger.info(f"STUB [Razorpay]: Processing {amount} {currency} via {method}")
        return PaymentResult(
            success=True, 
            transaction_id=f"pay_stub_{uuid.uuid4().hex[:12]}",
            provider_data={"stubbed": True, "provider": "razorpay"}
        )

    def refund_payment(self, transaction_id: str, amount: Optional[float] = None) -> PaymentResult:
        logger.info(f"STUB [Razorpay]: Refunding transaction {transaction_id}")
        return PaymentResult(
            success=True,
            transaction_id=f"rfnd_stub_{uuid.uuid4().hex[:12]}",
            provider_data={"stubbed": True, "provider": "razorpay", "refunded": True}
        )
