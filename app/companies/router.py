"""
app/companies/router.py

FastAPI APIRouter for the Companies module.
Router's only job: HTTP concerns (request parsing, response codes, DI).
All logic is delegated to CompanyService.
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.auth.tenant import require_platform_admin
from app.companies.model import CompanyPlan, CompanyStatus
from app.companies.schema import (
    CompanyCreate,
    CompanyUpdate,
    CompanyAdminUpdate,
    CompanyResponse,
    CompanyListResponse,
)
from app.companies.service import CompanyService


router = APIRouter(
    prefix="/companies",
    tags=["Companies"],
)


def get_company_service(db: Session = Depends(get_db)) -> CompanyService:
    """FastAPI dependency — provides a CompanyService with a DB session."""
    return CompanyService(db)


# ── Public Endpoints ──────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=CompanyListResponse,
    summary="List all active companies",
)
def list_companies(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    status_filter: Optional[CompanyStatus] = Query(default=None, alias="status"),
    plan_filter: Optional[CompanyPlan] = Query(default=None, alias="plan"),
    q: Optional[str] = Query(default=None, description="Search name / slug / display_name"),
    include_inactive: bool = Query(default=False, description="Include inactive companies"),
    current_user: UserProfileResponse = Depends(get_current_user),
    service: CompanyService = Depends(get_company_service),
):
    """
    Retrieve a paginated list of company tenants.
    Platform admin only.
    """
    require_platform_admin(current_user)
    return service.list_companies(
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        plan_filter=plan_filter,
        q=q,
        include_inactive=include_inactive,
    )


@router.post(
    "/",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new company tenant",
)
def create_company(
    payload: CompanyCreate,
    service: CompanyService = Depends(get_company_service),
):
    """
    Register a new company on the THTWAAT platform.
    - Validates slug uniqueness
    - Auto-assigns FREE plan limits
    - Sets status to TRIAL
    """
    return service.create_company(payload)


@router.get(
    "/slug/{slug}",
    response_model=CompanyResponse,
    summary="Get company by slug",
)
def get_company_by_slug(
    slug: str,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: CompanyService = Depends(get_company_service),
):
    """Retrieve a company by its URL-safe slug (tenant-scoped)."""
    return service.get_company_by_slug(slug, actor=current_user)


@router.get(
    "/{company_id}",
    response_model=CompanyResponse,
    summary="Get company by ID",
)
def get_company(
    company_id: uuid.UUID,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: CompanyService = Depends(get_company_service),
):
    """Retrieve a single company by its UUID (own company or platform admin)."""
    return service.get_company(company_id, actor=current_user)


@router.patch(
    "/{company_id}",
    response_model=CompanyResponse,
    summary="Update company details",
)
def update_company(
    company_id: uuid.UUID,
    payload: CompanyUpdate,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: CompanyService = Depends(get_company_service),
):
    """Partially update company information (name, description, logo, etc.)."""
    return service.update_company(company_id, payload, actor=current_user)


# ── Admin Endpoints ───────────────────────────────────────────────────────────

@router.patch(
    "/{company_id}/admin",
    response_model=CompanyResponse,
    summary="[Admin] Update plan, status, limits",
)
def admin_update_company(
    company_id: uuid.UUID,
    payload: CompanyAdminUpdate,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: CompanyService = Depends(get_company_service),
):
    """
    Platform-admin endpoint to change subscription plan, company status,
    verification, and resource limits.
    """
    require_platform_admin(current_user)
    return service.admin_update_company(company_id, payload)


@router.delete(
    "/{company_id}",
    status_code=status.HTTP_200_OK,
    summary="Deactivate (soft-delete) a company",
)
def deactivate_company(
    company_id: uuid.UUID,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: CompanyService = Depends(get_company_service),
):
    """
    Soft-delete a company — marks it as inactive.
    Own company or platform admin only.
    """
    return service.deactivate_company(company_id, actor=current_user)
