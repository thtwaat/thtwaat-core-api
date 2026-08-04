"""
app/users/repository.py

Repository Pattern implementation for User.
"""

import uuid
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.users.model import User, UserStatus
from app.users.schema import UserUpdate


class UserRepository:
    """
    Data-access layer for the User entity.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        """Fetch a single user by its UUID primary key."""
        return self.db.get(User, user_id)

    def get_by_email_and_company(self, email: str, company_id: uuid.UUID) -> Optional[User]:
        """Fetch a single user by email within a specific company."""
        stmt = select(User).where(User.email == email, User.company_id == company_id)
        return self.db.scalar(stmt)

    def email_exists_in_company(self, email: str, company_id: uuid.UUID) -> bool:
        """Check whether an email is already registered within a company."""
        stmt = select(func.count()).select_from(User).where(
            User.email == email,
            User.company_id == company_id
        )
        return self.db.scalar(stmt) > 0

    def list_all(
        self,
        company_id: Optional[uuid.UUID] = None,
        page: int = 1,
        page_size: int = 20,
        status: Optional[UserStatus] = None,
        is_active: Optional[bool] = None,
        q: Optional[str] = None,
        role: Optional[str] = None,
    ) -> tuple[list[User], int]:
        """
        Return a paginated list of users with optional filters.
        Returns (rows, total_count).
        """
        stmt = select(User)

        if company_id is not None:
            stmt = stmt.where(User.company_id == company_id)
        if status is not None:
            stmt = stmt.where(User.status == status)
        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)
        if role is not None:
            stmt = stmt.where(User.role == role)
        if q:
            term = f"%{q.strip()}%"
            stmt = stmt.where(
                (User.email.ilike(term))
                | (User.first_name.ilike(term))
                | (User.last_name.ilike(term))
            )

        # Total count (before pagination)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.scalar(count_stmt)

        # Paginated rows
        offset = (page - 1) * page_size
        stmt = stmt.order_by(User.created_at.desc()).offset(offset).limit(page_size)
        rows = list(self.db.scalars(stmt).all())

        return rows, total

    # ── Write ─────────────────────────────────────────────────────────────────

    def create_from_dict(self, data: dict) -> User:
        """Persist a new User record from a dictionary and return the ORM object."""
        user = User(**data)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_from_dict(self, user: User, update_data: dict) -> User:
        """
        Apply a partial update to an existing User from a dictionary.
        """
        for field, value in update_data.items():
            setattr(user, field, value)
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, user: User) -> None:
        """
        Soft-delete: mark as inactive and status as INACTIVE instead of hard-deleting.
        """
        user.is_active = False
        user.status = UserStatus.INACTIVE
        self.db.commit()
