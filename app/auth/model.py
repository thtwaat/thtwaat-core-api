"""
app/auth/model.py

SQLAlchemy models for Authentication.
Stores Refresh Tokens to allow token revocation and tracking.
"""

import uuid
import enum
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Boolean, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class RefreshToken(Base, TimestampMixin):
    """
    Stores long-lived refresh tokens for users.
    When a user logs out, the token is revoked (deleted or marked revoked).
    """

    __tablename__ = "refresh_tokens"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    token = Column(String(500), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="refresh_tokens")

    def __repr__(self) -> str:
        return f"<RefreshToken id={self.id} user_id={self.user_id}>"

class OTPPurpose(str, enum.Enum):
    REGISTER = "REGISTER"
    LOGIN = "LOGIN"
    PASSWORD_RESET = "PASSWORD_RESET"
    EMAIL_VERIFY = "EMAIL_VERIFY"
    PHONE_VERIFY = "PHONE_VERIFY"
    MFA = "MFA"

class OTPCode(Base, TimestampMixin):
    __tablename__ = "otp_codes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(50), nullable=True, index=True)
    
    purpose = Column(SAEnum(OTPPurpose, name="otp_purpose_enum"), nullable=False)
    otp_hash = Column(String(255), nullable=False)
    
    expires_at = Column(DateTime(timezone=True), nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    
    attempts = Column(Integer, default=0, nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)

    user = relationship("User", backref="otp_codes")
    company = relationship("Company", backref="otp_codes")

    def __repr__(self) -> str:
        return f"<OTPCode id={self.id} purpose={self.purpose} email={self.email} phone={self.phone}>"
