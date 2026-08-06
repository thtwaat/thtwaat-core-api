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
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )
        # Match login: authenticated identity that is suspended → 403 (not 401).
        if not user.is_active or user.status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is suspended or inactive.",
            )

        return UserProfileResponse(
            id=user.id,
            company_id=user.company_id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role.value
        )

    # ── Session helpers ───────────────────────────────────────────────────────

    def issue_tokens_for_user(self, user: User) -> TokenResponse:
        """Issue access + refresh tokens for an active user (no MFA gate)."""
        if not user.is_active or user.status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is suspended or inactive.",
            )
        access_token = self.create_access_token(subject=str(user.id))
        refresh_token = self.create_refresh_token(subject=str(user.id))
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    def mark_email_verified(self, user: User) -> None:
        if user.email_verified:
            return
        user.email_verified = True
        user.email_verified_at = datetime.now(timezone.utc)

    # ── Password reset (email link) ───────────────────────────────────────────

    @staticmethod
    def _hash_reset_token(raw_token: str) -> str:
        import hashlib

        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    def _send_password_reset_email(self, recipient: str, reset_url: str) -> None:
        from app.notifications.email.errors import EmailConfigurationError, EmailDeliveryError
        from app.notifications.email.factory import get_email_backend
        from app.notifications.email.templates import render_password_reset_link_email

        subject, html, text = render_password_reset_link_email(reset_url)
        try:
            backend = get_email_backend()
            result = backend.send(
                recipient=recipient,
                subject=subject,
                body=text,
                html=html,
                text=text,
            )
        except EmailConfigurationError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Email delivery is not configured",
            ) from None
        except EmailDeliveryError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Email delivery failed",
            ) from None
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=result.error_message or "Email delivery failed",
            )

    def send_welcome_email(self, *, email: str, first_name: str = "") -> None:
        """Best-effort welcome email after signup (never blocks account creation)."""
        try:
            from app.notifications.email.factory import get_email_backend
            from app.notifications.email.templates import render_welcome_email

            subject, html, text = render_welcome_email(first_name=first_name)
            backend = get_email_backend()
            backend.send(
                recipient=email,
                subject=subject,
                body=text,
                html=html,
                text=text,
            )
        except Exception:
            pass

    def forgot_password(
        self,
        email: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> dict:
        """
        Send a one-time reset link. Always returns the same message to avoid
        account enumeration when the email is unknown or delivery fails quietly.
        """
        import secrets

        from app.auth.audit import log_otp_event
        from app.auth.model import PasswordResetToken

        generic = {
            "detail": "If an account exists for that email, a reset link has been sent."
        }
        stmt = select(User).where(User.email == email)
        user = self.db.scalar(stmt)
        if not user:
            log_otp_event(
                "PASSWORD_RESET_REQUESTED_UNKNOWN",
                email=email,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            return generic

        raw = secrets.token_urlsafe(32)
        ttl = int(getattr(settings, "PASSWORD_RESET_TOKEN_TTL_MINUTES", 60) or 60)
        record = PasswordResetToken(
            user_id=user.id,
            token_hash=self._hash_reset_token(raw),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl),
        )
        self.db.add(record)
        self.db.commit()

        app_base = (settings.PUBLIC_APP_BASE_URL or "").rstrip("/")
        reset_url = f"{app_base}/reset-password?token={raw}"
        try:
            self._send_password_reset_email(user.email, reset_url)
        except HTTPException:
            # Do not leak configuration failures to callers of forgot-password.
            log_otp_event(
                "PASSWORD_RESET_EMAIL_FAILED",
                email=email,
                user_id=user.id,
                company_id=user.company_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            return generic

        log_otp_event(
            "PASSWORD_RESET_LINK_SENT",
            email=email,
            user_id=user.id,
            company_id=user.company_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return generic

    def reset_password(
        self,
        token: str,
        new_password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> dict:
        from app.auth.audit import log_otp_event
        from app.auth.model import PasswordResetToken

        token_hash = self._hash_reset_token(token.strip())
        stmt = select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        record = self.db.scalar(stmt)
        if not record or record.used_at is not None:
            raise HTTPException(status_code=400, detail="Invalid or expired reset link")
        if datetime.now(timezone.utc) > record.expires_at:
            raise HTTPException(status_code=400, detail="Invalid or expired reset link")

        user = self.db.scalar(select(User).where(User.id == record.user_id))
        if not user:
            raise HTTPException(status_code=400, detail="Invalid or expired reset link")

        user.hashed_password = self.get_password_hash(new_password)
        record.used_at = datetime.now(timezone.utc)
        self.db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
        self.db.commit()

        log_otp_event(
            "PASSWORD_RESET",
            email=user.email,
            user_id=user.id,
            company_id=user.company_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return {"detail": "Password reset successfully"}

    # ── Google OAuth (consumer) ───────────────────────────────────────────────

    def login_or_register_google_profile(self, profile: dict) -> TokenResponse:
        """
        Find user by email or create company + owner automatically, then issue JWTs.
        """
        import re
        import secrets

        from app.companies.schema import CompanyCreate
        from app.companies.service import CompanyService
        from app.rbac.enums import EnterpriseRole
        from app.users.schema import UserCreate
        from app.users.service import UserService

        email = (profile.get("email") or "").strip().lower()
        if not email:
            raise HTTPException(status_code=400, detail="Google account has no email")

        candidates = list(
            self.db.scalars(select(User).where(User.email == email).limit(2)).all()
        )
        if len(candidates) > 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "company_required",
                    "message": "This email belongs to multiple organizations; use email login with company_slug.",
                },
            )
        if candidates:
            user = candidates[0]
            self.mark_email_verified(user)
            self.db.commit()
            return self.issue_tokens_for_user(user)

        local = re.sub(r"[^a-z0-9]+", "-", email.split("@", 1)[0].lower()).strip("-") or "workspace"
        base_slug = (local[:40] or "workspace").strip("-") or "workspace"
        companies = CompanyService(self.db)
        slug = base_slug
        for _ in range(8):
            if not companies.repo.slug_exists(slug):
                break
            slug = f"{base_slug}-{secrets.token_hex(2)}"
        else:
            slug = f"ws-{secrets.token_hex(4)}"

        display = f"{profile.get('first_name', 'My')} Workspace"
        company = companies.create_company(
            CompanyCreate(
                name=display[:255],
                slug=slug,
                display_name=display[:255],
            )
        )
        users = UserService(self.db)
        created = users.create_user(
            UserCreate(
                email=email,
                password=secrets.token_urlsafe(32),
                first_name=profile.get("first_name") or "User",
                last_name=profile.get("last_name") or "User",
                company_id=company.id,
                role=EnterpriseRole.COMPANY_OWNER,
            )
        )
        user = self.db.scalar(select(User).where(User.id == created.id))
        if not user:
            raise HTTPException(status_code=500, detail="Could not create Google user")
        self.mark_email_verified(user)
        self.db.commit()
        self.send_welcome_email(email=user.email, first_name=user.first_name or "")
        return self.issue_tokens_for_user(user)

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
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )
        if not user.is_active or user.status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is suspended or inactive.",
            )

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

