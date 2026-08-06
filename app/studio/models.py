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


class StudioProjectBuildPlan(Base, TimestampMixin):
    """Versioned module compose / build plan for a Studio project (no codegen)."""

    __tablename__ = "studio_project_build_plans"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_studio_build_plan_project_version"),
        Index("ix_studio_build_plans_project_current", "project_id", "is_current"),
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
    blueprint_version = Column(Integer, nullable=False, default=1)
    version = Column(Integer, nullable=False, default=1)
    is_current = Column(Boolean, nullable=False, default=True)
    modules = Column(JSONB, nullable=False, default=list)
    dependency_graph = Column(JSONB, nullable=False, default=list)
    dependency_tree = Column(JSONB, nullable=False, default=list)
    build_plan = Column(JSONB, nullable=False, default=list)
    summary = Column(JSONB, nullable=False, default=dict)
    created_by = Column(UUID(as_uuid=True), nullable=True)


class StudioProjectFrontend(Base, TimestampMixin):
    """Versioned frontend manifest for a Studio project (preview only — no codegen)."""

    __tablename__ = "studio_project_frontends"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_studio_frontend_project_version"),
        Index("ix_studio_frontends_project_current", "project_id", "is_current"),
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
    blueprint_version = Column(Integer, nullable=False, default=1)
    build_plan_version = Column(Integer, nullable=False, default=1)
    version = Column(Integer, nullable=False, default=1)
    is_current = Column(Boolean, nullable=False, default=True)
    status = Column(String(32), nullable=False, default="draft")  # draft | approved
    manifest = Column(JSONB, nullable=False, default=dict)
    created_by = Column(UUID(as_uuid=True), nullable=True)


class StudioProjectBackend(Base, TimestampMixin):
    """Versioned backend architecture manifest (preview only — no codegen)."""

    __tablename__ = "studio_project_backends"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_studio_backend_project_version"),
        Index("ix_studio_backends_project_current", "project_id", "is_current"),
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
    blueprint_version = Column(Integer, nullable=False, default=1)
    build_plan_version = Column(Integer, nullable=False, default=1)
    frontend_version = Column(Integer, nullable=False, default=1)
    version = Column(Integer, nullable=False, default=1)
    is_current = Column(Boolean, nullable=False, default=True)
    status = Column(String(32), nullable=False, default="draft")  # draft | approved
    manifest = Column(JSONB, nullable=False, default=dict)
    created_by = Column(UUID(as_uuid=True), nullable=True)


class StudioProjectAi(Base, TimestampMixin):
    """Versioned AI architecture manifest (preview only — no codegen)."""

    __tablename__ = "studio_project_ai"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_studio_ai_project_version"),
        Index("ix_studio_ai_project_current", "project_id", "is_current"),
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
    blueprint_version = Column(Integer, nullable=False, default=1)
    build_plan_version = Column(Integer, nullable=False, default=1)
    frontend_version = Column(Integer, nullable=False, default=1)
    backend_version = Column(Integer, nullable=False, default=1)
    version = Column(Integer, nullable=False, default=1)
    is_current = Column(Boolean, nullable=False, default=True)
    status = Column(String(32), nullable=False, default="draft")  # draft | approved
    manifest = Column(JSONB, nullable=False, default=dict)
    created_by = Column(UUID(as_uuid=True), nullable=True)


class StudioProjectInfrastructure(Base, TimestampMixin):
    """Versioned infrastructure planning manifest (no deploy / no codegen)."""

    __tablename__ = "studio_project_infrastructures"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_studio_infra_project_version"),
        Index("ix_studio_infra_project_current", "project_id", "is_current"),
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
    blueprint_version = Column(Integer, nullable=False, default=1)
    build_plan_version = Column(Integer, nullable=False, default=1)
    frontend_version = Column(Integer, nullable=False, default=1)
    backend_version = Column(Integer, nullable=False, default=1)
    ai_version = Column(Integer, nullable=False, default=1)
    version = Column(Integer, nullable=False, default=1)
    is_current = Column(Boolean, nullable=False, default=True)
    status = Column(String(32), nullable=False, default="draft")  # draft | approved
    manifest = Column(JSONB, nullable=False, default=dict)
    created_by = Column(UUID(as_uuid=True), nullable=True)


class StudioProjectApproval(Base, TimestampMixin):
    """Final build approval audit (Phase 8) — no codegen / no deploy."""

    __tablename__ = "studio_project_approvals"
    __table_args__ = (
        Index("ix_studio_approvals_project_created", "project_id", "created_at"),
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
    blueprint_version = Column(Integer, nullable=False, default=1)
    build_plan_version = Column(Integer, nullable=False, default=1)
    frontend_version = Column(Integer, nullable=False, default=0)
    backend_version = Column(Integer, nullable=False, default=0)
    ai_version = Column(Integer, nullable=False, default=0)
    infrastructure_version = Column(Integer, nullable=False, default=0)
    notes = Column(Text, nullable=True)
    snapshot = Column(JSONB, nullable=False, default=dict)
    created_by = Column(UUID(as_uuid=True), nullable=True)
