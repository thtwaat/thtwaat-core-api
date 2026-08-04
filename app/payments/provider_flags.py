"""Provider enablement helpers for enterprise billing."""
from __future__ import annotations

from app.config.settings import settings


def stripe_enabled() -> bool:
    return bool(getattr(settings, "BILLING_ENABLE_STRIPE", True)) and bool(
        (settings.STRIPE_SECRET_KEY or "").strip()
    )


def razorpay_enabled() -> bool:
    return bool(getattr(settings, "BILLING_ENABLE_RAZORPAY", True)) and bool(
        (settings.RAZORPAY_KEY_ID or "").strip()
        and (settings.RAZORPAY_KEY_SECRET or "").strip()
    )


def billing_providers_status() -> dict:
    return {
        "stripe": {
            "flag_enabled": bool(getattr(settings, "BILLING_ENABLE_STRIPE", True)),
            "configured": bool((settings.STRIPE_SECRET_KEY or "").strip()),
            "available": stripe_enabled(),
        },
        "razorpay": {
            "flag_enabled": bool(getattr(settings, "BILLING_ENABLE_RAZORPAY", True)),
            "configured": bool(
                (settings.RAZORPAY_KEY_ID or "").strip()
                and (settings.RAZORPAY_KEY_SECRET or "").strip()
            ),
            "available": razorpay_enabled(),
        },
        "default": getattr(settings, "BILLING_DEFAULT_PROVIDER", "auto") or "auto",
    }
