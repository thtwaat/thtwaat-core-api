"""
app/apps/model.py

SQLAlchemy ORM model for App.
"""

import uuid
import enum
from sqlalchemy import (
    Column, String, Enum as SAEnum, ForeignKey, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class AppType(str, enum.Enum):
    """Types of applications."""
    WEB    = "web"
    MOBILE = "mobile"
    API    = "api"


class AppStatus(str, enum.Enum):
    """Lifecycle status of an app."""
    ACTIVE   = "active"
    INACTIVE = "inactive"


class App(Base, TimestampMixin):
    """
    Represents an application owned by a Company tenant.
    """

    __tablename__ = "apps"

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

    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False)
    
    type = Column(
        SAEnum(AppType, name="app_type_enum"),
        default=AppType.WEB,
        nullable=False,
    )
    status = Column(
        SAEnum(AppStatus, name="app_status_enum"),
        default=AppStatus.ACTIVE,
        nullable=False,
    )
    
    domain = Column(String(500), nullable=True)
    api_key = Column(String(255), unique=True, index=True, nullable=False)
    
    settings = Column(JSONB, default=dict, nullable=False)

    __table_args__ = (
        # Ensure an app slug is unique per company
        UniqueConstraint("company_id", "slug", name="uq_app_company_slug"),
    )

    company = relationship("Company", back_populates="apps")

    def __repr__(self) -> str:
        return f"<App id={self.id} slug={self.slug!r} company_id={self.company_id}>"
