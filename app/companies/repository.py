"""
app/companies/repository.py

Repository Pattern implementation for Company.
This layer is the ONLY place that speaks directly to the database.
All business logic lives in service.py — NOT here.

Responsibilities:
  - CRUD operations using SQLAlchemy 2.0 ORM
  - Pagination
  - Filtering by status / plan
  - Slug uniqueness check
"""

import uuid
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.companies.model import Company, CompanyStatus, CompanyPlan
from app.companies.schema import CompanyCreate, CompanyUpdate


class CompanyRepository:
    """
    Data-access layer for the Company entity.
    Receives a SQLAlchemy Session via dependency injection (no global state).
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_by_id(self, company_id: uuid.UUID) -> Optional[Company]:
        """Fetch a single company by its UUID primary key."""
        return self.db.get(Company, company_id)

    def get_by_slug(self, slug: str) -> Optional[Company]:
        """Fetch a single company by its URL slug."""
        stmt = select(Company).where(Company.slug == slug)
        return self.db.scalar(stmt)

    def slug_exists(self, slug: str) -> bool:
        """Check whether a slug is already taken."""
        stmt = select(func.count()).select_from(Company).where(Company.slug == slug)
        return self.db.scalar(stmt) > 0

    def list_all(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[CompanyStatus] = None,
        plan: Optional[CompanyPlan] = None,
        is_active: Optional[bool] = None,
        q: Optional[str] = None,
    ) -> tuple[list[Company], int]:
        """
        Return a paginated list of companies with optional filters.
        Returns (rows, total_count).
        """
        stmt = select(Company)

        if status is not None:
            stmt = stmt.where(Company.status == status)
        if plan is not None:
            stmt = stmt.where(Company.plan == plan)
        if is_active is not None:
            stmt = stmt.where(Company.is_active == is_active)
        if q:
            term = f"%{q.strip()}%"
            stmt = stmt.where(
                (Company.name.ilike(term))
                | (Company.slug.ilike(term))
                | (Company.display_name.ilike(term))
            )

        # Total count (before pagination)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.scalar(count_stmt)

        # Paginated rows
        offset = (page - 1) * page_size
        stmt = stmt.order_by(Company.created_at.desc()).offset(offset).limit(page_size)
        rows = list(self.db.scalars(stmt).all())

        return rows, total

    # ── Write ─────────────────────────────────────────────────────────────────

    def create_from_dict(self, data: dict) -> Company:
        """Persist a new Company record from a dictionary and return the ORM object."""
        company = Company(**data)
        self.db.add(company)
        self.db.commit()
        self.db.refresh(company)
        return company

    def update(self, company: Company, data: CompanyUpdate) -> Company:
        """
        Apply a partial update to an existing Company.
        Only fields explicitly set (not None) in the schema are written.
        """
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(company, field, value)
        self.db.commit()
        self.db.refresh(company)
        return company

    def delete(self, company: Company) -> None:
        """
        Soft-delete: mark as inactive instead of hard-deleting.
        Preserves audit trail and referential integrity.
        """
        company.is_active = False
        self.db.commit()

    def hard_delete(self, company: Company) -> None:
        """Permanently remove a company record. Use only in admin / test scenarios."""
        self.db.delete(company)
        self.db.commit()
