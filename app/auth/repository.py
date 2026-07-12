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
        rt = self.get_refresh_token(token)
        if rt and rt.revoked_at is None:
            rt.revoked_at = func.now()
            self.db.commit()
            return True
        return False
