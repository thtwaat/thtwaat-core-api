"""Public branding resolve for white-label frontends / widgets."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.branding.schemas import PublicBrandingResponse
from app.branding.service import BrandingService
from app.database.database import get_db

router = APIRouter(prefix="/public/v1/branding", tags=["Public Branding"])


def get_branding_service(db: Session = Depends(get_db)) -> BrandingService:
    return BrandingService(db)


@router.get(
    "",
    response_model=PublicBrandingResponse,
    summary="Resolve published branding by company_id, slug, or custom hostname",
)
def public_branding(
    company_id: Optional[UUID] = Query(None),
    slug: Optional[str] = Query(None),
    hostname: Optional[str] = Query(None),
    service: BrandingService = Depends(get_branding_service),
):
    if not any([company_id, slug, hostname]):
        raise HTTPException(
            status_code=400,
            detail="Provide company_id, slug, or hostname",
        )
    return service.public_branding(company_id=company_id, slug=slug, hostname=hostname)
