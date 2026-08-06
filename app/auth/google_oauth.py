"""Consumer Google OAuth (login / signup) — separate from enterprise Workspace SSO."""
from __future__ import annotations

import logging
import secrets
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status

from app.config.settings import settings

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


def google_oauth_configured() -> bool:
    return bool(
        (settings.GOOGLE_OAUTH_CLIENT_ID or "").strip()
        and (settings.GOOGLE_OAUTH_CLIENT_SECRET or "").strip()
    )


def require_google_oauth_configured() -> None:
    if not google_oauth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google login is not configured",
        )


def build_authorize_url(*, state: str, redirect_uri: Optional[str] = None) -> str:
    require_google_oauth_configured()
    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID.strip(),
        "redirect_uri": (redirect_uri or settings.GOOGLE_OAUTH_REDIRECT_URI).strip(),
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "include_granted_scopes": "true",
        "prompt": "select_account",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def new_oauth_state() -> str:
    return secrets.token_urlsafe(24)


async def exchange_code_for_userinfo(
    code: str,
    *,
    redirect_uri: Optional[str] = None,
) -> Dict[str, Any]:
    """Exchange authorization code for Google profile (email, sub, name)."""
    require_google_oauth_configured()
    redirect = (redirect_uri or settings.GOOGLE_OAUTH_REDIRECT_URI).strip()
    async with httpx.AsyncClient(timeout=20.0) as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_OAUTH_CLIENT_ID.strip(),
                "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET.strip(),
                "redirect_uri": redirect,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code >= 400:
            logger.warning("Google token exchange failed status=%s", token_resp.status_code)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google authorization failed",
            )
        tokens = token_resp.json()
        access_token = tokens.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google authorization failed",
            )
        info_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if info_resp.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not load Google profile",
            )
        return info_resp.json()


async def verify_google_id_token(id_token: str) -> Dict[str, Any]:
    """Validate a Google ID token (GIS / one-tap) via tokeninfo."""
    require_google_oauth_configured()
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(GOOGLE_TOKENINFO_URL, params={"id_token": id_token})
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google credential",
            )
        payload = resp.json()
    aud = str(payload.get("aud") or "")
    expected = settings.GOOGLE_OAUTH_CLIENT_ID.strip()
    if aud != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google credential audience",
        )
    if str(payload.get("email_verified", "")).lower() not in {"true", "1"}:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google email is not verified",
        )
    email = (payload.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account has no email",
        )
    return payload


def normalize_google_profile(raw: Dict[str, Any]) -> Dict[str, str]:
    email = (raw.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account has no email",
        )
    given = (raw.get("given_name") or raw.get("first_name") or "").strip()
    family = (raw.get("family_name") or raw.get("last_name") or "").strip()
    name = (raw.get("name") or "").strip()
    if not given and name:
        parts = name.split(None, 1)
        given = parts[0]
        family = parts[1] if len(parts) > 1 else "User"
    if not given:
        given = email.split("@", 1)[0][:100] or "User"
    if not family:
        family = "User"
    return {
        "email": email,
        "first_name": given[:100],
        "last_name": family[:100],
        "sub": str(raw.get("sub") or ""),
    }
