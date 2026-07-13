"""
app/auth/schema.py

Pydantic schemas for Authentication endpoints.
"""

from typing import Optional
from pydantic import BaseModel, EmailStr, Field
import uuid

# ── Requests ─────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    """Schema for JSON payload on POST /login."""
    email: EmailStr
    password: str = Field(..., min_length=1)


class RefreshRequest(BaseModel):
    """Schema for POST /refresh to obtain a new access token."""
    refresh_token: str


class LogoutRequest(BaseModel):
    """Schema for POST /logout to revoke a refresh token."""
    refresh_token: str


# ── Responses ────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    """Response returned upon successful login or refresh."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token expiration in seconds")


class UserProfileResponse(BaseModel):
    """Basic user profile returned by GET /me."""
    id: uuid.UUID
    company_id: uuid.UUID
    email: EmailStr
    first_name: str
    last_name: str
    role: str

# ── OTP ──────────────────────────────────────────────────────────────────────

from app.auth.model import OTPPurpose

class SendOTPRequest(BaseModel):
    purpose: OTPPurpose
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

class VerifyOTPRequest(BaseModel):
    purpose: OTPPurpose
    code: str = Field(..., min_length=6, max_length=6)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

class ResendOTPRequest(BaseModel):
    purpose: OTPPurpose
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
