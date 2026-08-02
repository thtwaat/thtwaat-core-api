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
from sqlalchemy import select, func, delete

# To fetch users, we import the model directly (or UserRepository)
from app.users.model import User, UserStatus
from app.auth.model import RefreshToken
from app.auth.repository import AuthRepository
from app.auth.schema import LoginRequest, TokenResponse, UserProfileResponse


# ── Configuration (Environment or Default) ───────────────────────────────────
from app.config.settings import settings

JWT_SECRET_KEY = settings.JWT_SECRET_KEY
JWT_REFRESH_SECRET_KEY = settings.JWT_REFRESH_SECRET_KEY
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
        if not hashed_password or hashed_password.startswith("dummy_hash_"):
            # Reject legacy scaffolding hashes — never accept plaintext bypasses.
            return False
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
        
        to_encode = {"exp": expire, "sub": str(subject), "type": "access", "jti": str(uuid.uuid4())}
        encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    def create_refresh_token(self, subject: str) -> str:
        """Create a long-lived JWT refresh token and store it in DB."""
        user_id = uuid.UUID(subject)
        expires_delta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        # Enterprise session policy extends existing token issuance without
        # creating a parallel session implementation.
        try:
            from app.enterprise.models import EnterpriseSecurityPolicy

            user = self.db.get(User, user_id)
            policy = (
                self.db.scalar(
                    select(EnterpriseSecurityPolicy).where(
                        EnterpriseSecurityPolicy.company_id == user.company_id
                    )
                )
                if user
                else None
            )
            if policy:
                expires_delta = timedelta(minutes=policy.session_ttl_minutes)
                active = list(
                    self.db.scalars(
                        select(RefreshToken)
                        .where(
                            RefreshToken.user_id == user_id,
                            RefreshToken.revoked_at.is_(None),
                            RefreshToken.expires_at > datetime.now(timezone.utc),
                        )
                        .order_by(RefreshToken.created_at.asc())
                    ).all()
                )
                excess = len(active) - policy.max_sessions_per_user + 1
                for old_token in active[:max(0, excess)]:
                    old_token.revoked_at = datetime.now(timezone.utc)
                if excess > 0:
                    self.db.commit()
        except Exception:
            # Token issuance remains available if the optional enterprise
            # module has not been migrated yet. Rollback so a missing table
            # does not abort the rest of the login transaction.
            self.db.rollback()
        expire = datetime.now(timezone.utc) + expires_delta
        
        to_encode = {"exp": expire, "sub": str(subject), "type": "refresh", "jti": str(uuid.uuid4())}
        encoded_jwt = jwt.encode(to_encode, JWT_REFRESH_SECRET_KEY, algorithm=ALGORITHM)
        
        # Save to DB for revocation tracking
        self.repo.save_refresh_token(
            user_id=user_id,
            token=encoded_jwt,
            expires_at=expire
        )
        return encoded_jwt

    def create_mfa_token(self, subject: str) -> str:
        """Create a short-lived token specifically for MFA verification during login."""
        expires_delta = timedelta(minutes=5)
        expire = datetime.now(timezone.utc) + expires_delta
        
        to_encode = {"exp": expire, "sub": str(subject), "type": "mfa_verify", "jti": str(uuid.uuid4())}
        encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    # ── Core Operations ───────────────────────────────────────────────────────

    def authenticate_user(self, data: LoginRequest) -> TokenResponse:
        """
        Verify credentials and issue tokens.
        """
        # Fetch user directly using SQLAlchemy to avoid tight coupling if preferred,
        # but we can just use the DB session here.
        stmt = select(User).where(User.email == data.email)
        if data.company_slug:
            from app.companies.model import Company

            stmt = stmt.join(Company, Company.id == User.company_id).where(
                Company.slug == data.company_slug
            )
        candidates = list(self.db.scalars(stmt.limit(2)).all())
        if not data.company_slug and len(candidates) > 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "company_required",
                    "message": "This email belongs to multiple organizations; provide company_slug.",
                },
            )
        user = candidates[0] if candidates else None
        
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

        # Enforced enterprise SSO replaces password login for matching domains.
        try:
            from app.enterprise.models import EnterpriseSSOConnection

            email_domain = user.email.rsplit("@", 1)[-1].lower()
            sso = self.db.scalar(
                select(EnterpriseSSOConnection).where(
                    EnterpriseSSOConnection.company_id == user.company_id,
                    EnterpriseSSOConnection.domain == email_domain,
                    EnterpriseSSOConnection.enforce_sso.is_(True),
                    EnterpriseSSOConnection.is_active.is_(True),
                )
            )
            if sso:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "sso_required",
                        "provider": sso.provider.value,
                        "connection_id": str(sso.id),
                        "initiate_endpoint": f"/api/v1/enterprise/sso/{sso.id}/initiate",
                    },
                )
        except HTTPException:
            raise
        except Exception:
            # Login remains available before enterprise migrations are applied.
            self.db.rollback()
            
        if not user.is_active or user.status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is suspended or inactive.",
            )

        # Check if MFA is enabled
        from app.auth.model import MFASettings
        stmt = select(MFASettings).where(MFASettings.user_id == user.id)
        mfa_settings = self.db.scalar(stmt)
        
        if mfa_settings and mfa_settings.enabled:
            # Issue temporary MFA token instead of standard tokens
            mfa_token = self.create_mfa_token(subject=str(user.id))
            from app.auth.schema import MFARequiredResponse
            return MFARequiredResponse(
                mfa_required=True,
                mfa_token=mfa_token,
                expires_in=300
            )

        # Generate standard tokens only after MFA gating, so a pending MFA
        # challenge never leaves an active refresh session behind.
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

    # ── MFA Implementation ───────────────────────────────────────────────────

    def generate_backup_codes(self) -> list[str]:
        import secrets
        import string
        # Generate 10 random 10-character codes
        return [''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10)) for _ in range(10)]

    def hash_backup_code(self, code: str) -> str:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(code.encode("utf-8"), salt).decode("utf-8")

    def verify_backup_code_hash(self, code: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(code.encode("utf-8"), hashed.encode("utf-8"))
        except ValueError:
            return False

    def setup_mfa(self, user_id: uuid.UUID) -> dict:
        import pyotp
        import qrcode
        import io
        import base64
        from app.auth.model import MFASettings
        from app.config.settings import settings
        
        # Check if already enabled
        mfa = self.repo.get_mfa_settings(user_id)
        if mfa and mfa.enabled:
            raise HTTPException(status_code=400, detail="MFA is already enabled")
            
        secret = pyotp.random_base32()
        
        if not mfa:
            mfa = MFASettings(user_id=user_id, secret=secret, enabled=False)
            self.repo.create_mfa_settings(mfa)
        else:
            mfa.secret = secret
            self.repo.update_mfa_settings(mfa)
            
        # Get user email for URI
        stmt = select(User).where(User.id == user_id)
        user = self.db.scalar(stmt)
        
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(name=user.email, issuer_name=settings.MFA_ISSUER_NAME)
        
        # Generate QR Code
        qr = qrcode.make(uri)
        buf = io.BytesIO()
        qr.save(buf, format="PNG")
        qr_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        
        return {
            "secret": secret,
            "qr_code_uri": uri,
            "qr_code_base64": qr_b64
        }

    def enable_mfa(self, user_id: uuid.UUID, code: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> dict:
        import pyotp
        import json
        from app.auth.audit import log_otp_event
        
        mfa = self.repo.get_mfa_settings(user_id)
        if not mfa or not mfa.secret:
            raise HTTPException(status_code=400, detail="MFA setup not initiated")
        if mfa.enabled:
            raise HTTPException(status_code=400, detail="MFA is already enabled")
            
        totp = pyotp.TOTP(mfa.secret)
        if not totp.verify(code):
            raise HTTPException(status_code=400, detail="Invalid MFA code")
            
        raw_backup_codes = self.generate_backup_codes()
        hashed_codes = [self.hash_backup_code(c) for c in raw_backup_codes]
        
        mfa.enabled = True
        mfa.backup_codes = json.dumps(hashed_codes)
        self.repo.update_mfa_settings(mfa)
        
        stmt = select(User).where(User.id == user_id)
        user = self.db.scalar(stmt)
        
        log_otp_event("MFA_ENABLED", user_id=user_id, company_id=user.company_id if user else None, ip_address=ip_address, user_agent=user_agent)
        
        return {
            "detail": "MFA enabled successfully",
            "backup_codes": raw_backup_codes
        }

    def disable_mfa(self, user_id: uuid.UUID, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> dict:
        from app.auth.audit import log_otp_event
        
        mfa = self.repo.get_mfa_settings(user_id)
        if not mfa or not mfa.enabled:
            raise HTTPException(status_code=400, detail="MFA is not enabled")
            
        mfa.enabled = False
        mfa.secret = None
        mfa.backup_codes = None
        self.repo.update_mfa_settings(mfa)
        
        stmt = select(User).where(User.id == user_id)
        user = self.db.scalar(stmt)
        
        log_otp_event("MFA_DISABLED", user_id=user_id, company_id=user.company_id if user else None, ip_address=ip_address, user_agent=user_agent)
        
        return {"detail": "MFA disabled successfully"}

    def get_recovery_codes_status(self, user_id: uuid.UUID) -> dict:
        import json
        mfa = self.repo.get_mfa_settings(user_id)
        if not mfa or not mfa.enabled:
            raise HTTPException(status_code=400, detail="MFA is not enabled")
            
        codes = json.loads(mfa.backup_codes) if mfa.backup_codes else []
        return {"remaining_codes": len(codes)}

    def regenerate_recovery_codes(self, user_id: uuid.UUID, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> dict:
        import json
        from app.auth.audit import log_otp_event
        
        mfa = self.repo.get_mfa_settings(user_id)
        if not mfa or not mfa.enabled:
            raise HTTPException(status_code=400, detail="MFA is not enabled")
            
        raw_backup_codes = self.generate_backup_codes()
        hashed_codes = [self.hash_backup_code(c) for c in raw_backup_codes]
        
        mfa.backup_codes = json.dumps(hashed_codes)
        self.repo.update_mfa_settings(mfa)
        
        stmt = select(User).where(User.id == user_id)
        user = self.db.scalar(stmt)
        
        log_otp_event("MFA_BACKUP_CODES_GENERATED", user_id=user_id, company_id=user.company_id if user else None, ip_address=ip_address, user_agent=user_agent)
        
        return {
            "detail": "Recovery codes regenerated successfully",
            "backup_codes": raw_backup_codes
        }

    def verify_mfa(self, mfa_token: Optional[str], totp_code: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> TokenResponse:
        import pyotp
        import json
        from app.auth.audit import log_otp_event
        from app.auth.model import OTPCode, OTPPurpose
        
        user_id_str = None
        if mfa_token:
            try:
                payload = jwt.decode(mfa_token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
                user_id_str = payload.get("sub")
                token_type = payload.get("type")
                
                if user_id_str is None or token_type != "mfa_verify":
                    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
            except JWTError:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired MFA token")
        else:
            raise HTTPException(status_code=400, detail="mfa_token is required")
            
        user_id = uuid.UUID(user_id_str)
        stmt = select(User).where(User.id == user_id)
        user = self.db.scalar(stmt)
        
        if not user or not user.is_active or user.status != UserStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
            
        mfa = self.repo.get_mfa_settings(user_id)
        if not mfa or not mfa.enabled:
            raise HTTPException(status_code=400, detail="MFA is not enabled for this user")
            
        # Rate Limiting: 5 attempts per 15 minutes
        fifteen_mins_ago = datetime.now(timezone.utc) - timedelta(minutes=15)
        stmt_count = select(func.count(OTPCode.id)).where(
            OTPCode.user_id == user_id, 
            OTPCode.purpose == OTPPurpose.MFA, 
            OTPCode.created_at >= fifteen_mins_ago,
            OTPCode.is_used == False # Failed attempts
        )
        failed_attempts = self.db.scalar(stmt_count) or 0
        
        if failed_attempts >= 5:
            log_otp_event("MFA_LOCKED", user_id=user_id, company_id=user.company_id, ip_address=ip_address, user_agent=user_agent)
            raise HTTPException(status_code=429, detail="Too many failed MFA attempts. Account locked for 15 minutes.")
            
        success = False
        used_recovery = False
        
        totp = pyotp.TOTP(mfa.secret)
        if totp.verify(totp_code):
            success = True
        else:
            # Check recovery codes
            if mfa.backup_codes:
                codes = json.loads(mfa.backup_codes)
                remaining_codes = []
                for hashed in codes:
                    if not success and self.verify_backup_code_hash(totp_code, hashed):
                        success = True
                        used_recovery = True
                    else:
                        remaining_codes.append(hashed)
                        
                if success and used_recovery:
                    mfa.backup_codes = json.dumps(remaining_codes)
                    self.repo.update_mfa_settings(mfa)
        
        if not success:
            # Log failed attempt
            otp_record = OTPCode(
                user_id=user_id,
                company_id=user.company_id,
                purpose=OTPPurpose.MFA,
                otp_hash="failed",
                expires_at=datetime.now(timezone.utc),
                is_used=False # Mark as failed
            )
            self.repo.create_otp(otp_record)
            log_otp_event("MFA_FAILED", user_id=user_id, company_id=user.company_id, ip_address=ip_address, user_agent=user_agent)
            raise HTTPException(status_code=400, detail="Invalid MFA code")
            
        # Success
        if used_recovery:
            log_otp_event("RECOVERY_CODE_USED", user_id=user_id, company_id=user.company_id, ip_address=ip_address, user_agent=user_agent)
        else:
            log_otp_event("MFA_SUCCESS", user_id=user_id, company_id=user.company_id, ip_address=ip_address, user_agent=user_agent)
            
        # Issue JWTs
        access_token = self.create_access_token(subject=str(user.id))
        refresh_token = self.create_refresh_token(subject=str(user.id))
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

