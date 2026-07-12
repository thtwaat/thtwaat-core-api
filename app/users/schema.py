"""
app/users/schema.py

Pydantic v2 schemas for the Users module.
"""

import uuid
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.users.model import UserStatus
from app.rbac.enums import EnterpriseRole


# ── Shared base ─────────────────────────────────────────────────────────────

class UserBase(BaseModel):
    email: EmailStr = Field(..., description="User's email address")
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)


# ── Create ───────────────────────────────────────────────────────────────────

class UserCreate(UserBase):
    """Schema used when registering or creating a new user."""
    password: str = Field(..., min_length=8, max_length=128)
    company_id: uuid.UUID
    role: EnterpriseRole = Field(default=EnterpriseRole.EMPLOYEE)


# ── Update (PATCH — all optional) ───────────────────────────────────────────

class UserUpdate(BaseModel):
    """Partial update schema for user profiles."""
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    role: Optional[EnterpriseRole] = None
    status: Optional[UserStatus] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8, max_length=128)


# ── Response ─────────────────────────────────────────────────────────────────

class UserResponse(UserBase):
    """Safe response schema returned by API endpoints. (No passwords!)"""
    id: uuid.UUID
    company_id: uuid.UUID
    role: EnterpriseRole
    status: UserStatus
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# ── Paginated List Response ──────────────────────────────────────────────────

class UserListResponse(BaseModel):
    """Wrapper for paginated user list results."""
    total: int
    page: int
    page_size: int
    results: list[UserResponse]
