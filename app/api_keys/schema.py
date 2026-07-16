from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid

class APIKeyCreate(BaseModel):
    name: str
    app_label: str
    scopes: Optional[List[str]] = []

class APIKeyResponse(BaseModel):
    id: uuid.UUID
    name: str
    app_label: str
    scopes: List[str]
    created_at: datetime
    last_used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    masked_key: str  # Only return the last 4 characters e.g. ****abcd

class APIKeyGenerateResponse(APIKeyResponse):
    raw_key: str  # Only returned ONCE during creation
