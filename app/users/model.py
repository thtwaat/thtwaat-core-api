"""
app/users/model.py

SQLAlchemy ORM model for User.
Represents an individual user account belonging to a specific Company.
"""

import uuid
import enum
from sqlalchemy import (
    Column, String, Boolean, Enum as SAEnum, ForeignKey, UniqueConstraint, DateTime
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin
from app.rbac.enums import EnterpriseRole


class UserStatus(str, enum.Enum):
    """Lifecycle status of a user account."""
    PENDING   = "pending"     # E.g. invited but hasn't set password
    ACTIVE    = "active"      # Normal active user
    SUSPENDED = "suspended"   # Temporarily disabled by admin
    INACTIVE  = "inactive"    # Soft-deleted


class User(Base, TimestampMixin):
    """
    Represents a user within the THTWAAT platform.
    Every user must belong to exactly one company (tenant).
    """

    __tablename__ = "users"

    # ── Identity ────────────────────────────────────────────────────────────
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        nullable=False,
    )
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # ── Credentials & Profile ───────────────────────────────────────────────
    email = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)

    # ── Access & Status ─────────────────────────────────────────────────────
    role = Column(
        SAEnum(EnterpriseRole, name="user_role_enum"),
        default=EnterpriseRole.EMPLOYEE,
        nullable=False,
    )
    status = Column(
        SAEnum(UserStatus, name="user_status_enum"),
        default=UserStatus.ACTIVE,
        nullable=False,
    )

    # ── Verification / Security ─────────────────────────────────────────────
    is_active = Column(Boolean, default=True, nullable=False)
    
    phone = Column(String(50), nullable=True)
    email_verified = Column(Boolean, default=False, nullable=False)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    phone_verified = Column(Boolean, default=False, nullable=False)
    phone_verified_at = Column(DateTime(timezone=True), nullable=True)

    # ── Constraints ─────────────────────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint("company_id", "email", name="uq_user_company_email"),
    )

    company = relationship("Company", back_populates="users")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    mfa_settings = relationship("MFASettings", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role}>"
