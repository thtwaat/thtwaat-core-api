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

    # ── OTP Foundation ────────────────────────────────────────────────────────

    @staticmethod
    def generate_otp() -> str:
        """Generate a secure 6-digit OTP."""
        import secrets
        return "".join(str(secrets.randbelow(10)) for _ in range(6))

    @staticmethod
    def hash_otp(code: str) -> str:
        """Hash OTP using bcrypt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(code.encode("utf-8"), salt).decode("utf-8")

    @staticmethod
    def verify_otp_hash(code: str, hashed: str) -> bool:
        """Check if OTP matches hash."""
        try:
            return bcrypt.checkpw(code.encode("utf-8"), hashed.encode("utf-8"))
        except ValueError:
            return False

    def send_otp(self, purpose, email: Optional[str], phone: Optional[str], ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> dict:
        from app.auth.model import OTPCode
        from app.auth.audit import log_otp_event
        from app.auth.providers.factory import OTPProviderFactory
        
        if not email and not phone:
            raise HTTPException(status_code=400, detail="Must provide email or phone")

        # Rate Limiting: max 5 requests per hour
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        count = self.repo.count_recent_otps(email=email, phone=phone, since=one_hour_ago)
        if count >= 5:
            log_otp_event("OTP Blocked (Rate Limit)", email=email, phone=phone, ip_address=ip_address, user_agent=user_agent)
            raise HTTPException(status_code=429, detail="Too many OTP requests. Please try again later.")

        # Cooldown: 60 seconds
        latest = self.repo.get_latest_otp(email=email, phone=phone, purpose=purpose)
        if latest and latest.created_at >= datetime.now(timezone.utc) - timedelta(seconds=60):
            raise HTTPException(status_code=429, detail="Please wait 60 seconds before requesting a new OTP.")

        # Lookup user if exists
        user_id = None
        company_id = None
        if email:
            stmt = select(User).where(User.email == email)
            user = self.db.scalar(stmt)
            if user:
                user_id = user.id
                company_id = user.company_id

        code = self.generate_otp()
        hashed = self.hash_otp(code)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

        otp_record = OTPCode(
            company_id=company_id,
            user_id=user_id,
            email=email,
            phone=phone,
            purpose=purpose,
            otp_hash=hashed,
            expires_at=expires_at
        )
        self.repo.create_otp(otp_record)

        channel = "email" if email else "phone"
        recipient = email if email else phone
        provider = OTPProviderFactory.get_provider(channel)
        provider.send_otp(recipient, code)

        log_otp_event("OTP Sent", email=email, phone=phone, user_id=user_id, company_id=company_id, ip_address=ip_address, user_agent=user_agent)
        return {"detail": "OTP sent successfully"}

    def resend_otp(self, purpose, email: Optional[str], phone: Optional[str], ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> dict:
        from app.auth.audit import log_otp_event
        # Resend logic is basically the same as send, but logs "OTP Resent"
        # We call send_otp directly and override the log if successful
        res = self.send_otp(purpose=purpose, email=email, phone=phone, ip_address=ip_address, user_agent=user_agent)
        log_otp_event("OTP Resent", email=email, phone=phone, ip_address=ip_address, user_agent=user_agent)
        return res

    def verify_otp(self, purpose, code: str, email: Optional[str], phone: Optional[str], ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        from app.auth.audit import log_otp_event
        if not email and not phone:
            raise HTTPException(status_code=400, detail="Must provide email or phone")

        latest = self.repo.get_latest_otp(email=email, phone=phone, purpose=purpose)
        if not latest:
            raise HTTPException(status_code=404, detail="No OTP requested")

        # Expiry Check
        if datetime.now(timezone.utc) > latest.expires_at:
            log_otp_event("OTP Expired", email=email, phone=phone, user_id=latest.user_id, company_id=latest.company_id, ip_address=ip_address, user_agent=user_agent)
            raise HTTPException(status_code=400, detail="OTP has expired")

        # Used Check
        if latest.is_used:
            log_otp_event("OTP Failed (Reused)", email=email, phone=phone, user_id=latest.user_id, company_id=latest.company_id, ip_address=ip_address, user_agent=user_agent)
            raise HTTPException(status_code=400, detail="OTP has already been used")

        # Attempts Check
        if latest.attempts >= 5:
            log_otp_event("OTP Failed (Max Attempts)", email=email, phone=phone, user_id=latest.user_id, company_id=latest.company_id, ip_address=ip_address, user_agent=user_agent)
            raise HTTPException(status_code=400, detail="Maximum OTP attempts reached")

        # Validation Check
        if not self.verify_otp_hash(code, latest.otp_hash):
            latest.attempts += 1
            self.repo.update_otp(latest)
            log_otp_event("OTP Failed", email=email, phone=phone, user_id=latest.user_id, company_id=latest.company_id, ip_address=ip_address, user_agent=user_agent)
            raise HTTPException(status_code=400, detail="Invalid OTP")

        # Success
        latest.is_used = True
        latest.verified_at = datetime.now(timezone.utc)
        self.repo.update_otp(latest)

        log_otp_event("OTP Verified", email=email, phone=phone, user_id=latest.user_id, company_id=latest.company_id, ip_address=ip_address, user_agent=user_agent)
        
        # If purpose is LOGIN and user_id is present, issue tokens
        if purpose == "LOGIN" and latest.user_id:
            stmt = select(User).where(User.id == latest.user_id)
            user = self.db.scalar(stmt)
            if user and user.is_active and user.status == UserStatus.ACTIVE:
                access_token = self.create_access_token(subject=str(user.id))
                refresh_token = self.create_refresh_token(subject=str(user.id))
                return TokenResponse(
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
                )

        return {"detail": "OTP verified successfully"}

    # ── Identity Verification ────────────────────────────────────────────────

    def send_email_verification(self, email: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> dict:
        stmt = select(User).where(User.email == email)
        user = self.db.scalar(stmt)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.email_verified:
            raise HTTPException(status_code=400, detail="Email is already verified")
            
        return self.send_otp(purpose="EMAIL_VERIFY", email=email, phone=None, ip_address=ip_address, user_agent=user_agent)

    def verify_email(self, email: str, code: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> dict:
        from app.auth.audit import log_otp_event
        stmt = select(User).where(User.email == email)
        user = self.db.scalar(stmt)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.email_verified:
            raise HTTPException(status_code=400, detail="Email is already verified")
            
        self.verify_otp(purpose="EMAIL_VERIFY", code=code, email=email, phone=None, ip_address=ip_address, user_agent=user_agent)
        
        user.email_verified = True
        user.email_verified_at = datetime.now(timezone.utc)
        self.db.commit()
        log_otp_event("EMAIL_VERIFIED", email=email, user_id=user.id, company_id=user.company_id, ip_address=ip_address, user_agent=user_agent)
        return {"detail": "Email verified successfully"}

    def send_phone_verification(self, phone: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> dict:
        # Note: phone might not be set yet on user registration, 
        # but if we require it to be attached to a user first, they must update their profile.
        # Alternatively, verify_phone can just attach it.
        # The prompt didn't specify, but let's assume the phone is verified globally.
        return self.send_otp(purpose="PHONE_VERIFY", email=None, phone=phone, ip_address=ip_address, user_agent=user_agent)

    def verify_phone(self, phone: str, code: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> dict:
        from app.auth.audit import log_otp_event
        
        self.verify_otp(purpose="PHONE_VERIFY", code=code, email=None, phone=phone, ip_address=ip_address, user_agent=user_agent)
        
        # Link to a user if the phone matches an existing user profile's phone
        stmt = select(User).where(User.phone == phone)
        user = self.db.scalar(stmt)
        if user:
            user.phone_verified = True
            user.phone_verified_at = datetime.now(timezone.utc)
            self.db.commit()
            log_otp_event("PHONE_VERIFIED", phone=phone, user_id=user.id, company_id=user.company_id, ip_address=ip_address, user_agent=user_agent)
        else:
            # We still log the verification even if no user found with that phone yet.
            log_otp_event("PHONE_VERIFIED", phone=phone, ip_address=ip_address, user_agent=user_agent)

        return {"detail": "Phone verified successfully"}

    def forgot_password(self, email: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> dict:
        stmt = select(User).where(User.email == email)
        user = self.db.scalar(stmt)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        return self.send_otp(purpose="PASSWORD_RESET", email=email, phone=None, ip_address=ip_address, user_agent=user_agent)

    def reset_password(self, email: str, code: str, new_password: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> dict:
        from app.auth.audit import log_otp_event
        from sqlalchemy import delete
        
        stmt = select(User).where(User.email == email)
        user = self.db.scalar(stmt)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        try:
            self.verify_otp(purpose="PASSWORD_RESET", code=code, email=email, phone=None, ip_address=ip_address, user_agent=user_agent)
        except Exception as e:
            log_otp_event("PASSWORD_RESET_FAILED", email=email, user_id=user.id, company_id=user.company_id, ip_address=ip_address, user_agent=user_agent)
            raise e
            
        user.hashed_password = self.get_password_hash(new_password)
        
        # Invalidate all refresh tokens
        self.db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
        self.db.commit()
        
        log_otp_event("PASSWORD_RESET", email=email, user_id=user.id, company_id=user.company_id, ip_address=ip_address, user_agent=user_agent)
        return {"detail": "Password reset successfully"}

