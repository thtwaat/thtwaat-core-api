"""
app/payments/providers/razorpay.py

Real Razorpay payment provider using the official Razorpay Python SDK.
"""
import logging
import hmac
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Tuple
import razorpay
from app.payments.providers.base import PaymentProviderBase, PaymentResult
from app.config.settings import settings

logger = logging.getLogger(__name__)


def extract_subscription_period(entity: Dict) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Read ``current_start``/``current_end`` (unix seconds) off a Razorpay
    Subscription entity, as sent on subscription.activated/charged webhook
    payloads and by ``client.subscription.fetch()``. Either may be absent
    depending on the event/lifecycle stage — callers must tolerate ``None``.
    """
    start_ts = entity.get("current_start")
    end_ts = entity.get("current_end")
    start = datetime.fromtimestamp(start_ts, tz=timezone.utc) if start_ts else None
    end = datetime.fromtimestamp(end_ts, tz=timezone.utc) if end_ts else None
    return start, end

class RazorpayProvider(PaymentProviderBase):
    def __init__(self):
        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            raise ValueError("RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are not configured.")
        self.client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )

    def process_payment(self, amount: float, currency: str, method: str, metadata: Optional[Dict] = None) -> PaymentResult:
        """Create a Razorpay Order."""
        try:
            order_data = {
                "amount": int(amount * 100),  # Razorpay uses paise
                "currency": currency.upper(),
                "payment_capture": 1,
                "notes": metadata or {}
            }
            order = self.client.order.create(data=order_data)
            return PaymentResult(
                success=True,
                transaction_id=order["id"],
                provider_data={"order_id": order["id"], "status": order["status"]}
            )
        except Exception as e:
            logger.error(f"[Razorpay] Order creation failed: {e}")
            return PaymentResult(success=False, error_message=str(e))

    def refund_payment(self, transaction_id: str, amount: Optional[float] = None) -> PaymentResult:
        """Refund a Razorpay payment."""
        try:
            data = {}
            if amount:
                data["amount"] = int(amount * 100)
            refund = self.client.payment.refund(transaction_id, data)
            return PaymentResult(
                success=True,
                transaction_id=refund["id"],
                provider_data={"status": refund["status"]}
            )
        except Exception as e:
            logger.error(f"[Razorpay] Refund failed: {e}")
            return PaymentResult(success=False, error_message=str(e))

    @staticmethod
    def verify_signature(order_id: str, payment_id: str, signature: str) -> bool:
        """Verify Razorpay webhook/payment signature."""
        if not settings.RAZORPAY_KEY_SECRET:
            return False
        msg = f"{order_id}|{payment_id}"
        generated = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode(),
            msg.encode(),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(generated, signature)
