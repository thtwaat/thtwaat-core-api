"""Helpers to resolve billing region from request + company + user override."""
from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.companies.model import Company
from app.payments.region_pricing import (
    BillingRegion,
    detect_billing_region,
    normalize_country,
)


BILLING_COUNTRY_SETTING_KEY = "billing_country"


def request_header_map(request: Optional[Request]) -> dict[str, str]:
    if request is None:
        return {}
    return {k: v for k, v in request.headers.items()}


def _preference_country(company: Optional[Company]) -> Optional[str]:
    if company is None:
        return None
    settings = getattr(company, "settings", None) or {}
    if not isinstance(settings, dict):
        return None
    return settings.get(BILLING_COUNTRY_SETTING_KEY) or settings.get("billingCountry")


def resolve_region_for_company(
    db: Session,
    company_id: Optional[UUID],
    request: Optional[Request] = None,
    *,
    country: Optional[str] = None,
) -> BillingRegion:
    """Resolve region. Explicit ``country`` (query/body) always wins."""
    company = db.get(Company, company_id) if company_id else None
    headers = request_header_map(request)
    accept = headers.get("accept-language")
    return detect_billing_region(
        selected_country=country,
        preference_country=_preference_country(company),
        company_country=getattr(company, "country", None) if company else None,
        headers=headers,
        accept_language=accept,
    )


def save_billing_country_preference(db: Session, company_id: UUID, country: str) -> Dict[str, Any]:
    """Persist selected billing country on company.settings (additive JSON key)."""
    code = normalize_country(country)
    if not code:
        raise HTTPException(status_code=400, detail="Invalid country code")
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    settings = dict(company.settings or {})
    settings[BILLING_COUNTRY_SETTING_KEY] = code
    company.settings = settings
    # Also mirror onto company.country when empty so other tools see it.
    if not (company.country or "").strip():
        company.country = code
    db.add(company)
    db.commit()
    db.refresh(company)
    region = region_payload(resolve_region_for_company(db, company_id, country=code))
    return region


def region_payload(region: BillingRegion) -> Dict[str, Any]:
    """Public billing-context shape (compat + requested fields)."""
    return {
        "country": region.country_code or ("IN" if region.region == "IN" else "US"),
        "currency": region.currency,
        "gateway": region.provider,
        # Backward-compatible aliases
        "region": region.region,
        "provider": region.provider,
        "country_code": region.country_code,
        "source": region.source,
    }
