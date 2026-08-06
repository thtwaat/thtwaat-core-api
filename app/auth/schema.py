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
    company_slug: Optional[str] = Field(
        None,
        description="Required when the same email belongs to multiple tenants",
    )


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


# ── Password reset (link-based) ──────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=20, description="Token from the reset email link")
    new_password: str = Field(..., min_length=8, description="Must be at least 8 characters long")


class GoogleIdTokenRequest(BaseModel):
    """GIS / one-tap credential (ID token)."""
    id_token: str = Field(..., min_length=20)


# ── MFA (TOTP — not email OTP) ───────────────────────────────────────────────

class MFASetupResponse(BaseModel):
    secret: str
    qr_code_uri: str
    qr_code_base64: str

class MFAEnableRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)

class MFAVerifyRequest(BaseModel):
    mfa_token: Optional[str] = None # Used during login
    totp: str = Field(..., min_length=6, max_length=10) # Supports 6-8 digit TOTP or recovery codes

class MFABackupCodesResponse(BaseModel):
    backup_codes: list[str]

class MFARequiredResponse(BaseModel):
    mfa_required: bool = True
    mfa_token: str
    expires_in: int = 300
