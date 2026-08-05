"""Region-based billing pricing (India INR/Razorpay vs International USD/Stripe)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping, Optional

from app.payments.plans.model import Plan

# ISO / common aliases for India
_INDIA_CODES = {
    "IN",
    "IND",
    "INDIA",
    "BHARAT",
}


@dataclass(frozen=True)
class BillingRegion:
    region: str  # IN | INTL
    currency: str  # INR | USD
    provider: str  # razorpay | stripe
    country_code: Optional[str]
    source: str  # user | preference | company | header | accept_language | default


def normalize_country(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = str(value).strip().upper()
    if not text:
        return None
    # Keep first token for values like "IN,XX" or "India"
    text = text.replace("_", " ").split(",")[0].strip()
    if text in _INDIA_CODES or text.startswith("INDIA"):
        return "IN"
    # ISO-2 already
    if len(text) == 2:
        return text
    # ISO-3 IND already handled; common names
    if "INDIA" in text:
        return "IN"
    return text[:2] if len(text) >= 2 else text


def is_india(country: Optional[str]) -> bool:
    code = normalize_country(country)
    return code == "IN"


def region_from_country_code(code: Optional[str], *, source: str) -> BillingRegion:
    normalized = normalize_country(code) or "US"
    if normalized == "IN":
        return BillingRegion("IN", "INR", "razorpay", "IN", source)
    return BillingRegion("INTL", "USD", "stripe", normalized, source)


def detect_billing_region(
    *,
    selected_country: Optional[str] = None,
    preference_country: Optional[str] = None,
    company_country: Optional[str] = None,
    headers: Optional[Mapping[str, str]] = None,
    accept_language: Optional[str] = None,
) -> BillingRegion:
    """Resolve billing region.

    Priority:
    1. Explicit user selection (query/body)
    2. Saved workspace preference (settings.billing_country)
    3. Workspace/company country
    4. CDN / proxy country headers
    5. Accept-Language hint (hi-IN / en-IN)
    6. Default United States (USD / Stripe)
    """
    if selected_country:
        return region_from_country_code(selected_country, source="user")

    if preference_country:
        return region_from_country_code(preference_country, source="preference")

    headers = {str(k).lower(): str(v) for k, v in (headers or {}).items()}

    company_code = normalize_country(company_country)
    if company_code:
        return region_from_country_code(company_code, source="company")

    for key in (
        "cf-ipcountry",
        "cloudfront-viewer-country",
        "x-vercel-ip-country",
        "x-country-code",
        "x-geo-country",
    ):
        code = normalize_country(headers.get(key))
        if code and code not in {"XX", "T1"}:  # CF uses XX unknown / T1 tor
            return region_from_country_code(code, source="header")

    lang = accept_language or headers.get("accept-language") or ""
    lang_l = lang.lower()
    if "-in" in lang_l or lang_l.startswith("hi") or ",hi" in lang_l:
        return BillingRegion("IN", "INR", "razorpay", "IN", "accept_language")

    return BillingRegion("INTL", "USD", "stripe", "US", "default")


def plan_price_for_region(
    plan: Plan,
    region: BillingRegion,
    *,
    interval: str = "month",
) -> Decimal:
    """Pick the charged amount for a plan in the given region (backward compatible)."""
    use_yearly = (interval or "month").lower() == "year"
    if getattr(plan, "is_custom_pricing", False):
        return Decimal("0")

    if region.region == "IN":
        if use_yearly:
            raw = getattr(plan, "yearly_price_inr", None)
            if raw is not None:
                return Decimal(str(raw))
        raw = getattr(plan, "price_inr", None)
        if raw is not None:
            return Decimal(str(raw))
        # Fallback: legacy amount treated as USD — do not invent INR
        return Decimal(str(plan.amount or 0))

    # International USD
    if use_yearly:
        raw = getattr(plan, "yearly_price_usd", None)
        if raw is not None:
            return Decimal(str(raw))
        if plan.yearly_amount is not None:
            return Decimal(str(plan.yearly_amount))
    raw = getattr(plan, "price_usd", None)
    if raw is not None:
        return Decimal(str(raw))
    return Decimal(str(plan.amount or 0))


def plan_currency_for_region(plan: Plan, region: BillingRegion) -> str:
    if region.region == "IN":
        return "INR"
    # Prefer explicit USD region price; else legacy plan.currency
    if getattr(plan, "price_usd", None) is not None:
        return "USD"
    return (plan.currency or "USD").upper()


def serialize_plan_region_fields(plan: Plan, region: Optional[BillingRegion] = None) -> dict[str, Any]:
    """Additive fields for Plan API responses."""
    effective = region or BillingRegion("INTL", "USD", "stripe", "US", "default")
    display_currency = effective.currency
    display_amount = float(plan_price_for_region(plan, effective))
    return {
        "price_inr": float(plan.price_inr) if getattr(plan, "price_inr", None) is not None else None,
        "price_usd": float(plan.price_usd) if getattr(plan, "price_usd", None) is not None else None,
        "yearly_price_inr": (
            float(plan.yearly_price_inr) if getattr(plan, "yearly_price_inr", None) is not None else None
        ),
        "yearly_price_usd": (
            float(plan.yearly_price_usd) if getattr(plan, "yearly_price_usd", None) is not None else None
        ),
        "is_custom_pricing": bool(getattr(plan, "is_custom_pricing", False)),
        "display_amount": display_amount,
        "display_currency": display_currency,
        "resolved_provider": effective.provider,
    }
