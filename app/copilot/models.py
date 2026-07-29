"""Copilot persistence models."""
from __future__ import annotations

import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.copilot.intents import MessageRole, StepStatus, TaskStatus
from app.models.base import Base, TimestampMixin


class CopilotConversation(Base, TimestampMixin):
    __tablename__ = "copilot_conversations"
    __table_args__ = (Index("ix_copilot_conversations_company_user", "company_id", "user_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = Column(String(255), nullable=True)
    memory = Column(JSONB, nullable=False, default=dict)  # slots: agent_id, generation_id, …
    is_active = Column(String(16), nullable=False, default="active")  # active|archived


class CopilotMessage(Base, TimestampMixin):
    __tablename__ = "copilot_messages"
    __table_args__ = (Index("ix_copilot_messages_conversation", "conversation_id", "created_at"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("copilot_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    role = Column(
        SAEnum(
            MessageRole,
            name="copilot_message_role_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    content = Column(Text, nullable=False)
    intent = Column(String(64), nullable=True)
    confidence = Column(String(16), nullable=True)
    meta = Column("metadata", JSONB, nullable=False, default=dict)


class CopilotTask(Base, TimestampMixin):
    __tablename__ = "copilot_tasks"
    __table_args__ = (
        Index("ix_copilot_tasks_company_status", "company_id", "status"),
        Index("ix_copilot_tasks_conversation", "conversation_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("copilot_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    intent = Column(String(64), nullable=False)
    status = Column(
        SAEnum(
            TaskStatus,
            name="copilot_task_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=TaskStatus.PLANNED,
    )
    prompt = Column(Text, nullable=False)
    plan = Column(JSONB, nullable=False, default=list)
    slots = Column(JSONB, nullable=False, default=dict)
    result = Column(JSONB, nullable=False, default=dict)
    error = Column(Text, nullable=True)
    requires_confirmation = Column(String(8), nullable=False, default="false")
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    progress_percent = Column(Integer, nullable=False, default=0)
    parent_task_id = Column(
        UUID(as_uuid=True), ForeignKey("copilot_tasks.id", ondelete="SET NULL"), nullable=True
    )  # replay lineage


class CopilotTaskStep(Base, TimestampMixin):
    __tablename__ = "copilot_task_steps"
    __table_args__ = (Index("ix_copilot_task_steps_task", "task_id", "step_index"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(
        UUID(as_uuid=True), ForeignKey("copilot_tasks.id", ondelete="CASCADE"), nullable=False
    )
    step_index = Column(Integer, nullable=False)
    tool_name = Column(String(100), nullable=False)
    title = Column(String(255), nullable=False)
    status = Column(
        SAEnum(
            StepStatus,
            name="copilot_step_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=StepStatus.PENDING,
    )
    input_args = Column(JSONB, nullable=False, default=dict)
    output = Column(JSONB, nullable=False, default=dict)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
