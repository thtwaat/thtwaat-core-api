"""Provider enablement helpers for enterprise billing."""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.config.settings import settings


def _truthy_flag(value: Any, default: bool = True) -> bool:
    """Normalize env/bool feature flags (handles bool, 'true'/'1'/'yes', etc.)."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "y"}:
        return True
    if text in {"0", "false", "no", "off", "n", ""}:
        return False
    return default


def _strip(value: Optional[str]) -> str:
    return (value or "").strip()


def stripe_enabled() -> bool:
    return _truthy_flag(getattr(settings, "BILLING_ENABLE_STRIPE", True), True) and bool(
        _strip(settings.STRIPE_SECRET_KEY)
    )


def razorpay_enabled() -> bool:
    """Razorpay is available when the feature flag is on and both keys exist."""
    return _truthy_flag(getattr(settings, "BILLING_ENABLE_RAZORPAY", True), True) and bool(
        _strip(settings.RAZORPAY_KEY_ID) and _strip(settings.RAZORPAY_KEY_SECRET)
    )


def billing_providers_status() -> Dict[str, Any]:
    """Status payload for GET /payments/subscriptions/providers.

    Includes Razorpay ``key_id`` (public checkout key) when available so the
    SaaS Billing UI does not depend solely on NEXT_PUBLIC_RAZORPAY_KEY_ID
    baked into the web image at build time.
    """
    stripe_flag = _truthy_flag(getattr(settings, "BILLING_ENABLE_STRIPE", True), True)
    razorpay_flag = _truthy_flag(getattr(settings, "BILLING_ENABLE_RAZORPAY", True), True)
    stripe_key = _strip(settings.STRIPE_SECRET_KEY)
    razorpay_key_id = _strip(settings.RAZORPAY_KEY_ID)
    razorpay_secret = _strip(settings.RAZORPAY_KEY_SECRET)

    stripe_configured = bool(stripe_key)
    razorpay_configured = bool(razorpay_key_id and razorpay_secret)
    stripe_ok = stripe_flag and stripe_configured
    razorpay_ok = razorpay_flag and razorpay_configured

    return {
        "stripe": {
            "flag_enabled": stripe_flag,
            "configured": stripe_configured,
            "available": stripe_ok,
        },
        "razorpay": {
            "flag_enabled": razorpay_flag,
            "configured": razorpay_configured,
            "available": razorpay_ok,
            # Public key only — required by Razorpay Checkout.js on the client.
            "key_id": razorpay_key_id if razorpay_ok else None,
        },
        "default": getattr(settings, "BILLING_DEFAULT_PROVIDER", "auto") or "auto",
    }
