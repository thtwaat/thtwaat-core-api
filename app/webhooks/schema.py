from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid

class WebhookCreate(BaseModel):
    url: str
    event_types: List[str]

class WebhookResponse(BaseModel):
    id: uuid.UUID
    url: str
    event_types: List[str]
    is_active: bool
    created_at: datetime
    # Secret is returned only once
    secret: Optional[str] = None

class WebhookGenerateResponse(WebhookResponse):
    secret: str
