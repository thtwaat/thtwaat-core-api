"""
app/payments/plans/schema.py
"""
import uuid
from typing import Optional, List, Any
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class PlanCreate(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    interval: str = Field(default="month", pattern="^(month|year)$")
    interval_count: int = Field(default=1, ge=1)
    max_users: int = Field(default=5, ge=1)
    max_apps: int = Field(default=1, ge=1)
    ai_credits: Decimal = Field(default=Decimal("100.0"), ge=0)
    features: Optional[List[str]] = None
    stripe_price_id: Optional[str] = None
    razorpay_plan_id: Optional[str] = None
    max_agents: int = Field(default=1, ge=0)
    max_messages: int = Field(default=100, ge=0)
    max_tokens: int = Field(default=50000, ge=0)
    max_storage: int = Field(default=104857600, ge=0)
    max_domains: int = Field(default=0, ge=0)
    max_team_members: int = Field(default=5, ge=0)
    max_api_keys: int = Field(default=1, ge=0)
    max_templates: int = Field(default=0, ge=0)


class PlanUpdate(BaseModel):
    description: Optional[str] = None
    is_active: Optional[bool] = None
    features: Optional[List[str]] = None
    ai_credits: Optional[Decimal] = None
    max_users: Optional[int] = None
    max_apps: Optional[int] = None
    max_agents: Optional[int] = None
    max_messages: Optional[int] = None
    max_tokens: Optional[int] = None
    max_storage: Optional[int] = None
    max_domains: Optional[int] = None
    max_team_members: Optional[int] = None
    max_api_keys: Optional[int] = None
    max_templates: Optional[int] = None


class PlanResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    amount: float
    currency: str
    interval: str
    interval_count: int
    max_users: int
    max_apps: int
    ai_credits: float
    features: Optional[List[Any]]
    stripe_price_id: Optional[str]
    razorpay_plan_id: Optional[str]
    max_agents: int = 1
    max_messages: int = 100
    max_tokens: int = 50000
    max_storage: int = 104857600
    max_domains: int = 0
    max_team_members: int = 5
    max_api_keys: int = 1
    max_templates: int = 0
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
