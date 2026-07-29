"""
app/auth/repository.py

Repository for Authentication models (RefreshTokens).
"""

import uuid
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.auth.model import RefreshToken


class AuthRepository:
    """
    Data-access layer for Authentication records.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def save_refresh_token(self, user_id: uuid.UUID, token: str, expires_at) -> RefreshToken:
        """Persist a new refresh token for a user."""
        rt = RefreshToken(user_id=user_id, token=token, expires_at=expires_at)
        self.db.add(rt)
        self.db.commit()
        self.db.refresh(rt)
        return rt

    def get_refresh_token(self, token: str) -> Optional[RefreshToken]:
        """Retrieve a refresh token by its exact string."""
        stmt = select(RefreshToken).where(RefreshToken.token == token)
        return self.db.scalar(stmt)

    def revoke_refresh_token(self, token: str) -> bool:
        """
        Mark a refresh token as revoked. 
        Returns True if revoked successfully, False if token wasn't found.
        """
        from datetime import datetime, timezone
        rt = self.get_refresh_token(token)
        if rt and rt.revoked_at is None:
            rt.revoked_at = datetime.now(timezone.utc)
            self.db.commit()
            return True
        return False

    # ── OTP Operations ────────────────────────────────────────────────────────
    
    def create_otp(self, otp: "OTPCode") -> "OTPCode":
        """Persist a new OTP record."""
        self.db.add(otp)
        self.db.commit()
        self.db.refresh(otp)
        return otp

    def get_latest_otp(self, email: Optional[str], phone: Optional[str], purpose: str) -> Optional["OTPCode"]:
        """Retrieve the latest OTP for a given email/phone and purpose."""
        from app.auth.model import OTPCode
        stmt = select(OTPCode).where(OTPCode.purpose == purpose)
        if email:
            stmt = stmt.where(OTPCode.email == email)
        if phone:
            stmt = stmt.where(OTPCode.phone == phone)
        stmt = stmt.order_by(OTPCode.created_at.desc()).limit(1)
        return self.db.scalar(stmt)

    def count_recent_otps(self, email: Optional[str], phone: Optional[str], since) -> int:
        """Count OTP requests since a given time for rate limiting."""
        from app.auth.model import OTPCode
        stmt = select(func.count(OTPCode.id)).where(OTPCode.created_at >= since)
        if email:
            stmt = stmt.where(OTPCode.email == email)
        if phone:
            stmt = stmt.where(OTPCode.phone == phone)
        return self.db.scalar(stmt) or 0

    def update_otp(self, otp: "OTPCode") -> "OTPCode":
        """Save changes to an existing OTP record."""
        self.db.commit()
        self.db.refresh(otp)
        return otp

    # ── MFA Operations ────────────────────────────────────────────────────────
    
    def get_mfa_settings(self, user_id: uuid.UUID) -> Optional["MFASettings"]:
        from app.auth.model import MFASettings
        stmt = select(MFASettings).where(MFASettings.user_id == user_id)
        return self.db.scalar(stmt)
        
    def create_mfa_settings(self, mfa: "MFASettings") -> "MFASettings":
        self.db.add(mfa)
        self.db.commit()
        self.db.refresh(mfa)
        return mfa
        
    def update_mfa_settings(self, mfa: "MFASettings") -> "MFASettings":
        self.db.commit()
        self.db.refresh(mfa)
        return mfa
