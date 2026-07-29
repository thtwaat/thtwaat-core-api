"""
app/companies/service.py

Service Layer for the Companies module.
This is where ALL business logic lives.

Responsibilities:
  - Enforce business rules (slug uniqueness, plan limits, status transitions)
  - Orchestrate repository calls
  - Raise domain-appropriate HTTP exceptions
  - Keep router.py and repository.py clean and single-purpose

Never import from router.py here — service knows nothing about HTTP details
except for raising HTTPException for now (acceptable in FastAPI projects).
"""

import uuid
from typing import Optional
from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy.orm import Session

from app.companies.model import Company, CompanyPlan, CompanyStatus
from app.companies.repository import CompanyRepository
from app.companies.schema import (
    CompanyCreate,
    CompanyUpdate,
    CompanyAdminUpdate,
    CompanyListResponse,
    CompanyResponse,
)

# Plan → resource limits map (single source of truth)
PLAN_LIMITS: dict[CompanyPlan, dict] = {
    CompanyPlan.FREE:       {"max_users": 5,    "max_apps": 1},
    CompanyPlan.STARTER:    {"max_users": 25,   "max_apps": 5},
    CompanyPlan.GROWTH:     {"max_users": 150,  "max_apps": 25},
    CompanyPlan.ENTERPRISE: {"max_users": 10000,"max_apps": 1000},
}

# Valid status transitions (state machine)
ALLOWED_STATUS_TRANSITIONS: dict[CompanyStatus, list[CompanyStatus]] = {
    CompanyStatus.TRIAL:     [CompanyStatus.ACTIVE, CompanyStatus.CANCELLED],
    CompanyStatus.ACTIVE:    [CompanyStatus.SUSPENDED, CompanyStatus.CANCELLED],
    CompanyStatus.SUSPENDED: [CompanyStatus.ACTIVE, CompanyStatus.CANCELLED],
    CompanyStatus.CANCELLED: [],  # Terminal state — no transitions allowed
}


class CompanyService:
    """
    Orchestrates all company-related business operations.
    Injected with a DB session; creates its own repository instance.
    """

    def __init__(self, db: Session) -> None:
        self.repo = CompanyRepository(db)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _get_or_404(self, company_id: uuid.UUID) -> Company:
        """Fetch company or raise 404."""
        company = self.repo.get_by_id(company_id)
        if not company:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Company with id '{company_id}' not found.",
            )
        return company

    def _assert_active(self, company: Company) -> None:
        """Raise 403 if the company account is not active."""
        if not company.is_active:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="This company account is inactive or has been deactivated.",
            )

    def _validate_status_transition(
        self, current: CompanyStatus, target: CompanyStatus
    ) -> None:
        """Enforce the status state machine."""
        if target not in ALLOWED_STATUS_TRANSITIONS.get(current, []):
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Invalid status transition: '{current}' → '{target}'. "
                    f"Allowed: {[s.value for s in ALLOWED_STATUS_TRANSITIONS[current]]}"
                ),
            )

    # ── Public API ────────────────────────────────────────────────────────────

    def create_company(self, data: CompanyCreate) -> CompanyResponse:
        """
        Register a new company tenant.
        - Validates slug uniqueness
        - Applies plan-based resource limits automatically
        """
        if self.repo.slug_exists(data.slug):
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail=f"Slug '{data.slug}' is already taken. Please choose another.",
            )

        # Apply FREE plan limits automatically on creation
        # Plan is always FREE at registration; admin can upgrade later
        limits = PLAN_LIMITS[CompanyPlan.FREE]
        company_data = data.model_dump()
        company_data.setdefault("max_users", limits["max_users"])
        company_data.setdefault("max_apps", limits["max_apps"])

        company = self.repo.create_from_dict(company_data)

        # ── Dispatch in-app notification event ───────────────────────────────
        try:
            from app.notifications.events import NotificationEventBus
            NotificationEventBus.dispatch(
                event_type="company.created",
                db=self.repo.db,
                company_id=company.id,
                user_id=None,
                data={"company_name": company.name},
            )
        except Exception:
            pass  # Never break company creation due to notification failure

        return CompanyResponse.model_validate(company)

    def get_company(self, company_id: uuid.UUID) -> CompanyResponse:
        company = self._get_or_404(company_id)
        self._assert_active(company)
        return CompanyResponse.model_validate(company)

    def get_company_by_slug(self, slug: str) -> CompanyResponse:
        company = self.repo.get_by_slug(slug)
        if not company:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Company with slug '{slug}' not found.",
            )
        self._assert_active(company)
        return CompanyResponse.model_validate(company)

    def list_companies(
        self,
        page: int = 1,
        page_size: int = 20,
        status_filter: Optional[CompanyStatus] = None,
        plan_filter: Optional[CompanyPlan] = None,
    ) -> CompanyListResponse:
        # page_size already capped at 100 by Query(le=100) in router,
        # but we guard here too for direct service calls
        if page_size > 100:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="page_size cannot exceed 100.",
            )
        rows, total = self.repo.list_all(
            page=page,
            page_size=page_size,
            status=status_filter,
            plan=plan_filter,
            is_active=True,
        )
        return CompanyListResponse(
            total=total,
            page=page,
            page_size=page_size,
            results=[CompanyResponse.model_validate(c) for c in rows],
        )

    def update_company(
        self, company_id: uuid.UUID, data: CompanyUpdate
    ) -> CompanyResponse:
        company = self._get_or_404(company_id)
        self._assert_active(company)
        updated = self.repo.update(company, data)
        return CompanyResponse.model_validate(updated)

    def admin_update_company(
        self, company_id: uuid.UUID, data: CompanyAdminUpdate
    ) -> CompanyResponse:
        """
        Admin-only: update plan, status, limits.
        Validates status transitions via state machine.
        Automatically adjusts resource limits when plan changes.
        """
        company = self._get_or_404(company_id)

        # Validate status transition if status is being changed
        if data.status and data.status != company.status:
            self._validate_status_transition(company.status, data.status)

        # Auto-update limits when plan changes (unless overridden)
        if data.plan and data.plan != company.plan:
            limits = PLAN_LIMITS[data.plan]
            if data.max_users is None:
                data = data.model_copy(update={"max_users": limits["max_users"]})
            if data.max_apps is None:
                data = data.model_copy(update={"max_apps": limits["max_apps"]})

        updated = self.repo.update(company, data)
        return CompanyResponse.model_validate(updated)

    def deactivate_company(self, company_id: uuid.UUID) -> dict:
        """Soft-delete: mark company as inactive."""
        company = self._get_or_404(company_id)
        self.repo.delete(company)
        return {"message": f"Company '{company.slug}' has been deactivated."}
