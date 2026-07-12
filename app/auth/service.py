"""
app/auth/service.py

Business logic for Authentication (JWT creation, verification, password hashing).
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import bcrypt
from jose import jwt, JWTError
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

# To fetch users, we import the model directly (or UserRepository)
from app.users.model import User, UserStatus
from app.auth.model import RefreshToken
from app.auth.repository import AuthRepository
from app.auth.schema import LoginRequest, TokenResponse, UserProfileResponse


# ── Configuration (Environment or Default) ───────────────────────────────────

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-secret-enterprise-key-change-in-prod")
JWT_REFRESH_SECRET_KEY = os.getenv("JWT_REFRESH_SECRET_KEY", "super-secret-refresh-key-change-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


class AuthService:
    """
    Service layer for issuing tokens, validating credentials, and managing sessions.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = AuthRepository(db)

    # ── Password Hashing ──────────────────────────────────────────────────────

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Check if the provided password matches the bcrypt hash."""
        # Handle the dummy hash from the Users module scaffolding temporarily
        if hashed_password.startswith("dummy_hash_"):
            return hashed_password == f"dummy_hash_{plain_password[::-1]}"
            
        try:
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                hashed_password.encode("utf-8")
            )
        except ValueError:
            return False

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    # ── Token Generation ──────────────────────────────────────────────────────

    def create_access_token(self, subject: str) -> str:
        """Create a short-lived JWT access token."""
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        expire = datetime.now(timezone.utc) + expires_delta
        
        to_encode = {"exp": expire, "sub": str(subject), "type": "access"}
        encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    def create_refresh_token(self, subject: str) -> str:
        """Create a long-lived JWT refresh token and store it in DB."""
        expires_delta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        expire = datetime.now(timezone.utc) + expires_delta
        
        to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
        encoded_jwt = jwt.encode(to_encode, JWT_REFRESH_SECRET_KEY, algorithm=ALGORITHM)
        
        # Save to DB for revocation tracking
        self.repo.save_refresh_token(
            user_id=uuid.UUID(subject),
            token=encoded_jwt,
            expires_at=expire
        )
        return encoded_jwt

    # ── Core Operations ───────────────────────────────────────────────────────

    def authenticate_user(self, data: LoginRequest) -> TokenResponse:
        """
        Verify credentials and issue tokens.
        """
        # Fetch user directly using SQLAlchemy to avoid tight coupling if preferred,
        # but we can just use the DB session here.
        stmt = select(User).where(User.email == data.email)
        user = self.db.scalar(stmt)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not self.verify_password(data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        if not user.is_active or user.status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is suspended or inactive.",
            )

        # Generate tokens
        access_token = self.create_access_token(subject=str(user.id))
        refresh_token = self.create_refresh_token(subject=str(user.id))
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    def refresh_tokens(self, token: str) -> TokenResponse:
        """
        Validate refresh token, issue a new access token, and optionally rotate refresh token.
        """
        try:
            payload = jwt.decode(token, JWT_REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
            user_id_str = payload.get("sub")
            token_type = payload.get("type")
            
            if user_id_str is None or token_type != "refresh":
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
        except JWTError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

        # Check if token is revoked in DB
        db_token = self.repo.get_refresh_token(token)
        if not db_token or db_token.revoked_at is not None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has been revoked")

        # (Optional) Token rotation: Revoke old and issue new refresh token
        # For simplicity, we just issue a new access token here
        access_token = self.create_access_token(subject=user_id_str)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=token, # reusing the same refresh token
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    def logout_user(self, token: str) -> None:
        """Revoke a refresh token."""
        # Does not validate signature here, just revokes exact string match
        self.repo.revoke_refresh_token(token)

    def get_current_user_profile(self, token: str) -> UserProfileResponse:
        """
        Extract user from an access token.
        """
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
            user_id_str = payload.get("sub")
            token_type = payload.get("type")
            
            if user_id_str is None or token_type != "access":
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
        except JWTError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token")

        # Fetch user
        stmt = select(User).where(User.id == uuid.UUID(user_id_str))
        user = self.db.scalar(stmt)
        
        if not user or not user.is_active or user.status != UserStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

        return UserProfileResponse(
            id=user.id,
            company_id=user.company_id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role.value
        )
