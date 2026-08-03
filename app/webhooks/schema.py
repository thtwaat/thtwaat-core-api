from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import uuid


class WebhookCreate(BaseModel):
    url: str
    event_types: List[str] = Field(default_factory=lambda: ["*"])


class WebhookUpdate(BaseModel):
    url: Optional[str] = None
    event_types: Optional[List[str]] = None
    is_active: Optional[bool] = None


class WebhookResponse(BaseModel):
    id: uuid.UUID
    url: str
    event_types: List[str]
    is_active: bool
    created_at: datetime
    # Secret is returned only once on create / reveal
    secret: Optional[str] = None


class WebhookGenerateResponse(WebhookResponse):
    secret: str


class WebhookDeliveryResponse(BaseModel):
    id: uuid.UUID
    delivery_id: str
    webhook_id: Optional[uuid.UUID] = None
    event: str
    url: str
    status: str
    attempts: int
    last_error: Optional[str] = None
    next_attempt_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class WebhookDeliveryListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    results: List[WebhookDeliveryResponse]
