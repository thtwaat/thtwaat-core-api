"""
app/auth/router.py

FastAPI APIRouter for Authentication.
"""

from fastapi import APIRouter, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.auth.schema import (
    LoginRequest, 
    RefreshRequest, 
    LogoutRequest, 
    TokenResponse, 
    UserProfileResponse
)
from app.auth.service import AuthService


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

security = HTTPBearer()


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    """Dependency provider for AuthService."""
    return AuthService(db)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and obtain tokens",
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
