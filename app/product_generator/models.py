"""Product Generator job tracking ORM."""
from __future__ import annotations

import enum
import uuid

from sqlalchemy import Column, ForeignKey, Index, String, Text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base, TimestampMixin


class ProductGenerationStatus(str, enum.Enum):
    DRAFT = "draft"
    ANALYZING = "analyzing"
    TEMPLATE_SELECTED = "template_selected"
    PROVISIONING = "provisioning"
    CONFIGURING = "configuring"
    BINDING = "binding"
    PREVIEW_READY = "preview_ready"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


class ProductGeneration(Base, TimestampMixin):
    """Tracks an AI Product Generator run that orchestrates existing services."""

    __tablename__ = "product_generations"
    __table_args__ = (
        Index("ix_product_generations_company_status", "company_id", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(UUID(as_uuid=True), nullable=True)
    prompt = Column(Text, nullable=False)
    status = Column(
        SAEnum(
            ProductGenerationStatus,
            name="product_generation_status_enum",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ProductGenerationStatus.DRAFT,
        index=True,
    )

    # Step 1 analysis
    analysis = Column(JSONB, nullable=False, default=dict)

    # Step 2 template selection
    template_id = Column(UUID(as_uuid=True), nullable=True)
    template_slug = Column(String(120), nullable=True)
    installation_id = Column(UUID(as_uuid=True), nullable=True)

    # Step 3 provisioned resources
    agent_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    knowledge_base_id = Column(UUID(as_uuid=True), nullable=True)
    api_key_id = Column(UUID(as_uuid=True), nullable=True)
    api_key_prefix = Column(String(32), nullable=True)
    widget_id = Column(String(64), nullable=True)
    domain_id = Column(UUID(as_uuid=True), nullable=True)

    # Step 4–6 config + preview
    product_config = Column(JSONB, nullable=False, default=dict)
    preview_url = Column(String(500), nullable=True)
    widget_snippet = Column(Text, nullable=True)

    # Step 7 publish
    publish_status = Column(String(32), nullable=True)
    result = Column(JSONB, nullable=False, default=dict)
    deployment_checklist = Column(JSONB, nullable=False, default=list)
    failure_reason = Column(Text, nullable=True)
    # One-time raw key stored only until first GET after publish (cleared after read)
    ephemeral_api_key = Column(String(128), nullable=True)
