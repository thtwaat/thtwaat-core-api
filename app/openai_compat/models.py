"""ORM: audit log for OpenAI-compatible completions."""
from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base, TimestampMixin

# Ensure Company.relationship("User") resolves when mappers configure
import app.users.model  # noqa: F401
import app.companies.model  # noqa: F401


class OpenAICompletionLog(Base, TimestampMixin):
    __tablename__ = "openai_completion_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    api_key_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    agent_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    completion_id = Column(String(64), nullable=False, unique=True, index=True)
    model = Column(String(200), nullable=False)
    provider = Column(String(64), nullable=False, default="stub")
    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    finish_reason = Column(String(32), nullable=True)
    request_messages = Column(JSONB, nullable=False, default=list)
    response_content = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=False, default=0)
    status = Column(String(32), nullable=False, default="succeeded")
    error_detail = Column(Text, nullable=True)
