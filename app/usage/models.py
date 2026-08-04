"""Usage metering ORM models."""
from __future__ import annotations

import uuid
from sqlalchemy import (
    Column,
    String,
    BigInteger,
    Integer,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
    Text,
    Numeric,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base, TimestampMixin


class UsageEvent(Base, TimestampMixin):
    """Immutable usage event stream."""

    __tablename__ = "usage_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    dimension = Column(String(64), nullable=False, index=True)
    quantity = Column(BigInteger, nullable=False, default=1)
    agent_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    api_key_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    widget_id = Column(String(64), nullable=True, index=True)
    source = Column(String(64), nullable=True)  # public_chat, gateway, knowledge, ...
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    occurred_at = Column(DateTime(timezone=True), nullable=False)


class CompanyUsageMeter(Base, TimestampMixin):
    """Current billing-period counters + limits snapshot per company."""

    __tablename__ = "company_usage_meters"
    __table_args__ = (
        UniqueConstraint("company_id", "period_start", "period_type", name="uq_usage_meter_period"),
        Index("ix_usage_meter_company_period", "company_id", "period_type"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    period_type = Column(String(16), nullable=False, default="monthly")  # hourly|daily|monthly|lifetime
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    plan_key = Column(String(50), nullable=False, default="free")

    # Counters
    ai_messages = Column(BigInteger, nullable=False, default=0)
    conversations = Column(BigInteger, nullable=False, default=0)
    prompt_tokens = Column(BigInteger, nullable=False, default=0)
    completion_tokens = Column(BigInteger, nullable=False, default=0)
    total_tokens = Column(BigInteger, nullable=False, default=0)
    api_requests = Column(BigInteger, nullable=False, default=0)
    widget_requests = Column(BigInteger, nullable=False, default=0)
    knowledge_searches = Column(BigInteger, nullable=False, default=0)
    knowledge_upload_bytes = Column(BigInteger, nullable=False, default=0)
    storage_bytes = Column(BigInteger, nullable=False, default=0)
    agents_count = Column(Integer, nullable=False, default=0)
    active_users = Column(Integer, nullable=False, default=0)
    api_keys = Column(Integer, nullable=False, default=0)
    domains = Column(Integer, nullable=False, default=0)
    templates_published = Column(Integer, nullable=False, default=0)
    estimated_cost = Column(Numeric(12, 6), nullable=False, default=0)

    # Limits snapshot (copied from plan at period open / upgrade)
    max_agents = Column(Integer, nullable=False, default=1)
    max_messages = Column(Integer, nullable=False, default=100)
    max_tokens = Column(BigInteger, nullable=False, default=50000)
    max_storage = Column(BigInteger, nullable=False, default=104857600)
    max_domains = Column(Integer, nullable=False, default=0)
    max_team_members = Column(Integer, nullable=False, default=5)
    max_api_keys = Column(Integer, nullable=False, default=1)
    max_templates = Column(Integer, nullable=False, default=0)
    max_widgets = Column(Integer, nullable=False, default=1)
    max_knowledge = Column(Integer, nullable=False, default=1)


class UsageDailyAggregate(Base, TimestampMixin):
    """Daily rollups for history charts."""

    __tablename__ = "usage_daily_aggregates"
    __table_args__ = (
        UniqueConstraint("company_id", "day", "dimension", name="uq_usage_daily_dim"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    day = Column(DateTime(timezone=True), nullable=False, index=True)
    dimension = Column(String(64), nullable=False)
    quantity = Column(BigInteger, nullable=False, default=0)
