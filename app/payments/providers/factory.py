"""
app/payments/providers/factory.py
"""
from app.payments.model import Gateway
from app.payments.providers.base import PaymentProviderBase
from app.payments.providers.stripe import StripeProvider
from app.payments.providers.razorpay import RazorpayProvider
from app.payments.providers.paypal import PayPalProvider
from app.payments.providers.manual import ManualProvider


def get_payment_provider(gateway: Gateway) -> PaymentProviderBase:
    """
    Returns the appropriate provider stub for the given gateway.
    """
    if gateway == Gateway.STRIPE:
        return StripeProvider()
    elif gateway == Gateway.RAZORPAY:
        return RazorpayProvider()
    elif gateway == Gateway.PAYPAL:
        return PayPalProvider()
    elif gateway == Gateway.MANUAL:
        return ManualProvider()
    
    raise ValueError(f"Unsupported gateway: {gateway}")
