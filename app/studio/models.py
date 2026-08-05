"""Studio project ORM — prompt workspace for product generation (no codegen in Phase 1)."""
from __future__ import annotations

import enum
import uuid

from sqlalchemy import Column, ForeignKey, Index, String, Text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, TimestampMixin


class StudioProjectStatus(str, enum.Enum):
    DRAFT = "draft"
    ANALYZING = "analyzing"
    BLUEPRINT_READY = "blueprint_ready"
    APPROVED = "approved"
    BUILDING = "building"
    COMPLETED = "completed"
    FAILED = "failed"


class StudioProject(Base, TimestampMixin):
    """Saved product-generation prompt. Workspace == company in this platform."""

    __tablename__ = "studio_projects"
    __table_args__ = (
        Index("ix_studio_projects_workspace_status", "workspace_id", "status"),
        Index("ix_studio_projects_workspace_created", "workspace_id", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    # Workspace is the tenant company (reuse Auth/Workspace — no parallel tenant table).
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title = Column(String(255), nullable=False)
    prompt = Column(Text, nullable=False)
    status = Column(
        SAEnum(
            StudioProjectStatus,
            name="studio_project_status_enum",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=StudioProjectStatus.DRAFT,
        index=True,
    )
