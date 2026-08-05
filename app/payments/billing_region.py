"""Helpers to resolve billing region from request + company."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import Request
from sqlalchemy.orm import Session

from app.companies.model import Company
from app.payments.region_pricing import BillingRegion, detect_billing_region


def request_header_map(request: Optional[Request]) -> dict[str, str]:
    if request is None:
        return {}
    return {k: v for k, v in request.headers.items()}


def resolve_region_for_company(
    db: Session,
    company_id: Optional[UUID],
    request: Optional[Request] = None,
) -> BillingRegion:
    country = None
    if company_id:
        company = db.get(Company, company_id)
        if company is not None:
            country = getattr(company, "country", None)
    headers = request_header_map(request)
    accept = headers.get("accept-language")
    return detect_billing_region(
        company_country=country,
        headers=headers,
        accept_language=accept,
    )
