"""
app/payments/providers/stripe.py
"""
import uuid
import logging
from typing import Optional, Dict
from app.payments.providers.base import PaymentProviderBase, PaymentResult

logger = logging.getLogger(__name__)

class StripeProvider(PaymentProviderBase):
    def process_payment(self, amount: float, currency: str, method: str, metadata: Optional[Dict] = None) -> PaymentResult:
        logger.info(f"STUB [Stripe]: Processing {amount} {currency} via {method}")
        return PaymentResult(
            success=True, 
            transaction_id=f"pi_stub_{uuid.uuid4().hex[:12]}",
            provider_data={"stubbed": True, "provider": "stripe"}
        )

    def refund_payment(self, transaction_id: str, amount: Optional[float] = None) -> PaymentResult:
        logger.info(f"STUB [Stripe]: Refunding transaction {transaction_id}")
        return PaymentResult(
            success=True,
            transaction_id=f"re_stub_{uuid.uuid4().hex[:12]}",
            provider_data={"stubbed": True, "provider": "stripe", "refunded": True}
        )
