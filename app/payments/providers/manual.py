"""
app/payments/providers/manual.py
"""
import uuid
import logging
from typing import Optional, Dict
from app.payments.providers.base import PaymentProviderBase, PaymentResult

logger = logging.getLogger(__name__)

class ManualProvider(PaymentProviderBase):
    def process_payment(self, amount: float, currency: str, method: str, metadata: Optional[Dict] = None) -> PaymentResult:
        logger.info(f"STUB [Manual]: Recording manual payment of {amount} {currency} via {method}")
        return PaymentResult(
            success=True, 
            transaction_id=f"manual_{uuid.uuid4().hex[:12]}",
            provider_data={"stubbed": True, "provider": "manual"}
        )

    def refund_payment(self, transaction_id: str, amount: Optional[float] = None) -> PaymentResult:
        logger.info(f"STUB [Manual]: Recording manual refund for {transaction_id}")
        return PaymentResult(
            success=True,
            transaction_id=f"manual_rfnd_{uuid.uuid4().hex[:12]}",
            provider_data={"stubbed": True, "provider": "manual", "refunded": True}
        )
