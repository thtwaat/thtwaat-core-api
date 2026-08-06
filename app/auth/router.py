"""
app/auth/router.py

FastAPI APIRouter for Authentication.
"""

from typing import Optional, Union
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Depends, status, Request, Query
from fastapi.responses import RedirectResponse
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
    ForgotPasswordRequest,
    ResetPasswordRequest,
    GoogleIdTokenRequest,
    MFASetupResponse,
    MFAEnableRequest,
    MFAVerifyRequest,
    MFABackupCodesResponse,
    MFARequiredResponse,
)
from app.auth.service import AuthService
from app.auth.rate_limit import auth_rate_limit
from app.auth import google_oauth
from app.config.settings import settings


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

security = bearer_scheme

_LOGIN_LIMIT = auth_rate_limit(times=10, seconds=60)
_REFRESH_LIMIT = auth_rate_limit(times=30, seconds=60)
_PASSWORD_RESET_LIMIT = auth_rate_limit(times=5, seconds=60)
_GOOGLE_LIMIT = auth_rate_limit(times=20, seconds=60)


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    """Dependency provider for AuthService."""
    return AuthService(db)


def _frontend_auth_redirect(
    *,
    access_token: Optional[str] = None,
    refresh_token: Optional[str] = None,
    expires_in: Optional[int] = None,
    error: Optional[str] = None,
) -> RedirectResponse:
    base = (settings.PUBLIC_APP_BASE_URL or "").rstrip("/")
    if error:
        url = f"{base}/login?error={quote(error)}"
        return RedirectResponse(url=url, status_code=302)
    fragment = urlencode(
        {
            "access_token": access_token or "",
            "refresh_token": refresh_token or "",
            "expires_in": str(expires_in or 0),
            "token_type": "bearer",
        }
    )
    return RedirectResponse(url=f"{base}/auth/callback#{fragment}", status_code=302)


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
    """Authenticate with email and password."""
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
    return service.get_current_user_profile(credentials.credentials)


@router.post(
    "/forgot-password",
    summary="Send a password reset link",
    dependencies=_PASSWORD_RESET_LIMIT,
)
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
        user_agent=user_agent,
    )


@router.post(
    "/reset-password",
    summary="Reset password using email link token",
    dependencies=_PASSWORD_RESET_LIMIT,
)
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return service.reset_password(
        token=payload.token,
        new_password=payload.new_password,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.get(
    "/google/start",
    summary="Start Google OAuth (redirect)",
    dependencies=_GOOGLE_LIMIT,
)
def google_oauth_start():
    google_oauth.require_google_oauth_configured()
    state = google_oauth.new_oauth_state()
    url = google_oauth.build_authorize_url(state=state)
    response = RedirectResponse(url=url, status_code=302)
    response.set_cookie(
        "tht_google_oauth_state",
        state,
        httponly=True,
        samesite="lax",
        max_age=600,
        path="/",
    )
    return response


@router.get(
    "/google/callback",
    summary="Google OAuth callback",
    dependencies=_GOOGLE_LIMIT,
)
async def google_oauth_callback(
    request: Request,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    service: AuthService = Depends(get_auth_service),
):
    if error:
        return _frontend_auth_redirect(error="google_denied")
    cookie_state = request.cookies.get("tht_google_oauth_state")
    if not code or not state or not cookie_state or state != cookie_state:
        return _frontend_auth_redirect(error="google_invalid_state")
    try:
        raw = await google_oauth.exchange_code_for_userinfo(code)
        profile = google_oauth.normalize_google_profile(raw)
        tokens = service.login_or_register_google_profile(profile)
    except Exception:
        return _frontend_auth_redirect(error="google_failed")
    response = _frontend_auth_redirect(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )
    response.delete_cookie("tht_google_oauth_state", path="/")
    return response


@router.post(
    "/google",
    response_model=TokenResponse,
    summary="Sign in with Google ID token",
    dependencies=_GOOGLE_LIMIT,
)
async def google_id_token_login(
    payload: GoogleIdTokenRequest,
    service: AuthService = Depends(get_auth_service),
):
    raw = await google_oauth.verify_google_id_token(payload.id_token)
    profile = google_oauth.normalize_google_profile(raw)
    return service.login_or_register_google_profile(profile)


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
