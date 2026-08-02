"""
app/auth/router.py

FastAPI APIRouter for Authentication.
"""

from fastapi import APIRouter, Depends, status, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.auth.security import bearer_scheme
from app.auth.schema import (
    LoginRequest, 
    RefreshRequest, 
    LogoutRequest, 
    TokenResponse, 
    UserProfileResponse,
    SendOTPRequest,
    VerifyOTPRequest,
    ResendOTPRequest,
    EmailVerificationRequest,
    VerifyEmailRequest,
    PhoneVerificationRequest,
    VerifyPhoneRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    MFASetupResponse,
    MFAEnableRequest,
    MFAVerifyRequest,
    MFABackupCodesResponse,
    MFARequiredResponse
)
from app.auth.service import AuthService
from app.auth.rate_limit import auth_rate_limit


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

security = bearer_scheme

# Auth-sensitive routes: keep limits tight to blunt credential stuffing / OTP spray.
_LOGIN_LIMIT = auth_rate_limit(times=10, seconds=60)
_REFRESH_LIMIT = auth_rate_limit(times=30, seconds=60)
_OTP_LIMIT = auth_rate_limit(times=5, seconds=60)
_PASSWORD_RESET_LIMIT = auth_rate_limit(times=5, seconds=60)


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    """Dependency provider for AuthService."""
    return AuthService(db)


# ── Endpoints ─────────────────────────────────────────────────────────────────

from typing import Union

@router.post(
    "/login",
    response_model=Union[TokenResponse, MFARequiredResponse],
    summary="Login and obtain tokens",
    dependencies=_LOGIN_LIMIT,
)
def login(
    payload: LoginRequest,
    service: AuthService = Depends(get_auth_service),
):
    """
    Authenticate a user by email and password, returning JWT access and refresh tokens.
    Accepts application/json payload.
    """
    return service.authenticate_user(payload)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    dependencies=_REFRESH_LIMIT,
)
def refresh_token(
    payload: RefreshRequest,
    service: AuthService = Depends(get_auth_service),
):
    """
    Obtain a new access token by providing a valid refresh token.
    """
    return service.refresh_tokens(payload.refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Logout and revoke refresh token",
)
def logout(
    payload: LogoutRequest,
    service: AuthService = Depends(get_auth_service),
):
    """
    Log out by revoking the provided refresh token so it cannot be used again.
    """
    service.logout_user(payload.refresh_token)
    return {"detail": "Successfully logged out."}


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get current user profile",
)
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    service: AuthService = Depends(get_auth_service),
):
    """
    Retrieve the profile of the currently authenticated user based on their access token.
    Requires Authorization: Bearer <token> header.
    """
    return service.get_current_user_profile(credentials.credentials)

# ── OTP Endpoints ─────────────────────────────────────────────────────────────

@router.post("/send-otp", summary="Send an OTP code", dependencies=_OTP_LIMIT)
def send_otp(
    payload: SendOTPRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    """Generate and send an OTP code to the provided email or phone."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return service.send_otp(
        purpose=payload.purpose,
        email=payload.email,
        phone=payload.phone,
        ip_address=ip_address,
        user_agent=user_agent
    )


@router.post("/verify-otp", summary="Verify an OTP code", dependencies=_OTP_LIMIT)
def verify_otp(
    payload: VerifyOTPRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    """Verify an OTP code. If the purpose is LOGIN, this returns JWT tokens."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return service.verify_otp(
        purpose=payload.purpose,
        code=payload.code,
        email=payload.email,
        phone=payload.phone,
        ip_address=ip_address,
        user_agent=user_agent
    )


@router.post("/resend-otp", summary="Resend an OTP code", dependencies=_OTP_LIMIT)
def resend_otp(
    payload: ResendOTPRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    """Resend an OTP code after the cooldown period."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return service.resend_otp(
        purpose=payload.purpose,
        email=payload.email,
        phone=payload.phone,
        ip_address=ip_address,
        user_agent=user_agent
    )

# ── Identity Verification Endpoints ───────────────────────────────────────────

@router.post("/send-email-verification", summary="Send an email verification code")
def send_email_verification(
    payload: EmailVerificationRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return service.send_email_verification(
        email=payload.email,
        ip_address=ip_address,
        user_agent=user_agent
    )

@router.post("/verify-email", summary="Verify email with code")
def verify_email(
    payload: VerifyEmailRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return service.verify_email(
        email=payload.email,
        code=payload.code,
        ip_address=ip_address,
        user_agent=user_agent
    )

@router.post("/send-phone-verification", summary="Send a phone verification code")
def send_phone_verification(
    payload: PhoneVerificationRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return service.send_phone_verification(
        phone=payload.phone,
        ip_address=ip_address,
        user_agent=user_agent
    )

@router.post("/verify-phone", summary="Verify phone with code")
def verify_phone(
    payload: VerifyPhoneRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return service.verify_phone(
        phone=payload.phone,
        code=payload.code,
        ip_address=ip_address,
        user_agent=user_agent
    )

@router.post("/forgot-password", summary="Send a password reset code", dependencies=_PASSWORD_RESET_LIMIT)
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return service.forgot_password(
        email=payload.email,
        ip_address=ip_address,
        user_agent=user_agent
    )

@router.post("/reset-password", summary="Reset password using OTP code", dependencies=_PASSWORD_RESET_LIMIT)
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return service.reset_password(
        email=payload.email,
        code=payload.code,
        new_password=payload.new_password,
        ip_address=ip_address,
        user_agent=user_agent
    )

# ── MFA Endpoints ────────────────────────────────────────────────────────────

@router.post("/mfa/setup", response_model=MFASetupResponse, summary="Setup MFA for the current user")
def setup_mfa(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    service: AuthService = Depends(get_auth_service),
):
    profile = service.get_current_user_profile(credentials.credentials)
    return service.setup_mfa(user_id=profile.id)

@router.post("/mfa/enable", summary="Enable MFA with verification code")
def enable_mfa(
    payload: MFAEnableRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    service: AuthService = Depends(get_auth_service),
):
    profile = service.get_current_user_profile(credentials.credentials)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return service.enable_mfa(
        user_id=profile.id,
        code=payload.code,
        ip_address=ip_address,
        user_agent=user_agent
    )

@router.post("/mfa/disable", summary="Disable MFA")
def disable_mfa(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    service: AuthService = Depends(get_auth_service),
):
    profile = service.get_current_user_profile(credentials.credentials)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return service.disable_mfa(
        user_id=profile.id,
        ip_address=ip_address,
        user_agent=user_agent
    )

@router.get("/mfa/recovery-codes", summary="Get remaining recovery codes count")
def get_recovery_codes_status(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    service: AuthService = Depends(get_auth_service),
):
    profile = service.get_current_user_profile(credentials.credentials)
    return service.get_recovery_codes_status(user_id=profile.id)

@router.post("/mfa/regenerate-recovery-codes", response_model=MFABackupCodesResponse, summary="Regenerate recovery codes")
def regenerate_recovery_codes(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    service: AuthService = Depends(get_auth_service),
):
    profile = service.get_current_user_profile(credentials.credentials)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return service.regenerate_recovery_codes(
        user_id=profile.id,
        ip_address=ip_address,
        user_agent=user_agent
    )

@router.post("/mfa/verify", response_model=TokenResponse, summary="Verify MFA code and obtain tokens")
def verify_mfa(
    payload: MFAVerifyRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return service.verify_mfa(
        mfa_token=payload.mfa_token,
        totp_code=payload.totp,
        ip_address=ip_address,
        user_agent=user_agent
    )

