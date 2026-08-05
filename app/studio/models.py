"""Studio project + blueprint version ORM."""
from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

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


class StudioProjectBlueprint(Base, TimestampMixin):
    """Versioned product blueprint JSON for a Studio project (no codegen)."""

    __tablename__ = "studio_project_blueprints"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_studio_blueprint_project_version"),
        Index("ix_studio_blueprints_project_current", "project_id", "is_current"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("studio_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version = Column(Integer, nullable=False, default=1)
    is_current = Column(Boolean, nullable=False, default=True)
    source = Column(String(32), nullable=False, default="heuristic")  # heuristic | ai_gateway | manual
    blueprint = Column(JSONB, nullable=False, default=dict)
    warnings = Column(JSONB, nullable=False, default=list)
    recommendations = Column(JSONB, nullable=False, default=dict)
    created_by = Column(UUID(as_uuid=True), nullable=True)
