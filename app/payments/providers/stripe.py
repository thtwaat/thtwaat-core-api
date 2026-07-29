"""
app/payments/providers/stripe.py

Real Stripe payment provider using the official Stripe Python SDK.
"""
import logging
from typing import Optional, Dict
import stripe
from app.payments.providers.base import PaymentProviderBase, PaymentResult
from app.config.settings import settings

logger = logging.getLogger(__name__)

class StripeProvider(PaymentProviderBase):
    def __init__(self):
        if settings.STRIPE_SECRET_KEY:
            stripe.api_key = settings.STRIPE_SECRET_KEY
        else:
            raise ValueError("STRIPE_SECRET_KEY is not configured.")

    def process_payment(self, amount: float, currency: str, method: str, metadata: Optional[Dict] = None) -> PaymentResult:
        """Create a Stripe PaymentIntent."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Stripe uses cents
                currency=currency.lower(),
                payment_method_types=["card"],
                metadata=metadata or {}
            )
            return PaymentResult(
                success=True,
                transaction_id=intent.id,
                provider_data={"client_secret": intent.client_secret, "status": intent.status}
            )
        except stripe.StripeError as e:
            logger.error(f"[Stripe] PaymentIntent failed: {e}")
            return PaymentResult(success=False, error_message=str(e))

    def refund_payment(self, transaction_id: str, amount: Optional[float] = None) -> PaymentResult:
        """Refund a Stripe PaymentIntent."""
        try:
            kwargs = {"payment_intent": transaction_id}
            if amount:
                kwargs["amount"] = int(amount * 100)
            refund = stripe.Refund.create(**kwargs)
            return PaymentResult(
                success=True,
                transaction_id=refund.id,
                provider_data={"status": refund.status}
            )
        except stripe.StripeError as e:
            logger.error(f"[Stripe] Refund failed: {e}")
            return PaymentResult(success=False, error_message=str(e))
