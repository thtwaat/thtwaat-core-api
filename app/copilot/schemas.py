"""Pydantic schemas for AI Copilot."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.copilot.intents import CopilotIntent, MessageRole, StepStatus, TaskStatus


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: Optional[UUID] = None
    auto_execute: bool = Field(
        default=True,
        description="If false, only plan the task without running tools",
    )
    confirm: bool = Field(
        default=False,
        description="Confirm a pending destructive task in this conversation",
    )


class ConfirmTaskRequest(BaseModel):
    confirm: bool = True
    note: Optional[str] = Field(None, max_length=500)


class ToolInfo(BaseModel):
    name: str
    integration: str
    description: str
    destructive: bool = False
    platform_admin: bool = False


class StepProgress(BaseModel):
    id: UUID
    step_index: int
    tool_name: str
    title: str
    status: StepStatus
    input_args: Dict[str, Any] = Field(default_factory=dict)
    output: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TaskResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    intent: str
    status: TaskStatus
    prompt: str
    plan: List[Dict[str, Any]] = Field(default_factory=list)
    slots: Dict[str, Any] = Field(default_factory=dict)
    result: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    requires_confirmation: bool = False
    progress_percent: int = 0
    steps: List[StepProgress] = Field(default_factory=list)
    created_at: datetime
    completed_at: Optional[datetime] = None
    parent_task_id: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    intent: Optional[str] = None
    confidence: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="meta")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ChatResponse(BaseModel):
    conversation_id: UUID
    message: MessageResponse
    intent: CopilotIntent
    confidence: float
    matched_keywords: List[str] = Field(default_factory=list)
    task: Optional[TaskResponse] = None
    needs_confirmation: bool = False
    missing_slots: List[str] = Field(default_factory=list)
    progress: List[Dict[str, Any]] = Field(default_factory=list)


class HistoryResponse(BaseModel):
    conversation_id: Optional[UUID] = None
    messages: List[MessageResponse] = Field(default_factory=list)
    tasks: List[TaskResponse] = Field(default_factory=list)


class TaskListResponse(BaseModel):
    total: int
    items: List[TaskResponse]


class ToolsResponse(BaseModel):
    tools: List[ToolInfo]
    workflows: List[Dict[str, Any]]


class FailureDiagnostics(BaseModel):
    task_id: UUID
    intent: str
    status: TaskStatus
    error: Optional[str] = None
    failed_step: Optional[StepProgress] = None
    preceding_steps: List[StepProgress] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    related_monitoring: Dict[str, Any] = Field(default_factory=dict)
